from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('intranet', '0012_guide_destinationhost_trip_fks'),
        ('tariff', '0027_feedback_entity_and_targets'),
    ]

    operations = [
        migrations.AddField(
            model_name='feedback',
            name='target_guide',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='feedback_guides',
                to='intranet.guide',
            ),
        ),
        migrations.AddField(
            model_name='feedback',
            name='target_dh',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='feedback_dhs',
                to='intranet.destinationhost',
            ),
        ),
    ]
