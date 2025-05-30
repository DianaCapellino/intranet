# Generated by Django 4.2.1 on 2025-05-09 01:22

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('intranet', '0016_remove_entry_version_booking_entry_version_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='trip',
            name='dh_type',
            field=models.CharField(choices=[('B', 'Basic'), ('S', 'Standard'), ('F', 'Full'), ('Sin definir', 'Sin definir'), ('No', 'Sin seguimiento')], default='Sin definir', max_length=64),
        ),
        migrations.AddField(
            model_name='trip',
            name='itId',
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddField(
            model_name='trip',
            name='trip_type',
            field=models.CharField(choices=[("FIT's", "FIT's"), ('Personal Trips', 'Personal Trips'), ('FAM Tours', 'FAM Tours'), ('Grupos', 'Grupos')], default="FIT's", max_length=64),
        ),
        migrations.AlterField(
            model_name='trip',
            name='creation_date',
            field=models.DateTimeField(default=django.utils.timezone.now, verbose_name='creation date'),
        ),
        migrations.AlterField(
            model_name='trip',
            name='tourplanId',
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AlterField(
            model_name='trip',
            name='version_quote',
            field=models.CharField(default='@', max_length=64, null=True),
        ),
    ]
