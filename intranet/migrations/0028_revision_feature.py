from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('intranet', '0027_trip_vr_requested_by'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='seniority',
            field=models.CharField(
                blank=True, default='',
                choices=[('Junior', 'Junior'), ('Senior', 'Senior')],
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name='entry',
            name='is_revised',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='entry',
            name='revision_link',
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
        migrations.AddField(
            model_name='entry',
            name='revising_user',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='revising_entries',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.CreateModel(
            name='RevisionScheduleDay',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('weekday', models.IntegerField(choices=[(0, 'Lunes'), (1, 'Martes'), (2, 'Miércoles'), (3, 'Jueves'), (4, 'Viernes')])),
                ('order', models.IntegerField(default=0)),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='revision_days',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'ordering': ['weekday', 'order'],
                'unique_together': {('user', 'weekday')},
            },
        ),
    ]
