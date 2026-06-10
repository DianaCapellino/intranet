from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tariff', '0034_rate_locked'),
    ]

    operations = [
        migrations.AddField(
            model_name='fixedratecost',
            name='code',
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
    ]
