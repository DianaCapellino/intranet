from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tariff', '0048_carfixedcost_recommended'),
    ]

    operations = [
        migrations.AddField(
            model_name='carhireconfig',
            name='extras_rounding',
            field=models.PositiveSmallIntegerField(default=5, verbose_name='Redondeo extras x pax (USD)'),
        ),
    ]
