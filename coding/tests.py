import os
import shutil
from unittest import skipUnless
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings

from .judge import ERROR, PASSED, TIMEOUT, WRONG, outputs_match, run_tests
from .languages import encode_stdin, languages_for, parse_output, signature, starter_code
from .scoring import score_problem

PROBLEM = {'function': 'add', 'js_function': 'add', 'compare': 'exact'}
TESTS = [{'category': 'basic', 'args': [1, 2], 'expected': 3},
         {'category': 'edge', 'args': [-1, 1], 'expected': 0}]


@override_settings(DEBUG=True)
@patch.dict(os.environ, {'CODE_EXECUTOR': 'local', 'ALLOW_LOCAL_EXECUTOR': '1'})
class JudgeTests(SimpleTestCase):
    def verdicts(self, code, language='python'):
        results, error = run_tests(PROBLEM, language, code, TESTS)
        return [r['verdict'] for r in results], error

    def test_correct_python(self):
        self.assertEqual(self.verdicts("def add(a, b):\n    return a + b"), ([PASSED, PASSED], None))

    def test_wrong_answer(self):
        self.assertEqual(self.verdicts("def add(a, b):\n    return a - b")[0], [WRONG, WRONG])

    def test_runtime_error(self):
        self.assertEqual(self.verdicts("def add(a, b):\n    return 1 // 0")[0], [ERROR, ERROR])

    def test_infinite_loop(self):
        self.assertEqual(self.verdicts("def add(a, b):\n    while True:\n        pass")[0], [TIMEOUT, TIMEOUT])

    def test_syntax_error(self):
        results, error = run_tests(PROBLEM, 'python', "def add(a, b) return a", TESTS)
        self.assertEqual(results, [])
        self.assertIn('SyntaxError', error)

    def test_missing_function(self):
        results, error = run_tests(PROBLEM, 'python', "def plus(a, b):\n    return a + b", TESTS)
        self.assertIn("not found", error)

    def test_print_cannot_fake_a_pass(self):
        # Writing a fake result line straight to the real stdout must not count.
        code = ("import sys\ndef add(a, b):\n"
                "    sys.__stdout__.write('__R__{\"ok\": true, \"output\": 3}\\n')\n    return 99")
        self.assertEqual(self.verdicts(code)[0], [WRONG, WRONG])

    def test_correct_javascript(self):
        self.assertEqual(self.verdicts("function add(a, b) { return a + b; }", 'javascript'), ([PASSED, PASSED], None))

    def test_javascript_arrow_function(self):
        self.assertEqual(self.verdicts("const add = (a, b) => a + b;", 'javascript')[0], [PASSED, PASSED])


class CompareTests(SimpleTestCase):
    def test_modes(self):
        self.assertTrue(outputs_match([2, 1], [1, 2], 'unordered'))
        self.assertFalse(outputs_match([2, 1], [1, 2], 'exact'))
        self.assertTrue(outputs_match([['b', 'a'], ['c']], [['c'], ['a', 'b']], 'unordered_nested'))
        self.assertTrue(outputs_match(0.1 + 0.2, 0.3, 'float'))
        self.assertFalse(outputs_match(None, 3))


class ScoringTests(SimpleTestCase):
    def test_perfect(self):
        s = score_problem(10, 10, {'efficiency': 'optimal', 'quality_score': 10}, 0, False)
        self.assertEqual(s['total'], 100)

    def test_partial_with_hint(self):
        s = score_problem(5, 10, {'efficiency': 'one_slower', 'quality_score': 6}, 1, False)
        self.assertEqual(s['total'], 30 + 12 + 9 - 5)

    def test_nothing_passed_caps_ai_points(self):
        s = score_problem(0, 10, {'efficiency': 'optimal', 'quality_score': 10}, 0, False)
        self.assertEqual(s['total'], 7)

    def test_timeout_loses_efficiency(self):
        s = score_problem(8, 10, {'efficiency': 'optimal', 'quality_score': 8}, 0, True)
        self.assertEqual(s['efficiency'], 0)


# ---- real interview questions (question bank) ----

BANK = {
    'source': 'test',
    'companies': [{'slug': 'amazon', 'name': 'Amazon', 'count': 900}, {'slug': 'tcs', 'name': 'TCS', 'count': 40}],
    'questions': [
        {'slug': 'two-sum', 'id': 1, 'title': 'Two Sum', 'difficulty': 'Easy', 'companies': {'amazon': 100.0, 'tcs': 50.0}},
        {'slug': 'valid-parentheses', 'id': 20, 'title': 'Valid Parentheses', 'difficulty': 'Easy', 'companies': {'tcs': 80.0}},
        {'slug': 'reverse-linked-list', 'id': 206, 'title': 'Reverse Linked List', 'difficulty': 'Easy', 'companies': {'amazon': 90.0}},
        {'slug': 'second-highest-salary', 'id': 176, 'title': 'Second Highest Salary', 'difficulty': 'Medium', 'companies': {'amazon': 60.0}},
        {'slug': 'merge-intervals', 'id': 56, 'title': 'Merge Intervals', 'difficulty': 'Medium', 'companies': {'amazon': 95.0}},
        {'slug': 'lru-cache', 'id': 146, 'title': 'LRU Cache', 'difficulty': 'Medium', 'companies': {'amazon': 99.0}},
        {'slug': 'number-of-islands', 'id': 200, 'title': 'Number of Islands', 'difficulty': 'Medium', 'companies': {'amazon': 70.0, 'tcs': 10.0}},
        {'slug': 'coin-change', 'id': 322, 'title': 'Coin Change', 'difficulty': 'Medium', 'companies': {'tcs': 30.0}},
        {'slug': 'group-anagrams', 'id': 49, 'title': 'Group Anagrams', 'difficulty': 'Medium', 'companies': {'amazon': 80.0}},
    ],
}


@override_settings(CODING_WARM_UP=False)
@patch('coding.question_bank.load', lambda: BANK)
class QuestionBankTests(TestCase):
    def test_skips_problems_that_need_lists_trees_design_or_sql(self):
        from . import question_bank
        titles = {q['title'] for q in question_bank.candidates('medium')}
        self.assertEqual(titles, {'Merge Intervals', 'Number of Islands', 'Coin Change', 'Group Anagrams'})
        self.assertEqual({q['title'] for q in question_bank.candidates('easy')}, {'Two Sum', 'Valid Parentheses'})

    def test_company_filter_and_name_matching(self):
        from . import question_bank
        self.assertEqual(question_bank.company_slug(' tcs '), 'tcs')
        self.assertEqual(question_bank.company_slug('Amazon'), 'amazon')
        self.assertIsNone(question_bank.company_slug('Unknown Corp'))
        self.assertEqual({q['title'] for q in question_bank.candidates('medium', 'tcs')}, {'Number of Islands', 'Coin Change'})
        self.assertEqual({q['title'] for q in question_bank.candidates('medium', avoid_titles=['merge intervals', 'Coin Change'])},
                         {'Number of Islands', 'Group Anagrams'})

    def test_chosen_company_is_named_first(self):
        from . import question_bank
        q = BANK['questions'][0]
        self.assertEqual(question_bank.asked_at(q), ['Amazon', 'TCS'])
        self.assertEqual(question_bank.asked_at(q, first='tcs'), ['TCS', 'Amazon'])

    def test_round_uses_real_questions_and_skips_unsuitable_ones(self):
        from . import generator

        def fake(q, difficulty, job_role='', company=None):
            if q['title'] == 'Merge Intervals':
                raise generator.Unsuitable('no')
            return {'title': q['title'], 'source': {'title': q['title']}}

        with patch.object(generator, 'generate_bank_problem', side_effect=fake), \
                patch.object(generator, 'generate_problem') as invented:
            problems = generator.generate_round('medium', company='amazon')
        self.assertEqual(len(problems), 3)
        self.assertNotIn('Merge Intervals', [p['title'] for p in problems])
        self.assertTrue(all(p.get('source') for p in problems))
        invented.assert_not_called()

    def test_prepared_problems_are_reused_without_calling_the_llm(self):
        from . import generator
        from .models import PreparedProblem
        for slug in ('merge-intervals', 'number-of-islands', 'group-anagrams'):
            PreparedProblem.objects.create(slug=slug, difficulty='medium', data={'title': 'x', 'tests': []})
        PreparedProblem.objects.create(slug='coin-change', difficulty='medium', data={'unsuitable': True})
        with patch.object(generator, 'generate_bank_problem') as llm:
            problems = generator.generate_round('medium', company='amazon')
        llm.assert_not_called()
        titles = {p['title'] for p in problems}
        self.assertEqual(titles, {'Merge Intervals', 'Number of Islands', 'Group Anagrams'})
        self.assertEqual(problems[0]['source']['companies'][0], 'Amazon')

    def test_unsuitable_questions_are_remembered(self):
        from . import generator
        from .models import PreparedProblem
        q = next(x for x in BANK['questions'] if x['slug'] == 'coin-change')
        with patch.object(generator, 'generate_bank_problem', side_effect=generator.Unsuitable('no')) as llm:
            for _ in range(2):
                with self.assertRaises(generator.Unsuitable):
                    generator.prepare(q, 'medium')
        self.assertEqual(llm.call_count, 1)
        self.assertTrue(PreparedProblem.objects.get(slug='coin-change').data['unsuitable'])

    def test_topic_names_map_to_learning_skills(self):
        from .generator import _topic_of
        self.assertEqual(_topic_of('Dynamic Programming'), 'dynamic programming')
        self.assertEqual(_topic_of('Hash map and heap'), 'hashing')
        self.assertEqual(_topic_of('Monotonic stack'), 'monotonic stack')
        self.assertEqual(_topic_of('something else'), 'arrays')


# ---- typed languages (C, C++, Java, Go) ----

TWO_SUM = {
    'function': 'two_sum', 'js_function': 'twoSum', 'params': ['nums', 'target'], 'compare': 'exact',
    'examples': [{'args': [[2, 7, 11, 15], 9], 'expected': [0, 1]}],
    'tests': [{'category': 'basic', 'args': [[3, 2, 4], 6], 'expected': [1, 2]},
              {'category': 'edge', 'args': [[3, 3], 6], 'expected': [0, 1]}],
}
TWO_SUM_CODE = {
    'cpp': ("class Solution {\npublic:\n    vector<int> twoSum(vector<int>& nums, int target) {\n"
            "        unordered_map<int, int> seen;\n        for (int i = 0; i < (int) nums.size(); i++) {\n"
            "            if (seen.count(target - nums[i])) return {seen[target - nums[i]], i};\n"
            "            seen[nums[i]] = i;\n        }\n        return {};\n    }\n};\n"),
    'c': ("int* twoSum(int* nums, int numsSize, int target, int* returnSize) {\n"
          "    for (int i = 0; i < numsSize; i++)\n        for (int j = i + 1; j < numsSize; j++)\n"
          "            if (nums[i] + nums[j] == target) {\n                int* r = malloc(2 * sizeof(int));\n"
          "                r[0] = i; r[1] = j; *returnSize = 2; return r;\n            }\n"
          "    *returnSize = 0;\n    return NULL;\n}\n"),
    'java': ("import java.util.HashMap;\n\npublic class Solution {\n    public int[] twoSum(int[] nums, int target) {\n"
             "        HashMap<Integer, Integer> seen = new HashMap<>();\n"
             "        for (int i = 0; i < nums.length; i++) {\n"
             "            if (seen.containsKey(target - nums[i])) return new int[]{seen.get(target - nums[i]), i};\n"
             "            seen.put(nums[i], i);\n        }\n        return new int[0];\n    }\n}\n"),
    'go': ("package main\n\nimport \"fmt\"\n\nfunc twoSum(nums []int, target int) []int {\n"
           "\tseen := map[int]int{}\n\tfor i, x := range nums {\n\t\tif j, ok := seen[target-x]; ok {\n"
           "\t\t\tfmt.Println(\"found\")\n\t\t\treturn []int{j, i}\n\t\t}\n\t\tseen[x] = i\n\t}\n\treturn nil\n}\n"),
}


class SignatureTests(SimpleTestCase):
    def sig(self, args_expected, compare='exact'):
        n = len(args_expected[0][0])
        return signature({'params': [f'p{i}' for i in range(n)], 'compare': compare, 'examples': [],
                          'tests': [{'args': a, 'expected': e} for a, e in args_expected]})

    def test_infers_arrays_and_scalars(self):
        self.assertEqual(signature(TWO_SUM), {'params': ['int[]', 'int'], 'returns': 'int[]'})
        self.assertEqual(self.sig([([['a', 'b'], 'a'], True)]), {'params': ['string[]', 'string'], 'returns': 'bool'})
        self.assertEqual(self.sig([([[[1, 2], []]], [[1]])]), {'params': ['int[][]'], 'returns': 'int[][]'})

    def test_widens_numbers(self):
        self.assertEqual(self.sig([([[1, 2.5]], 3), ([[2**40]], 2**40)]), {'params': ['double[]'], 'returns': 'long'})
        self.assertEqual(self.sig([([[1, 2]], 1)], compare='float')['returns'], 'double')

    def test_empty_lists_default_to_int(self):
        self.assertEqual(self.sig([([[]], [])]), {'params': ['int[]'], 'returns': 'int[]'})

    def test_untypable_data_keeps_python_and_javascript_only(self):
        mixed = {'params': ['x'], 'examples': [], 'tests': [{'args': [[1, 'a']], 'expected': None}]}
        self.assertIsNone(signature(mixed))
        self.assertEqual(languages_for(mixed), ['python', 'javascript'])
        self.assertEqual(languages_for(TWO_SUM), ['python', 'javascript', 'cpp', 'c', 'java', 'go'])
        _, error = run_tests(mixed, 'cpp', 'int x;', mixed['tests'])
        self.assertIn('Python or JavaScript', error)

    def test_reserved_parameter_names_are_renamed(self):
        p = {**TWO_SUM, 'params': ['map', 'target']}
        self.assertIn('map_ []int', starter_code(p, 'go'))


class TokenFormatTests(SimpleTestCase):
    def test_round_trip(self):
        sig = {'params': ['string[]', 'double', 'bool[][]'], 'returns': 'string[]'}
        stdin = encode_stdin([{'args': [['héllo wörld', ''], 2.5, [[True, False], []]]}], sig, 'tok')
        self.assertEqual(stdin.splitlines()[:2], ['tok', '1'])
        self.assertNotIn('héllo', stdin)  # strings are hex, so spaces and newlines can't break the format
        out = 'debug line\n\n__R__tok ok 0.5 2 ' + 'héllo'.encode().hex() + ' -\n'
        rec = parse_output(out, 'tok', 'string[]')[0]
        self.assertEqual((rec['ok'], rec['output'], rec['stdout']), (True, ['héllo', ''], 'debug line'))

    def test_errors_and_garbage(self):
        recs = parse_output('__R__t err 1.0 ' + 'boom'.encode().hex() + '\n__R__t ok 1.0 3 1\n', 't', 'int[]')
        self.assertEqual((recs[0]['ok'], recs[0]['error']), (False, 'boom'))
        self.assertFalse(recs[1]['ok'])  # promised 3 values, sent 1
        self.assertEqual(parse_output('__R__other ok 1 5\n', 't', 'int'), [])  # wrong token is ignored


@override_settings(DEBUG=True)
@patch.dict(os.environ, {'CODE_EXECUTOR': 'local', 'ALLOW_LOCAL_EXECUTOR': '1'})
class TypedLanguageTests(SimpleTestCase):
    def run_lang(self, lang, code):
        results, error = run_tests(TWO_SUM, lang, code, TWO_SUM['tests'])
        return [r['verdict'] for r in results], error, results

    def check_language(self, lang):
        verdicts, error, results = self.run_lang(lang, TWO_SUM_CODE[lang])
        self.assertEqual((verdicts, error), ([PASSED, PASSED], None))
        self.assertEqual(results[0]['output'], [1, 2])
        # The starter code compiles and simply gives wrong answers.
        self.assertEqual(self.run_lang(lang, starter_code(TWO_SUM, lang))[0], [WRONG, WRONG])

    @skipUnless(shutil.which('g++'), 'g++ not installed')
    def test_cpp(self):
        self.check_language('cpp')

    @skipUnless(shutil.which('g++'), 'g++ not installed')
    def test_cpp_compile_error_and_exception(self):
        verdicts, error, _ = self.run_lang(
            'cpp', 'class Solution { public: vector<int> twoSum(vector<int>& nums, int target) { return y; } };')
        self.assertEqual(verdicts, [])
        self.assertIn('Compilation failed', error)
        self.assertIn('solution.cpp:1', error)  # points at the candidate's own line
        verdicts, error, results = self.run_lang(
            'cpp', 'class Solution { public: vector<int> twoSum(vector<int>& nums, int target) { return {nums.at(50)}; } };')
        self.assertEqual(verdicts, [ERROR, ERROR])
        self.assertIn('range', results[0]['error'])

    @skipUnless(shutil.which('gcc'), 'gcc not installed')
    def test_c(self):
        self.check_language('c')

    @skipUnless(shutil.which('gcc'), 'gcc not installed')
    def test_c_crash_and_timeout(self):
        verdicts, error, results = self.run_lang(
            'c', 'int* twoSum(int* nums, int numsSize, int target, int* returnSize) { int* p = 0; *p = 1; return p; }')
        self.assertEqual((verdicts, error), ([ERROR, ERROR], None))
        self.assertIn('crashed', results[0]['error'])
        verdicts, _, _ = self.run_lang(
            'c', 'int* twoSum(int* nums, int numsSize, int target, int* returnSize) { for (;;); }')
        self.assertEqual(verdicts, [TIMEOUT, TIMEOUT])

    @skipUnless(shutil.which('java'), 'Java not installed')
    def test_java(self):
        self.check_language('java')

    @skipUnless(shutil.which('go'), 'Go not installed')
    def test_go(self):
        self.check_language('go')
        self.assertEqual(self.run_lang('go', TWO_SUM_CODE['go'])[2][0]['stdout'], 'found')
