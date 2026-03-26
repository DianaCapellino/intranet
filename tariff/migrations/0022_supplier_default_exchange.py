from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tariff', '0021_costitem_fcu'),
    ]

    operations = [
        migrations.AddField(
            model_name='supplier',
            name='default_exchange',
            field=models.PositiveIntegerField(default=1),
        ),
    ]
