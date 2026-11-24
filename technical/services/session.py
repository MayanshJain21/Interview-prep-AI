"""Technical interview lifecycle. Views call these and only translate errors to HTTP."""
from django.db import transaction
from django.utils import timezone

from ai_features.llm import LLMError
from learning.models import Skill
from learning.services.taxonomy import build_index, match_skill
from technical.models import TechnicalInterviewSession as Session, TechnicalInterviewTurn as Turn
from .ai import RUBRIC, evaluate_answer, generate_question
from .plan import INTERVIEW_TYPES, LEVEL_NAMES, START_LEVEL, next_step, plan_topics


class Conflict(Exception):
    """The request clashes with the session state (already answered, finished, ...)."""


def _resume(user):
    from resume.models import Resume
    return Resume.objects.filter(user=user).first()


def _job_summary(job):
    if not job or not job.extracted:
        return ''
    e = job.extracted
    return f"required: {', '.join(e.get('required_skills', [])[:12])}; responsibilities: {'; '.join(e.get('responsibilities', [])[:4])}"


def _ask(session, step, previous):
    question = generate_question(session, step, previous, _job_summary(session.job))
    skill = Skill.objects.filter(slug=step['skill']).first() if step.get('skill') else None
    return Turn.objects.create(session=session, number=len(previous) + 1, topic=step['topic'], skill=skill,
                               difficulty=LEVEL_NAMES[step['level']], kind=step['kind'], question=question)


def start(user, *, interview_type, difficulty, num_questions, job_role='', company='', job=None):
    if interview_type not in INTERVIEW_TYPES:
        raise ValueError('Unknown interview type.')
    resume = _resume(user)
    resume_slugs = set()
    if resume and isinstance(resume.parsed_data, dict):
        index = build_index(Skill.objects.all())
        resume_slugs = {s.slug for s in (match_skill(x, index) for x in resume.parsed_data.get('skills', [])) if s}
    if interview_type == 'project' and not resume:
        raise ValueError('A project-based interview needs your resume. Upload it first.')
    job_slugs = set(job.requirements.exclude(skill=None).values_list('skill__slug', flat=True)) if job else set()

    resume_context = ''
    if resume and interview_type in ('project', 'mixed'):
        try:
            from ai_features.rag import retrieve_context
            resume_context = retrieve_context(user.id, 'projects architecture technologies built implemented', k=5)
        except Exception:
            resume_context = ''
        resume_context = resume_context or (resume.raw_text or '')[:5000]

    session = Session.objects.create(
        user=user, interview_type=interview_type, difficulty=difficulty, num_questions=num_questions,
        job_role=job_role or (job.target_role or job.title if job else ''), company=company or (job.company if job else ''),
        job=job, level=START_LEVEL[difficulty], resume_context=resume_context,
        topic_plan=plan_topics(interview_type, num_questions, resume_slugs, job_slugs, has_resume=bool(resume)),
    )
    first = session.topic_plan[0]
    try:
        _ask(session, {**first, 'kind': 'core', 'level': session.level}, [])
    except LLMError:
        session.delete()
        raise
    session.status = Session.IN_PROGRESS
    session.save(update_fields=['status'])
    return session


def submit_answer(user, session_id, answer):
    answer = (answer or '').strip()
    if not answer:
        raise ValueError('Write or speak an answer first.')
    if len(answer) > 6000:
        raise ValueError('That answer is too long (6000 characters max).')
    session = Session.objects.filter(id=session_id, user=user).first()
    if not session:
        raise Session.DoesNotExist()
    if session.status != Session.IN_PROGRESS:
        raise Conflict('This interview is not in progress.')
    turn = session.turns.filter(state=Turn.OPEN).first()
    if not turn:
        raise Conflict('There is no open question. Use continue to get the next one.')

    # Claim the turn atomically: a second submit for the same question gets a conflict instead of
    # evaluating twice and corrupting the session.
    claimed = Turn.objects.filter(id=turn.id, state=Turn.OPEN).update(state=Turn.EVALUATING, answer=answer)
    if not claimed:
        raise Conflict('This answer is already being evaluated.')
    try:
        evaluation = evaluate_answer(session, turn, answer)
    except LLMError:
        Turn.objects.filter(id=turn.id).update(state=Turn.OPEN, answer='')  # let them resend
        raise
    Turn.objects.filter(id=turn.id).update(state=Turn.ANSWERED, score=evaluation['score'], evaluation=evaluation,
                                           answered_at=timezone.now())
    return advance(session)


def advance(session):
    """Ask the next question, or finish when the planned number has been asked."""
    turns = list(session.turns.all())
    if any(t.state != Turn.ANSWERED for t in turns):
        return session, None
    step = next_step(session.topic_plan, turns, session.num_questions, session.level)
    if step is None:
        return finish(session), None
    session.level = step['level']
    session.save(update_fields=['level'])
    return session, _ask(session, step, turns)  # LLMError here leaves the session waiting for continue


def continue_session(user, session_id):
    session = Session.objects.filter(id=session_id, user=user).first()
    if not session:
        raise Session.DoesNotExist()
    if session.status != Session.IN_PROGRESS:
        raise Conflict('This interview is not in progress.')
    if session.turns.filter(state__in=[Turn.OPEN, Turn.EVALUATING]).exists():
        return session, session.turns.filter(state=Turn.OPEN).first()
    return advance(session)


def end_early(user, session_id):
    session = Session.objects.filter(id=session_id, user=user).first()
    if not session:
        raise Session.DoesNotExist()
    if session.status == Session.COMPLETED:
        return session
    if not session.turns.filter(state=Turn.ANSWERED).exists():
        raise Conflict('Answer at least one question before ending the interview.')
    session.turns.exclude(state=Turn.ANSWERED).delete()
    return finish(session)


def finish(session):
    from learning.services.evidence import record_technical_turn
    with transaction.atomic():
        session = Session.objects.select_for_update().get(id=session.id)
        if session.status == Session.COMPLETED:
            return session
        turns = list(session.turns.filter(state=Turn.ANSWERED).select_related('skill'))
        for t in turns:
            record_technical_turn(session.user, t)  # idempotent evidence -> mastery -> roadmap
        session.report = build_report(session, turns)
        session.overall_score = session.report['overall_score']
        session.status = Session.COMPLETED
        session.completed_at = timezone.now()
        session.save()
    return session


def build_report(session, turns):
    from learning.services.insights import goal_context
    from learning.services.recommender import recommendations, skill_states

    scores = [t.score for t in turns if t.score is not None]
    overall = round(sum(scores) / len(scores) * 10, 1) if scores else 0.0
    topics = {}
    for t in turns:
        e = topics.setdefault(t.topic, {'topic': t.topic, 'skill': t.skill.name if t.skill else None,
                                        'skill_slug': t.skill.slug if t.skill else None, 'scores': []})
        e['scores'].append(t.score)
    topic_rows = [{**v, 'average': round(sum(v['scores']) / len(v['scores']), 1)} for v in topics.values()]
    for row in topic_rows:
        row.pop('scores')
    topic_rows.sort(key=lambda r: -r['average'])

    criteria = {k: round(sum(t.evaluation['scores'][k] for t in turns) / len(turns), 1) for k in RUBRIC} if turns else {}
    handled = [t for t in turns if (t.score or 0) >= 6]
    hardest = max((t.difficulty for t in handled), key=lambda d: ['Easy', 'Medium', 'Hard'].index(d), default=None)

    # Next priorities come from the learning engine, which already includes this interview's evidence.
    _, analysis, role = goal_context(session.user)
    states, _ = skill_states(session.user, role or session.job_role, analysis)
    interview_skills = {r['skill_slug'] for r in topic_rows if r['skill_slug']}
    recs = recommendations(states, limit=12)
    focused = [r for r in recs if r['skill_slug'] in interview_skills] + [r for r in recs if r['skill_slug'] not in interview_skills]

    return {
        'overall_score': overall,
        'verdict': 'Interview ready' if overall >= 75 else 'Almost there' if overall >= 55 else 'Needs practice',
        'interview_type': INTERVIEW_TYPES[session.interview_type]['label'],
        'questions_answered': len(turns),
        'topic_performance': topic_rows,
        'strengths': [r['topic'] for r in topic_rows if r['average'] >= 7],
        'knowledge_gaps': [r['topic'] for r in topic_rows if r['average'] < 5],
        'incorrect_concepts': [s for t in turns for s in t.evaluation.get('incorrect_statements', [])][:10],
        'missing_concepts': [s for t in turns for s in t.evaluation.get('missing_concepts', [])][:12],
        'criteria_averages': criteria,
        'communication_score': criteria.get('clarity'),
        'difficulty_handled': hardest or 'None yet (no answer scored 6 or more)',
        'next_priorities': focused[:4],
    }
