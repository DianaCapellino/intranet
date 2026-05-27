from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('intranet', '0019_notificationpreference'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='show_in_client_team',
            field=models.BooleanField(default=True),
        ),
    ]
