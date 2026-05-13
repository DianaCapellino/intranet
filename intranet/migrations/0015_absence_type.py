from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('intranet', '0014_add_trip_tp_notes'),
    ]

    operations = [
        migrations.AddField(
            model_name='absence',
            name='type_absence',
            field=models.CharField(
                choices=[
                    ('Vacaciones', 'Vacaciones'),
                    ('Beneficio Vacaciones', 'Beneficio Vacaciones'),
                    ('Compensatorios', 'Compensatorios'),
                    ('Cumpleaños', 'Cumpleaños'),
                    ('Cumpleaños en baja', 'Cumpleaños en baja'),
                    ('Exámenes/Día de Estudio', 'Exámenes/Día de Estudio'),
                    ('FAM/Trabajando fuera ofi', 'FAM/Trabajando fuera ofi'),
                    ('Feriado trabajado', 'Feriado trabajado'),
                    ('Semana home', 'Semana home'),
                    ('Sin goce de sueldo', 'Sin goce de sueldo'),
                    ('Viernes OFF alta', 'Viernes OFF alta'),
                ],
                default='Vacaciones',
                max_length=64,
            ),
        ),
    ]
