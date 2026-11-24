"""Roadmap lifecycle: generate, refresh after new evidence, complete / skip / reschedule."""
from datetime import date, timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from learning.models import LearningGoal, LearningRoadmap, RoadmapItem
from .mastery import band_for
from .recommender import activity_link, skill_states
from .scheduler import build_schedule

# Which roadmap activities a piece of evidence can complete.
SOURCE_COMPLETES = {'mcq': ('diagnostic', 'mcq', 'revision'), 'coding': ('coding', 'diagnostic', 'revision'),
                    'technical': ('interview', 'diagnostic', 'revision')}


def active_roadmap(user):
    return LearningRoadmap.objects.filter(user=user, status=LearningRoadmap.ACTIVE).order_by('-id').first()


@transaction.atomic
def generate_roadmap(user, *, target_role, analysis, deadline, minutes_per_day, study_days, start=None):
    start = start or timezone.localdate()
    if deadline <= start:
        raise ValueError('The deadline must be after today.')
    if not 15 <= minutes_per_day <= 600:
        raise ValueError('Study time must be between 15 and 600 minutes a day.')
    study_days = sorted({int(d) for d in study_days if 0 <= int(d) <= 6}) or list(range(7))

    LearningGoal.objects.update_or_create(user=user, defaults={
        'target_role': target_role, 'job_analysis': analysis, 'deadline': deadline,
        'minutes_per_day': minutes_per_day, 'study_days': study_days})

    states, _ = skill_states(user, target_role, analysis)
    plan = build_schedule(states, start, deadline, minutes_per_day, study_days)

    # Old roadmaps are archived, not deleted: completed history stays visible.
    LearningRoadmap.objects.filter(user=user, status=LearningRoadmap.ACTIVE).update(status=LearningRoadmap.ARCHIVED)
    roadmap = LearningRoadmap.objects.create(
        user=user, target_role=target_role, job_analysis=analysis, start_date=start, deadline=deadline,
        minutes_per_day=minutes_per_day, study_days=study_days,
        summary={'milestones': plan['milestones'],
                 'unscheduled': [{'title': t['title'], 'why': t['why'], 'duration_min': t['duration_min']}
                                 for t in plan['unscheduled']],
                 'config': {k: settings.LEARNING_ENGINE[k] for k in ('ALPHA', 'PREREQ_THRESHOLD', 'MASTERED')}},
    )
    RoadmapItem.objects.bulk_create([
        RoadmapItem(roadmap=roadmap, skill_id=t['skill_id'], title=t['title'][:200], activity_type=t['activity_type'],
                    difficulty=t['difficulty'], scheduled_date=t['date'], duration_min=t['duration_min'],
                    week=t['week'], order=i, reason=t['reason'][:300], link=t['link'])
        for i, t in enumerate(plan['items'])
    ])
    return roadmap


def on_mastery_updated(user, skill, mastery, source):
    """Adaptive loop step: called inside the evidence transaction."""
    roadmap = active_roadmap(user)
    if not roadmap:
        return
    pending = roadmap.items.filter(skill=skill, status=RoadmapItem.PENDING)
    # 1. The work the student just did completes the matching planned activity.
    done = pending.filter(activity_type__in=SOURCE_COMPLETES.get(source, ())).order_by('scheduled_date', 'order').first()
    if done:
        done.status, done.completed_at = RoadmapItem.COMPLETED, timezone.now()
        done.reason = (done.reason + f' Completed automatically by your {source} result.')[:300]
        done.save(update_fields=['status', 'completed_at', 'reason'])
    # 2. Remaining work for this skill moves to the new difficulty band.
    band = band_for(mastery)
    for item in pending.exclude(id=done.id if done else None):
        if item.activity_type in ('mcq', 'revision', 'diagnostic'):
            item.difficulty = band['mcq']
        elif item.activity_type == 'coding':
            item.difficulty = band['coding']
        elif item.activity_type == 'interview':
            item.difficulty = band['interview']
        else:
            continue
        item.link = activity_link(item.activity_type, skill, item.difficulty)
        item.save(update_fields=['difficulty', 'link'])
    # 3. Once a skill is mastered its remaining "learn" tasks are no longer needed.
    if mastery >= settings.LEARNING_ENGINE['MASTERED']:
        pending.filter(activity_type='learn').update(status=RoadmapItem.SKIPPED,
                                                     reason=f'Skipped: {skill.name} is already mastered.')


def set_item_status(user, item_id, status):
    item = RoadmapItem.objects.select_related('roadmap').get(id=item_id, roadmap__user=user)
    if status not in (RoadmapItem.COMPLETED, RoadmapItem.SKIPPED, RoadmapItem.PENDING):
        raise ValueError('Unknown status.')
    item.status = status
    item.completed_at = timezone.now() if status == RoadmapItem.COMPLETED else None
    item.save(update_fields=['status', 'completed_at'])
    return item


def reschedule_item(user, item_id, new_date):
    item = RoadmapItem.objects.select_related('roadmap').get(id=item_id, roadmap__user=user)
    if item.status != RoadmapItem.PENDING:
        raise ValueError('Only pending tasks can be rescheduled.')
    if not isinstance(new_date, date) or new_date < timezone.localdate():
        raise ValueError('Pick a date from today onwards.')
    if new_date > item.roadmap.deadline + timedelta(days=30):
        raise ValueError('That date is too far past your deadline.')
    planned = sum(i.duration_min for i in item.roadmap.items.filter(scheduled_date=new_date, status=RoadmapItem.PENDING)
                  .exclude(id=item.id))
    item.scheduled_date = new_date
    item.week = (new_date - item.roadmap.start_date).days // 7 + 1
    item.save(update_fields=['scheduled_date', 'week'])
    over = planned + item.duration_min - item.roadmap.minutes_per_day
    return item, (f'That day now has {planned + item.duration_min} min planned, {over} min over your daily time.'
                  if over > 0 else '')
