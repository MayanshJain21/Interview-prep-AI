from django.core.management.base import BaseCommand

from learning.models import Skill, SkillPrerequisite
from learning.services.taxonomy import sync_taxonomy


class Command(BaseCommand):
    help = 'Load or update the skill taxonomy from learning/taxonomy_data.py (safe to run again).'

    def handle(self, *args, **options):
        sync_taxonomy(Skill, SkillPrerequisite)
        self.stdout.write(self.style.SUCCESS(f'{Skill.objects.count()} skills, '
                                             f'{SkillPrerequisite.objects.count()} prerequisite links.'))
