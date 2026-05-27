import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('intranet', '0018_user_show_in_calendar'),
    ]

    operations = [
        migrations.CreateModel(
            name='NotificationPreference',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('notification_type', models.CharField(
                    max_length=40,
                    choices=[
                        ('tariff_client', 'Tariff Updates – Clients'),
                        ('tariff_team', 'Tariff Updates – Team (Internal)'),
                        ('margin_warning', 'Margin Warnings (Sellers)'),
                        ('margin_manager', 'Margin Report (Manager)'),
                        ('weekly_roster', 'Weekly Roster'),
                        ('holiday_reminder', 'Holiday Reminder'),
                    ],
                )),
                ('is_active', models.BooleanField(default=True)),
                ('opt_out_by', models.CharField(
                    blank=True, default='', max_length=10,
                    choices=[('admin', 'Admin'), ('self', 'Self')],
                )),
                ('unsubscribe_token', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('notes', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='notification_prefs',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'ordering': ['notification_type', 'user__username'],
            },
        ),
        migrations.AddConstraint(
            model_name='notificationpreference',
            constraint=models.UniqueConstraint(
                fields=['user', 'notification_type'],
                name='unique_user_notification_type',
            ),
        ),
    ]
