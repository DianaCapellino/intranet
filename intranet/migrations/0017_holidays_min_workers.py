from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('intranet', '0016_holidays_work_level'),
    ]

    operations = [
        migrations.AddField(
            model_name='holidays',
            name='min_workers',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
    ]
