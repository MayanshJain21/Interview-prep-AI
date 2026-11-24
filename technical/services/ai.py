"""
LLM parts of the technical interview, kept as two separate calls:
- the interviewer writes the next question (it never sees scores, only the topic plan and the
  answers, plus the evaluator's list of missing concepts for probing follow-ups);
- the evaluator scores an answer against a fixed rubric. The final 0-10 score is a weighted sum
  computed here, not a number the model picks.
"""
import re

from ai_features.llm import (DEFAULT_MODEL, STRONG_MODEL, call_llm_json, clamp_int, clean_list, clean_str,
                             untrusted)
from .plan import INTERVIEW_TYPES, LEVEL_NAMES

RUBRIC = {  # criterion: weight (sums to 1)
    'technical_correctness': 0.30,
    'conceptual_understanding': 0.20,
    'completeness': 0.15,
    'logical_reasoning': 0.15,
    'practical_application': 0.10,
    'clarity': 0.10,
}

KIND_GUIDE = {
    'core': 'Ask a fresh question on this topic.',
    'deeper': 'The candidate answered the previous question well. Ask a harder follow-up on the same topic that '
              'tests depth (internals, trade-offs, edge cases).',
    'probe': 'The previous answer was partly right. Ask a follow-up that targets the missing concepts listed.',
    'foundational': 'The previous answer was weak. Ask a simpler follow-up on the same topic that checks the '
                    'foundations, e.g. asking them to explain it with a simple real-world example.',
}

INTERVIEWER_SYSTEM = """You are a senior software engineer conducting a technical interview for a placement candidate.
Write the NEXT interview question only.
Rules:
- One question, 1 to 3 sentences, spoken style. No numbered lists, no answer, no hints.
- Stay on the given topic and difficulty. Never repeat or rephrase a question already asked.
- For project questions, use ONLY projects, technologies and details present in the resume excerpts.
  If the resume has no project details, ask a general question about a project they built instead of inventing one.
- Do not mention scores or evaluations.
Return JSON: {"question": "..."}"""

EVALUATOR_SYSTEM = """You are a strict, fair technical interviewer grading one answer.
Score each criterion from 0 to 10:
- technical_correctness: are the statements technically correct?
- conceptual_understanding: does the candidate understand why, not just what?
- completeness: are the key points for this question covered?
- logical_reasoning: is the reasoning coherent and step by step?
- practical_application: can they apply it (examples, real use, trade-offs)?
- clarity: is it explained clearly and concisely?
Rules:
- Length is not quality: a long answer with errors or filler scores low. A short, correct, complete answer can score high.
- An empty, off-topic or "I don't know" answer scores 0-2 on every criterion.
- If the question allows several valid approaches or interpretations, accept any correct one.
- Only list "incorrect_statements" that are actually wrong; do not invent facts. If unsure, do not list it.
- The example answer must be technically accurate and about 4-6 sentences.
Return JSON:
{"scores": {"technical_correctness": n, "conceptual_understanding": n, "completeness": n, "logical_reasoning": n,
  "practical_application": n, "clarity": n},
 "correct_points": ["..."], "missing_concepts": ["..."], "incorrect_statements": ["..."],
 "suggestions": ["..."], "example_answer": "..."}"""


def _norm(q):
    return re.sub(r'[^a-z0-9 ]', '', q.lower())


def generate_question(session, step, previous_turns, job_summary=''):
    asked = [t.question for t in previous_turns]
    last = previous_turns[-1] if previous_turns else None
    parts = [
        f"Target role: {session.job_role or 'Software Engineer'}" + (f" at {session.company}" if session.company else ''),
        f"Interview type: {INTERVIEW_TYPES[session.interview_type]['label']}",
        f"Topic: {step['topic']}",
        f"Difficulty: {LEVEL_NAMES[step['level']]}",
        f"Question kind: {KIND_GUIDE[step['kind']]}",
        'Questions already asked:\n' + ('\n'.join(f'- {q}' for q in asked) or '- none'),
    ]
    if job_summary:
        parts.append(f'Job requirements (summary): {job_summary}')
    if last and step['kind'] != 'core':
        parts.append(f'Previous question: {last.question}')
        parts.append(untrusted('answer', last.answer, 3000))
        missing = last.evaluation.get('missing_concepts', [])
        if missing:
            parts.append('Missing concepts noted by the evaluator: ' + '; '.join(missing[:5]))
    if session.resume_context and (session.interview_type in ('project', 'mixed') or 'Project' in step['topic']):
        parts.append(untrusted('resume', session.resume_context, 5000))

    asked_norm = {_norm(q) for q in asked}

    def validate(data):
        q = clean_str(data.get('question'), 700)
        if len(q) < 15:
            raise ValueError('question too short')
        if _norm(q) in asked_norm:
            raise ValueError('repeated question')
        return q

    return call_llm_json(INTERVIEWER_SYSTEM, '\n\n'.join(parts), model=DEFAULT_MODEL, temperature=0.7,
                         max_tokens=1500, validate=validate)


def validate_evaluation(data):
    scores = data.get('scores')
    if not isinstance(scores, dict):
        raise ValueError('missing scores')
    clean = {k: clamp_int(scores.get(k), 0, 10) for k in RUBRIC}
    weighted = round(sum(clean[k] * w for k, w in RUBRIC.items()), 1)
    return {
        'scores': clean,
        'score': weighted,
        'correct_points': clean_list(data.get('correct_points'), 8, 300),
        'missing_concepts': clean_list(data.get('missing_concepts'), 8, 300),
        'incorrect_statements': clean_list(data.get('incorrect_statements'), 8, 300),
        'suggestions': clean_list(data.get('suggestions'), 6, 300),
        'example_answer': clean_str(data.get('example_answer'), 2000),
    }


def evaluate_answer(session, turn, answer):
    user = '\n\n'.join([
        f"Role: {session.job_role or 'Software Engineer'}. Topic: {turn.topic}. Difficulty: {turn.difficulty}.",
        f'Question: {turn.question}',
        untrusted('answer', answer, 6000),
    ])
    return call_llm_json(EVALUATOR_SYSTEM, user, model=STRONG_MODEL, temperature=0.1, max_tokens=2500,
                         validate=validate_evaluation)
