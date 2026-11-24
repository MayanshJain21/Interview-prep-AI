"""
Assessment evidence -> mastery. This is the entry point the other modules call.

Every call is idempotent: (user, source, source_ref, skill) is unique, so re-processing the same
MCQ attempt, coding problem or interview turn never changes mastery twice.
"""
import logging
from collections import defaultdict

from django.db import IntegrityError, transaction
from django.utils import timezone

from learning.models import LearningAttempt, Skill, SkillMastery
from learning.taxonomy_data import CODING_TOPIC_TO_SKILL
from .mastery import get_estimator
from .taxonomy import build_index, match_skill

log = logging.getLogger(__name__)


def record_evidence(user, skill, source, source_ref, score, difficulty='', correct=None, hints_used=0):
    """Store one attempt and update mastery. Returns (attempt, created)."""
    score = max(0.0, min(100.0, float(score)))
    try:
        with transaction.atomic():
            attempt, created = LearningAttempt.objects.get_or_create(
                user=user, skill=skill, source=source, source_ref=str(source_ref)[:100],
                defaults={'score': score, 'difficulty': str(difficulty or '')[:10], 'correct': correct,
                          'hints_used': hints_used},
            )
            if not created:
                return attempt, False

            row = SkillMastery.objects.select_for_update().filter(user=user, skill=skill).first()
            old = row.mastery if row else None
            new = get_estimator().update(old, score)
            now = timezone.now()
            if row:
                row.mastery = new
                row.attempts += 1
                row.last_assessed = now
                row.sources = {**row.sources, source: row.sources.get(source, 0) + 1}
                row.save()
            else:
                SkillMastery.objects.create(user=user, skill=skill, mastery=new, attempts=1, last_assessed=now,
                                            sources={source: 1}, algorithm=get_estimator().name)
            attempt.mastery_before, attempt.mastery_after = old, new
            attempt.save(update_fields=['mastery_before', 'mastery_after'])

            from .roadmap import on_mastery_updated
            on_mastery_updated(user, skill, new, source)
            return attempt, True
    except IntegrityError:
        # Two requests raced on the same evidence; the other one won.
        return LearningAttempt.objects.get(user=user, skill=skill, source=source, source_ref=source_ref), False


def record_mcq_results(user, attempt_ref, results, difficulty):
    """results: [{"skill": "Python", "correct": true}, ...] for one MCQ test.
    Each skill gets its own score from only its own questions."""
    index = build_index(Skill.objects.all())
    per_skill = defaultdict(lambda: [0, 0])
    unmatched = set()
    for r in results:
        skill = match_skill(r.get('skill', ''), index)
        if not skill:
            unmatched.add(str(r.get('skill', ''))[:60])
            continue
        per_skill[skill][1] += 1
        per_skill[skill][0] += 1 if r.get('correct') else 0
    recorded = []
    for skill, (right, total) in per_skill.items():
        _, created = record_evidence(user, skill, 'mcq', f'mcq:{attempt_ref}', 100 * right / total,
                                     difficulty=difficulty, correct=right == total)
        recorded.append({'skill': skill.name, 'score': round(100 * right / total), 'new': created})
    return {'recorded': recorded, 'not_in_taxonomy': sorted(unmatched)}


def record_coding_problem(user, problem, total_score, passed, total, hints_used, difficulty):
    slug = CODING_TOPIC_TO_SKILL.get(problem.topic.lower())
    skill = Skill.objects.filter(slug=slug).first() if slug else None
    if not skill:
        return None
    attempt, _ = record_evidence(user, skill, 'coding', f'coding-problem:{problem.id}', total_score,
                                 difficulty=difficulty, correct=(total > 0 and passed == total), hints_used=hints_used)
    return attempt


def record_technical_turn(user, turn):
    if not turn.skill_id or turn.score is None:
        return None
    attempt, _ = record_evidence(user, turn.skill, 'technical', f'technical-turn:{turn.id}', turn.score * 10,
                                 difficulty=turn.difficulty, correct=turn.score >= 7)
    return attempt
