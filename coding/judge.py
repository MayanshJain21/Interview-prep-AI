"""Wraps candidate code in the harness, runs it, and compares outputs here in Django
(never inside the sandbox, so printed text can't fake a pass)."""
import json
import math
import secrets
from pathlib import Path

from . import languages
from .executor import get_executor

HARNESS_DIR = Path(__file__).parent / 'harness'
RUNNERS = {
    'python': (HARNESS_DIR / 'runner.py').read_text(encoding='utf-8'),
    'javascript': (HARNESS_DIR / 'runner.js').read_text(encoding='utf-8'),
}
LANGUAGES = list(languages.LABELS)  # python, javascript, cpp, c, java, go
MAX_CODE_SIZE = 64 * 1024

PASSED = 'Passed'
WRONG = 'Wrong answer'
ERROR = 'Runtime error'
TIMEOUT = 'Time limit exceeded'


def _normalize(value, mode):
    if mode == 'unordered':
        return sorted(json.dumps(v, sort_keys=True) for v in value) if isinstance(value, list) else value
    if mode == 'unordered_nested':
        if not isinstance(value, list):
            return value
        inner = [sorted(json.dumps(x) for x in v) if isinstance(v, list) else json.dumps(v) for v in value]
        return sorted(json.dumps(i) for i in inner)
    return value


def outputs_match(actual, expected, mode='exact'):
    if mode == 'float':
        try:
            return math.isclose(float(actual), float(expected), rel_tol=1e-6, abs_tol=1e-6)
        except (TypeError, ValueError):
            return False
    try:
        return _normalize(actual, mode) == _normalize(expected, mode)
    except TypeError:
        return False


def function_name(problem, language):
    return problem['function'] if language == 'python' else problem['js_function']


def _execute(problem, language, code, tests, token):
    """Run the code. Returns (records, stderr, timed_out, started), where started means the program
    compiled and began running tests. Raises ValueError with a message for the user."""
    if language in languages.TYPED:
        sig = languages.signature(problem)
        if not sig:
            raise ValueError(f"This problem's inputs can't be typed for {languages.LABELS[language]}. "
                             "Please use Python or JavaScript.")
        source, offset = languages.build_source(language, problem, sig, code)
        res = get_executor().execute(language, source, languages.encode_stdin(tests, sig, token))
        records = languages.parse_output(res.stdout, token, sig['returns'])
        stderr = languages.clean_errors(res.stderr, language, offset)
        if res.compile_error:
            return [], stderr, False, False
        if len(records) < len(tests) and not res.timed_out and not stderr.strip():
            # Compiled code that crashes (bad pointer, out-of-range index, stack overflow) prints nothing.
            stderr = (f"Your program crashed (exit code {res.exit_code}). Common causes: reading outside an array, "
                      "a null pointer, or recursion that goes too deep.")
        return records, stderr, res.timed_out, True

    source = code + '\n' + RUNNERS[language]
    stdin = json.dumps({'fn': function_name(problem, language), 'tests': [t['args'] for t in tests], 'token': token})
    marker = '__R__' + token
    res = get_executor().execute(language, source, stdin)
    records = []
    for line in res.stdout.splitlines():
        if line.startswith(marker):
            try:
                records.append(json.loads(line[len(marker):]))
            except json.JSONDecodeError:
                pass
    return records, res.stderr, res.timed_out, False


def run_tests(problem, language, code, tests):
    """Run `tests` (list of {"args": [...], "expected": ...}). Returns (results, error_message)."""
    if language not in LANGUAGES:
        return [], f"Unsupported language: {language}"
    if len(code.encode('utf-8')) > MAX_CODE_SIZE:
        return [], "Code is too long (64 KB max)."

    token = secrets.token_hex(8)  # results must carry this, so printed text can't pose as a result
    try:
        records, stderr, timed_out, started = _execute(problem, language, code, tests, token)
    except ValueError as e:
        return [], str(e)

    if records and 'fatal' in records[0]:
        return [], records[0]['fatal']
    if not records and not timed_out and not started:
        # Nothing ran: a syntax or compile error, or the code crashed while loading.
        return [], (stderr.strip() or "Your code didn't run. Check for syntax errors.")[-3000:]

    compare = problem.get('compare', 'exact')
    results = []
    for i, test in enumerate(tests):
        base = {'category': test.get('category', 'basic')}
        if i >= len(records):
            # The process stopped before this test: killed for time, or crashed hard.
            verdict = TIMEOUT if timed_out else ERROR
            err = None if timed_out else (stderr.strip()[-500:] or 'The program stopped unexpectedly.')
            results.append({**base, 'verdict': verdict, 'output': None, 'error': err, 'stdout': '', 'ms': None})
            continue
        rec = records[i]
        if not rec.get('ok'):
            verdict = ERROR
        elif outputs_match(rec.get('output'), test['expected'], compare):
            verdict = PASSED
        else:
            verdict = WRONG
        results.append({**base, 'verdict': verdict, 'output': rec.get('output'), 'error': rec.get('error'),
                        'stdout': rec.get('stdout', ''), 'ms': rec.get('ms')})
    return results, None
