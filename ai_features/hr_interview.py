"""
Adaptive HR mock interview.

An interview is a session of 6 questions. Each question has a stage (introduction, resume
deep-dive, follow-up, ...) that decides what it should cover, and every question after the
first is generated from the transcript so far, so it can react to what the candidate said.

Each answer is scored against a fixed rubric when it is submitted, in the same LLM call that
writes the next question. Scores are kept from the candidate until the final report.
"""
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import HRSession, HRHistory
from .rag import retrieve_context
from .views import ask_llm


STAGES = [
    {
        "key": "introduction",
        "label": "Introduction",
        "goal": "Open the interview. Ask the candidate to walk you through their background, "
                "anchored to something concrete from their resume (their degree, latest role or a "
                "standout project) so it is not a generic 'tell me about yourself'.",
    },
    {
        "key": "resume_deep_dive",
        "label": "Resume deep-dive",
        "goal": "Pick ONE specific project, internship or job from the resume that has not been "
                "discussed yet and ask about the candidate's personal contribution, a decision they "
                "made, or a challenge they hit in it.",
    },
    {
        "key": "follow_up",
        "label": "Follow-up",
        "goal": "Dig deeper into the candidate's previous answer. Target the weakest or vaguest part: "
                "a claim without evidence, a 'we' where their own role is unclear, a missing result, "
                "or a decision they did not justify. Quote or paraphrase what they said.",
    },
    {
        "key": "behavioral",
        "label": "Behavioral",
        "goal": "Ask a behavioral question that invites a STAR-style story (conflict with a teammate, "
                "a failure or mistake, a tight deadline, handling criticism, leading without authority). "
                "Choose a theme that has NOT been covered in the interview so far.",
    },
    {
        "key": "situational",
        "label": "Situational / role fit",
        "goal": "Ask a realistic hypothetical scenario they could face in the target role "
                "(competing priorities, disagreeing with a manager, an unclear requirement, a "
                "production issue) and how they would handle it.",
    },
    {
        "key": "closing",
        "label": "Closing",
        "goal": "Close the interview. Ask about their motivation for this kind of role and where they "
                "want to grow in the next few years, connecting it to something they said earlier.",
    },
]

QUESTION_RULES = """
Rules for the question you write:
- Ask exactly ONE question. No numbered lists and no bundles of several questions.
- Keep it conversational, 1 to 3 sentences, like a real HR interviewer speaking out loud.
- You may open with a brief, neutral acknowledgement of their last answer (e.g. "Thanks for that."),
  but never praise, judge or hint at how well they did.
- Make it specific: reference real details from the resume or the candidate's own words.
  Never invent facts that are not in the resume or transcript.
- Do not repeat or rephrase a question or topic that was already covered.
- No yes/no questions.
- If a target role is given, make the question relevant to it.
"""

SCORING_RUBRIC = """
Score the answer from 0 to 10 using this rubric:
- Relevance: does it actually answer the question that was asked?
- Structure: for stories, does it cover Situation, Task, Action and Result (STAR)?
- Specificity: concrete examples, the candidate's OWN actions ("I" rather than "we"), numbers or evidence.
- Outcome and reflection: a clear result and what they learned.
- Communication: clear, focused and appropriately concise.

Calibration:
- 9-10: exceptional, specific, well structured, clear impact. Rare.
- 7-8: strong, with minor gaps.
- 5-6: adequate but generic or missing a key element (e.g. no result).
- 3-4: vague, mostly claims without examples, or only partly answers the question.
- 0-2: off-topic, empty, or nonsense.
An answer of one or two short sentences cannot score above 3.
"""


def _clamp_score(value):
    try:
        return max(0, min(10, int(round(float(value)))))
    except (TypeError, ValueError):
        return 0


def _as_str_list(value):
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _stage_for(question_number):
    return STAGES[min(question_number, len(STAGES)) - 1]


def _role_line(session):
    return f"Target role: {session.job_role}" if session.job_role else "Target role: not specified (general entry-level / early-career role)"


def _resume_block(session):
    return session.resume_context.strip() or "No resume uploaded. Ask strong general questions instead of resume-specific ones."


def _transcript(turns):
    lines = []
    for turn in turns:
        lines.append(f"Q{turn.question_number} [{turn.stage}]: {turn.question}")
        lines.append(f"A{turn.question_number}: {turn.answer or '(no answer yet)'}")
    return "\n".join(lines) or "(the interview has not started yet)"


def _turn_payload(session, turn):
    return {
        "session_id": session.id,
        "question_number": turn.question_number,
        "total_questions": session.total_questions,
        "stage": _stage_for(turn.question_number)["label"],
        "question": turn.question,
    }


def _session_report_payload(session):
    turns = session.turns.order_by('question_number')
    return {
        "session_id": session.id,
        "status": session.status,
        "job_role": session.job_role,
        "overall_score": session.overall_score,
        "report": session.report,
        "turns": [
            {
                "question_number": t.question_number,
                "stage": _stage_for(t.question_number)["label"],
                "question": t.question,
                "answer": t.answer,
                "score": t.score,
                "feedback": t.feedback,
                "strengths": t.strengths,
                "improvements": t.improvements,
            }
            for t in turns
        ],
        "created_at": session.created_at,
        "completed_at": session.completed_at,
    }


def generate_first_question(session):
    stage = _stage_for(1)
    prompt = f"""
    You are an experienced, friendly but rigorous HR interviewer running a {session.total_questions}-question mock interview.
    {_role_line(session)}

    Candidate's resume (excerpts):
    {_resume_block(session)}

    Write question 1 of {session.total_questions}. Stage: {stage['label']}.
    Goal of this question: {stage['goal']}
    {QUESTION_RULES}
    Return exactly JSON: {{"question": "the question"}}
    """
    result = ask_llm(prompt, temperature=0.7)
    question = str(result.get("question", "")).strip()
    if not question:
        raise ValueError("The AI did not return a question.")
    return question


def evaluate_and_continue(session, turns, current_turn, answer):
    """Score the current answer and, unless it was the last question, write the next one."""
    is_last = current_turn.question_number >= session.total_questions
    stage = _stage_for(current_turn.question_number)

    if is_last:
        next_block = 'This was the final question. Set "next_question" to an empty string.'
    else:
        next_number = current_turn.question_number + 1
        next_stage = _stage_for(next_number)
        next_block = f"""
    Then write question {next_number} of {session.total_questions}. Stage: {next_stage['label']}.
    Goal of this question: {next_stage['goal']}
    If the answer you just scored was weak or vague (score 4 or below), this next question should
    briefly probe that gap while still serving the goal above.
    {QUESTION_RULES}"""

    prompt = f"""
    You are an experienced, friendly but rigorous HR interviewer running a {session.total_questions}-question mock interview.
    {_role_line(session)}

    Candidate's resume (excerpts):
    {_resume_block(session)}

    Interview so far:
    {_transcript(turns)}

    The candidate just answered question {current_turn.question_number} [{stage['label']}]:
    Question: {current_turn.question}
    Answer: {answer}

    First, evaluate this answer.
    {SCORING_RUBRIC}
    Feedback must be addressed to the candidate ("you"), 2-4 sentences, and name what to change.
    {next_block}

    Return exactly JSON:
    {{
      "evaluation": {{
        "score": integer 0-10,
        "feedback": "string",
        "strengths": ["short point", ...],
        "improvements": ["short, actionable point", ...]
      }},
      "next_question": "string"
    }}
    """
    result = ask_llm(prompt, temperature=0.4)
    evaluation = result.get("evaluation") or {}
    next_question = "" if is_last else str(result.get("next_question", "")).strip()
    if not is_last and not next_question:
        raise ValueError("The AI did not return the next question.")
    return {
        "score": _clamp_score(evaluation.get("score")),
        "feedback": str(evaluation.get("feedback", "")).strip(),
        "strengths": _as_str_list(evaluation.get("strengths")),
        "improvements": _as_str_list(evaluation.get("improvements")),
    }, next_question


def generate_final_report(session, turns):
    scores = [t.score for t in turns]
    overall = round(sum(scores) / len(scores) * 10) if scores else 0
    scored_transcript = "\n".join(
        f"Q{t.question_number} [{t.stage}] (score {t.score}/10): {t.question}\nA: {t.answer}"
        for t in turns
    )
    prompt = f"""
    You ran a mock HR interview. {_role_line(session)}
    Here is the full transcript with the score you gave each answer:
    {scored_transcript}

    The overall score is {overall}/100.
    Write the final report for the candidate. Be honest and specific, refer to their actual answers,
    and make every improvement something they can practise.

    Return exactly JSON:
    {{
      "summary": "3-4 sentence overall assessment addressed to the candidate",
      "strengths": ["3 specific strengths"],
      "improvements": ["3 specific, actionable improvements"],
      "verdict": "one of: Interview ready, Almost there, Needs practice"
    }}
    """
    try:
        result = ask_llm(prompt, temperature=0.3)
    except Exception:
        # Scores are already saved per answer, so a failed summary should not lose the interview.
        result = {}
    verdict = result.get("verdict")
    if verdict not in ("Interview ready", "Almost there", "Needs practice"):
        verdict = "Interview ready" if overall >= 75 else "Almost there" if overall >= 55 else "Needs practice"
    report = {
        "summary": str(result.get("summary", "")).strip(),
        "strengths": _as_str_list(result.get("strengths")),
        "improvements": _as_str_list(result.get("improvements")),
        "verdict": verdict,
    }
    return overall, report


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_session(request):
    job_role = str(request.data.get('job_role', '')).strip()[:255]

    try:
        resume_context = retrieve_context(
            request.user.id,
            "work experience internship projects achievements challenges responsibilities education",
            k=5,
        )
    except Exception:
        resume_context = ''

    session = HRSession(user=request.user, job_role=job_role, resume_context=resume_context)
    try:
        question = generate_first_question(session)
    except Exception as e:
        return Response({"error": f"Could not start the interview: {e}"}, status=500)

    with transaction.atomic():
        session.save()
        turn = HRHistory.objects.create(
            user=request.user,
            session=session,
            question_number=1,
            stage=_stage_for(1)["key"],
            question=question,
        )
    return Response(_turn_payload(session, turn))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def answer_session(request):
    session_id = request.data.get('session_id')
    answer = str(request.data.get('answer', '')).strip()
    if not session_id or not answer:
        return Response({'error': 'session_id and answer are required'}, status=400)

    session = get_object_or_404(HRSession, id=session_id, user=request.user)
    if session.status != HRSession.STATUS_IN_PROGRESS:
        return Response({'error': 'This interview is already finished.'}, status=400)

    turns = list(session.turns.order_by('question_number'))
    current_turn = next((t for t in turns if not t.answer), None)
    if current_turn is None:
        return Response({'error': 'No open question in this interview.'}, status=400)
    previous_turns = [t for t in turns if t.answer]

    # Call the LLM before saving anything, so a failure leaves the session unchanged and the
    # candidate can simply submit the same answer again.
    try:
        evaluation, next_question = evaluate_and_continue(session, previous_turns, current_turn, answer)
    except Exception as e:
        return Response({"error": f"Could not evaluate your answer: {e}"}, status=500)

    with transaction.atomic():
        current_turn.answer = answer
        current_turn.score = evaluation["score"]
        current_turn.feedback = evaluation["feedback"]
        current_turn.strengths = evaluation["strengths"]
        current_turn.improvements = evaluation["improvements"]
        current_turn.save()

        if next_question:
            next_turn = HRHistory.objects.create(
                user=request.user,
                session=session,
                question_number=current_turn.question_number + 1,
                stage=_stage_for(current_turn.question_number + 1)["key"],
                question=next_question,
            )
            return Response({"done": False, **_turn_payload(session, next_turn)})

    answered = previous_turns + [current_turn]
    overall, report = generate_final_report(session, answered)
    session.overall_score = overall
    session.report = report
    session.status = HRSession.STATUS_COMPLETED
    session.completed_at = timezone.now()
    session.save()
    return Response({"done": True, **_session_report_payload(session)})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def session_detail(request, session_id):
    session = get_object_or_404(HRSession, id=session_id, user=request.user)
    return Response(_session_report_payload(session))
