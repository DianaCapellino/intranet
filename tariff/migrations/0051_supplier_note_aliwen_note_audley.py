from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tariff', '0050_carhireconfig_conditions_text'),
    ]

    operations = [
        migrations.AddField(
            model_name='supplier',
            name='note_aliwen',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='supplier',
            name='note_audley',
            field=models.TextField(blank=True, default=''),
        ),
    ]
