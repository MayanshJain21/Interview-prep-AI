from django.db import migrations


def seed(apps, schema_editor):
    from learning.services.taxonomy import sync_taxonomy
    sync_taxonomy(apps.get_model('learning', 'Skill'), apps.get_model('learning', 'SkillPrerequisite'))


class Migration(migrations.Migration):
    dependencies = [('learning', '0001_initial')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
