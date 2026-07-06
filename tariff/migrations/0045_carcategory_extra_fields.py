from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tariff', '0044_carhireconfig_extra_discount'),
    ]

    operations = [
        migrations.AddField(
            model_name='carcategory',
            name='max_passengers',
            field=models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='Máx. pasajeros'),
        ),
        migrations.AddField(
            model_name='carcategory',
            name='max_luggage',
            field=models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='Máx. valijas'),
        ),
        migrations.AddField(
            model_name='carcategory',
            name='transmission',
            field=models.CharField(blank=True, choices=[('M', 'Manual'), ('A', 'Automático')], default='', max_length=1),
        ),
    ]
