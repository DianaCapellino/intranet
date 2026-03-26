from django.apps import AppConfig


class IntranetConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'intranet'

    def ready(self):
        import intranet.signals  # noqa: F401
