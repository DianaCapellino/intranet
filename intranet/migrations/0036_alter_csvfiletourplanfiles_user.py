# Generated by Django 4.2.1 on 2025-06-16 14:27

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('intranet', '0035_csvfiletourplanfiles_user'),
    ]

    operations = [
        migrations.AlterField(
            model_name='csvfiletourplanfiles',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='tourplan_files_users', to=settings.AUTH_USER_MODEL),
        ),
    ]
