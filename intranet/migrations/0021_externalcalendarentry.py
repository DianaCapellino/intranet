from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('intranet', '0020_user_show_in_client_team'),
        ('tariff', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExternalCalendarEntry',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_from', models.DateField()),
                ('date_to', models.DateField()),
                ('name', models.CharField(blank=True, max_length=128)),
                ('category', models.CharField(
                    choices=[
                        ('holiday', 'Holiday'),
                        ('long_weekend', 'Long Weekend'),
                        ('other', 'Other special dates'),
                        ('full_moon', 'Full Moon'),
                    ],
                    default='holiday',
                    max_length=20,
                )),
                ('location', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='calendar_entries',
                    to='tariff.location',
                )),
            ],
        ),
    ]
