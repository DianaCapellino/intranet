from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tariff', '0033_add_increase_to_cost_item'),
    ]

    operations = [
        migrations.AddField(
            model_name='rate',
            name='locked',
            field=models.BooleanField(default=False),
        ),
    ]
