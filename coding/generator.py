"""
Builds coding problems with the LLM, then checks them by running the problem's own
reference solution against its tests. Tests where the reference disagrees with the LLM's
expected output are dropped; a problem with too few good tests is regenerated.
"""
import json
import random
import re
import time
import copy
from concurrent.futures import ThreadPoolExecutor
from threading import Lock, Thread

from django.conf import settings
from django.db import IntegrityError, connection

from groq import APIStatusError, RateLimitError

from ai_features.llm import LLMError, call_llm_json, clean_list, groq_client
from learning.taxonomy_data import CODING_TOPIC_TO_SKILL
from . import question_bank
from .executor import get_executor
from .judge import RUNNERS, outputs_match

ROUNDS = {
    'easy': {'count': 2, 'minutes': 30, 'topics': ['arrays', 'strings', 'hashing', 'two pointers', 'stack', 'math']},
    'medium': {'count': 3, 'minutes': 45, 'topics': ['sliding window', 'stack', 'binary search', 'intervals',
                                                     'hashing', 'two pointers', 'prefix sums', 'BFS/DFS on grids']},
    'hard': {'count': 3, 'minutes': 60, 'topics': ['graphs', 'dynamic programming', 'heaps', 'intervals',
                                                   'monotonic stack', 'sliding window', 'backtracking']},
}
ROLE_TOPICS = {
    'backend': ['hashing', 'intervals', 'heaps', 'graphs'],
    'data': ['hashing', 'sliding window', 'prefix sums', 'dynamic programming'],
    'frontend': ['strings', 'stack', 'hashing', 'two pointers'],
}
MIN_HIDDEN_TESTS = 8
# The larger free model is noticeably more accurate at writing correct tests.
GENERATION_MODEL = 'openai/gpt-oss-120b'
FALLBACK_MODEL = 'openai/gpt-oss-20b'
MAX_ATTEMPTS = 3
IDENT = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


class GenerationError(Exception):
    pass


class Unsuitable(GenerationError):
    """The model says a bank question can't be posed as one function with JSON inputs."""


def pick_topics(difficulty, job_role=''):
    cfg = ROUNDS[difficulty]
    pool = list(cfg['topics'])
    role = job_role.lower()
    preferred = [t for key, topics in ROLE_TOPICS.items() if key in role for t in topics if t in pool]
    random.shuffle(pool)
    # Role-related topics go first, but the rest of the round stays varied.
    ordered = list(dict.fromkeys(preferred[:1] + pool))
    return ordered[:cfg['count']]


def _prompt(topic, difficulty, job_role, avoid_titles):
    avoid = ', '.join(avoid_titles[-30:]) or 'none'
    role = f"The candidate is preparing for: {job_role}." if job_role else ''
    return f"""
    You write coding interview problems in the style of LeetCode, as commonly asked in real interviews.
    Write ONE {difficulty} problem on the topic: {topic}. {role}
    Do not reuse any of these problems: {avoid}.
    """ + _SPEC.format(topic_field='')


def _bank_prompt(q, job_role, company=None):
    """Ask for the model's own write-up of a real, named interview problem."""
    role = f"The candidate is preparing for: {job_role}." if job_role else ''
    companies = ', '.join(question_bank.asked_at(q, first=company)) or 'many companies'
    number = f"LeetCode #{q['id']}, " if q.get('id') else ''
    return f"""
    You write coding interview problems for practice. Write a function-style version of the real interview
    problem "{q['title']}" ({number}{q['difficulty']}), which is asked at {companies}. {role}
    Keep the same problem, core idea and similar constraints, and keep the title "{q['title']}", but write the
    statement, examples and tests in your own words. Do not copy LeetCode's text.
    If this problem cannot be posed as one function with plain JSON inputs and output (for example it needs
    a linked list, a tree, a class with several methods, SQL or a shell script), reply with only:
    ```json
    {{"unsuitable": true}}
    ```
    """ + _SPEC.format(topic_field=f'"topic": "the best fit from: {", ".join(TOPICS)}",\n      ')


TOPICS = list(CODING_TOPIC_TO_SKILL)

_SPEC = """
    Rules:
    - Function-style: the candidate implements one function. Inputs and output must be plain JSON values
      (ints, floats, strings, booleans, lists, nested lists). No linked lists, tree objects or classes.
    - If several answers could be correct, say exactly which one to return (e.g. "indices in increasing order")
      or set "compare" to "unordered" (list order doesn't matter) or "unordered_nested" (order of the outer list
      and inside each inner list doesn't matter). Use "float" only for floating-point answers.
    - Hidden tests: 12 tests with categories "basic" and "edge" (empty, single element, duplicates, negatives,
      boundaries), at least 4 edge tests. Keep test inputs small. Work out every expected value carefully.
    - The reference solution is correct, efficient Python 3 defining the function with exactly the given name
      and parameters. Standard library only.
    - The large-input code is Python 3 defining generate(), which returns a list of 1 or 2 argument lists near
      the constraint limits, using random.Random(<fixed seed>). Standard library only.

    Reply with exactly three fenced blocks and nothing else:

    ```json
    {{
      {topic_field}"title": "short title",
      "statement": "problem statement, using `backticks` for parameter names",
      "constraints": ["..."],
      "function": "snake_case_python_name",
      "js_function": "camelCaseJsName",
      "params": ["param1", "param2"],
      "compare": "exact | unordered | unordered_nested | float",
      "examples": [{{"args": [arg1, arg2], "expected": value, "explanation": "one sentence"}}],
      "tests": [{{"category": "basic | edge", "args": [arg1, arg2], "expected": value}}],
      "complexity": {{"time": "O(...)", "space": "O(...)"}},
      "hints": ["gentle hint", "more direct hint"]
    }}
    ```

    ```python reference
    def snake_case_python_name(param1, param2):
        ...
    ```

    ```python large
    import random
    def generate():
        ...
    ```
    Give 2 or 3 examples.
    """


FENCE = re.compile(r"```(\w+)?[ \t]*(\w+)?[^\n]*\n(.*?)```", re.S)


def _ask_for_problem(prompt, effort='medium'):
    """The JSON + code-block reply is too long for strict JSON mode, so parse it ourselves."""
    text = None
    for model in (GENERATION_MODEL, FALLBACK_MODEL):
        for _ in range(2):
            try:
                completion = groq_client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model=model, temperature=0.7, max_tokens=5000, reasoning_effort=effort,
                )
                text = completion.choices[0].message.content or ''
                break
            except (RateLimitError, APIStatusError) as e:
                # Free tier: 429 = too many requests, 413 = over the tokens-per-minute budget.
                if getattr(e, 'status_code', None) not in (413, 429):
                    raise
                wait = re.search(r'try again in ([\d.]+)s', str(e))
                time.sleep(min(float(wait.group(1)) + 0.5, 20) if wait else 8)
        if text is not None:
            break
    if text is None:
        raise GenerationError("the AI service is busy (free-tier rate limit), please try again in a minute")
    pkg, code_blocks = None, []
    for lang, label, body in FENCE.findall(text):
        if lang == 'json':
            pkg = json.loads(body)
        elif lang == 'python':
            code_blocks.append((label, body))
    if pkg is None:
        raise GenerationError("reply had no JSON block")
    if pkg.get('unsuitable'):
        raise Unsuitable("not expressible as a single function")
    for label, body in code_blocks:
        if label == 'large' or 'def generate' in body:
            pkg['large_input_code'] = body
        else:
            pkg['reference_solution'] = body
    return pkg


def _run_reference(reference, function, arg_lists):
    """Run the reference on each argument list. Returns the list of outputs (None where it failed)."""
    source = reference + '\n' + RUNNERS['python']
    stdin = json.dumps({'fn': function, 'tests': arg_lists, 'token': 'ref'})
    res = get_executor().execute('python', source, stdin)
    outputs = []
    for line in res.stdout.splitlines():
        if line.startswith('__R__ref'):
            rec = json.loads(line[8:])
            if 'fatal' in rec:
                raise GenerationError(rec['fatal'])
            outputs.append(rec['output'] if rec.get('ok') and not rec.get('unserializable') else None)
    if not outputs:
        raise GenerationError(f"Reference solution did not run: {res.stderr[-300:]}")
    return outputs + [None] * (len(arg_lists) - len(outputs))


def _large_inputs(code):
    source = code + "\nimport json as _j\nprint('__G__' + _j.dumps(generate()))\n"
    res = get_executor().execute('python', source, '')
    for line in res.stdout.splitlines():
        if line.startswith('__G__'):
            data = json.loads(line[5:])
            if isinstance(data, list) and all(isinstance(a, list) for a in data):
                return data[:2]
    return []


def _validate(pkg, difficulty, topic):
    for key in ('title', 'statement', 'function', 'js_function', 'params', 'examples', 'tests', 'reference_solution'):
        if not pkg.get(key):
            raise GenerationError(f"missing {key}")
    if not IDENT.match(pkg['function']) or not IDENT.match(pkg['js_function']):
        raise GenerationError("bad function name")
    compare = pkg.get('compare', 'exact')
    if compare not in ('exact', 'unordered', 'unordered_nested', 'float'):
        compare = 'exact'
    n_params = len(pkg['params'])
    examples = [e for e in pkg['examples'] if isinstance(e.get('args'), list) and len(e['args']) == n_params]
    tests = [t for t in pkg['tests'] if isinstance(t.get('args'), list) and len(t['args']) == n_params]
    if not examples:
        raise GenerationError("no usable examples")

    outputs = _run_reference(pkg['reference_solution'], pkg['function'],
                             [e['args'] for e in examples] + [t['args'] for t in tests])
    ex_out, test_out = outputs[:len(examples)], outputs[len(examples):]

    # Only show examples the reference agrees with; if none agree, the statement and code don't match.
    good = [(e, o) for e, o in zip(examples, ex_out) if o is not None and outputs_match(o, e['expected'], compare)]
    if not good:
        raise GenerationError("no example agrees with the reference solution")
    examples, ex_out = [e for e, _ in good], [o for _, o in good]

    hidden = []
    for t, out in zip(tests, test_out):
        if out is not None and outputs_match(out, t['expected'], compare):
            hidden.append({'category': t.get('category', 'basic') if t.get('category') in ('basic', 'edge') else 'basic',
                           'args': t['args'], 'expected': out})
    if len(hidden) < MIN_HIDDEN_TESTS:
        raise GenerationError(f"only {len(hidden)} tests agreed with the reference")

    # Large tests: expected output comes from the reference (no LLM value to compare with).
    if pkg.get('large_input_code'):
        try:
            large_args = [a for a in _large_inputs(pkg['large_input_code']) if len(a) == n_params]
            if large_args:
                large_out = _run_reference(pkg['reference_solution'], pkg['function'], large_args)
                hidden += [{'category': 'large', 'args': a, 'expected': o}
                           for a, o in zip(large_args, large_out) if o is not None]
        except (GenerationError, json.JSONDecodeError):
            pass  # small tests are enough to keep the problem

    return {
        'title': str(pkg['title'])[:200],
        'topic': topic,
        'difficulty': difficulty,
        'statement': pkg['statement'],
        'constraints': [str(c) for c in pkg.get('constraints', [])],
        'function': pkg['function'],
        'js_function': pkg['js_function'],
        'params': [str(p) for p in pkg['params']],
        'compare': compare,
        'examples': [{'args': e['args'], 'expected': o, 'explanation': e.get('explanation', '')}
                     for e, o in zip(examples, ex_out)],
        'tests': hidden,
        'reference_solution': pkg['reference_solution'],
        'complexity': pkg.get('complexity') or {},
        'hints': [str(h) for h in pkg.get('hints', [])][:2],
    }


def generate_problem(topic, difficulty, job_role='', avoid_titles=()):
    last_error = None
    for _ in range(MAX_ATTEMPTS):
        try:
            pkg = _ask_for_problem(_prompt(topic, difficulty, job_role, list(avoid_titles)))
            return _validate(pkg, difficulty, topic)
        except Exception as e:  # bad JSON, failed validation, executor hiccup: try again
            last_error = e
    raise GenerationError(f"Couldn't build a valid {topic} problem: {last_error}")


def _same_problem(a, b):
    norm = lambda t: re.sub(r'[^a-z0-9]', '', t.lower())
    return norm(a['title']) == norm(b['title']) or a['function'] == b['function']


def _topic_of(text):
    """Map the model's topic to one the learning path knows ('Hash map / heap' -> 'hashing')."""
    text = str(text or '').strip().lower()
    if text in CODING_TOPIC_TO_SKILL:
        return text
    aliases = {'hash': 'hashing', 'heap': 'heaps', 'priority queue': 'heaps', 'dp': 'dynamic programming',
               'dynamic': 'dynamic programming', 'graph': 'graphs', 'bfs': 'graphs', 'dfs': 'graphs',
               'string': 'strings', 'array': 'arrays', 'pointer': 'two pointers', 'window': 'sliding window',
               'binary search': 'binary search', 'stack': 'stack', 'interval': 'intervals', 'greedy': 'intervals',
               'backtrack': 'backtracking', 'recursion': 'backtracking', 'prefix': 'prefix sums', 'math': 'math',
               'sort': 'arrays', 'matrix': 'arrays'}
    for topic in sorted(CODING_TOPIC_TO_SKILL, key=len, reverse=True):
        if topic in text:
            return topic
    for key, topic in aliases.items():
        if key in text:
            return topic
    return 'arrays'


def generate_bank_problem(q, difficulty, job_role='', company=None):
    """The model's own write-up of a real interview question, checked like any other problem.
    The prompt leaves out the role and company so the result can be cached for every user."""
    last_error = None
    for _ in range(2):
        try:
            pkg = _ask_for_problem(_bank_prompt(q, ''), effort='low')
            problem = _validate(pkg, difficulty, _topic_of(pkg.get('topic')))
        except Unsuitable:
            raise
        except Exception as e:  # bad JSON, failed validation, executor hiccup: try again
            last_error = e
            continue
        problem['title'] = q['title']  # the real problem's name, not the model's paraphrase
        problem['source'] = {'title': q['title'], 'url': question_bank.link(q), 'leetcode_id': q.get('id'),
                             'companies': question_bank.asked_at(q, first=company)}
        return problem
    raise GenerationError(f"Couldn't build \"{q['title']}\": {last_error}")


def _titles_for_topic(topic, pool):
    """Which of these real titles practise `topic`? One small model call; [] if it fails."""
    titles = [q['title'] for q in pool[:60]]
    try:
        reply = call_llm_json(
            'You classify coding interview problems by the main technique they test.',
            f'Topic: {topic}\nProblems:\n' + '\n'.join(titles) +
            '\n\nReturn JSON {"titles": [...]} with up to 5 titles from the list whose main technique is the topic.',
            temperature=0, max_tokens=800, retries=1,
            validate=lambda d: {'titles': [t for t in clean_list(d.get('titles'), 5, 200) if t in titles]})
    except LLMError:
        return []
    return [q for t in reply['titles'] for q in pool if q['title'] == t]


def _with_source(problem, q, company):
    problem = copy.deepcopy(problem)
    problem['title'] = q['title']
    problem['source'] = {'title': q['title'], 'url': question_bank.link(q), 'leetcode_id': q.get('id'),
                         'companies': question_bank.asked_at(q, first=company)}
    return problem


def _save(q, difficulty, data):
    from .models import PreparedProblem
    try:
        PreparedProblem.objects.get_or_create(slug=q['slug'], defaults={'difficulty': difficulty, 'data': data})
    except IntegrityError:
        pass  # saved by another round at the same moment


def prepare(q, difficulty):
    """Return the saved problem for this question, generating and saving it first if needed."""
    from .models import PreparedProblem
    saved = PreparedProblem.objects.filter(slug=q['slug']).first()
    if saved:
        if saved.data.get('unsuitable'):
            raise Unsuitable('marked unsuitable earlier')
        return saved.data
    try:
        data = generate_bank_problem(q, difficulty)
    except Unsuitable:
        _save(q, difficulty, {'unsuitable': True})  # so later rounds don't spend an LLM call on it again
        raise
    _save(q, difficulty, data)
    return data


_warming = Lock()
WARM_UP_COUNT = 3


def _warm_up(difficulty, company, avoid_titles):
    """Prepare a few more questions in the background so the next round starts instantly.
    Only one warm-up runs at a time, to stay inside the free-tier rate limit."""
    if not _warming.acquire(blocking=False):
        return
    try:
        from .models import PreparedProblem
        pool = question_bank.candidates(difficulty, company, avoid_titles, limit=30)
        done = set(PreparedProblem.objects.filter(slug__in=[q['slug'] for q in pool]).values_list('slug', flat=True))
        made = 0
        for q in pool:
            if made >= WARM_UP_COUNT:
                break
            if q['slug'] in done:
                continue
            try:
                prepare(q, difficulty)
                made += 1
            except GenerationError:
                continue
    except Exception:  # background work must never break anything
        pass
    finally:
        connection.close()
        _warming.release()


def start_warm_up(difficulty, company=None, avoid_titles=()):
    if getattr(settings, 'CODING_WARM_UP', True):
        Thread(target=_warm_up, args=(difficulty, company, list(avoid_titles)), daemon=True).start()


def _bank_round(difficulty, job_role, avoid_titles, focus_topic, company):
    count = ROUNDS[difficulty]['count']
    pool = question_bank.candidates(difficulty, company, avoid_titles)
    if company and len(pool) < count + 3:
        # Not enough of this company's questions at this level: top up with commonly asked ones.
        pool += [q for q in question_bank.candidates(difficulty, None, avoid_titles) if q not in pool]
    if len(pool) < count:
        return None
    if focus_topic:
        # A round opened from the learning roadmap starts with a real question on that topic.
        wanted = _titles_for_topic(focus_topic, pool) or _titles_for_topic(
            focus_topic, question_bank.candidates(difficulty, None, avoid_titles, limit=60))
        pool = wanted + [q for q in pool if q not in wanted]

    # Questions already prepared are used first, so most rounds start without waiting for the LLM.
    from .models import PreparedProblem
    saved = {p.slug: p.data for p in PreparedProblem.objects.filter(slug__in=[q['slug'] for q in pool])}
    pool = [q for q in pool if not saved.get(q['slug'], {}).get('unsuitable')]
    head = pool[:1] if focus_topic else []  # keep the roadmap's topic question first
    rest = [q for q in pool if q not in head]
    pool = head + [q for q in rest if q['slug'] in saved] + [q for q in rest if q['slug'] not in saved]

    lock = Lock()
    queue = list(pool)
    unsuitable = []

    def build(_slot):
        # Each slot takes the next candidate until one turns into a valid problem (at most 4 tries).
        # Worker threads only call the LLM; all database reads and writes stay in this thread.
        for _ in range(4):
            with lock:
                if not queue:
                    break
                q = queue.pop(0)
            if q['slug'] in saved:
                return q, saved[q['slug']], False
            try:
                return q, generate_bank_problem(q, difficulty), True
            except Unsuitable:
                unsuitable.append(q)
            except GenerationError:
                continue
        return None

    # Two at a time keeps us under the free-tier tokens-per-minute limit most of the time.
    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(build, range(count)))

    for q in unsuitable:
        _save(q, difficulty, {'unsuitable': True})
    problems = []
    for r in results:
        if r is None:
            problems.append(None)
            continue
        q, data, fresh = r
        if fresh:
            _save(q, difficulty, data)
        problems.append(_with_source(data, q, company))
    # A slot whose questions all failed gets a topic-based problem instead, so the round still starts.
    topics = pick_topics(difficulty, job_role)
    for i, p in enumerate(problems):
        if p is None:
            taken = list(avoid_titles) + [x['title'] for x in problems if x]
            problems[i] = generate_problem(topics[i % len(topics)], difficulty, job_role, taken)
    return problems


def generate_round(difficulty, job_role='', avoid_titles=(), focus_topic='', company=None):
    """Real interview questions from the question bank when it's installed; otherwise the model
    writes its own problems by topic."""
    if question_bank.available():
        try:
            problems = _bank_round(difficulty, job_role, avoid_titles, focus_topic, company)
            if problems:
                start_warm_up(difficulty, company, list(avoid_titles) + [p['title'] for p in problems])
                return problems
        except GenerationError:
            pass  # fall back to topic-based problems below
    topics = pick_topics(difficulty, job_role)
    # A round opened from the learning roadmap starts with the topic being practised.
    if focus_topic:
        topics = [focus_topic] + [t for t in topics if t != focus_topic][:len(topics) - 1]
    # Two at a time keeps us under the free-tier tokens-per-minute limit most of the time.
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(generate_problem, t, difficulty, job_role, avoid_titles) for t in topics]
        problems = [f.result() for f in futures]

    # Problems made in parallel can't see each other, so replace any repeat.
    for i in range(1, len(problems)):
        for _ in range(2):
            if not any(_same_problem(problems[i], earlier) for earlier in problems[:i]):
                break
            taken = list(avoid_titles) + [p['title'] for p in problems]
            problems[i] = generate_problem(topics[i], difficulty, job_role, taken)
    return problems
