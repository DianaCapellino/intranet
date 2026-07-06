from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tariff', '0049_carhireconfig_extras_rounding'),
    ]

    operations = [
        migrations.AddField(
            model_name='carhireconfig',
            name='conditions_text',
            field=models.TextField(blank=True, default='', verbose_name='Condiciones generales (cotizador)'),
        ),
    ]
