from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tariff', '0046_carratelline_usd'),
    ]

    operations = [
        migrations.AddField(
            model_name='carfixedcost',
            name='per_day',
            field=models.BooleanField(default=True, verbose_name='Por día (vs único por estadía)'),
        ),
    ]
