# Generated by Django 4.2.1 on 2025-06-16 13:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('intranet', '0032_alter_trip_difficulty'),
    ]

    operations = [
        migrations.AddField(
            model_name='client',
            name='tp_id',
            field=models.CharField(blank=True, default='', max_length=64, null=True),
        ),
    ]
