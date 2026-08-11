from django.db import migrations


def migrate_to_dm(apps, schema_editor):
    User = apps.get_model('intranet', 'User')
    Client = apps.get_model('intranet', 'Client')
    Trip = apps.get_model('intranet', 'Trip')
    for model in (User, Client, Trip):
        model.objects.filter(department='SH').update(department='DM')
        model.objects.filter(department='SHD').update(department='DM')


class Migration(migrations.Migration):

    dependencies = [
        ('intranet', '0031_alter_revisionscheduleday_id'),
    ]

    operations = [
        migrations.RunPython(migrate_to_dm, migrations.RunPython.noop),
    ]
