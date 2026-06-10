from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tariff', '0035_fixedratecost_code'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='tp_location_code',
            field=models.CharField(blank=True, max_length=10),
        ),
    ]
