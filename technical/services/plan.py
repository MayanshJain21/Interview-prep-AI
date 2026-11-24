"""
Interview types, topic plans and the adaptive policy (deterministic).

Adaptive policy after each evaluated answer (score 0-10):
    score >= 7   strong   -> follow-up goes deeper on the same topic, level + 1
    4 <= s < 7   partial  -> follow-up probes the missing concepts, same level
    score < 4    weak     -> follow-up asks for the foundations, level - 1
At most one follow-up per topic, and only while there are enough questions left to still cover the
planned number of topics, so the interview stays on its configured subject.
"""
import math
import random

INTERVIEW_TYPES = {
    'dsa': {'label': 'Data Structures & Algorithms', 'topics': [
        ('Arrays and hashing', 'hashing'), ('Two pointers and sliding window', 'sliding-window'),
        ('Stacks and queues', 'stacks'), ('Linked lists', 'linked-lists'), ('Trees and BSTs', 'trees'),
        ('Graphs, BFS and DFS', 'graphs'), ('Dynamic programming', 'dynamic-programming'),
        ('Binary search', 'binary-search'), ('Recursion and backtracking', 'recursion'), ('Heaps', 'heaps')]},
    'programming': {'label': 'Programming Languages', 'topics': []},  # filled from the resume language
    'oop': {'label': 'Object-Oriented Programming', 'topics': [
        ('Classes, objects and encapsulation', 'oop'), ('Inheritance and polymorphism', 'oop'),
        ('Abstraction and interfaces', 'oop'), ('SOLID principles', 'oop'), ('Design patterns', 'oop')]},
    'dbms': {'label': 'DBMS', 'topics': [
        ('Normalization', 'dbms'), ('Transactions and ACID', 'dbms'), ('Indexing', 'dbms'),
        ('SQL joins and queries', 'sql'), ('Concurrency control and locking', 'dbms')]},
    'os': {'label': 'Operating Systems', 'topics': [
        ('Processes and threads', 'operating-systems'), ('CPU scheduling', 'operating-systems'),
        ('Synchronization and deadlocks', 'operating-systems'), ('Memory management and paging', 'operating-systems'),
        ('File systems and I/O', 'operating-systems')]},
    'networks': {'label': 'Computer Networks', 'topics': [
        ('OSI and TCP/IP models', 'computer-networks'), ('TCP vs UDP', 'computer-networks'),
        ('HTTP and HTTPS', 'computer-networks'), ('DNS and how a URL loads', 'computer-networks'),
        ('IP addressing and routing', 'computer-networks')]},
    'web': {'label': 'Web Development', 'topics': [
        ('HTML and CSS layout', 'css'), ('JavaScript event loop and async', 'javascript'),
        ('React state and rendering', 'react'), ('REST API design', 'rest-apis'),
        ('Authentication and sessions', 'rest-apis'), ('Node.js and servers', 'nodejs')]},
    'system_design': {'label': 'System Design', 'topics': [
        ('Scalability basics', 'system-design'), ('Caching', 'system-design'),
        ('Databases, replication and sharding', 'system-design'), ('Load balancing', 'system-design'),
        ('Design a URL shortener', 'system-design')]},
    'project': {'label': 'Project-based', 'topics': [
        ('Project architecture', None), ('Technology choices', None), ('Hardest technical problem', None),
        ('Data model and database', 'dbms'), ('Authentication and security', 'rest-apis'),
        ('Scaling to 10,000 users', 'system-design')]},
    'mixed': {'label': 'Mixed Technical', 'topics': []},  # built from the other types
}

LANGUAGE_SKILLS = [('python', 'Python'), ('java', 'Java'), ('cpp', 'C++'), ('javascript', 'JavaScript'), ('c', 'C')]
LEVEL_NAMES = {1: 'Easy', 2: 'Medium', 3: 'Hard'}
START_LEVEL = {'Easy': 1, 'Medium': 2, 'Hard': 3}


def language_topics(resume_skill_slugs):
    slug, name = next(((s, n) for s, n in LANGUAGE_SKILLS if s in resume_skill_slugs), ('python', 'Python'))
    return [(f'{name}: data types and memory', slug), (f'{name}: functions and scope', slug),
            (f'{name}: object-oriented features', slug), (f'{name}: error handling', slug),
            (f'{name}: concurrency', slug), (f'{name}: standard library and collections', slug)]


def plan_topics(interview_type, num_questions, resume_skill_slugs=(), job_skill_slugs=(), has_resume=True, seed=None):
    """Ordered list of {"topic", "skill"}. Topics linked to the job description come first."""
    rng = random.Random(seed)
    if interview_type == 'programming':
        pool = language_topics(set(resume_skill_slugs))
    elif interview_type == 'mixed':
        pool = []
        for t in ('dsa', 'oop', 'dbms', 'os', 'networks'):
            pool.append(rng.choice(INTERVIEW_TYPES[t]['topics']))
        if has_resume:
            pool.insert(1, INTERVIEW_TYPES['project']['topics'][0])
        pool.append(rng.choice(INTERVIEW_TYPES['web']['topics'] + INTERVIEW_TYPES['system_design']['topics']))
    else:
        pool = list(INTERVIEW_TYPES[interview_type]['topics'])
        if interview_type not in ('project',):
            rng.shuffle(pool)
    job = set(job_skill_slugs)
    pool.sort(key=lambda t: 0 if t[1] in job else 1)  # stable: keeps shuffle order otherwise
    target = min(len(pool), max(3, math.ceil(num_questions * 0.6)))
    return [{'topic': t, 'skill': s} for t, s in pool[:target]]


def next_step(plan, turns, num_questions, level):
    """Decide what to ask next from the answered turns. Returns {"topic", "skill", "kind", "level"} or None."""
    if len(turns) >= num_questions:
        return None
    last = turns[-1]
    covered = []
    for t in turns:
        if t.topic not in covered:
            covered.append(t.topic)
    remaining = num_questions - len(turns)
    uncovered = [p for p in plan if p['topic'] not in covered]
    followed_up = sum(1 for t in turns if t.topic == last.topic) > 1

    score = last.score if last.score is not None else 0
    if score >= 8:
        level = min(3, level + 1)
    elif score < 4:
        level = max(1, level - 1)

    if not followed_up and remaining > len(uncovered):
        if score >= 7:
            kind, lvl = 'deeper', min(3, level)
        elif score >= 4:
            kind, lvl = 'probe', level
        else:
            kind, lvl = 'foundational', level  # level was already lowered above
        return {'topic': last.topic, 'skill': plan_skill(plan, last.topic), 'kind': kind, 'level': lvl}
    if uncovered:
        nxt = uncovered[0]
        return {'topic': nxt['topic'], 'skill': nxt['skill'], 'kind': 'core', 'level': level}
    # Every topic covered and followed up: revisit the weakest topic.
    weakest = min(turns, key=lambda t: t.score if t.score is not None else 10)
    return {'topic': weakest.topic, 'skill': plan_skill(plan, weakest.topic), 'kind': 'probe', 'level': level}


def plan_skill(plan, topic):
    return next((p['skill'] for p in plan if p['topic'] == topic), None)
