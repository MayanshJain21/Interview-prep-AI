"""Orchestrates one analysis: extraction (cached on the job), matching, report."""
import logging

from django.db import transaction

from ai_features.llm import LLMError, call_llm_json, clean_list, untrusted
from learning.models import Skill, SkillPrerequisite
from learning.services.taxonomy import build_index, match_skill
from resume.models import Resume
from jobs.models import JobRequirement, ResumeJobAnalysis
from . import matching
from .extraction import extract_requirements

log = logging.getLogger(__name__)


class NoResume(Exception):
    pass


class NoRequirements(Exception):
    """The document names no skills to compare against (e.g. a company profile)."""


def ensure_requirements(job):
    """Extract requirements once per job and store them as rows linked to canonical skills."""
    if job.extracted:
        return job.extracted
    extracted = extract_requirements(job)  # may raise LLMError
    index = build_index(Skill.objects.all())
    languages = {s.lower() for s in extracted['programming_languages']}
    tools = {s.lower() for s in extracted['frameworks_tools']}
    rows, seen = [], set()
    for importance in ('required', 'preferred'):
        for name in extracted[f'{importance}_skills']:
            parts = matching.split_alternatives(name)
            skill = match_skill(parts[0], index)
            # Dedupe on the canonical skill, except for "X or Y" rows, which are their own requirement.
            key = skill.slug if skill and len(parts) == 1 else name.lower()
            if key in seen:  # "Data Structures" and "Algorithms" both map to DSA: keep one row
                continue
            seen.add(key)
            kind = 'language' if name.lower() in languages else 'tool' if name.lower() in tools else 'technical'
            rows.append(JobRequirement(job=job, name=name[:120], skill=skill, kind=kind, importance=importance))
    with transaction.atomic():
        job.requirements.all().delete()
        JobRequirement.objects.bulk_create(rows)
        job.extracted = extracted
        job.save(update_fields=['extracted'])
    return extracted


def related_skills_map():
    skills = {s.id: s for s in Skill.objects.all()}
    related = {sid: [] for sid in skills}
    for s in skills.values():
        if s.parent_id:
            related[s.id].append(skills[s.parent_id])
            related[s.parent_id].append(s)
    for skill_id, pre_id in SkillPrerequisite.objects.values_list('skill_id', 'prerequisite_id'):
        related[pre_id].append(skills[skill_id])  # a skill built on it (React for JavaScript)
        related[skill_id].append(skills[pre_id])  # its prerequisite (DBMS for SQL)
    return related


def _validate_suggestions(data):
    tips = clean_list(data.get('suggestions'), 6, 300)
    if not tips:
        raise ValueError('no suggestions')
    return {'suggestions': tips}


def personalised_suggestions(job, resume, matches):
    """Optional LLM wording on top of the deterministic report; failures fall back silently."""
    gaps = [f"{m['skill']} ({m['importance']}, {m['status']})" for m in matches if m['status'] != 'matched'][:12]
    if not gaps:
        return []
    system = ('You are a placement mentor. Given resume excerpts, a job title and the gaps found by an algorithm, '
              'write up to 5 short, specific resume or preparation suggestions. Only refer to things in the resume; '
              'never claim the student has a skill. Return JSON {"suggestions": ["..."]}.')
    user = (f'Job: {job.title} at {job.company or "a company"}\nGaps: {", ".join(gaps)}\n\n'
            + untrusted('resume', resume.raw_text, 6000))
    try:
        return call_llm_json(system, user, temperature=0.3, max_tokens=1200, retries=1,
                             validate=_validate_suggestions)['suggestions']
    except LLMError as e:
        log.info('suggestions skipped: %s', e)
        return []


def analyze(user, job):
    resume = Resume.objects.filter(user=user).first()
    if not resume or not (resume.raw_text or '').strip():
        raise NoResume()
    ensure_requirements(job)
    if not job.requirements.exists():
        raise NoRequirements()

    sections = matching.resume_sections(resume.parsed_data, resume.raw_text)
    related = related_skills_map()
    matches = []
    index = build_index(Skill.objects.all())
    for req in job.requirements.select_related('skill'):
        # "Python or Java": any one alternative satisfies the requirement.
        options = []
        for part in matching.split_alternatives(req.name):
            skill = match_skill(part, index) if part != req.name else req.skill
            options.append({'name': part, 'importance': req.importance, 'kind': req.kind, 'skill': skill})
        results = [matching.match_requirement(o, sections, related.get(o['skill'].id, []) if o['skill'] else [])
                   for o in options]
        best = max(results, key=lambda r: r['credit'])
        if len(options) > 1:
            best = {**best, 'requirement': req.name, 'alternatives': [o['name'] for o in options]}
        matches.append(best)
    scored = matching.score(matches, job.extracted, resume.parsed_data, resume.raw_text)

    recs = matching.deterministic_recommendations(matches)
    extra = personalised_suggestions(job, resume, matches)
    return ResumeJobAnalysis.objects.create(
        user=user, job=job, resume_filename=resume.filename, overall_score=scored['overall'],
        technical_score=scored['technical'], breakdown=scored, skill_matches=matches,
        recommendations=[{'text': t, 'source': 'rule'} for t in recs] + [{'text': t, 'source': 'ai'} for t in extra],
        preparation_areas=matching.preparation_areas(matches),
        relevant_sections=matching.relevant_sections(matches),
    )
