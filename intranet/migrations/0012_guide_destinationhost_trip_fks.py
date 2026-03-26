from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('intranet', '0011_add_margin_reviewed'),
    ]

    operations = [
        migrations.CreateModel(
            name='Guide',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('email', models.EmailField(blank=True, default='')),
                ('notes', models.CharField(blank=True, default='', max_length=300)),
            ],
            options={
                'verbose_name': 'Guía',
                'verbose_name_plural': 'Guías',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='DestinationHost',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('location', models.CharField(blank=True, default='', max_length=200)),
                ('email', models.EmailField(blank=True, default='')),
                ('notes', models.CharField(blank=True, default='', max_length=300)),
            ],
            options={
                'verbose_name': 'Destination Host',
                'verbose_name_plural': 'Destination Hosts',
                'ordering': ['name'],
            },
        ),
        migrations.AddField(
            model_name='trip',
            name='guide_fk',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='trips',
                to='intranet.guide',
                verbose_name='Guía (perfil)',
            ),
        ),
        migrations.AddField(
            model_name='trip',
            name='dh_fk',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='trips',
                to='intranet.destinationhost',
                verbose_name='DH (perfil)',
            ),
        ),
    ]
