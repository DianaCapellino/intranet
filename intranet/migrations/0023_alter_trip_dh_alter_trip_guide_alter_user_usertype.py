# Generated by Django 4.2.1 on 2025-05-09 19:18

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('intranet', '0022_alter_user_usertype'),
    ]

    operations = [
        migrations.AlterField(
            model_name='trip',
            name='dh',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='dh_user', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='trip',
            name='guide',
            field=models.CharField(blank=True, default='', max_length=64, null=True),
        ),
        migrations.AlterField(
            model_name='user',
            name='userType',
            field=models.CharField(choices=[('Ventas', 'Ventas'), ('Operaciones', 'Operaciones'), ('DH', 'DH')], default='Sales', max_length=64),
        ),
    ]
