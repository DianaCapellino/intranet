from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tariff', '0042_carcategory_carhireconfig_carrategroup_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='carhireconfig',
            name='commission',
            field=models.FloatField(default=0, verbose_name='Comisión %'),
        ),
    ]
