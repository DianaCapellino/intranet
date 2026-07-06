from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tariff', '0045_carcategory_extra_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='carrateline',
            name='usd',
            field=models.BooleanField(default=False, verbose_name='Costo en USD'),
        ),
    ]
