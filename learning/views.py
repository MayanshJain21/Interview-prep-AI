from django.core.cache import cache
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from ai_features.llm import LLMError, LLMRateThrottle, call_llm_json, clean_list, clean_str
from jobs.models import ResumeJobAnalysis
from .models import LearningRoadmap, RoadmapItem, Skill
from .serializers import (GenerateRoadmapSerializer, ItemStatusSerializer, RescheduleSerializer,
                          RoadmapSerializer)
from .services import insights
from .services.recommender import recommendations, skill_states
from .services.roadmap import active_roadmap, generate_roadmap, reschedule_item, set_item_status


def _bad(serializer):
    return Response({'error': 'Invalid input.', 'fields': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def profile_view(request):
    return Response(insights.profile(request.user))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def mastery_view(request):
    _, analysis, role = insights.goal_context(request.user)
    states, _ = skill_states(request.user, role, analysis)
    return Response({'target_role': role, 'skills': insights.mastery_rows(states)})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def recommendations_view(request):
    _, analysis, role = insights.goal_context(request.user)
    states, _ = skill_states(request.user, role, analysis)
    limit = min(max(int(request.query_params.get('limit', 5) or 5), 1), 20)
    return Response({'target_role': role, 'recommendations': recommendations(states, limit=limit)})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def analytics_view(request):
    return Response(insights.analytics(request.user))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_view(request):
    s = GenerateRoadmapSerializer(data=request.data)
    if not s.is_valid():
        return _bad(s)
    data = s.validated_data
    analysis = None
    if data.get('job_analysis_id'):
        analysis = ResumeJobAnalysis.objects.filter(id=data['job_analysis_id'], user=request.user).select_related('job').first()
        if not analysis:
            return Response({'error': 'Job analysis not found.'}, status=404)
    role = data['target_role'] or (analysis.job.target_role or analysis.job.title if analysis else '')
    try:
        roadmap = generate_roadmap(request.user, target_role=role, analysis=analysis, deadline=data['deadline'],
                                   minutes_per_day=data['minutes_per_day'], study_days=data['study_days'])
    except ValueError as e:
        return Response({'error': str(e)}, status=400)
    return Response(RoadmapSerializer(roadmap).data, status=201)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def roadmap_view(request):
    roadmap = active_roadmap(request.user)
    history = LearningRoadmap.objects.filter(user=request.user, status=LearningRoadmap.ARCHIVED).order_by('-id')[:10]
    return Response({
        'roadmap': RoadmapSerializer(roadmap).data if roadmap else None,
        'history': [{'id': r.id, 'target_role': r.target_role, 'created_at': r.created_at, 'deadline': r.deadline,
                     'completed': r.items.filter(status='completed').count(), 'total': r.items.count()} for r in history],
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def roadmap_detail_view(request, roadmap_id):
    roadmap = LearningRoadmap.objects.filter(id=roadmap_id, user=request.user).first()
    if not roadmap:
        return Response({'error': 'Roadmap not found.'}, status=404)
    return Response(RoadmapSerializer(roadmap).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def complete_view(request):
    s = ItemStatusSerializer(data=request.data)
    if not s.is_valid():
        return _bad(s)
    try:
        item = set_item_status(request.user, s.validated_data['item_id'], s.validated_data['status'])
    except RoadmapItem.DoesNotExist:
        return Response({'error': 'Task not found.'}, status=404)
    except ValueError as e:
        return Response({'error': str(e)}, status=400)
    return Response({'id': item.id, 'status': item.status, 'completed_at': item.completed_at})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reschedule_view(request):
    s = RescheduleSerializer(data=request.data)
    if not s.is_valid():
        return _bad(s)
    try:
        item, warning = reschedule_item(request.user, s.validated_data['item_id'], s.validated_data['date'])
    except RoadmapItem.DoesNotExist:
        return Response({'error': 'Task not found.'}, status=404)
    except ValueError as e:
        return Response({'error': str(e)}, status=400)
    return Response({'id': item.id, 'scheduled_date': item.scheduled_date, 'week': item.week, 'warning': warning})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def skills_view(request):
    return Response([{'slug': s.slug, 'name': s.name, 'category': s.category, 'parent': s.parent.slug if s.parent else None,
                      'prerequisites': [p.prerequisite.slug for p in s.prerequisite_links.all()]}
                     for s in Skill.objects.select_related('parent').prefetch_related('prerequisite_links__prerequisite')])


def _validate_notes(data):
    out = {'summary': clean_str(data.get('summary'), 600), 'key_concepts': clean_list(data.get('key_concepts'), 10, 200),
           'practice_ideas': clean_list(data.get('practice_ideas'), 6, 200),
           'common_mistakes': clean_list(data.get('common_mistakes'), 6, 200)}
    if not out['summary'] or not out['key_concepts']:
        raise ValueError('incomplete notes')
    return out


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([LLMRateThrottle])
def notes_view(request):
    """Short study notes for a 'learn' task. Generic per skill, so cached for everyone."""
    skill = Skill.objects.filter(slug=str(request.data.get('skill', ''))[:60]).first()
    if not skill:
        return Response({'error': 'Unknown skill.'}, status=404)
    key = f'study-notes:{skill.slug}'
    notes = cache.get(key)
    if not notes:
        try:
            notes = call_llm_json(
                'You are a computer science tutor preparing a student for placement interviews. Write concise, '
                'accurate study notes. Return JSON: {"summary": "2-3 sentences", "key_concepts": ["..."], '
                '"practice_ideas": ["..."], "common_mistakes": ["..."]}',
                f'Topic: {skill.name}', validate=_validate_notes, max_tokens=1500)
        except LLMError as e:
            return Response({'error': str(e)}, status=503)
        cache.set(key, notes, 24 * 3600)
    return Response({'skill': skill.name, **notes})

