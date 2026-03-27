from datetime import date

from django.core.management import call_command
from django.core.management.base import BaseCommand

from intranet.models import Entry
from intranet.utils import update_entries, send_margin_warnings, send_margin_warning_manager, sync_from_tourplan_db


class Command(BaseCommand):
    help = "Ejecuta tareas diarias. Los miércoles también envía mails de rentabilidad."

    def handle(self, *args, **kwargs):

        # First task
        self.stdout.write("Actualizando colores...")
        result = update_entries()
        self.stdout.write(self.style.SUCCESS(f"Actualizados los colores - {result}"))

        self.stdout.write("-" * 30)

        # Second task
        self.stdout.write("Actualizando respuestas...")
        for entry in Entry.objects.all():
            entry.update_response()
        self.stdout.write(self.style.SUCCESS("Actualizadas las respuestas"))

        today = date.today()
        is_wednesday = today.weekday() == 2
        is_first_wednesday = is_wednesday and today.day <= 7

        # Sync from Tourplan DB — every day
        self.stdout.write("-" * 30)
        self.stdout.write("Sincronizando con base de datos Tourplan...")
        try:
            updated, not_found = sync_from_tourplan_db()
            self.stdout.write(self.style.SUCCESS(
                f"Tourplan sync: {updated} viajes actualizados, {not_found} en Tourplan sin match en la app"
            ))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error en Tourplan sync: {e}"))

        # Quality inbox — every day
        self.stdout.write("-" * 30)
        self.stdout.write("Procesando bandeja de calidad...")
        call_command("process_quality_inbox")

        # Margin warnings to sellers — every Wednesday
        if is_wednesday:
            self.stdout.write("-" * 30)
            self.stdout.write("Enviando mails de rentabilidad a vendedores...")
            send_margin_warnings()
            self.stdout.write(self.style.SUCCESS("Mails de rentabilidad enviados a vendedores"))
        else:
            self.stdout.write(f"Hoy no es miércoles ({today.strftime('%A')}), se omiten los mails de rentabilidad.")

        # Margin warning to manager — only on the first Wednesday of the month
        if is_first_wednesday:
            self.stdout.write("-" * 30)
            self.stdout.write("Enviando mail de rentabilidad a manager (primer miércoles del mes)...")
            send_margin_warning_manager()
            self.stdout.write(self.style.SUCCESS("Mail de rentabilidad enviado a manager"))
        elif is_wednesday:
            self.stdout.write(f"Miércoles {today.day}, no es el primero del mes, se omite el mail al manager.")
