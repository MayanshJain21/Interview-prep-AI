from itertools import count
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from ai_features.llm import LLMError
from learning.models import SkillMastery
from .models import TechnicalInterviewSession as Session, TechnicalInterviewTurn as Turn
from .services.ai import validate_evaluation
from .services.plan import next_step, plan_topics

_q = count(1)


def fake_question(session, step, previous, job_summary=''):
    return f"Q{next(_q)} about {step['topic']} ({step['kind']})"


def evaluation(score):
    return validate_evaluation({'scores': {k: score for k in ('technical_correctness', 'conceptual_understanding',
                                                              'completeness', 'logical_reasoning',
                                                              'practical_application', 'clarity')},
                                'missing_concepts': ['context switching'] if score < 7 else []})


def user(name):
    return User.objects.create_user(username=f'{name}@x.com', email=f'{name}@x.com', password='pw-12345!')


class PolicyTests(TestCase):
    def turns(self, *pairs):
        return [SimpleNamespace(topic=t, score=s) for t, s in pairs]

    def test_adapts_to_answer_quality(self):
        plan = [{'topic': 'A', 'skill': None}, {'topic': 'B', 'skill': None}, {'topic': 'C', 'skill': None}]
        self.assertEqual(next_step(plan, self.turns(('A', 9)), 6, 2)['kind'], 'deeper')
        self.assertEqual(next_step(plan, self.turns(('A', 9)), 6, 2)['level'], 3)
        self.assertEqual(next_step(plan, self.turns(('A', 5)), 6, 2)['kind'], 'probe')
        weak = next_step(plan, self.turns(('A', 2)), 6, 2)
        self.assertEqual((weak['kind'], weak['level']), ('foundational', 1))
        # One follow-up per topic, then move on.
        self.assertEqual(next_step(plan, self.turns(('A', 5), ('A', 5)), 6, 2)['topic'], 'B')
        # Not enough questions left to follow up and still cover the plan -> next topic.
        self.assertEqual(next_step(plan, self.turns(('A', 5)), 3, 2)['topic'], 'B')
        self.assertIsNone(next_step(plan, self.turns(('A', 5), ('B', 5), ('C', 5)), 3, 2))

    def test_plan_stays_on_topic_and_prefers_job_skills(self):
        plan = plan_topics('dbms', 6, job_skill_slugs={'sql'}, seed=1)
        self.assertEqual(plan[0]['skill'], 'sql')
        self.assertTrue(all(p['skill'] in ('dbms', 'sql') for p in plan))
        self.assertTrue(plan_topics('programming', 5, resume_skill_slugs={'java'})[0]['topic'].startswith('Java'))

    def test_rubric_is_weighted_by_backend(self):
        e = validate_evaluation({'scores': {'technical_correctness': 10, 'conceptual_understanding': 10, 'completeness': 0,
                                            'logical_reasoning': 0, 'practical_application': 0, 'clarity': 0}})
        self.assertEqual(e['score'], 5.0)  # 0.3*10 + 0.2*10
        with self.assertRaises(ValueError):
            validate_evaluation({'scores': 'great'})


@patch('technical.services.session.generate_question', side_effect=fake_question)
class SessionFlowTests(TestCase):
    def setUp(self):
        cache.clear()  # rate-limit counters live in the cache
        self.alice = user('alice')
        self.c = APIClient()
        self.c.force_authenticate(self.alice)

    def start(self, kind='os', n=4):
        r = self.c.post('/api/technical/session/start/', {'interview_type': kind, 'difficulty': 'Medium',
                                                          'num_questions': n, 'job_role': 'SDE'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        return r.json()

    def test_full_interview_report_and_feedback_loop(self, _):
        s = self.start('os', 4)
        self.assertIsNotNone(s['current_question'])
        with patch('technical.services.session.evaluate_answer', return_value=evaluation(2)):
            for _ in range(4):
                s = self.c.post('/api/technical/session/answer/', {'session_id': s['id'], 'answer': 'not sure'},
                                format='json').json()
        self.assertEqual(s['status'], 'completed')
        rep = s['report']
        self.assertEqual(rep['overall_score'], 20.0)
        self.assertTrue(rep['knowledge_gaps'])
        self.assertEqual(len(s['transcript']), 4)
        self.assertIn('evaluation', s['transcript'][0])  # revealed only after completion
        # Weak OS answers became evidence and now drive the recommendations.
        m = SkillMastery.objects.get(user=self.alice, skill__slug='operating-systems')
        self.assertLess(m.mastery, 40)
        self.assertEqual(rep['next_priorities'][0]['skill_slug'], 'operating-systems')
        hist = self.c.get('/api/technical/history/').json()
        self.assertEqual(hist['results'][0]['overall_score'], 20.0)

    def test_scores_hidden_during_interview(self, _):
        s = self.start()
        with patch('technical.services.session.evaluate_answer', return_value=evaluation(8)):
            s = self.c.post('/api/technical/session/answer/', {'session_id': s['id'], 'answer': 'threads share memory'},
                            format='json').json()
        self.assertNotIn('score', s['transcript'][0])
        self.assertEqual(s['current_question']['kind'], 'deeper')

    def test_concurrent_submit_is_rejected(self, _):
        s = self.start()
        Turn.objects.filter(session_id=s['id']).update(state=Turn.EVALUATING)  # another request is mid-evaluation
        r = self.c.post('/api/technical/session/answer/', {'session_id': s['id'], 'answer': 'x'}, format='json')
        self.assertEqual(r.status_code, 409)

    def test_evaluation_failure_lets_user_resend(self, _):
        s = self.start()
        with patch('technical.services.session.evaluate_answer', side_effect=LLMError('busy')):
            r = self.c.post('/api/technical/session/answer/', {'session_id': s['id'], 'answer': 'answer'}, format='json')
        self.assertEqual(r.status_code, 503)
        self.assertEqual(Turn.objects.get(session_id=s['id']).state, Turn.OPEN)

    def test_next_question_failure_then_continue(self, gen):
        s = self.start()
        gen.side_effect = [LLMError('busy')]
        with patch('technical.services.session.evaluate_answer', return_value=evaluation(6)):
            r = self.c.post('/api/technical/session/answer/', {'session_id': s['id'], 'answer': 'ok'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['awaiting_question'])
        gen.side_effect = fake_question
        r = self.c.post('/api/technical/session/continue/', {'session_id': s['id']}, format='json')
        self.assertIsNotNone(r.json()['current_question'])

    def test_end_early_and_ownership(self, _):
        s = self.start()
        self.assertEqual(self.c.post('/api/technical/session/end/', {'session_id': s['id']}, format='json').status_code, 409)
        bob = APIClient()
        bob.force_authenticate(user('bob'))
        self.assertEqual(bob.get(f"/api/technical/session/{s['id']}/").status_code, 404)
        self.assertEqual(bob.post('/api/technical/session/answer/', {'session_id': s['id'], 'answer': 'x'},
                                  format='json').status_code, 404)
        self.assertEqual(APIClient().get('/api/technical/history/').status_code, 401)

    def test_project_interview_needs_resume(self, _):
        r = self.c.post('/api/technical/session/start/', {'interview_type': 'project', 'difficulty': 'Easy',
                                                          'num_questions': 5}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Session.objects.count(), 0)
