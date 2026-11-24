import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from django.db.models import F
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from .executor import DisabledExecutor, ExecutorError
from .executor import get_executor


def get_executor_or_none():
    try:
        return get_executor()
    except ExecutorError:
        return None
from . import question_bank
from .generator import ROUNDS, GenerationError, generate_round
from .judge import LANGUAGES, PASSED, TIMEOUT, run_tests
from .languages import LABELS, languages_for, signature, starter_code
from .models import CodingProblem, CodingSession, CodingSubmission
from .scoring import review_solution, score_problem, verdict_for

# Submissions sent automatically when the timer hits zero arrive a little late.
GRACE = timedelta(seconds=60)


class RunThrottle(UserRateThrottle):
    rate = '10/min'


def _short(value, limit=300):
    text = json.dumps(value)
    return text if len(text) <= limit else text[:limit] + '...'


def _best_submission(problem):
    return problem.submissions.filter(kind=CodingSubmission.SUBMIT).order_by('-passed', '-created_at').first()


def _public_problem(p):
    d = p.data
    best = _best_submission(p)
    sig = signature(d)
    langs = languages_for(d, sig)
    return {
        'id': p.id,
        'order': p.order,
        'title': p.title,
        'topic': p.topic,
        'statement': d['statement'],
        'constraints': d['constraints'],
        'params': d['params'],
        'examples': d['examples'],
        'languages': langs,
        'starter_code': {lang: starter_code(d, lang, sig) for lang in langs},
        'saved_code': p.saved_code,
        'hints': d['hints'][:p.hints_used],
        'hints_total': len(d['hints']),
        'source': d.get('source'),
        'best': {'passed': best.passed, 'total': best.total} if best else None,
    }


def _session_payload(session):
    return {
        'session_id': session.id,
        'status': session.status,
        'difficulty': session.difficulty,
        'language': session.language,
        'job_role': session.job_role,
        'ends_at': session.ends_at,
        'server_now': timezone.now(),
        'problems': [_public_problem(p) for p in session.problems.all()],
        'overall_score': session.overall_score,
        'report': session.report if session.status == CodingSession.COMPLETED else None,
    }


def _load_problem(request, late_ok=False):
    problem = get_object_or_404(CodingProblem, id=request.data.get('problem_id'), session__user=request.user)
    session = problem.session
    if session.status != CodingSession.IN_PROGRESS:
        return problem, Response({'error': 'This round is already finished.'}, status=400)
    limit = session.ends_at + (GRACE if late_ok else timedelta(0))
    if timezone.now() > limit:
        return problem, Response({'error': "Time's up for this round."}, status=400)
    return problem, None


def _code_and_language(request):
    language = request.data.get('language', 'python')
    code = request.data.get('code', '')
    if language not in LANGUAGES:
        return None, None, Response({'error': 'Unsupported language.'}, status=400)
    if not isinstance(code, str) or not code.strip():
        return None, None, Response({'error': 'Write some code first.'}, status=400)
    return language, code, None


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def language_list(request):
    """Languages for the picker; `missing` says what to install when one can't run on this setup."""
    try:
        missing = get_executor().available()
    except ExecutorError as e:
        missing = {lang: str(e) for lang in LANGUAGES}
    return Response([{'id': lang, 'label': LABELS[lang], 'available': not missing.get(lang),
                      'missing': missing.get(lang)} for lang in LANGUAGES])


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def company_list(request):
    """Companies in the question bank, for the 'practise for a company' picker."""
    return Response([{'slug': c['slug'], 'name': c['name'], 'count': c['count']} for c in question_bank.companies()])


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_session(request):
    difficulty = str(request.data.get('difficulty', 'medium')).lower()
    language = request.data.get('language', 'python')
    job_role = str(request.data.get('job_role', '')).strip()[:255]
    if difficulty not in ROUNDS:
        return Response({'error': 'Difficulty must be easy, medium or hard.'}, status=400)
    if language not in LANGUAGES:
        language = 'python'
    # Optional: practise the questions a specific company asks (from the question bank).
    company = question_bank.company_slug(str(request.data.get('company', ''))[:100])
    focus_topic = str(request.data.get('topic', '')).strip().lower()[:50]
    if focus_topic and not re.fullmatch(r'[a-z /-]+', focus_topic):
        focus_topic = ''

    # Without a code runner the problems can't be checked or judged, so don't spend LLM calls on them.
    if isinstance(get_executor_or_none(), DisabledExecutor):
        return Response({'error': DisabledExecutor.MESSAGE, 'code': 'executor_off'}, status=503)

    seen = list(CodingProblem.objects.filter(session__user=request.user)
                .order_by('-id').values_list('title', flat=True)[:30])
    try:
        problems = generate_round(difficulty, job_role, seen, focus_topic, company)
    except (GenerationError, ExecutorError) as e:
        return Response({'error': f"Couldn't prepare the problems, please try again. ({e})"}, status=503)

    minutes = ROUNDS[difficulty]['minutes']
    session = CodingSession.objects.create(
        user=request.user, job_role=job_role, difficulty=difficulty, language=language,
        time_limit_sec=minutes * 60, ends_at=timezone.now() + timedelta(minutes=minutes),
    )
    for i, data in enumerate(problems, 1):
        CodingProblem.objects.create(session=session, order=i, bank_id=data['function'],
                                     topic=data['topic'], title=data['title'], data=data)
    return Response(_session_payload(session))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([RunThrottle])
def run_code(request):
    problem, error = _load_problem(request)
    if error:
        return error
    language, code, error = _code_and_language(request)
    if error:
        return error

    examples = [{'category': 'example', 'args': e['args'], 'expected': e['expected']} for e in problem.data['examples']]
    try:
        results, run_error = run_tests(problem.data, language, code, examples)
    except ExecutorError as e:
        return Response({'error': str(e)}, status=503)

    problem.saved_code = {**problem.saved_code, language: code}
    problem.save(update_fields=['saved_code'])
    passed = sum(r['verdict'] == PASSED for r in results)
    CodingSubmission.objects.create(problem=problem, kind=CodingSubmission.RUN, language=language, code=code,
                                    passed=passed, total=len(examples), results=results)
    return Response({
        'error': run_error,
        'passed': passed,
        'total': len(examples),
        'results': [{**r, 'input': _short(ex['args']), 'expected': _short(ex['expected']),
                     'output': _short(r.get('output')) if r.get('output') is not None else None}
                    for r, ex in zip(results, examples)],
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([RunThrottle])
def submit_code(request):
    problem, error = _load_problem(request, late_ok=True)
    if error:
        return error
    language, code, error = _code_and_language(request)
    if error:
        return error

    tests = problem.data['tests']
    try:
        results, run_error = run_tests(problem.data, language, code, tests)
    except ExecutorError as e:
        return Response({'error': str(e)}, status=503)

    if run_error:
        results = [{'category': t['category'], 'verdict': 'Runtime error', 'error': run_error} for t in tests]
    passed = sum(r['verdict'] == PASSED for r in results)
    problem.saved_code = {**problem.saved_code, language: code}
    problem.save(update_fields=['saved_code'])
    CodingSubmission.objects.create(problem=problem, kind=CodingSubmission.SUBMIT, language=language, code=code,
                                    passed=passed, total=len(tests), results=results)

    pastes = request.data.get('paste_flags', 0)
    if isinstance(pastes, int) and pastes > 0:
        CodingSession.objects.filter(id=problem.session_id).update(paste_flags=F('paste_flags') + pastes)

    first_fail = next((r for r in results if r['verdict'] != PASSED), None)
    best = _best_submission(problem)
    return Response({
        'error': run_error,
        'passed': passed,
        'total': len(tests),
        'first_failing': {'category': first_fail['category'], 'verdict': first_fail['verdict']} if first_fail else None,
        'best': {'passed': best.passed, 'total': best.total},
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def get_hint(request):
    problem, error = _load_problem(request)
    if error:
        return error
    hints = problem.data['hints']
    if problem.hints_used >= len(hints):
        return Response({'error': 'No more hints for this problem.'}, status=400)
    problem.hints_used += 1
    problem.save(update_fields=['hints_used'])
    return Response({'hints': hints[:problem.hints_used], 'hints_total': len(hints)})


def _review_problem(problem):
    best = _best_submission(problem)
    if not best:
        return problem, None, None
    review = review_solution(problem.data, best.language, best.code, best.passed, best.total, best.results)
    return problem, best, review


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def finish_session(request):
    session = get_object_or_404(CodingSession, id=request.data.get('session_id'), user=request.user)
    if session.status == CodingSession.COMPLETED:
        return Response(_session_payload(session))

    problems = list(session.problems.all())
    with ThreadPoolExecutor(max_workers=max(1, len(problems))) as pool:
        reviewed = list(pool.map(_review_problem, problems))

    items = []
    for problem, best, review in reviewed:
        d = problem.data
        if not best:
            items.append({'title': problem.title, 'topic': problem.topic, 'attempted': False,
                          'score': score_problem(0, 0, {}, 0, False), 'hints_used': problem.hints_used,
                          'reference_solution': d['reference_solution'], 'complexity': d['complexity']})
            continue
        had_timeout = any(r['verdict'] == TIMEOUT for r in best.results)
        score = score_problem(best.passed, best.total, review, problem.hints_used, had_timeout)
        failed_inputs = [
            {'category': t['category'], 'input': 'large input (too big to show)' if t['category'] == 'large' else _short(t['args'], 500),
             'expected': _short(t['expected'], 300), 'verdict': r['verdict']}
            for t, r in zip(d['tests'], best.results) if r['verdict'] != PASSED
        ][:5]
        items.append({
            'title': problem.title, 'topic': problem.topic, 'attempted': True, 'language': best.language,
            'passed': best.passed, 'total': best.total, 'score': score, 'hints_used': problem.hints_used,
            'review': review, 'code': best.code, 'failed_tests': failed_inputs,
            'reference_solution': d['reference_solution'], 'complexity': d['complexity'],
        })

    # Learning engine evidence: one record per attempted problem, idempotent per problem id.
    from learning.services.evidence import record_coding_problem
    for (problem, best, _), item in zip(reviewed, items):  # items were built in the same order
        if best:
            record_coding_problem(request.user, problem, item['score']['total'], best.passed, best.total,
                                  problem.hints_used, session.difficulty)

    overall = round(sum(i['score']['total'] for i in items) / len(items)) if items else 0
    tab_switches = request.data.get('tab_switches', 0)
    session.tab_switches = tab_switches if isinstance(tab_switches, int) else 0
    session.overall_score = overall
    session.report = {'verdict': verdict_for(overall), 'problems': items,
                      'paste_flags': session.paste_flags, 'tab_switches': session.tab_switches}
    session.status = CodingSession.COMPLETED
    session.completed_at = timezone.now()
    session.save()
    return Response(_session_payload(session))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def session_detail(request, session_id):
    session = get_object_or_404(CodingSession, id=session_id, user=request.user)
    return Response(_session_payload(session))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def active_session(request):
    """Lets the page resume a round after a refresh."""
    session = CodingSession.objects.filter(user=request.user, status=CodingSession.IN_PROGRESS).order_by('-id').first()
    return Response(_session_payload(session) if session else {'session_id': None})
