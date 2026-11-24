from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from ai_features.models import ATSHistory, MCQHistory, HRHistory, HRSession
from coding.models import CodingSession
from technical.models import TechnicalInterviewSession
from django.db.models import Avg


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_history(request):
    user = request.user

    mcq_entries = MCQHistory.objects.filter(user=user).order_by('-created_at')
    mcq_history = list(mcq_entries.values('id', 'score', 'total', 'skills', 'created_at'))

    # Only answered questions; an abandoned interview leaves an unanswered one behind.
    hr_entries = HRHistory.objects.filter(user=user).exclude(answer='').order_by('-created_at')
    hr_history = list(hr_entries.values('id', 'question', 'answer', 'score', 'feedback', 'created_at'))

    mcq_count = mcq_entries.count()
    # A full interview is one session; legacy single-question answers (no session) count individually.
    hr_count = (
        HRSession.objects.filter(user=user, status=HRSession.STATUS_COMPLETED).count()
        + hr_entries.filter(session__isnull=True).count()
    )

    coding_done = CodingSession.objects.filter(user=user, status=CodingSession.COMPLETED)
    coding_count = coding_done.count()
    avg_coding = coding_done.aggregate(avg=Avg('overall_score'))['avg'] or 0

    tech_done = TechnicalInterviewSession.objects.filter(user=user, status=TechnicalInterviewSession.COMPLETED)
    tech_count = tech_done.count()
    avg_tech = tech_done.aggregate(avg=Avg('overall_score'))['avg'] or 0

    avg_mcq = mcq_entries.aggregate(avg=Avg('score'))['avg'] or 0
    avg_hr = hr_entries.aggregate(avg=Avg('score'))['avg'] or 0

    latest_ats = ATSHistory.objects.filter(user=user).order_by('-created_at').first()

    stats = {
        'total_sessions': mcq_count + hr_count + coding_count + tech_count,
        'average_technical_score': round(avg_tech),
        'average_coding_score': round(avg_coding),
        'average_mcq_score': round(avg_mcq, 2),
        'average_hr_score': round(avg_hr, 2),
        'latest_ats_score': latest_ats.score if latest_ats else None,
        'coding_rounds': coding_count,
        'technical_interviews': tech_count,
        'hr_interviews': hr_count,
        'mcq_tests': mcq_count,
    }

    return Response({
        'mcq_history': mcq_history,
        'hr_history': hr_history,
        'stats': stats,
        'timeline': _timeline(user, mcq_entries, coding_done, tech_done),
    })


def _timeline(user, mcq_entries, coding_done, tech_done, limit=120):
    """Every finished assessment as {module, score 0-100, date}, oldest first, for the dashboard charts."""
    points = [{'module': 'mcq', 'score': round(100 * e.score / e.total) if e.total else 0, 'date': e.created_at}
              for e in mcq_entries[:limit]]
    points += [{'module': 'coding', 'score': s.overall_score, 'date': s.completed_at or s.started_at}
               for s in coding_done.order_by('-id')[:limit]]
    points += [{'module': 'technical', 'score': round(s.overall_score or 0), 'date': s.completed_at or s.created_at}
               for s in tech_done.order_by('-id')[:limit]]
    points += [{'module': 'hr', 'score': s.overall_score, 'date': s.completed_at or s.created_at}
               for s in HRSession.objects.filter(user=user, status=HRSession.STATUS_COMPLETED).order_by('-id')[:limit]]
    return sorted(points, key=lambda p: p['date'])
