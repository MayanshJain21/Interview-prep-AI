from django.conf import settings
from django.core.paginator import Paginator
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ai_features.llm import LLMError, LLMRateThrottle
from resume.pdf import PdfError, extract_pdf_text
from .models import JobDescription, ResumeJobAnalysis
from .services.analyzer import NoRequirements, NoResume, analyze


class JobInputSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=150)
    company = serializers.CharField(max_length=150, required=False, allow_blank=True, default='')
    target_role = serializers.CharField(max_length=150, required=False, allow_blank=True, default='')
    text = serializers.CharField(required=False, allow_blank=True, default='', trim_whitespace=True)


def analysis_payload(a):
    return {
        'id': a.id, 'job_id': a.job_id, 'created_at': a.created_at, 'resume_filename': a.resume_filename,
        'overall_score': a.overall_score, 'technical_score': a.technical_score, 'breakdown': a.breakdown,
        'skill_matches': a.skill_matches, 'recommendations': a.recommendations,
        'preparation_areas': a.preparation_areas, 'relevant_sections': a.relevant_sections,
    }


def job_payload(job, with_text=False):
    latest = job.analyses.order_by('-id').first()
    data = {
        'id': job.id, 'title': job.title, 'company': job.company, 'target_role': job.target_role, 'source': job.source,
        'created_at': job.created_at, 'requirements_summary': job.extracted or None,
        'requirements': [{'name': r.name, 'skill': r.skill.name if r.skill else None, 'importance': r.importance,
                          'kind': r.kind} for r in job.requirements.select_related('skill')],
        'latest_analysis': analysis_payload(latest) if latest else None,
        'analyses': [{'id': a.id, 'score': a.overall_score, 'created_at': a.created_at}
                     for a in job.analyses.order_by('-id')[:10]],
    }
    if with_text:
        data['text'] = job.text
    return data


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_job(request):
    """Create a job description from pasted text or an uploaded PDF (multipart field `file`)."""
    s = JobInputSerializer(data=request.data)
    if not s.is_valid():
        return Response({'error': 'Invalid input.', 'fields': s.errors}, status=400)
    data = s.validated_data
    cfg = settings.JOB_MATCH
    text, source = data['text'], 'paste'
    upload = request.FILES.get('file')
    if upload:
        try:
            text = extract_pdf_text(upload, max_bytes=cfg['MAX_PDF_BYTES'], max_pages=cfg['MAX_PDF_PAGES'],
                                    max_chars=cfg['MAX_JD_CHARS'])
        except PdfError as e:
            return Response({'error': str(e)}, status=400)
        source = 'pdf'
    if len(text) < 80:
        return Response({'error': 'Paste the full job description (at least a few sentences) or upload a PDF.'}, status=400)
    if len(text) > cfg['MAX_JD_CHARS']:
        return Response({'error': f"The job description is too long (max {cfg['MAX_JD_CHARS']} characters)."}, status=400)
    job = JobDescription.objects.create(user=request.user, title=data['title'], company=data['company'],
                                        target_role=data['target_role'], text=text, source=source)
    return Response(job_payload(job), status=201)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([LLMRateThrottle])
def analyze_job(request):
    job = JobDescription.objects.filter(id=request.data.get('job_id'), user=request.user).first()
    if not job:
        return Response({'error': 'Job description not found.'}, status=404)
    try:
        result = analyze(request.user, job)
    except NoResume:
        return Response({'error': 'Upload your resume first: the analysis compares it with this job.',
                         'code': 'no_resume'}, status=400)
    except NoRequirements:
        return Response({'error': "No skill requirements were found in this document. It may be a company profile "
                                  "rather than a job description; paste the role's requirements or eligibility section.",
                         'code': 'no_requirements'}, status=400)
    except LLMError as e:
        return Response({'error': str(e)}, status=503)
    return Response({'job': job_payload(job), 'analysis': analysis_payload(result)}, status=201)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def history(request):
    jobs = JobDescription.objects.filter(user=request.user).prefetch_related('analyses')
    page = Paginator(jobs, 10).get_page(request.query_params.get('page', 1))
    items = []
    for job in page:
        latest = job.analyses.order_by('-id').first()
        items.append({'id': job.id, 'title': job.title, 'company': job.company, 'target_role': job.target_role,
                      'created_at': job.created_at, 'latest_score': latest.overall_score if latest else None,
                      'latest_analysis_id': latest.id if latest else None})
    return Response({'results': items, 'page': page.number, 'pages': page.paginator.num_pages,
                     'count': page.paginator.count})


@api_view(['GET', 'DELETE'])
@permission_classes([IsAuthenticated])
def job_detail(request, job_id):
    job = JobDescription.objects.filter(id=job_id, user=request.user).first()
    if not job:
        return Response({'error': 'Job description not found.'}, status=404)
    if request.method == 'DELETE':
        job.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    return Response(job_payload(job, with_text=True))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def analysis_detail(request, analysis_id):
    a = ResumeJobAnalysis.objects.filter(id=analysis_id, user=request.user).select_related('job').first()
    if not a:
        return Response({'error': 'Analysis not found.'}, status=404)
    return Response({'job': job_payload(a.job), 'analysis': analysis_payload(a)})
