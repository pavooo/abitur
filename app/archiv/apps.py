from django.apps import AppConfig


class ArchivConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "archiv"
    verbose_name = "Archiv"

    def ready(self):
        from . import signals  # noqa: F401
