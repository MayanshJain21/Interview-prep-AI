"""LLM extraction of job requirements, with strict validation of the reply."""
from ai_features.llm import STRONG_MODEL, call_llm_json, clean_list, clean_str, untrusted

SYSTEM = """You extract structured requirements from a job description for a placement-preparation app.
Return JSON with exactly these keys:
{
  "role_summary": "one sentence",
  "required_skills": ["technical skills, languages, frameworks or tools the posting says are required / must-have"],
  "preferred_skills": ["technical skills listed as preferred, nice to have, plus, bonus"],
  "programming_languages": ["programming languages mentioned"],
  "frameworks_tools": ["frameworks, libraries, databases, platforms, tools mentioned"],
  "education": ["degree / qualification requirements, as written"],
  "min_years_experience": number or null,
  "experience_summary": "short text, or empty",
  "responsibilities": ["short phrases"],
  "soft_skills": ["communication, teamwork, ..."],
  "domain_knowledge": ["e.g. payments, healthcare, e-commerce"]
}
Rules:
- One skill per list item, short names ("Python", "REST APIs", "System Design"), no sentences.
- If the posting gives alternatives ("Python or Java", "Java/C++"), keep them as ONE item written "Python or Java".
- If the posting does not separate required and preferred, put core technical skills in required_skills.
- For non-software roles (analyst, trading, finance, operations), the core skills the role needs, such as
  "Data Analysis", "Excel", "Statistics", "Financial Markets" or "Risk Management", go in required_skills.
- If the document is a company or role brochure without a skills list, use the skills it says the role
  needs or will use (from the role description, eligibility and responsibilities). Never add ones it doesn't mention.
- Do not invent requirements that the posting does not state. Use [] or null when absent.
- For fresher / entry-level / 0 years, min_years_experience is 0."""


def validate_extraction(data):
    if not isinstance(data, dict):
        raise ValueError('not an object')
    out = {
        'role_summary': clean_str(data.get('role_summary'), 300),
        'required_skills': clean_list(data.get('required_skills'), 40, 80),
        'preferred_skills': clean_list(data.get('preferred_skills'), 40, 80),
        'programming_languages': clean_list(data.get('programming_languages'), 20, 60),
        'frameworks_tools': clean_list(data.get('frameworks_tools'), 40, 80),
        'education': clean_list(data.get('education'), 10, 200),
        'experience_summary': clean_str(data.get('experience_summary'), 300),
        'responsibilities': clean_list(data.get('responsibilities'), 15, 200),
        'soft_skills': clean_list(data.get('soft_skills'), 15, 60),
        'domain_knowledge': clean_list(data.get('domain_knowledge'), 10, 80),
    }
    years = data.get('min_years_experience')
    try:
        out['min_years_experience'] = None if years in (None, '') else max(0.0, min(30.0, float(years)))
    except (TypeError, ValueError):
        out['min_years_experience'] = None
    # A skill listed as required must not also count as preferred.
    required_keys = {s.lower() for s in out['required_skills']}
    out['preferred_skills'] = [s for s in out['preferred_skills'] if s.lower() not in required_keys]
    if not out['required_skills'] and not out['preferred_skills']:
        # Some postings only name tools, domain knowledge or soft skills; use those rather than reject the reply.
        out['required_skills'] = clean_list(out['programming_languages'] + out['frameworks_tools']
                                            + out['domain_knowledge'], 40, 80)
        out['preferred_skills'] = [s for s in out['soft_skills']
                                   if s.lower() not in {r.lower() for r in out['required_skills']}]
    # A document with no requirements at all is a valid answer, not a model failure: the analyzer reports it.
    return out


def extract_requirements(job):
    user = (f'Job title: {job.title}\nCompany: {job.company or "not given"}\n'
            f'Target role: {job.target_role or job.title}\n\n' + untrusted('job_description', job.text, 20000))
    return call_llm_json(SYSTEM, user, model=STRONG_MODEL, temperature=0.1, max_tokens=3000,
                         validate=validate_extraction)
