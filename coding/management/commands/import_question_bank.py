"""Builds coding/data/question_bank.json from the public company-wise LeetCode question lists at
https://github.com/snehasishroy/leetcode-companywise-interview-questions

Only facts are kept: the problem title, its LeetCode link and difficulty, and which companies ask it
(with LeetCode's frequency %). No problem statements are copied; the coding round has the LLM write
its own version of each problem.

    python manage.py import_question_bank
"""
import csv
import io
import json
import re
import zipfile
from datetime import date
from pathlib import Path

import requests
from django.core.management.base import BaseCommand, CommandError

REPO = 'https://github.com/snehasishroy/leetcode-companywise-interview-questions'
ZIP_URL = 'https://codeload.github.com/snehasishroy/leetcode-companywise-interview-questions/zip/refs/heads/master'
OUT = Path(__file__).resolve().parents[2] / 'data' / 'question_bank.json'

# Some company names don't title-case well from their folder names.
NAMES = {'ibm': 'IBM', 'tcs': 'TCS', 'jpmorgan': 'JPMorgan', 'paypal': 'PayPal', 'linkedin': 'LinkedIn',
         'tiktok': 'TikTok', 'bytedance': 'ByteDance', 'doordash': 'DoorDash', 'servicenow': 'ServiceNow',
         'phonepe': 'PhonePe', 'makemytrip': 'MakeMyTrip', 'paytm': 'Paytm', 'de-shaw': 'D. E. Shaw',
         'sap': 'SAP', 'amd': 'AMD', 'adp': 'ADP', 'ebay': 'eBay', 'mathworks': 'MathWorks',
         'goldman-sachs': 'Goldman Sachs', 'morgan-stanley': 'Morgan Stanley', 'zs-associates': 'ZS Associates'}


def company_name(slug):
    return NAMES.get(slug) or ' '.join(w.upper() if len(w) <= 2 else w.capitalize() for w in slug.split('-'))


def number(text):
    try:
        return float(str(text).strip().rstrip('%'))
    except ValueError:
        return 0.0


class Command(BaseCommand):
    help = 'Download the company-wise LeetCode question lists and build the coding question bank.'

    def handle(self, *args, **options):
        self.stdout.write(f'Downloading {REPO} ...')
        try:
            resp = requests.get(ZIP_URL, timeout=120)
            resp.raise_for_status()
        except requests.RequestException as e:
            raise CommandError(f"Couldn't download the question lists: {e}")

        questions, companies = {}, {}
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            for name in zf.namelist():
                parts = name.split('/')
                if len(parts) != 3 or parts[2] != 'all.csv':
                    continue
                slug = parts[1]
                rows = csv.DictReader(io.StringIO(zf.read(name).decode('utf-8', 'replace')))
                count = 0
                for row in rows:
                    url = (row.get('URL') or '').strip()
                    m = re.search(r'/problems/([a-z0-9-]+)', url)
                    title = (row.get('Title') or '').strip()
                    difficulty = (row.get('Difficulty') or '').strip().capitalize()
                    if not m or not title or difficulty not in ('Easy', 'Medium', 'Hard'):
                        continue
                    q = questions.setdefault(m.group(1), {
                        'slug': m.group(1), 'id': int(number(row.get('ID'))) or None, 'title': title,
                        'difficulty': difficulty, 'acceptance': number(row.get('Acceptance %')), 'companies': {},
                    })
                    q['companies'][slug] = number(row.get('Frequency %'))
                    count += 1
                if count:
                    companies[slug] = {'slug': slug, 'name': company_name(slug), 'count': count}

        if not questions:
            raise CommandError('No questions found; the repository layout may have changed.')
        OUT.parent.mkdir(parents=True, exist_ok=True)
        data = {
            'source': REPO,
            'imported': date.today().isoformat(),
            'companies': sorted(companies.values(), key=lambda c: c['name'].lower()),
            'questions': sorted(questions.values(), key=lambda q: (q['id'] or 0)),
        }
        OUT.write_text(json.dumps(data, separators=(',', ':')), encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(
            f'Saved {len(questions)} questions from {len(companies)} companies to {OUT} '
            f'({OUT.stat().st_size // 1024} KB).'))
