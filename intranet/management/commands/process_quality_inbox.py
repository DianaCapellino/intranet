"""
Management command: process_quality_inbox

Polls INBOX for emails carrying the Gmail 'Calidad' label, stores new ones as
FeedbackInboxItem (status=pendiente), archives them, then runs AI processing.

This is intentionally identical to the calidad_fetch_inbox view so both paths
behave the same way.

Usage:
    python manage.py process_quality_inbox
"""

import os
import re
from datetime import timezone as dt_timezone

from django.core.management.base import BaseCommand
from dotenv import load_dotenv
from imap_tools import MailBox

from tariff.models import FeedbackInboxItem

QUALITY_LABEL = "Calidad"


def _get_message_id(msg):
    raw = msg.headers.get("message-id") or msg.headers.get("Message-ID") or []
    if isinstance(raw, list) and raw:
        return raw[0].strip()
    if isinstance(raw, str):
        return raw.strip()
    return f"uid-{msg.uid}"


def _get_body(msg):
    return msg.text.strip() if msg.text else ""


def _gmail_archive(mb, uids):
    """Move messages to the Gmail All Mail folder (archives from INBOX).
    Detects the correct folder by special-use flag since the name varies by language."""
    all_mail_folder = None
    try:
        for f in mb.folder.list():
            flags = getattr(f, 'flags', ()) or ()
            if '\\All' in flags or '\\AllMail' in flags:
                all_mail_folder = f.name
                break
        if not all_mail_folder:
            for f in mb.folder.list():
                name_lower = (f.name or '').lower()
                if 'all mail' in name_lower or 'todos' in name_lower or 'all messages' in name_lower:
                    all_mail_folder = f.name
                    break
    except Exception:
        pass

    if all_mail_folder:
        mb.move(uids, all_mail_folder)
    else:
        mb.flag(uids, ['\\Seen'], True)


class Command(BaseCommand):
    help = "Importa emails nuevos de INBOX con etiqueta 'Calidad' y los procesa con IA."

    def handle(self, *args, **kwargs):
        load_dotenv(override=True)
        username = os.environ.get("MAIL_USERNAME")
        password = os.environ.get("MAIL_PASSWORD")
        server   = os.environ.get("MAIL_SERVER")

        if not all([username, password, server]):
            self.stderr.write("Faltan variables de entorno MAIL_USERNAME / MAIL_PASSWORD / MAIL_SERVER.")
            return

        self.stdout.write(f"Conectando a {server} como {username}…")

        imported = 0
        skipped  = 0
        errors   = 0

        try:
            # Login to INBOX — same as the manual button in the view
            with MailBox(server).login(username, password, "INBOX") as mb:
                to_archive = []

                # For Gmail: fetch only messages that also carry the Calidad label.
                # This avoids reading archived emails (those are not in INBOX).
                label_criterion = (
                    f'X-GM-LABELS "{QUALITY_LABEL}"'
                    if "gmail" in (server or "").lower()
                    else "ALL"
                )

                for msg in mb.fetch(label_criterion, mark_seen=False, bulk=True):
                    message_id = _get_message_id(msg)

                    if FeedbackInboxItem.objects.filter(gmail_message_id=message_id).exists():
                        # Already imported — archive it so it leaves the inbox
                        to_archive.append(msg.uid)
                        skipped += 1
                        continue

                    from_raw = msg.from_ or ""
                    m = re.search(r"<([^>]+)>", from_raw)
                    sender = m.group(1).lower() if m else from_raw.lower().strip()

                    received_at = msg.date
                    if received_at and received_at.tzinfo is None:
                        received_at = received_at.replace(tzinfo=dt_timezone.utc)

                    try:
                        FeedbackInboxItem.objects.create(
                            received_at=received_at,
                            email_subject=msg.subject or "",
                            email_body=_get_body(msg),
                            email_sender=sender,
                            gmail_label="INBOX",
                            gmail_message_id=message_id,
                            status="pendiente",
                        )
                        imported += 1
                        to_archive.append(msg.uid)
                        self.stdout.write(f"  + Guardado: {sender} — {(msg.subject or '')[:60]}")
                    except Exception as e:
                        errors += 1
                        self.stderr.write(f"  ! Error guardando {message_id}: {e}")

                # Archive in the same connection — UIDs are valid here
                if to_archive:
                    try:
                        _gmail_archive(mb, to_archive)
                        self.stdout.write(f"  Archivados {len(to_archive)} emails desde INBOX.")
                    except Exception as e:
                        self.stderr.write(f"  ! Error archivando: {e}")

        except Exception as e:
            self.stderr.write(f"Error conectando al buzón: {e}")
            return

        self.stdout.write(self.style.SUCCESS(
            f"\nImportados: {imported} | Ya existían: {skipped} | Errores: {errors}"
        ))

        if imported > 0:
            self.stdout.write("-" * 30)
            self.stdout.write("Procesando con IA...")
            from tariff.quality_ai import process_all_pending
            ai_ok, ai_err = process_all_pending(stdout=self.stdout)
            self.stdout.write(self.style.SUCCESS(
                f"IA: {ai_ok} procesados | {ai_err} errores"
            ))
