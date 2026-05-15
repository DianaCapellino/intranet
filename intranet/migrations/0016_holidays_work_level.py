from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('intranet', '0015_absence_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='holidays',
            name='work_level',
            field=models.CharField(
                choices=[('none', 'No se trabaja'), ('half', 'Medio día'), ('full', 'Día completo')],
                default='none',
                max_length=8,
            ),
        ),
    ]
