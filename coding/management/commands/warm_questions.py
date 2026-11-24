"""Prepare coding-round problems in advance, so rounds start without waiting for the LLM.

    python manage.py warm_questions               # 6 per difficulty
    python manage.py warm_questions --count 15
    python manage.py warm_questions --company amazon --count 10

Each new problem takes 15-60 s on the Groq free tier; already prepared ones are skipped.
"""
from django.core.management.base import BaseCommand, CommandError

from coding import question_bank
from coding.generator import ROUNDS, GenerationError, Unsuitable, prepare
from coding.models import PreparedProblem


class Command(BaseCommand):
    help = 'Prepare coding-round problems from the question bank ahead of time.'

    def add_arguments(self, parser):
        parser.add_argument('--count', type=int, default=6, help='new problems to prepare per difficulty')
        parser.add_argument('--company', default='', help='prepare this company\'s questions (e.g. amazon)')
        parser.add_argument('--difficulty', choices=list(ROUNDS), help='only this difficulty')

    def handle(self, *args, count, company, difficulty, **options):
        if not question_bank.available():
            raise CommandError('No question bank. Run `python manage.py import_question_bank` first.')
        slug = question_bank.company_slug(company) if company else None
        if company and not slug:
            raise CommandError(f'Unknown company "{company}".')

        for level in [difficulty] if difficulty else list(ROUNDS):
            made = 0
            done = set(PreparedProblem.objects.values_list('slug', flat=True))
            for q in question_bank.candidates(level, slug, limit=count * 4):
                if made >= count:
                    break
                if q['slug'] in done:
                    continue
                try:
                    prepare(q, level)
                    made += 1
                    self.stdout.write(f'  {level}: {q["title"]}')
                except Unsuitable:
                    self.stdout.write(f'  {level}: skipped "{q["title"]}" (not a single-function problem)')
                except GenerationError as e:
                    self.stdout.write(f'  {level}: failed "{q["title"]}" ({str(e)[:80]})')
            self.stdout.write(self.style.SUCCESS(f'{level}: {made} new problems prepared.'))
        # Counted in Python: on SQLite, excluding by a JSON key also drops rows that don't have the key.
        total = sum(1 for d in PreparedProblem.objects.values_list('data', flat=True) if not d.get('unsuitable'))
        self.stdout.write(self.style.SUCCESS(f'{total} problems ready in total.'))
