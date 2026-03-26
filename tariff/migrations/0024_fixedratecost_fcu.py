from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tariff', '0023_fixedratecost_supplier'),
    ]

    operations = [
        migrations.AddField(
            model_name='fixedratecost',
            name='fcu',
            field=models.CharField(
                choices=[('Group', 'Group'), ('Person', 'Person')],
                default='Person',
                max_length=64,
            ),
        ),
    ]
