from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('intranet', '0012_guide_destinationhost_trip_fks'),
        ('tariff', '0029_supplier_provisional'),
    ]

    operations = [
        migrations.AddField(
            model_name='guide',
            name='location',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='guides',
                to='tariff.location',
            ),
        ),
        migrations.RemoveField(
            model_name='destinationhost',
            name='location',
        ),
        migrations.AddField(
            model_name='destinationhost',
            name='location',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='destination_hosts',
                to='tariff.location',
            ),
        ),
    ]
