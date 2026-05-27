from datetime import date

from django.core.management import call_command
from django.core.management.base import BaseCommand

from intranet.models import Entry
from intranet.utils import update_entries, send_margin_warnings, send_margin_warning_manager, sync_from_tourplan_db, send_holiday_reminder


class Command(BaseCommand):
    help = "Ejecuta tareas diarias. Los miércoles también envía mails de rentabilidad."

    def handle(self, *args, **kwargs):

        # Tourplan DB sync
        self.stdout.write("Sincronizando datos desde Tourplan...")
        try:
            updated, no_tp1, no_tp2, no_tp3, not_in_app = sync_from_tourplan_db()
            self.stdout.write(self.style.SUCCESS(
                f"Tourplan sincronizado — {updated} viaje(s) actualizados"
            ))
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"Error al sincronizar Tourplan: {exc}"))

        self.stdout.write("-" * 30)

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
        is_monday = today.weekday() == 0
        is_first_wednesday = is_wednesday and today.day <= 7

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
        if is_monday:  # Monday - warnings for Marisol
            from intranet.utils import send_weekly_roster
            send_weekly_roster()

        # Holiday reminder — every day, fires only when a holiday starts in exactly 7 days
        self.stdout.write("-" * 30)
        self.stdout.write("Verificando recordatorio de feriado...")
        try:
            send_holiday_reminder()
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"Error al enviar recordatorio de feriado: {exc}"))