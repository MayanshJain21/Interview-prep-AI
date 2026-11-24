import json
import re
import time
from concurrent.futures import ThreadPoolExecutor

from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from resume.models import Resume
from .models import MCQHistory, ATSHistory
from .rag import retrieve_context
from .llm import (LLMError, LLMRateThrottle, STRONG_MODEL, call_llm_json, clamp_int, clean_list, clean_str,
                  groq_client, untrusted)

LLM_MODEL = "openai/gpt-oss-20b"


def ask_llm(prompt, temperature=0.3):
    completion = groq_client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model=LLM_MODEL,
        temperature=temperature,
        response_format={"type": "json_object"},
    )
    return json.loads(completion.choices[0].message.content)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_mcqs(request):
    skills = request.data.get('skills', [])
    difficulty = request.data.get('difficulty', 'Medium')

    if not skills:
        return Response({'error': 'Skills are required to generate MCQs'}, status=400)

    context = retrieve_context(request.user.id, f"projects and work experience using {', '.join(skills)}", k=4)
    questions_per_skill = 10

    # One request per skill. Asking for all skills in a single reply (40+ questions) makes the
    # model fail Groq's JSON validation every time, so each skill gets its own short request.
    def for_skill(skill):
        prompt = f"""
    Generate exactly {questions_per_skill} multiple-choice interview questions on the skill: {skill}.
    Difficulty level: {difficulty}.
    Use the following applicant context if relevant to personalize some questions:
    {context}

    Output exactly a JSON object with a single key "questions" containing a list of {questions_per_skill} objects. Each object should have:
    - "question": string
    - "options": list of 4 strings
    - "correct_answer": string (must exactly match one of the options)
    """
        last_error = None
        for attempt in range(3):  # retries cover a failed JSON check or a free-tier rate limit
            if attempt:
                time.sleep(3 * attempt)
            try:
                items = ask_llm(prompt, temperature=0.3).get('questions') or []
                good = [q for q in items if isinstance(q, dict) and isinstance(q.get('options'), list)
                        and q.get('correct_answer') in q['options']]
                for q in good:
                    q['skill'] = skill
                if good:
                    return good
            except Exception as e:
                last_error = e
        raise last_error or ValueError(f'No valid questions for {skill}')

    questions, failed = [], []
    with ThreadPoolExecutor(max_workers=min(4, len(skills))) as pool:
        futures = {skill: pool.submit(for_skill, skill) for skill in skills}
        for skill, fut in futures.items():
            try:
                questions.extend(fut.result())
            except Exception:
                failed.append(skill)

    if not questions:
        return Response({"error": "Could not generate questions right now. Please try again."}, status=502)
    return Response({"questions": questions, "failed_skills": failed})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def filter_skills(request):
    """
    Receives a list of candidate skills and a target job role.
    Uses LLM to filter and return only the skills relevant to the given job role.
    """
    job_role = request.data.get('job_role', '')
    skills = request.data.get('skills', [])

    if not job_role or not skills:
        return Response({'error': 'Both job role and skills are required to filter.'}, status=400)

    prompt = f"""
    You are an expert AI recruiting assistant.
    The candidate has the following skills extracted from their resume:
    {', '.join(skills)}
    
    Please filter this list and return ONLY the skills that are highly relevant to the job role: "{job_role}".
    Provide the output in a structured format.
    
    Output exactly a JSON object with a single key "filtered_skills" containing a list of strings representing the relevant skills.
    """

    try:
        result = ask_llm(prompt, temperature=0.1)
        return Response(result)
    except Exception as e:
        return Response({"error": str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_mcqs(request):
    score = request.data.get('score', 0)
    total = request.data.get('total', 10)
    skills = request.data.get('skills', [])
    difficulty = str(request.data.get('difficulty', ''))[:10]
    attempt_id = str(request.data.get('attempt_id', ''))[:64]
    results = request.data.get('results', [])

    # A resubmitted attempt (retry after a network error) must not be saved or counted twice.
    if attempt_id:
        existing = MCQHistory.objects.filter(user=request.user, attempt_id=attempt_id).first()
        if existing:
            return Response({'message': 'Score already saved', 'id': existing.id})

    history = MCQHistory.objects.create(
        user=request.user,
        score=score,
        total=total,
        skills=skills,
        attempt_id=attempt_id,
    )

    # Per-skill evidence for the learning engine: each skill is scored on its own questions only.
    evidence = None
    if isinstance(results, list) and results:
        from learning.services.evidence import record_mcq_results
        clean = [{'skill': str(r.get('skill', ''))[:100], 'correct': bool(r.get('correct'))}
                 for r in results[:200] if isinstance(r, dict)]
        evidence = record_mcq_results(request.user, history.id, clean, difficulty)

    return Response({'message': 'Score saved successfully', 'id': history.id, 'skill_evidence': evidence})


ATS_SYSTEM = """You are a career coach and recruitment expert with over 10 years of experience reviewing CVs
for {role} roles. Review the resume line by line for a {role} role.

How to judge:
- The candidate's experience level is: {level}. Judge them against what is expected of a {role} at that
  level (for example a student is compared with internship candidates, not seniors). If the resume clearly
  contradicts that level, say so in the verdict.
- No bias: judge only what is written. Ignore name, gender, age, location and the prestige of the college.
- Be honest and a little strict: point out weak lines clearly and say why, but stay polite and
  constructive. No harsh or mocking language. Do not reward length.
- Quote the resume exactly when you comment on a line. Never invent content.

Rate from 0 to 10 (5 is an average student resume, 8 is strong, 10 is exceptional and rare):
ATS criteria
- impact: measurable achievements with real numbers in experience and projects
- keywords: keywords and technologies an ATS would search for in {role} postings
- experience: depth, relevance and completeness of experience and internships
- structure: clear sections, action-verb bullets, no placeholder text, sensible length, contact details
  with LinkedIn or GitHub
- education_projects: relevance of education, certifications and projects
Fit for {role}
- skills_match: how well the listed skills cover what {role} roles need
- projects_relevance: how relevant and impressive the projects are for {role}
- experience_relevance: how relevant the experience and internships are for {role}
- level_fit: how ready the candidate is for {role} at their career stage

Then give:
- review: up to 12 lines or sections from the resume that matter most, each with the exact quote, a verdict
  ("keep", "fix" or "cut") and a one-sentence reason; for "fix", say how to fix it
- problems: concrete problems (placeholder text, bullets without numbers, vague claims, spelling errors, gaps)
- tips: the 3 to 5 most important changes for a {role} application, most impactful first
- verdict: two honest sentences on how this resume would fare for a {role} role today

Return JSON: {{"criteria": {{"impact": 0-10, "keywords": 0-10, "experience": 0-10, "structure": 0-10,
"education_projects": 0-10}}, "role_fit": {{"skills_match": 0-10, "projects_relevance": 0-10,
"experience_relevance": 0-10, "level_fit": 0-10}}, "review": [{{"quote": "...", "verdict": "keep | fix | cut",
"comment": "..."}}], "problems": ["..."], "tips": ["..."], "verdict": "..."}}"""

# Both scores are computed here from the ratings, so they stay consistent between runs and models.
ATS_WEIGHTS = {'impact': 0.30, 'keywords': 0.20, 'experience': 0.20, 'structure': 0.15, 'education_projects': 0.15}
ROLE_FIT_WEIGHTS = {'skills_match': 0.35, 'projects_relevance': 0.30, 'experience_relevance': 0.20, 'level_fit': 0.15}
ATS_MAX = 95  # a resume can always be improved
ATS_ROLE_DEFAULT = 'Software Engineer'
# Fixed list, so only known text reaches the prompt. Keys match LEVELS in AtsCheck.jsx.
ATS_LEVELS = {
    'student': 'student or intern, still studying',
    'fresher': 'fresher with 0-1 years of experience',
    'junior': 'junior developer with 1-3 years of experience',
    'mid': 'mid-level developer with 3-5 years of experience',
    'senior': 'senior developer with 5-8 years of experience',
    'lead': 'lead or staff engineer with 8+ years of experience',
}


def _weighted(scores, weights):
    return round(sum(weights[k] * v for k, v in scores.items()) * 10)


def _validate_ats(data):
    criteria = data.get('criteria') if isinstance(data.get('criteria'), dict) else {}
    fit = data.get('role_fit') if isinstance(data.get('role_fit'), dict) else {}
    scores = {k: clamp_int(criteria.get(k), 0, 10) for k in ATS_WEIGHTS}
    fit_scores = {k: clamp_int(fit.get(k), 0, 10) for k in ROLE_FIT_WEIGHTS}
    tips = [re.sub(r'^\s*\d+[.)]\s*', '', t) for t in clean_list(data.get('tips'), 5, 400)]
    if any(v is None for v in scores.values()) or any(v is None for v in fit_scores.values()) or len(tips) < 3:
        raise ValueError('missing criteria, role fit or tips')
    # Each concrete problem found costs a little, so a resume with issues can't reach the top band.
    problems = clean_list(data.get('problems'), 10, 300)
    score = max(0, min(ATS_MAX, _weighted(scores, ATS_WEIGHTS) - 2 * len(problems)))
    review = []
    for item in (data.get('review') if isinstance(data.get('review'), list) else [])[:12]:
        if not isinstance(item, dict):
            continue
        verdict = str(item.get('verdict', '')).strip().lower()
        quote, comment = clean_str(item.get('quote'), 300), clean_str(item.get('comment'), 400)
        if quote and comment and verdict in ('keep', 'fix', 'cut'):
            review.append({'quote': quote, 'verdict': verdict, 'comment': comment})
    return {'score': score, 'criteria': scores,
            'role_fit': {'score': min(ATS_MAX, _weighted(fit_scores, ROLE_FIT_WEIGHTS)), 'components': fit_scores},
            'review': review, 'problems': problems, 'tips': tips, 'verdict': clean_str(data.get('verdict'), 600)}


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([LLMRateThrottle])
def check_ats(request):
    # One line only, so typed text can't add instructions to the prompt.
    role = re.sub(r'\s+', ' ', clean_str(request.data.get('role'), 80)).strip() or ATS_ROLE_DEFAULT
    level = str(request.data.get('level') or 'student')
    if level not in ATS_LEVELS:
        return Response({'error': 'Choose an experience level from the list.'}, status=400)
    resume = Resume.objects.filter(user=request.user).first()
    text = ''
    if resume:
        # The full resume text is what an ATS reads; search chunks are only a fallback for old uploads.
        text = (resume.raw_text or '').strip() or retrieve_context(
            request.user.id, "skills experience achievements education certifications projects", k=6)
    if not (text or '').strip():
        return Response({'error': 'Upload your resume first: the ATS check scores it.', 'code': 'no_resume'}, status=400)

    # The role is user text, so it goes into the prompt only after cleaning and length-limiting.
    try:
        result = call_llm_json(ATS_SYSTEM.format(role=role, level=ATS_LEVELS[level]), untrusted('resume', text, 15000), model=STRONG_MODEL,
                               temperature=0.1, max_tokens=5000, validate=_validate_ats)
    except LLMError as e:
        return Response({'error': str(e)}, status=503)

    ATSHistory.objects.create(user=request.user, score=result['score'], tips=result['tips'],
                              role=role, role_fit=result['role_fit']['score'])
    return Response({**result, 'role': role, 'level': level})


COLD_EMAIL_SYSTEM = """You write short cold emails from a student or early-career candidate to a recruiter or
hiring manager, asking to be considered for a role. Use only facts from the resume: never invent skills,
numbers, projects or experience. Plain, polite and specific; no buzzwords, no flattery, no emojis.
Body: a greeting, 3 short paragraphs (who the candidate is and the role they want; 2 or 3 concrete
achievements from the resume that fit the role; a clear ask, such as a short call or being considered,
and a note that the resume is attached), then a sign-off with the candidate's name and any contact
details from the resume. Under 180 words. Plain text, no markdown.
Return JSON: {"subject": "under 10 words", "body": "the email"}"""


def _validate_email(data):
    subject = clean_str(data.get('subject'), 120)
    body = clean_str(data.get('body'), 3000)
    if not subject or len(body) < 80:
        raise ValueError('missing subject or body')
    return {'subject': subject, 'body': body}


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([LLMRateThrottle])
def cold_email(request):
    """Write a cold email for a role from the user's resume. Nothing is sent; the user copies it."""
    role = clean_str(request.data.get('role'), 100)
    company = clean_str(request.data.get('company'), 100)
    recipient = clean_str(request.data.get('recipient_name'), 100)
    if not role:
        return Response({'error': 'Enter the role you are applying for.'}, status=400)
    resume = Resume.objects.filter(user=request.user).first()
    if not resume or not (resume.raw_text or '').strip():
        return Response({'error': 'Upload your resume first: the email is written from it.', 'code': 'no_resume'},
                        status=400)

    user = (f"Role: {role}\nCompany: {company or 'not given (keep it general)'}\n"
            f"Recipient name: {recipient or 'not given (use Hello)'}\n\n" + untrusted('resume', resume.raw_text, 12000))
    try:
        return Response(call_llm_json(COLD_EMAIL_SYSTEM, user, temperature=0.5, max_tokens=1500,
                                      validate=_validate_email))
    except LLMError as e:
        return Response({'error': str(e)}, status=503)


# The HR mock interview lives in hr_interview.py.
