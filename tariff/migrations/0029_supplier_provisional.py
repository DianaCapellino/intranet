from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('tariff', '0028_feedback_guide_dh'),
    ]

    operations = [
        migrations.AddField(
            model_name='supplier',
            name='is_provisional',
            field=models.BooleanField(default=False, verbose_name='Provisional'),
        ),
        migrations.AlterField(
            model_name='supplier',
            name='order',
            field=models.PositiveIntegerField(default=9999),
        ),
        migrations.AlterField(
            model_name='supplier',
            name='group',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='group_products',
                to='tariff.suppliergroup',
            ),
        ),
    ]
