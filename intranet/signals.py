from django.contrib.auth.signals import user_logged_out
from django.dispatch import receiver


@receiver(user_logged_out)
def cleanup_uploaded_csvs(sender, request, user, **kwargs):
    """Delete all uploaded CSV files from disk and DB on logout."""
    from intranet.models import CsvFileTourplanFiles
    from tariff.models import CsvFileTourplan

    for model in (CsvFileTourplanFiles, CsvFileTourplan):
        for obj in model.objects.all():
            obj.file_name.delete(save=False)
        model.objects.all().delete()
