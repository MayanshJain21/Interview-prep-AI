from django.core.paginator import Paginator
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ai_features.llm import LLMError, LLMRateThrottle
from jobs.models import JobDescription
from .models import TechnicalInterviewSession as Session, TechnicalInterviewTurn as Turn
from .services import session as svc
from .services.plan import INTERVIEW_TYPES


class StartSerializer(serializers.Serializer):
    interview_type = serializers.ChoiceField(choices=list(INTERVIEW_TYPES))
    difficulty = serializers.ChoiceField(choices=['Easy', 'Medium', 'Hard'])
    num_questions = serializers.IntegerField(min_value=3, max_value=10)
    job_role = serializers.CharField(max_length=150, required=False, allow_blank=True, default='')
    company = serializers.CharField(max_length=150, required=False, allow_blank=True, default='')
    job_id = serializers.IntegerField(required=False, allow_null=True)


def turn_payload(t, reveal):
    data = {'number': t.number, 'topic': t.topic, 'difficulty': t.difficulty, 'kind': t.kind,
            'question': t.question, 'answer': t.answer, 'state': t.state}
    if reveal:  # evaluations are shown in the final report, not during the interview
        data.update({'score': t.score, 'evaluation': t.evaluation})
    return data


def session_payload(s):
    done = s.status == Session.COMPLETED
    turns = list(s.turns.all())
    open_turn = next((t for t in turns if t.state == Turn.OPEN), None)
    return {
        'id': s.id, 'status': s.status, 'interview_type': s.interview_type,
        'interview_label': INTERVIEW_TYPES[s.interview_type]['label'], 'difficulty': s.difficulty,
        'num_questions': s.num_questions, 'job_role': s.job_role, 'company': s.company, 'job_id': s.job_id,
        'created_at': s.created_at, 'completed_at': s.completed_at,
        'answered': sum(t.state == Turn.ANSWERED for t in turns),
        'current_question': turn_payload(open_turn, False) if open_turn else None,
        'awaiting_question': s.status == Session.IN_PROGRESS and not any(t.state != Turn.ANSWERED for t in turns),
        'transcript': [turn_payload(t, done) for t in turns],
        'overall_score': s.overall_score,
        'report': s.report if done else None,
    }


def _error(e):
    if isinstance(e, Session.DoesNotExist):
        return Response({'error': 'Interview not found.'}, status=404)
    if isinstance(e, svc.Conflict):
        return Response({'error': str(e)}, status=409)
    if isinstance(e, LLMError):
        return Response({'error': str(e), 'retry': True}, status=503)
    return Response({'error': str(e)}, status=400)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([LLMRateThrottle])
def start_view(request):
    s = StartSerializer(data=request.data)
    if not s.is_valid():
        return Response({'error': 'Invalid input.', 'fields': s.errors}, status=400)
    d = s.validated_data
    job = None
    if d.get('job_id'):
        job = JobDescription.objects.filter(id=d['job_id'], user=request.user).first()
        if not job:
            return Response({'error': 'Job description not found.'}, status=404)
    if Session.objects.filter(user=request.user, status=Session.IN_PROGRESS).count() >= 3:
        return Response({'error': 'You already have unfinished interviews. Finish or end one first.'}, status=409)
    try:
        session = svc.start(request.user, interview_type=d['interview_type'], difficulty=d['difficulty'],
                            num_questions=d['num_questions'], job_role=d['job_role'], company=d['company'], job=job)
    except (ValueError, LLMError) as e:
        return _error(e)
    return Response(session_payload(session), status=201)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([LLMRateThrottle])
def answer_view(request):
    try:
        session, _ = svc.submit_answer(request.user, request.data.get('session_id'), request.data.get('answer'))
    except LLMError as e:
        # The evaluation is saved before the next question is generated; tell the client which failed.
        s = Session.objects.filter(id=request.data.get('session_id'), user=request.user).first()
        if s and s.turns.filter(state=Turn.OPEN).count() == 0 and s.turns.filter(state=Turn.ANSWERED).exists() \
                and s.status == Session.IN_PROGRESS and not s.turns.filter(state=Turn.EVALUATING).exists():
            return Response({**session_payload(s), 'warning': str(e)}, status=200)
        return _error(e)
    except (ValueError, svc.Conflict, Session.DoesNotExist) as e:
        return _error(e)
    return Response(session_payload(Session.objects.get(id=session.id)))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([LLMRateThrottle])
def continue_view(request):
    try:
        session, _ = svc.continue_session(request.user, request.data.get('session_id'))
    except (LLMError, svc.Conflict, Session.DoesNotExist) as e:
        return _error(e)
    return Response(session_payload(Session.objects.get(id=session.id)))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def end_view(request):
    try:
        session = svc.end_early(request.user, request.data.get('session_id'))
    except (svc.Conflict, Session.DoesNotExist) as e:
        return _error(e)
    return Response(session_payload(session))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def session_view(request, session_id):
    s = Session.objects.filter(id=session_id, user=request.user).first()
    return Response(session_payload(s)) if s else _error(Session.DoesNotExist())


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def report_view(request, session_id):
    s = Session.objects.filter(id=session_id, user=request.user, status=Session.COMPLETED).first()
    return Response(session_payload(s)) if s else Response({'error': 'Report not found.'}, status=404)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def history_view(request):
    qs = Session.objects.filter(user=request.user).exclude(status=Session.PENDING)
    page = Paginator(qs, 10).get_page(request.query_params.get('page', 1))
    return Response({
        'results': [{'id': s.id, 'status': s.status, 'interview_label': INTERVIEW_TYPES[s.interview_type]['label'],
                     'difficulty': s.difficulty, 'job_role': s.job_role, 'overall_score': s.overall_score,
                     'num_questions': s.num_questions, 'created_at': s.created_at} for s in page],
        'page': page.number, 'pages': page.paginator.num_pages, 'count': page.paginator.count,
        'interview_types': {k: v['label'] for k, v in INTERVIEW_TYPES.items()},
    })
