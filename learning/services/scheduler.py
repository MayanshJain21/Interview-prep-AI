"""
Roadmap scheduler (pure Python, no database access, so it is easy to test).

1. Skills are ordered with Kahn's algorithm: prerequisites first, higher priority first among
   the skills that are ready.
2. Each skill becomes a short sequence of tasks that depends on its mastery band.
3. Tasks are packed into the student's study days without exceeding minutes_per_day.
   A task longer than a whole study day, or work past the deadline, is reported as unscheduled
   instead of overfilling days.
4. A revision task is placed at least REVISION_GAP_DAYS after a skill's last task.
5. The last study day of each week gets a weekly assessment when it has room.
"""
from datetime import timedelta

from django.conf import settings

from .recommender import activity, next_activity
from .taxonomy import ordered_by_prerequisites

REVISION_GAP_DAYS = 7
MAX_HORIZON_DAYS = 180


def tasks_for_skill(state):
    """The sequence of tasks planned for one skill."""
    skill, mastery, band = state['skill'], state['mastery'], state['band']
    first = next_activity(state)
    tasks = [first]
    via = set(skill.assessable_via)
    if mastery is None:
        # After the diagnostic, one practice task at the easy level; the roadmap re-tunes the
        # difficulty automatically once the diagnostic result arrives.
        if 'coding' in via and first['activity_type'] != 'coding':
            tasks.append(activity('coding', skill, 'easy', f'{skill.name}: easy coding problems',
                                  f'First practice for {skill.name} after the diagnostic.'))
        elif 'mcq' in via and first['activity_type'] != 'diagnostic':
            tasks.append(activity('mcq', skill, 'Easy', f'{skill.name}: easy MCQ practice',
                                  f'First practice for {skill.name} after the diagnostic.'))
    elif mastery < 40:
        if 'mcq' in via:
            tasks.append(activity('mcq', skill, 'Easy', f'{skill.name}: easy MCQ practice',
                                  f'Check the fundamentals of {skill.name} after studying them.'))
        if 'coding' in via:
            tasks.append(activity('coding', skill, 'easy', f'{skill.name}: easy coding problems',
                                  f'Apply the {skill.name} basics in code.'))
    elif mastery < settings.LEARNING_ENGINE['MASTERED']:
        if 'technical' in via and first['activity_type'] != 'interview' and mastery >= 60:
            tasks.append(activity('interview', skill, band['interview'], f'{skill.name}: technical interview practice',
                                  f'Explain {skill.name} concepts out loud at the {band["label"].lower()} level.'))
        elif 'mcq' in via and first['activity_type'] != 'mcq':
            tasks.append(activity('mcq', skill, band['mcq'], f"{skill.name}: {band['mcq'].lower()} MCQ practice",
                                  f'Second practice for {skill.name} at your current level.'))
    revision = None
    if first['activity_type'] != 'revision':
        revision = activity('revision', skill, band['mcq'], f'Revise {skill.name}',
                            f'Spaced revision of {skill.name} about a week after practising it.')
    for t in tasks + ([revision] if revision else []):
        t['skill_id'] = state['skill_id']
        t['skill_name'] = skill.name
    return tasks, revision


def study_dates(start, deadline, study_days):
    days = set(study_days) if study_days else set(range(7))
    d = start
    end = min(deadline, start + timedelta(days=MAX_HORIZON_DAYS))
    while d <= end:
        if d.weekday() in days:
            yield d
        d += timedelta(days=1)


def build_schedule(states, start, deadline, minutes_per_day, study_days):
    """Returns {"items": [...], "unscheduled": [...], "milestones": [...]}.
    `states` is the dict from recommender.skill_states()."""
    minutes = settings.LEARNING_ENGINE['ACTIVITY_MINUTES']
    plannable = {sid: st for sid, st in states.items()
                 if not (st['status'] == 'mastered' and (st['days_since'] or 0) <= settings.LEARNING_ENGINE['STALE_DAYS'])}
    graph = {sid: set(st['prerequisites']) for sid, st in plannable.items()}
    order = ordered_by_prerequisites(plannable.keys(), graph, {s: st['priority'] for s, st in plannable.items()})

    queue, revisions = [], []
    for sid in order:
        tasks, revision = tasks_for_skill(plannable[sid])
        queue.extend(tasks)
        if revision:
            revisions.append(revision)

    items, unscheduled = [], []
    last_day_of_skill, pending_revisions = {}, []
    dates = list(study_dates(start, deadline, study_days))
    week_skills = {}

    for d in dates:
        left = minutes_per_day
        week = (d - start).days // 7 + 1
        # Revisions that are due go first (spaced repetition).
        for rev in list(pending_revisions):
            if rev['earliest'] <= d and rev['duration_min'] <= left:
                items.append({**rev, 'date': d, 'week': week})
                left -= rev['duration_min']
                pending_revisions.remove(rev)
        while queue and queue[0]['duration_min'] <= left:
            task = queue.pop(0)
            items.append({**task, 'date': d, 'week': week})
            left -= task['duration_min']
            last_day_of_skill[task['skill_id']] = d
            week_skills.setdefault(week, [])
            if task['skill_name'] not in week_skills[week]:
                week_skills[week].append(task['skill_name'])
            # The skill's revision becomes available a week after its last planned task.
            if not any(t['skill_id'] == task['skill_id'] for t in queue):
                rev = next((r for r in revisions if r['skill_id'] == task['skill_id']), None)
                if rev:
                    revisions.remove(rev)
                    pending_revisions.append({**rev, 'earliest': d + timedelta(days=REVISION_GAP_DAYS)})
        # A task that can never fit in one study day would block the queue forever.
        while queue and queue[0]['duration_min'] > minutes_per_day:
            task = queue.pop(0)
            unscheduled.append({**task, 'why': f"needs {task['duration_min']} min but a study day has {minutes_per_day}"})
        # Weekly assessment on the last study day of each week, if there is room.
        next_d = dates[dates.index(d) + 1] if dates.index(d) + 1 < len(dates) else None
        if week_skills.get(week) and (next_d is None or (next_d - start).days // 7 + 1 != week):
            if left >= minutes['assessment']:
                items.append({'activity_type': 'assessment', 'difficulty': 'easy', 'skill_id': None,
                              'skill_name': '', 'title': f'Week {week} assessment: ' + ', '.join(week_skills[week][:4]),
                              'reason': 'A mixed coding round to check what you practised this week.',
                              'duration_min': minutes['assessment'], 'date': d, 'week': week,
                              'link': {'path': '/coding-round', 'params': {'difficulty': 'easy'}}})

    for task in queue:
        unscheduled.append({**task, 'why': 'does not fit before the deadline'})
    for rev in pending_revisions + revisions:
        unscheduled.append({**rev, 'why': 'revision falls after the deadline'})

    milestones = [{'week': w, 'title': f'Week {w}: ' + ', '.join(names[:5])} for w, names in sorted(week_skills.items())]
    return {'items': items, 'unscheduled': unscheduled, 'milestones': milestones}
