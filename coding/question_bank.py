"""Real interview questions for the coding round.

coding/data/question_bank.json (built by `manage.py import_question_bank`) lists LeetCode problems by
the companies that ask them. Only titles, difficulty and frequency are stored; the LLM writes its own
statement and tests for each chosen problem.
"""
import json
import random
import re
from functools import lru_cache
from pathlib import Path

BANK_FILE = Path(__file__).resolve().parent / 'data' / 'question_bank.json'

# The round is function-style with plain JSON inputs, so skip problems built on linked lists, trees,
# class design, SQL tables, shell scripts, concurrency or interactive judges. The LLM also refuses any
# that slip through, and the next candidate is used.
UNSUITABLE = re.compile(
    r'\b(linked ?lists?|lists?\b(?! of)|tree|trees|bst|nodes?|ancestor|inorder|preorder|postorder|level order|'
    r'leaf|leaves|subtree|design|implement|iterator|lru|lfu|serialize|deserialize|clone|copy list|'
    r'threads?|concurren|in order|foobar|fizz ?buzz multithreaded|dining philosophers|h2o|'
    r'employees?|customers?|salar(y|ies)|department|sales|orders|products|users?|managers?|transactions|'
    r'sellers?|buyers?|accounts?|visits?|activity|activities|logins?|tweets?|movies?|students? and|'
    r'table|tables|tenth line|file|phone numbers|interactive|guess|read n characters|api|'
    r'query|queries for|game play analysis|big countries|duplicate emails|rising temperature|'
    r'consecutive numbers|nth highest|rank scores|trips and users|exchange seats|delete duplicate emails)\b',
    re.I)


@lru_cache(maxsize=1)
def load():
    if not BANK_FILE.exists():
        return {'companies': [], 'questions': [], 'source': None}
    return json.loads(BANK_FILE.read_text(encoding='utf-8'))


def available():
    return bool(load()['questions'])


def companies():
    return load()['companies']


def company_slug(text):
    """Match what the user typed to a company in the bank ('Goldman Sachs' -> 'goldman-sachs')."""
    key = re.sub(r'[^a-z0-9]', '', (text or '').lower())
    if not key:
        return None
    for c in load()['companies']:
        if key in (re.sub(r'[^a-z0-9]', '', c['slug']), re.sub(r'[^a-z0-9]', '', c['name'].lower())):
            return c['slug']
    return None


def suitable(q):
    return not UNSUITABLE.search(q['title'])


def candidates(difficulty, company=None, avoid_titles=(), limit=40):
    """Suitable questions of this difficulty, most asked first (with some randomness so rounds vary).
    With a company, only its questions, ranked by how often that company asks them."""
    avoid = {t.lower() for t in avoid_titles}
    pool = [q for q in load()['questions']
            if q['difficulty'].lower() == difficulty and suitable(q) and q['title'].lower() not in avoid
            and (not company or company in q['companies'])]

    def weight(q):
        # Asked by more companies = a well-known classic; with a company, its own frequency counts too.
        spread = len(q['companies']) ** 0.5
        return max(q['companies'][company], 1.0) * spread if company else float(len(q['companies']))

    # Weighted shuffle: higher weight tends to come first, but every run differs.
    keyed = sorted(pool, key=lambda q: random.random() ** (1.0 / weight(q)), reverse=True)
    return keyed[:limit]


def asked_at(q, n=3, first=None):
    """A few companies that ask this question: the chosen one first, then the best-known (largest lists)."""
    info = {c['slug']: c for c in load()['companies']}
    slugs = sorted(q['companies'], key=lambda s: -info.get(s, {}).get('count', 0))
    if first in q['companies']:
        slugs = [first] + [s for s in slugs if s != first]
    return [info[s]['name'] if s in info else s for s in slugs[:n]]


def link(q):
    return f"https://leetcode.com/problems/{q['slug']}/"
