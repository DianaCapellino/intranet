from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('tariff', '0022_supplier_default_exchange'),
    ]

    operations = [
        migrations.AddField(
            model_name='fixedratecost',
            name='supplier',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='fixed_rate_costs',
                to='tariff.supplier',
            ),
        ),
        migrations.RemoveField(
            model_name='fixedratecost',
            name='location',
        ),
    ]
