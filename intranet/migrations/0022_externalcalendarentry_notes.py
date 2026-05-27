from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('intranet', '0021_externalcalendarentry'),
    ]

    operations = [
        migrations.AddField(
            model_name='externalcalendarentry',
            name='notes',
            field=models.TextField(blank=True, default=''),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='externalcalendarentry',
            name='category',
            field=models.CharField(
                choices=[
                    ('holiday',         'Holiday'),
                    ('long_weekend',    'Long Weekend'),
                    ('other',           'Other special dates'),
                    ('full_moon',       'Full Moon'),
                    ('not_recommended', 'Not recommended'),
                ],
                default='holiday',
                max_length=20,
            ),
        ),
    ]
