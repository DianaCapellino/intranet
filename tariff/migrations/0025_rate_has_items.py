from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tariff', '0024_fixedratecost_fcu'),
    ]

    operations = [
        migrations.AddField(
            model_name='rate',
            name='has_items',
            field=models.BooleanField(default=False),
        ),
    ]
