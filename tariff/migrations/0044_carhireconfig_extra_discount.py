from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tariff', '0043_carhireconfig_commission'),
    ]

    operations = [
        migrations.AddField(
            model_name='carhireconfig',
            name='extra_discount',
            field=models.FloatField(default=20, verbose_name='Descuento adicional %'),
        ),
    ]
