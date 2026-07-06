from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('intranet', '0029_user_chat_webhook'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='chat_user_id',
            field=models.CharField(blank=True, default='', max_length=64, verbose_name='Google Chat User ID'),
        ),
    ]
