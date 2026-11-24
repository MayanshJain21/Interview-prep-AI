"""
Resume <-> job description matching. Deterministic: the LLM only extracted the requirements.

Per requirement:
    matched  (credit 1.0)  the skill (or one of its aliases) appears in the resume; we keep the snippet
    partial  (credit 0.5)  no direct mention, but a closely related skill does (parent/child in the
                           taxonomy, a prerequisite, or a skill built on it, e.g. React for JavaScript)
    missing  (credit 0.0)

Components (each 0-1):
    required    = sum(credit of required skills) / number of required skills
    preferred   = same for preferred skills
    exp_qual    = mean of the verifiable parts: experience (resume years / required years, capped at 1)
                  and qualification (resume degree level >= required level)

overall = 100 * sum(w_i * c_i) / sum(w_i) over the components that have data, so a job with no
preferred skills is scored on required + exp_qual only (weights renormalised, shown in the report).
This is resume-job alignment, not a probability of being hired.
"""
import re
from datetime import date

from django.conf import settings

STATUS_CREDIT = {'matched': 1.0, 'missing': 0.0}

DEGREE_LEVELS = [  # (level, label, patterns)
    (4, 'Doctorate', [r'\bph\.?\s?d\b', r'\bdoctorate\b']),
    # Abbreviations need their dots ("B.E.", "M.S.") so words like "be" or "MS Office" don't match.
    (3, "Master's", [r'\bm\.?\s?tech\b', r'\bm\.\s?e\.', r'\bm\.?\s?sc\b', r'\bmaster', r'\bmca\b', r'\bm\.\s?s\.', r'\bmba\b']),
    (2, "Bachelor's", [r'\bb\.?\s?tech\b', r'\bb\.\s?e\.', r'\bb\.?\s?sc\b', r'\bbachelor', r'\bbca\b', r'\bundergraduate\b',
                        r'\bb\.\s?s\.', r'\bgraduate\b', r'\bdegree\b']),
    (1, 'Diploma', [r'\bdiploma\b']),
]
# "2022 - 2024", "Jun 2022 – Present" and "May 2025 – Jul 2025" (a month may precede the second year).
YEAR_RANGE = re.compile(r'((?:19|20)\d{2})\s*(?:-|–|—|to)\s*(?:[A-Za-z]{3,9}\.?,?\s+)?'
                        r'((?:19|20)\d{2}|present|current|now|till date|ongoing)', re.I)
YEARS_STATED = re.compile(r'(\d+(?:\.\d+)?)\s*\+?\s*years?\s+(?:of\s+)?(?:professional\s+|work\s+|industry\s+)?experience', re.I)


def split_alternatives(name):
    """'Python or Java' / 'Java/C++' -> ['Python', 'Java']; anything else -> [name].
    'TCP/IP' and 'CI/CD' stay whole (no spaces and both sides very short)."""
    parts = [p.strip() for p in re.split(r'\s+or\s+|\s*/\s*(?=[A-Za-z])', name) if p.strip()]
    if len(parts) > 1 and all(len(p) <= 3 for p in parts) and ' or ' not in name.lower():
        return [name]
    return parts if len(parts) > 1 else [name]


def _text(value):
    if isinstance(value, list):
        return '\n'.join(_text(v) for v in value)
    if isinstance(value, dict):
        return ' '.join(_text(v) for v in value.values())
    return str(value or '')


def resume_sections(parsed, raw_text):
    """Searchable text per resume section."""
    parsed = parsed if isinstance(parsed, dict) else {}
    return {
        'skills': [str(s) for s in parsed.get('skills', []) if s] if isinstance(parsed.get('skills'), list) else [],
        'experience': _text(parsed.get('experience')),
        'education': _text(parsed.get('education')),
        'full_text': raw_text or '',
    }


def _find(term, text):
    """Case-insensitive whole-term search; returns a short snippet or None."""
    term = term.strip().lower()
    if not term or not text:
        return None
    pattern = r'(?<![a-z0-9+#])' + re.escape(term) + r'(?![a-z0-9+#])'
    m = re.search(pattern, text.lower())
    if not m:
        return None
    start, end = max(0, m.start() - 60), min(len(text), m.end() + 60)
    snippet = re.sub(r'\s+', ' ', text[start:end]).strip()
    return ('...' if start else '') + snippet + ('...' if end < len(text) else '')


def find_evidence(names, sections):
    """Look for any of `names` in the resume. Very short names (C, R, JS, OS) only count when they
    are listed as a skill, because they are ambiguous in free text."""
    for name in names:
        key = name.strip().lower()
        for s in sections['skills']:
            if s.strip().lower() == key:
                return {'section': 'skills', 'snippet': s}
    for name in names:
        if len(name.strip()) < 3:
            continue
        for s in sections['skills']:
            if _find(name, s):
                return {'section': 'skills', 'snippet': s}
        for section in ('experience', 'education', 'full_text'):
            snippet = _find(name, sections[section])
            if snippet:
                return {'section': 'projects / other' if section == 'full_text' else section, 'snippet': snippet}
    return None


def skill_names(skill):
    return [skill.name, skill.slug.replace('-', ' '), *skill.aliases]


def match_requirement(req, sections, related_skills):
    """req: {"name", "importance", "kind", "skill": Skill|None}. related_skills: Skills related to req["skill"]."""
    skill = req.get('skill')
    names = [req['name']] + (skill_names(skill) if skill else [])
    evidence = find_evidence(names, sections)
    result = {'requirement': req['name'], 'skill': skill.name if skill else req['name'],
              'skill_slug': skill.slug if skill else None, 'category': skill.category if skill else req.get('kind', 'technical'),
              'importance': req['importance'], 'evidence': evidence, 'related_evidence': None}
    if evidence:
        return {**result, 'status': 'matched', 'credit': 1.0}
    for other in related_skills:
        ev = find_evidence(skill_names(other), sections)
        if ev:
            return {**result, 'status': 'partial', 'credit': settings.JOB_MATCH['PARTIAL_CREDIT'],
                    'related_evidence': {**ev, 'via': other.name}}
    return {**result, 'status': 'missing', 'credit': 0.0}


def degree_level(text):
    text = (text or '').lower()
    for level, label, patterns in DEGREE_LEVELS:
        if any(re.search(p, text) for p in patterns):
            return level, label
    return None, None


def resume_years(parsed, raw_text, today=None):
    """Years of experience shown on the resume, or None if it can't be verified.
    No experience entries at all = 0 years (verifiably none)."""
    today = today or date.today()
    exp_text = _text((parsed or {}).get('experience'))
    stated = [float(m.group(1)) for m in YEARS_STATED.finditer(raw_text or '')]
    spans = []
    for a, b in YEAR_RANGE.findall(exp_text):
        start = int(a)
        end = today.year if not b[:1].isdigit() else int(b)
        if start <= end <= today.year + 1:
            spans.append((start, end))
    if spans:
        spans.sort()
        merged = [list(spans[0])]
        for s, e in spans[1:]:
            if s <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], e)
            else:
                merged.append([s, e])
        return float(sum(e - s for s, e in merged)), 'from dated experience entries'
    if stated:
        return max(stated), 'stated on the resume'
    if not exp_text.strip():
        return 0.0, 'no work experience listed'
    return None, 'experience entries have no dates'


def score(requirements_matched, extracted, parsed, raw_text):
    """Combine the per-requirement results and experience/qualification into the final score."""
    weights = settings.JOB_MATCH['WEIGHTS']
    required = [m for m in requirements_matched if m['importance'] == 'required']
    preferred = [m for m in requirements_matched if m['importance'] == 'preferred']

    def coverage(items):
        return sum(m['credit'] for m in items) / len(items) if items else None

    # Experience and qualification, only where both sides are verifiable.
    sub, notes = [], []
    need_years = extracted.get('min_years_experience')
    if need_years is not None:
        have, how = resume_years(parsed, raw_text)
        if need_years == 0:
            sub.append(1.0)
            notes.append('No minimum experience required.')
        elif have is not None:
            sub.append(min(1.0, have / need_years))
            notes.append(f'Experience: {have:g} year(s) on the resume ({how}) vs {need_years:g} required.')
        else:
            notes.append(f'Experience: {need_years:g} year(s) required, but the resume {how}, so it was not scored.')
    need_level, need_label = degree_level(' '.join(extracted.get('education', [])))
    if need_level:
        have_level, have_label = degree_level(_text((parsed or {}).get('education')) or raw_text)
        ok = bool(have_level and have_level >= need_level)
        sub.append(1.0 if ok else 0.0)
        notes.append(f"Qualification: {need_label} required; resume shows {have_label or 'no recognised degree'}.")
    exp_qual = sum(sub) / len(sub) if sub else None

    components = [
        {'key': 'required', 'label': 'Required skills', 'weight': weights['required'], 'value': coverage(required),
         'detail': f'{sum(m["status"] == "matched" for m in required)} matched, '
                   f'{sum(m["status"] == "partial" for m in required)} partial, '
                   f'{sum(m["status"] == "missing" for m in required)} missing of {len(required)}'},
        {'key': 'preferred', 'label': 'Preferred skills', 'weight': weights['preferred'], 'value': coverage(preferred),
         'detail': f'{sum(m["status"] == "matched" for m in preferred)} matched, '
                   f'{sum(m["status"] == "partial" for m in preferred)} partial of {len(preferred)}'},
        {'key': 'experience_qualification', 'label': 'Experience & qualification',
         'weight': weights['experience_qualification'], 'value': exp_qual, 'detail': ' '.join(notes) or 'Not stated in the job description.'},
    ]
    available = [c for c in components if c['value'] is not None]
    total_weight = sum(c['weight'] for c in available) or 1
    overall = 0.0
    for c in components:
        c['available'] = c['value'] is not None
        c['normalized_weight'] = round(c['weight'] / total_weight, 3) if c['available'] else 0
        c['score'] = round(100 * c['value'], 1) if c['available'] else None
        c['contribution'] = round(100 * c['value'] * c['weight'] / total_weight, 1) if c['available'] else 0
        overall += c['contribution']
        c.pop('value')

    technical = coverage(required + preferred)
    return {
        'overall': round(overall, 1),
        'technical': round(100 * technical, 1) if technical is not None else 0.0,
        'components': components,
        'formula': 'overall = 100 x sum(weight x coverage) / sum(weights of components with data); '
                   f'partial matches count {settings.JOB_MATCH["PARTIAL_CREDIT"]:g}.',
        'note': 'This measures how well the resume matches the job description. It is not a probability of being hired.',
    }


def deterministic_recommendations(matches):
    recs = []
    for m in sorted(matches, key=lambda m: (m['importance'] != 'required', m['status'] != 'missing')):
        if m['status'] == 'missing':
            recs.append(f"{m['skill']} is {m['importance']} but not on your resume. If you have used it, add a project "
                        f"or experience bullet showing how; if not, it is a priority to learn.")
        elif m['status'] == 'partial':
            via = m['related_evidence']['via'] if m.get('related_evidence') else 'a related skill'
            recs.append(f"Your resume shows {via} but not {m['skill']} itself. Name {m['skill']} explicitly where you used it.")
    return recs[:10]


def preparation_areas(matches):
    areas = [m for m in matches if m['status'] != 'matched']
    areas.sort(key=lambda m: (m['importance'] != 'required', m['status'] != 'missing', m['skill']))
    return [{'skill': m['skill'], 'skill_slug': m['skill_slug'], 'importance': m['importance'], 'status': m['status']}
            for m in areas]


def relevant_sections(matches):
    counts = {}
    for m in matches:
        ev = m.get('evidence') or m.get('related_evidence')
        if ev:
            counts[ev['section']] = counts.get(ev['section'], 0) + 1
    return [{'section': s, 'matches': n} for s, n in sorted(counts.items(), key=lambda x: -x[1])]
