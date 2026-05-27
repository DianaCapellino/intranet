from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('intranet', '0017_holidays_min_workers'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='show_in_calendar',
            field=models.BooleanField(default=True),
        ),
    ]
