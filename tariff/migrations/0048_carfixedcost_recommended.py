from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tariff', '0047_carfixedcost_per_day'),
    ]

    operations = [
        migrations.AddField(
            model_name='carfixedcost',
            name='recommended',
            field=models.BooleanField(default=True, verbose_name='Recomendado (pre-tildado en cotizador)'),
        ),
    ]
