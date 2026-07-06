from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('intranet', '0028_revision_feature'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='chat_webhook_url',
            field=models.URLField(blank=True, default='', verbose_name='Google Chat Webhook URL'),
        ),
    ]
