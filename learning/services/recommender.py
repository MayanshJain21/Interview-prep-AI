"""
Deterministic recommendation engine.

For every skill that matters for the student's goal:
    importance  in [0, 1]   from the selected job description (required / preferred) and the target
                            role profile; prerequisites of relevant skills inherit part of it.
    gap         = 100 - mastery                (unassessed skills have no gap: they get a diagnostic)
    priority    = gap * importance * staleness (staleness boosts skills not practised for a while)

Skills whose prerequisites are below the threshold are not recommended directly; the blocking
prerequisite is recommended instead. The LLM is never asked what to study next.
"""
from django.conf import settings
from django.utils import timezone

from learning.models import Skill, SkillMastery, SkillPrerequisite
from learning.taxonomy_data import ROLE_ALIASES, ROLE_PROFILES
from .mastery import band_for, confidence, status_for
from .taxonomy import all_prerequisites, prerequisite_map

PREREQ_INHERIT = 0.8  # share of importance passed down to a prerequisite
UMBRELLA_INHERIT = 0.8  # share passed from an umbrella skill (e.g. DSA) to its children


def role_profile(target_role):
    role = (target_role or '').strip().lower()
    if not role:
        return {}, None
    role = ROLE_ALIASES.get(role, role)
    if role in ROLE_PROFILES:
        return ROLE_PROFILES[role], role
    for name in sorted(ROLE_PROFILES, key=len, reverse=True):
        if name in role or role in name:
            return ROLE_PROFILES[name], name
    for alias, name in ROLE_ALIASES.items():
        if alias in role:
            return ROLE_PROFILES[name], name
    return {}, None


def importance_map(skills_by_slug, target_role='', analysis=None):
    """Returns ({skill_id: importance}, {skill_id: [reasons]})."""
    cfg = settings.LEARNING_ENGINE
    imp, why = {}, {}

    def bump(skill, value, reason):
        if skill is None or value <= 0:
            return
        if value > imp.get(skill.id, 0):
            imp[skill.id] = round(min(1.0, value), 2)
        why.setdefault(skill.id, [])
        if reason not in why[skill.id]:
            why[skill.id].append(reason)

    if analysis:
        for m in analysis.skill_matches:
            skill = skills_by_slug.get(m.get('skill_slug'))
            weight = cfg['REQUIRED_IMPORTANCE'] if m.get('importance') == 'required' else cfg['PREFERRED_IMPORTANCE']
            bump(skill, weight, f"{m.get('importance', 'listed')} in the job description ({m.get('status')})")

    profile, profile_name = role_profile(target_role)
    for slug, value in profile.items():
        bump(skills_by_slug.get(slug), value, f'important for a {profile_name} role')

    if not imp:  # no goal at all: a general software engineering profile
        for slug, value in ROLE_PROFILES['software engineer'].items():
            bump(skills_by_slug.get(slug), value, 'core skill for software roles (no goal set yet)')

    # Umbrella skills (DSA) spread their importance to the concrete topics.
    for skill in list(skills_by_slug.values()):
        if skill.parent_id and skill.parent_id in imp:
            parent = next(s for s in skills_by_slug.values() if s.id == skill.parent_id)
            bump(skill, imp[parent.id] * UMBRELLA_INHERIT, f'part of {parent.name}')
    return imp, why


def skill_states(user, target_role='', analysis=None, now=None):
    """Everything the recommender and scheduler need, one dict per relevant skill."""
    cfg = settings.LEARNING_ENGINE
    now = now or timezone.now()
    skills = {s.id: s for s in Skill.objects.all()}
    by_slug = {s.slug: s for s in skills.values()}
    graph = prerequisite_map(SkillPrerequisite.objects.values_list('skill_id', 'prerequisite_id'))
    mastery = {m.skill_id: m for m in SkillMastery.objects.filter(user=user)}

    imp, why = importance_map(by_slug, target_role, analysis)
    # Pull in prerequisites of relevant skills so gating can recommend them.
    for sid in list(imp):
        for pre in all_prerequisites(sid, graph):
            if pre not in imp:
                imp[pre] = round(imp[sid] * PREREQ_INHERIT, 2)
                why.setdefault(pre, []).append(f'prerequisite for {skills[sid].name}')
    # Umbrella skills with children are planned through their children.
    umbrellas = {s.parent_id for s in skills.values() if s.parent_id}

    states = {}
    for sid, importance in imp.items():
        if sid in umbrellas:
            continue
        skill, m = skills[sid], mastery.get(sid)
        value = round(m.mastery, 1) if m else None
        days = (now - m.last_assessed).days if m else None
        stale = 1.0
        if days is not None and days > cfg['STALE_DAYS']:
            stale += min(cfg['STALE_BOOST_MAX'], (days - cfg['STALE_DAYS']) / 60)
        gap = None if value is None else round(100 - value, 1)
        base_gap = cfg['DIAGNOSTIC_PRIORITY_GAP'] if gap is None else gap
        states[sid] = {
            'skill': skill, 'skill_id': sid, 'slug': skill.slug, 'name': skill.name, 'category': skill.category,
            'importance': importance, 'mastery': value, 'gap': gap, 'status': status_for(value),
            'attempts': m.attempts if m else 0, 'sources': m.sources if m else {},
            'last_assessed': m.last_assessed if m else None, 'days_since': days,
            'confidence': confidence(m.attempts, m.last_assessed, now) if m else 0.0,
            'priority': round(base_gap * importance * stale, 1), 'stale_factor': round(stale, 2),
            'band': band_for(value), 'reasons': why.get(sid, []),
            'prerequisites': sorted(graph.get(sid, set())),
        }

    threshold = cfg['PREREQ_THRESHOLD']
    for st in states.values():
        st['blocked_by'] = [p for p in st['prerequisites']
                            if (mastery.get(p).mastery if p in mastery else None) is None
                            or mastery[p].mastery < threshold]
    return states, graph


def next_activity(state):
    """Pick the activity and difficulty for one skill (deterministic)."""
    cfg = settings.LEARNING_ENGINE
    skill, mastery, band = state['skill'], state['mastery'], state['band']
    via = set(skill.assessable_via)
    name = skill.name

    if mastery is None:
        if 'mcq' in via:
            return activity('diagnostic', skill, 'Easy', f'Diagnostic quiz: {name}',
                            f'{name} has not been assessed yet, so a short quiz measures your starting level.')
        if 'coding' in via:
            return activity('coding', skill, 'easy', f'Diagnostic coding problem: {name}',
                            f'{name} has not been assessed yet; one easy problem measures your starting level.')
        return activity('interview', skill, 'Easy', f'Diagnostic interview: {name}',
                        f'{name} has not been assessed yet; a short technical interview measures your level.')
    if mastery < 40:
        return activity('learn', skill, '', f'Learn the fundamentals of {name}',
                        f'Your {name} mastery is {mastery:.0f}%, below 40%: start with the basics before practice.')
    if mastery >= cfg['MASTERED']:
        return activity('revision', skill, band['mcq'], f'Revise {name}',
                        f'{name} is mastered ({mastery:.0f}%); a quick revision keeps it fresh.')
    # Practice: rotate to the module that has assessed this skill least.
    sources = state['sources']
    options = [s for s in ('coding', 'mcq', 'technical') if s in via]
    pick = min(options, key=lambda s: sources.get(s, 0)) if options else 'mcq'
    reason = f"{name} is at {mastery:.0f}% ({band['label'].lower()} level)"
    if pick == 'coding':
        return activity('coding', skill, band['coding'], f"{name}: {band['coding']} coding problems",
                        reason + '; solve problems at this level to move up.')
    if pick == 'technical':
        return activity('interview', skill, band['interview'], f'{name}: technical interview practice',
                        reason + '; explaining it out loud tests real understanding.')
    return activity('mcq', skill, band['mcq'], f"{name}: {band['mcq'].lower()} MCQ practice",
                    reason + '; a practice test at this level checks your progress.')


def activity(kind, skill, difficulty, title, reason):
    minutes = settings.LEARNING_ENGINE['ACTIVITY_MINUTES']
    duration = minutes['coding'][difficulty or 'easy'] if kind == 'coding' else minutes[kind]
    return {'activity_type': kind, 'difficulty': difficulty, 'title': title, 'reason': reason,
            'duration_min': duration, 'link': activity_link(kind, skill, difficulty)}


def activity_link(kind, skill, difficulty):
    if kind in ('diagnostic', 'mcq', 'revision') and 'mcq' in skill.assessable_via:
        return {'path': '/mcq', 'params': {'skill': skill.name, 'difficulty': difficulty or 'Easy'}}
    if kind == 'coding' or (kind == 'revision' and skill.coding_topic):
        return {'path': '/coding-round', 'params': {'difficulty': difficulty or 'easy', 'topic': skill.coding_topic}}
    if kind in ('interview', 'revision') and skill.interview_type:
        return {'path': '/technical-interview', 'params': {'type': skill.interview_type, 'difficulty': difficulty or 'Easy'}}
    return {'path': '/learning-path', 'params': {'skill': skill.slug}}


def recommendations(states, limit=5):
    """Ordered recommendations. Blocked skills are replaced by their weakest prerequisite."""
    ranked = sorted(states.values(), key=lambda s: -s['priority'])
    out, seen = [], set()
    for st in ranked:
        if st['status'] == 'mastered' and (st['days_since'] or 0) <= settings.LEARNING_ENGINE['STALE_DAYS']:
            continue
        target, why_extra = st, ''
        hops = 0
        while target['blocked_by'] and hops < 6:  # walk down to a prerequisite that is ready
            blockers = [states[b] for b in target['blocked_by'] if b in states]
            if not blockers:
                break
            nxt = min(blockers, key=lambda b: (b['mastery'] is not None, b['mastery'] or 0))
            why_extra = f" (needed before {st['name']})"
            target, hops = nxt, hops + 1
        if target['skill_id'] in seen:
            continue
        seen.add(target['skill_id'])
        act = next_activity(target)
        act['reason'] += why_extra
        out.append({**act, 'skill': target['name'], 'skill_slug': target['slug'], 'priority': st['priority'],
                    'mastery': target['mastery'], 'importance': target['importance'], 'status': target['status'],
                    'why_relevant': target['reasons'][:2]})
        if len(out) >= limit:
            break
    return out
