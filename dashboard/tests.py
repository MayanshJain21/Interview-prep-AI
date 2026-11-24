"""Cross-module integration tests and Part 1 regression checks (LLM calls mocked)."""
from datetime import timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from jobs.tests import EXTRACTED, JD, PARSED, RESUME_TEXT
from learning.models import SkillMastery
from resume.models import Resume


class Part1RegressionTests(TestCase):
    def test_auth_dashboard_and_legacy_mcq_submit(self):
        c = APIClient()
        r = c.post('/api/auth/signup/', {'email': 'p1@x.com', 'password': 'pw-12345!', 'name': 'P'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        token = c.post('/api/auth/login/', {'email': 'p1@x.com', 'password': 'pw-12345!'}, format='json').json()['tokens']['access']
        c.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertEqual(c.get('/api/auth/me/').status_code, 200)
        # Old clients that only send the total still work.
        self.assertEqual(c.post('/api/mcq/submit/', {'score': 5, 'total': 10, 'skills': ['Python']}, format='json').status_code, 200)
        stats = c.get('/api/dashboard/history/').json()['stats']
        self.assertEqual(stats['total_sessions'], 1)
        self.assertIn('average_technical_score', stats)


@patch('jobs.services.analyzer.personalised_suggestions', return_value=[])
@patch('jobs.services.analyzer.extract_requirements', return_value=EXTRACTED)
class JourneyTests(TestCase):
    def setUp(self):
        cache.clear()  # rate-limit counters live in the cache
        from django.contrib.auth.models import User
        self.user = User.objects.create_user(username='s@x.com', email='s@x.com', password='pw-12345!')
        Resume.objects.create(user=self.user, raw_text=RESUME_TEXT, parsed_data=PARSED, filename='cv.pdf')
        self.c = APIClient()
        self.c.force_authenticate(self.user)

    def test_jd_to_roadmap_to_mastery(self, *_):
        # 1-3. Job description -> analysis.
        job_id = self.c.post('/api/jobs/create/', {'title': 'SDE', 'text': JD}, format='json').json()['id']
        analysis = self.c.post('/api/jobs/analyze/', {'job_id': job_id}, format='json').json()['analysis']

        # 4. Roadmap from the analysis: missing required skills are planned.
        r = self.c.post('/api/engine/roadmap/generate/', {
            'job_analysis_id': analysis['id'], 'deadline': str(timezone.localdate() + timedelta(days=28)),
            'minutes_per_day': 120, 'study_days': list(range(7))}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        planned = {i['skill_slug'] for i in r.json()['items']}
        self.assertIn('sql', planned)
        self.assertTrue({'system-design', 'dbms', 'computer-networks', 'oop'} & planned)  # system design or its prerequisites

        # 5-6. An MCQ through the real endpoint updates mastery for that skill only.
        results = [{'skill': 'SQL', 'correct': i < 9} for i in range(10)]
        body = {'score': 9, 'total': 10, 'skills': ['SQL'], 'difficulty': 'Easy', 'results': results, 'attempt_id': 'abc'}
        self.c.post('/api/mcq/submit/', body, format='json')
        self.c.post('/api/mcq/submit/', body, format='json')  # retry: idempotent
        m = SkillMastery.objects.get(user=self.user, skill__slug='sql')
        self.assertEqual((m.mastery, m.attempts), (90, 1))
        self.assertFalse(SkillMastery.objects.filter(user=self.user, skill__slug='python').exists())

        # 10. Dashboard analytics reflect it.
        a = self.c.get('/api/engine/analytics/').json()
        sql_row = next(row for row in a['mastery'] if row['slug'] == 'sql')
        self.assertEqual(sql_row['mastery'], 90)
        self.assertGreater(a['roadmap_progress']['completed'], 0)  # the MCQ completed the SQL diagnostic
        self.assertTrue(any(j['skill'] == 'SQL' and j['mastery'] == 90 for j in a['job_progress']))
        profile = self.c.get('/api/engine/profile/').json()
        self.assertEqual(profile['job_analysis']['id'], analysis['id'])
        self.assertIn('communication', profile)
