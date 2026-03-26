from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tariff', '0020_costitem_code'),
    ]

    operations = [
        migrations.AddField(
            model_name='costitem',
            name='fcu',
            field=models.CharField(
                choices=[('Group', 'Group'), ('Person', 'Person')],
                default='Person',
                max_length=64,
            ),
        ),
    ]
