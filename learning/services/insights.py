"""Read-only views over the learning data: profile, mastery table, analytics."""
from datetime import timedelta

from django.db.models import Avg
from django.utils import timezone

from learning.models import LearningAttempt, LearningGoal, RoadmapItem, Skill, SkillMastery
from .recommender import recommendations, skill_states
from .roadmap import active_roadmap
from .taxonomy import build_index, match_skill


def goal_context(user):
    goal = LearningGoal.objects.filter(user=user).select_related('job_analysis__job').first()
    analysis = goal.job_analysis if goal else None
    if analysis is None:
        from jobs.models import ResumeJobAnalysis
        analysis = ResumeJobAnalysis.objects.filter(user=user).select_related('job').order_by('-id').first()
    role = (goal.target_role if goal and goal.target_role else '') or (analysis.job.target_role or analysis.job.title if analysis else '')
    return goal, analysis, role


def mastery_rows(states):
    rows = []
    for st in sorted(states.values(), key=lambda s: (-s['importance'], s['name'])):
        rows.append({k: st[k] for k in ('slug', 'name', 'category', 'importance', 'mastery', 'gap', 'status',
                                        'attempts', 'sources', 'confidence', 'priority', 'reasons')}
                    | {'band': st['band']['label'], 'last_assessed': st['last_assessed'],
                       'blocked_by': [s for s in st['blocked_by']]})
    return rows


def profile(user):
    from ai_features.models import HRHistory, HRSession
    from coding.models import CodingSession
    from resume.models import Resume

    goal, analysis, role = goal_context(user)
    resume = Resume.objects.filter(user=user).first()
    index = build_index(Skill.objects.all())
    resume_skills = (resume.parsed_data.get('skills', []) if resume and isinstance(resume.parsed_data, dict) else [])
    normalized = []
    for s in resume_skills:
        skill = match_skill(s, index)
        normalized.append({'name': s, 'canonical': skill.name if skill else None, 'slug': skill.slug if skill else None})
    hr_done = HRSession.objects.filter(user=user, status=HRSession.STATUS_COMPLETED)
    return {
        'has_resume': bool(resume),
        'resume_skills': normalized,
        'target_role': role,
        'goal': {'deadline': goal.deadline, 'minutes_per_day': goal.minutes_per_day, 'study_days': goal.study_days} if goal else None,
        'job_analysis': {'id': analysis.id, 'job_id': analysis.job_id, 'title': analysis.job.title,
                         'company': analysis.job.company, 'score': analysis.overall_score} if analysis else None,
        'assessments': {
            'mcq_attempts': LearningAttempt.objects.filter(user=user, source='mcq').values('source_ref').distinct().count(),
            'coding_rounds': CodingSession.objects.filter(user=user, status=CodingSession.COMPLETED).count(),
            'technical_interviews': user.technical_sessions.filter(status='completed').count(),
        },
        # HR / behavioural performance is a separate dimension and never feeds technical mastery.
        'communication': {'hr_interviews': hr_done.count(),
                          'average_hr_answer_score': round(HRHistory.objects.filter(user=user).exclude(answer='')
                                                           .aggregate(a=Avg('score'))['a'] or 0, 1)},
    }


def analytics(user):
    _, analysis, role = goal_context(user)
    states, _ = skill_states(user, role, analysis)
    rows = mastery_rows(states)
    assessed = [r for r in rows if r['mastery'] is not None]
    weighted = sum(r['importance'] for r in rows) or 1
    readiness = sum((r['mastery'] or 0) * r['importance'] for r in rows) / weighted

    # Recent improvement: change in each skill's mastery over the last 14 days.
    since = timezone.now() - timedelta(days=14)
    improvement = {}
    for a in LearningAttempt.objects.filter(user=user, created_at__gte=since).select_related('skill').order_by('created_at'):
        entry = improvement.setdefault(a.skill.name, {'skill': a.skill.name, 'from': a.mastery_before, 'to': a.mastery_after})
        entry['to'] = a.mastery_after
    recent = []
    for e in improvement.values():
        if e['from'] is not None and e['to'] is not None:
            recent.append({**e, 'change': round(e['to'] - e['from'], 1)})
    recent.sort(key=lambda e: -abs(e['change']))

    roadmap = active_roadmap(user)
    progress = None
    if roadmap:
        items = roadmap.items.all()
        total = items.exclude(status=RoadmapItem.SKIPPED).count()
        done = items.filter(status=RoadmapItem.COMPLETED).count()
        progress = {'completed': done, 'total': total, 'percent': round(100 * done / total) if total else 0}

    job_progress = None
    if analysis:
        req = [m for m in analysis.skill_matches if m.get('importance') == 'required' and m.get('skill_slug')]
        mastery = {m.skill.slug: m.mastery for m in SkillMastery.objects.filter(user=user).select_related('skill')}
        job_progress = [{'skill': m['skill'], 'resume_status': m['status'],
                         'mastery': round(mastery[m['skill_slug']], 1) if m['skill_slug'] in mastery else None}
                        for m in req]

    return {
        'target_role': role,
        'readiness': round(readiness, 1),  # importance-weighted mastery; unassessed skills count as 0
        'assessed_skills': len(assessed),
        'relevant_skills': len(rows),
        'mastery': rows,
        'weakest': sorted(assessed, key=lambda r: r['mastery'])[:5],
        'strongest': sorted(assessed, key=lambda r: -r['mastery'])[:5],
        'unassessed': [r['name'] for r in rows if r['mastery'] is None][:10],
        'recommendations': recommendations(states, limit=5),
        'recent_improvement': recent[:8],
        'roadmap_progress': progress,
        'job_progress': job_progress,
    }
