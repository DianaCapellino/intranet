from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('intranet', '0025_entry_last_followup_sent_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='trip',
            name='consultant_tp',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='trip_consultant_tp_users',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
