from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from ai_features.llm import LLMError
from learning.models import SkillMastery
from resume.models import Resume
from .models import JobDescription
from .services import matching
from .services.extraction import validate_extraction

RESUME_TEXT = """Asha Rao  asha@example.com
Skills: Python, React, SQL, Git
Experience: Software Intern, Acme Corp (2023 - 2024): built REST APIs in Django and a React dashboard.
Projects: Library system using Python and MySQL with indexing for fast search.
Education: B.Tech in Computer Science, 2025"""
PARSED = {'name': 'Asha Rao', 'skills': ['Python', 'React', 'SQL', 'Git'],
          'experience': ['Software Intern, Acme Corp (2023 - 2024): built REST APIs in Django and a React dashboard.'],
          'education': ['B.Tech in Computer Science, 2025']}
JD = ('We are hiring a Software Development Engineer. Required: Python, JavaScript, SQL, Data Structures, '
      'System Design. Nice to have: React, Docker. Bachelor degree in CS. 1+ years of experience. ' * 2)
EXTRACTED = {'role_summary': 'SDE', 'required_skills': ['Python', 'JavaScript', 'SQL', 'Data Structures', 'Algorithms',
                                                        'System Design', 'Python or Java'],
             'preferred_skills': ['React', 'Docker'], 'programming_languages': ['Python', 'JavaScript'],
             'frameworks_tools': ['React', 'Docker'], 'education': ["Bachelor's degree in Computer Science"],
             'min_years_experience': 1, 'experience_summary': '1+ years', 'responsibilities': ['Build services'],
             'soft_skills': ['Communication'], 'domain_knowledge': []}


def user(name):
    return User.objects.create_user(username=f'{name}@x.com', email=f'{name}@x.com', password='pw-12345!')


class ExtractionValidationTests(TestCase):
    def test_rejects_malformed(self):
        for bad in ([], 'text', None):
            with self.assertRaises(ValueError):
                validate_extraction(bad)
        self.assertEqual(validate_extraction({'required_skills': 'Python'})['required_skills'], [])

    def test_falls_back_to_tools_domain_and_soft_skills(self):
        out = validate_extraction({'required_skills': [], 'frameworks_tools': ['Excel'],
                                   'domain_knowledge': ['Financial Markets'], 'soft_skills': ['Communication']})
        self.assertEqual(out['required_skills'], ['Excel', 'Financial Markets'])
        self.assertEqual(out['preferred_skills'], ['Communication'])

    @patch('jobs.services.analyzer.extract_requirements')
    def test_document_without_requirements_gets_a_clear_error(self, extract):
        extract.return_value = validate_extraction({'role_summary': 'Company profile'})
        user = User.objects.create_user(username='np@x.com', email='np@x.com', password='pw12345678')
        Resume.objects.create(user=user, raw_text='Python developer', parsed_data={})
        job = JobDescription.objects.create(user=user, title='Analyst', text='About our company ' * 20)
        cache.clear()
        api = APIClient()
        api.force_authenticate(user)
        res = api.post('/api/jobs/analyze/', {'job_id': job.id}, format='json')
        self.assertEqual((res.status_code, res.data.get('code')), (400, 'no_requirements'))

    def test_cleans_and_dedupes(self):
        out = validate_extraction({'required_skills': ['Python', 'Python', ' SQL '], 'preferred_skills': ['python', 'Go'],
                                   'min_years_experience': 'abc', 'education': 'not a list'})
        self.assertEqual(out['required_skills'], ['Python', 'SQL'])
        self.assertEqual(out['preferred_skills'], ['Go'])  # already required
        self.assertIsNone(out['min_years_experience'])
        self.assertEqual(out['education'], [])


class MatchingAlgorithmTests(TestCase):
    def test_experience_and_degree_parsing(self):
        self.assertEqual(matching.resume_years(PARSED, RESUME_TEXT)[0], 1.0)
        self.assertEqual(matching.resume_years({'experience': []}, '')[0], 0.0)
        self.assertIsNone(matching.resume_years({'experience': ['Intern at X']}, '')[0])
        self.assertEqual(matching.degree_level('B.Tech in CSE')[0], 2)
        self.assertIsNone(matching.degree_level('You must be proficient in MS Office')[0])

    def test_alternatives_split(self):
        self.assertEqual(matching.split_alternatives('Python or Java'), ['Python', 'Java'])
        self.assertEqual(matching.split_alternatives('Java/C++'), ['Java', 'C++'])
        self.assertEqual(matching.split_alternatives('TCP/IP'), ['TCP/IP'])

    def test_weights_renormalise_when_a_component_is_missing(self):
        matches = [{'importance': 'required', 'status': 'matched', 'credit': 1.0},
                   {'importance': 'required', 'status': 'missing', 'credit': 0.0}]
        result = matching.score(matches, {'min_years_experience': None, 'education': []}, {}, '')
        # Only "required" has data: 50% coverage -> 50 overall (weight renormalised to 1.0).
        self.assertEqual(result['overall'], 50.0)
        req = next(c for c in result['components'] if c['key'] == 'required')
        self.assertEqual(req['normalized_weight'], 1.0)


@patch('jobs.services.analyzer.personalised_suggestions', return_value=['Add metrics to your intern project.'])
@patch('jobs.services.analyzer.extract_requirements', return_value=EXTRACTED)
class AnalyzerApiTests(TestCase):
    def setUp(self):
        cache.clear()  # rate-limit counters live in the cache
        self.alice = user('alice')
        self.client = APIClient()
        self.client.force_authenticate(self.alice)

    def create_job(self):
        r = self.client.post('/api/jobs/create/', {'title': 'SDE', 'company': 'Acme', 'text': JD}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        return r.json()['id']

    def test_requires_resume(self, *_):
        job_id = self.create_job()
        r = self.client.post('/api/jobs/analyze/', {'job_id': job_id}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'no_resume')

    def test_full_analysis_is_transparent_and_evidence_based(self, *_):
        Resume.objects.create(user=self.alice, raw_text=RESUME_TEXT, parsed_data=PARSED, filename='cv.pdf')
        job_id = self.create_job()
        r = self.client.post('/api/jobs/analyze/', {'job_id': job_id}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        a = r.json()['analysis']
        status = {m['skill']: m['status'] for m in a['skill_matches']}
        self.assertEqual(status['Python'], 'matched')
        self.assertEqual(status['SQL'], 'matched')
        self.assertEqual(status['JavaScript'], 'partial')  # React on the resume builds on JavaScript
        self.assertEqual(status['System Design'], 'missing')
        self.assertEqual(status['Docker'], 'missing')
        self.assertNotIn('Algorithms', status)
        # "Python or Java": having Python satisfies it.
        alt = next(m for m in a['skill_matches'] if m['requirement'] == 'Python or Java')
        self.assertEqual(alt['status'], 'matched')  # merged with Data Structures into one DSA requirement
        py = next(m for m in a['skill_matches'] if m['skill'] == 'Python')
        self.assertIn('Python', py['evidence']['snippet'])
        # Score recomputed by hand: required = (1+1+0.5+0+0)/5 ... DSA has no evidence -> missing.
        comps = {c['key']: c for c in a['breakdown']['components']}
        self.assertAlmostEqual(comps['required']['score'], 100 * 3.5 / 6, places=1)
        self.assertAlmostEqual(comps['preferred']['score'], 50.0)
        self.assertEqual(comps['experience_qualification']['score'], 100.0)
        expected = 0.7 * (100 * 3.5 / 6) + 0.2 * 50 + 0.1 * 100
        self.assertAlmostEqual(a['overall_score'], expected, places=1)
        self.assertTrue(any(rec['source'] == 'ai' for rec in a['recommendations']))
        # A matched skill on the resume is not turned into fake mastery.
        self.assertFalse(SkillMastery.objects.filter(user=self.alice).exists())

    def test_ownership_and_history(self, *_):
        Resume.objects.create(user=self.alice, raw_text=RESUME_TEXT, parsed_data=PARSED, filename='cv.pdf')
        job_id = self.create_job()
        a_id = self.client.post('/api/jobs/analyze/', {'job_id': job_id}, format='json').json()['analysis']['id']
        bob = APIClient()
        bob.force_authenticate(user('bob'))
        self.assertEqual(bob.get(f'/api/jobs/{job_id}/').status_code, 404)
        self.assertEqual(bob.get(f'/api/jobs/analysis/{a_id}/').status_code, 404)
        self.assertEqual(bob.post('/api/jobs/analyze/', {'job_id': job_id}, format='json').status_code, 404)
        self.assertEqual(bob.delete(f'/api/jobs/{job_id}/').status_code, 404)
        self.assertEqual(bob.get('/api/jobs/history/').json()['count'], 0)
        self.assertEqual(self.client.get('/api/jobs/history/').json()['results'][0]['latest_analysis_id'], a_id)
        self.assertEqual(APIClient().get('/api/jobs/history/').status_code, 401)

    def test_input_validation(self, *_):
        self.assertEqual(self.client.post('/api/jobs/create/', {'title': 'x', 'text': 'too short'}, format='json').status_code, 400)
        fake = SimpleUploadedFile('jd.pdf', b'not really a pdf' * 20, content_type='application/pdf')
        r = self.client.post('/api/jobs/create/', {'title': 'x', 'file': fake}, format='multipart')
        self.assertEqual(r.status_code, 400)
        self.assertIn('not a valid PDF', r.json()['error'])


class LLMFailureTests(TestCase):
    @patch('jobs.services.analyzer.extract_requirements', side_effect=LLMError('The AI service is busy.'))
    def test_llm_failure_is_a_clean_503(self, _):
        alice = user('alice')
        Resume.objects.create(user=alice, raw_text=RESUME_TEXT, parsed_data=PARSED, filename='cv.pdf')
        c = APIClient()
        c.force_authenticate(alice)
        job_id = c.post('/api/jobs/create/', {'title': 'SDE', 'text': JD}, format='json').json()['id']
        r = c.post('/api/jobs/analyze/', {'job_id': job_id}, format='json')
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.json()['error'], 'The AI service is busy.')
