from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('tariff', '0037_merge_20260604_1456'),
        ('tariff', '0037_populate_product_tp_location_code'),
    ]

    operations = [
        migrations.AddField(
            model_name='supplier',
            name='highlight',
            field=models.CharField(blank=True, default='', max_length=500),
        ),
        migrations.AddField(
            model_name='supplier',
            name='highlight_sustentability',
            field=models.CharField(blank=True, default='', max_length=500),
        ),
        migrations.AddField(
            model_name='supplier',
            name='room_quantity',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='supplier',
            name='inclusions',
            field=models.CharField(blank=True, default='', max_length=500),
        ),
        migrations.AddField(
            model_name='supplier',
            name='bedding',
            field=models.CharField(blank=True, default='', max_length=300),
        ),
        migrations.CreateModel(
            name='SustainableAction',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category', models.CharField(choices=[
                    ('WASTE', 'Wastes / Recycle'),
                    ('ENERGY', 'Energy'),
                    ('PURCHASING', 'Purchasing / Efficiency'),
                    ('SOCIAL', 'Social / Culture'),
                    ('SOIL', 'Soil / Food / Environment'),
                    ('GUEST', 'Guest Participation'),
                    ('OTHER', 'Other'),
                ], max_length=20)),
                ('description', models.TextField()),
                ('supplier', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='sustainable_actions',
                    to='tariff.supplier',
                )),
            ],
            options={
                'ordering': ['category'],
            },
        ),
    ]
