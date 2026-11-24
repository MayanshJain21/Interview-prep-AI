from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import LearningAttempt, Skill, SkillMastery, SkillPrerequisite
from .services.evidence import record_evidence, record_mcq_results
from .services.mastery import EMAEstimator, band_for
from .services.recommender import recommendations, skill_states
from .services.roadmap import generate_roadmap
from .services.scheduler import build_schedule
from .services.taxonomy import build_index, find_cycle, match_skill, ordered_by_prerequisites


def make_user(name='alice'):
    return User.objects.create_user(username=f'{name}@x.com', email=f'{name}@x.com', password='pw-12345!')


def skill(slug):
    return Skill.objects.get(slug=slug)


class TaxonomyTests(TestCase):
    def test_seeded_and_acyclic(self):
        self.assertGreaterEqual(Skill.objects.count(), 30)
        graph = {}
        for s, p in SkillPrerequisite.objects.values_list('skill_id', 'prerequisite_id'):
            graph.setdefault(s, set()).add(p)
        self.assertIsNone(find_cycle(graph))

    def test_cycle_is_rejected(self):
        link = SkillPrerequisite(skill=skill('arrays'), prerequisite=skill('graphs'))  # graphs already needs arrays
        with self.assertRaises(ValidationError):
            link.full_clean()

    def test_normalisation(self):
        index = build_index(Skill.objects.all())
        for name in ('Data Structures', 'Algorithms', 'Problem Solving', 'DSA'):
            self.assertEqual(match_skill(name, index).slug, 'dsa')
        self.assertEqual(match_skill('C++', index).slug, 'cpp')
        self.assertEqual(match_skill('C', index).slug, 'c')
        self.assertEqual(match_skill('ReactJS', index).slug, 'react')
        self.assertEqual(match_skill('Python programming', index).slug, 'python')
        # Unrelated skills are not merged just because they share a word.
        self.assertIsNone(match_skill('Java Swing Animation', index))
        self.assertIsNone(match_skill('Kubernetes', index))

    def test_prerequisites_ordered_first(self):
        graph = {3: {2}, 2: {1}}
        self.assertEqual(ordered_by_prerequisites([1, 2, 3], graph, {3: 99, 2: 1, 1: 0}), [1, 2, 3])


class MasteryTests(TestCase):
    def test_ema(self):
        ema = EMAEstimator(0.3)
        self.assertEqual(ema.update(None, 80), 80)  # first evidence sets mastery, no 50% prior
        self.assertAlmostEqual(ema.update(80, 30), 0.7 * 80 + 0.3 * 30)
        self.assertEqual(ema.update(50, 150), 0.7 * 50 + 0.3 * 100)  # clamped

    def test_bands(self):
        self.assertEqual(band_for(None)['label'], 'Fundamentals')
        self.assertEqual(band_for(39.9)['coding'], 'easy')
        self.assertEqual(band_for(65)['mcq'], 'Medium')
        self.assertEqual(band_for(80)['coding'], 'hard')
        self.assertEqual(band_for(95)['label'], 'Advanced and revision')


class EvidenceTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def test_idempotent(self):
        _, created = record_evidence(self.user, skill('arrays'), 'coding', 'coding-problem:1', 80)
        _, again = record_evidence(self.user, skill('arrays'), 'coding', 'coding-problem:1', 10)
        self.assertTrue(created)
        self.assertFalse(again)
        m = SkillMastery.objects.get(user=self.user, skill=skill('arrays'))
        self.assertEqual((m.mastery, m.attempts), (80, 1))

    def test_mcq_scores_each_skill_on_its_own_questions(self):
        results = [{'skill': 'Python', 'correct': True}] * 3 + [{'skill': 'Python', 'correct': False}] + \
                  [{'skill': 'SQL', 'correct': False}] * 2 + [{'skill': 'Underwater basket weaving', 'correct': True}]
        out = record_mcq_results(self.user, 7, results, 'Easy')
        mastery = {m.skill.slug: m.mastery for m in SkillMastery.objects.filter(user=self.user)}
        self.assertEqual(mastery, {'python': 75, 'sql': 0})
        self.assertEqual(out['not_in_taxonomy'], ['Underwater basket weaving'])
        record_mcq_results(self.user, 7, results, 'Easy')  # same attempt again
        self.assertEqual(LearningAttempt.objects.filter(user=self.user).count(), 2)


class RecommenderTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def test_unassessed_gets_diagnostic_not_invented_mastery(self):
        states, _ = skill_states(self.user, 'Software Engineer')
        st = next(s for s in states.values() if s['slug'] == 'arrays')
        self.assertIsNone(st['mastery'])
        self.assertEqual(st['status'], 'unassessed')
        recs = recommendations(states)
        self.assertEqual(recs[0]['activity_type'], 'diagnostic')

    def test_blocked_skill_recommends_prerequisite(self):
        for slug in ('arrays', 'recursion', 'linked-lists', 'queues'):
            record_evidence(self.user, skill(slug), 'mcq', f'mcq:{slug}', 85)
        record_evidence(self.user, skill('trees'), 'mcq', 'mcq:t', 20)   # weak prerequisite
        record_evidence(self.user, skill('graphs'), 'mcq', 'mcq:g', 10)  # weakest, but blocked by trees
        states, _ = skill_states(self.user, 'Software Engineer')
        graph_state = next(s for s in states.values() if s['slug'] == 'graphs')
        self.assertIn(skill('trees').id, graph_state['blocked_by'])
        recs = recommendations(states, limit=20)
        self.assertNotIn('graphs', [r['skill_slug'] for r in recs])
        self.assertIn('trees', [r['skill_slug'] for r in recs])

    def test_priority_uses_gap_and_importance(self):
        record_evidence(self.user, skill('arrays'), 'mcq', 'a', 30)
        record_evidence(self.user, skill('hashing'), 'mcq', 'h', 90)
        states, _ = skill_states(self.user, 'Software Engineer')
        arr = next(s for s in states.values() if s['slug'] == 'arrays')
        self.assertEqual(arr['gap'], 70)
        self.assertEqual(arr['priority'], round(70 * arr['importance'], 1))


class SchedulerTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def test_respects_daily_time_deadline_and_order(self):
        states, _ = skill_states(self.user, 'Software Engineer')
        start = date(2026, 1, 5)  # a Monday
        plan = build_schedule(states, start, start + timedelta(days=13), 60, [0, 2, 4])
        per_day = {}
        for item in plan['items']:
            per_day[item['date']] = per_day.get(item['date'], 0) + item['duration_min']
            self.assertIn(item['date'].weekday(), [0, 2, 4])
            self.assertLessEqual(item['date'], start + timedelta(days=13))
        self.assertTrue(all(v <= 60 for v in per_day.values()))
        self.assertTrue(plan['unscheduled'])  # far more work than 6 study hours: reported, not crammed in
        # Prerequisites come first: arrays before strings.
        first = {}
        for item in plan['items']:
            first.setdefault(item['skill_name'], item['date'])
        if 'Strings' in first:
            self.assertLessEqual(first['Arrays'], first['Strings'])

    def test_task_longer_than_a_day_is_unscheduled(self):
        # Assessed by MCQ and interview already, so the next activity rotates to coding: hard band = 60 min.
        record_evidence(self.user, skill('graphs'), 'mcq', 'g1', 85)
        record_evidence(self.user, skill('graphs'), 'technical', 'g2', 85)
        states, _ = skill_states(self.user, 'Software Engineer')
        states = {k: v for k, v in states.items() if v['slug'] == 'graphs'}
        states[next(iter(states))]['prerequisites'] = []
        plan = build_schedule(states, date(2026, 1, 5), date(2026, 1, 20), 30, list(range(7)))
        self.assertTrue(any('needs 60 min' in u['why'] for u in plan['unscheduled']))


class RoadmapAndLoopTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def roadmap(self):
        return generate_roadmap(self.user, target_role='Backend Developer', analysis=None,
                                deadline=timezone.localdate() + timedelta(days=30), minutes_per_day=90,
                                study_days=[0, 1, 2, 3, 4, 5, 6])

    def test_generate_archives_old_and_keeps_history(self):
        first = self.roadmap()
        first.items.update(status='completed')
        second = self.roadmap()
        first.refresh_from_db()
        self.assertEqual(first.status, 'archived')
        self.assertTrue(first.items.filter(status='completed').exists())
        self.assertEqual(second.status, 'active')

    def test_evidence_completes_task_and_retunes_difficulty(self):
        rm = self.roadmap()
        diag = rm.items.filter(skill__slug='sql', activity_type='diagnostic').first()
        self.assertIsNotNone(diag)
        record_mcq_results(self.user, 1, [{'skill': 'SQL', 'correct': True}] * 4 + [{'skill': 'SQL', 'correct': False}], 'Easy')
        diag.refresh_from_db()
        self.assertEqual(diag.status, 'completed')  # the MCQ completed the planned diagnostic
        later = rm.items.filter(skill__slug='sql', status='pending', activity_type='mcq').first()
        if later:
            self.assertEqual(later.difficulty, 'Hard')  # 80% -> hard band

    def test_api_ownership(self):
        rm = self.roadmap()
        item = rm.items.first()
        other = APIClient()
        other.force_authenticate(make_user('bob'))
        self.assertEqual(other.post('/api/engine/roadmap/complete/', {'item_id': item.id}, format='json').status_code, 404)
        self.assertEqual(other.get(f'/api/engine/roadmap/{rm.id}/').status_code, 404)
        self.assertEqual(APIClient().get('/api/engine/roadmap/').status_code, 401)

    def test_api_generate_complete_reschedule(self):
        c = APIClient()
        c.force_authenticate(self.user)
        r = c.post('/api/engine/roadmap/generate/', {'target_role': 'Frontend Developer',
                                                     'deadline': str(timezone.localdate() + timedelta(days=21)),
                                                     'minutes_per_day': 60, 'study_days': [0, 2, 4, 6]}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        item_id = r.json()['items'][0]['id']
        self.assertEqual(c.post('/api/engine/roadmap/complete/', {'item_id': item_id, 'status': 'skipped'},
                                format='json').json()['status'], 'skipped')
        other_item = r.json()['items'][1]['id']
        r2 = c.post('/api/engine/roadmap/reschedule/', {'item_id': other_item,
                                                         'date': str(timezone.localdate() + timedelta(days=3))}, format='json')
        self.assertEqual(r2.status_code, 200, r2.content)
        bad = c.post('/api/engine/roadmap/generate/', {'deadline': str(timezone.localdate()), 'minutes_per_day': 60,
                                                       'study_days': [0]}, format='json')
        self.assertEqual(bad.status_code, 400)
        a = c.get('/api/engine/analytics/').json()
        self.assertEqual(a['roadmap_progress']['completed'], 0)
        self.assertTrue(a['recommendations'])
