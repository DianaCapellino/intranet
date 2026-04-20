"""
Management command: process_quality_inbox

Polls the 'calidad' Gmail label on aliwenintranet@gmail.com and stores new
emails as FeedbackInboxItem (status=pendiente) for later AI processing.

Usage:
    python manage.py process_quality_inbox
"""

import os
from datetime import timezone as dt_timezone

from django.core.management.base import BaseCommand
from dotenv import load_dotenv
from imap_tools import MailBox

from tariff.models import FeedbackInboxItem

QUALITY_LABEL = "Calidad"


def _get_message_id(msg):
    """Extract the RFC Message-ID header, falling back to UID."""
    raw = msg.headers.get("message-id") or msg.headers.get("Message-ID") or []
    if isinstance(raw, list) and raw:
        return raw[0].strip()
    if isinstance(raw, str):
        return raw.strip()
    return f"uid-{msg.uid}"


def _get_body(msg):
    """Return plain text body only. Ignores HTML to keep storage small."""
    if msg.text:
        return msg.text.strip()
    return ""


class Command(BaseCommand):
    help = "Importa emails nuevos del label 'calidad' de Gmail a FeedbackInboxItem."

    def handle(self, *args, **kwargs):
        load_dotenv(override=True)
        username = os.environ.get("MAIL_USERNAME")
        password = os.environ.get("MAIL_PASSWORD")
        server   = os.environ.get("MAIL_SERVER")

        if not all([username, password, server]):
            self.stderr.write("Faltan variables de entorno MAIL_USERNAME / MAIL_PASSWORD / MAIL_SERVER.")
            return

        self.stdout.write(f"Conectando a {server} como {username}…")

        imported              = 0
        skipped               = 0
        errors                = 0
        to_archive            = []
        message_ids_to_archive = set()

        try:
            with MailBox(server).login(username, password, QUALITY_LABEL) as mb:
                # Fetch all unseen emails in the label
                for msg in mb.fetch(mark_seen=False, bulk=True):
                    message_id = _get_message_id(msg)

                    if FeedbackInboxItem.objects.filter(gmail_message_id=message_id).exists():
                        skipped += 1
                        to_archive.append(msg.uid)
                        message_ids_to_archive.add(message_id)
                        continue

                    # Normalize sender
                    import re
                    from_raw = msg.from_ or ""
                    m = re.search(r"<([^>]+)>", from_raw)
                    sender = m.group(1).lower() if m else from_raw.lower().strip()

                    # Received date — ensure timezone-aware
                    received_at = msg.date
                    if received_at and received_at.tzinfo is None:
                        received_at = received_at.replace(tzinfo=dt_timezone.utc)

                    try:
                        FeedbackInboxItem.objects.create(
                            received_at=received_at,
                            email_subject=msg.subject or "",
                            email_body=_get_body(msg),
                            email_sender=sender,
                            gmail_label=QUALITY_LABEL,
                            gmail_message_id=message_id,
                            status="pendiente",
                        )
                        imported += 1
                        to_archive.append(msg.uid)
                        message_ids_to_archive.add(message_id)
                        self.stdout.write(f"  + Guardado: {sender} — {msg.subject[:60]}")
                    except Exception as e:
                        errors += 1
                        self.stderr.write(f"  ! Error guardando {message_id}: {e}")


        except Exception as e:
            self.stderr.write(f"Error conectando al buzón '{QUALITY_LABEL}': {e}")
            return

        # Remove emails from INBOX (Gmail "archive") while keeping the Calidad label.
        if message_ids_to_archive:
            try:
                with MailBox(server).login(username, password, "INBOX") as mb_inbox:
                    inbox_uids = [
                        msg.uid
                        for msg in mb_inbox.fetch(mark_seen=False, bulk=True)
                        if _get_message_id(msg) in message_ids_to_archive
                    ]
                    if inbox_uids:
                        mb_inbox.move(inbox_uids, "[Gmail]/All Mail")
                        self.stdout.write(f"  Archivados {len(inbox_uids)} emails desde INBOX.")
                    else:
                        self.stdout.write("  (Ningún email encontrado en INBOX para archivar.)")
            except Exception as e:
                self.stderr.write(f"  ! Error archivando desde INBOX: {e}")

        self.stdout.write(self.style.SUCCESS(
            f"\nImportados: {imported} | Ya existían: {skipped} | Errores: {errors}"
        ))

        # Auto-process new items with AI
        if imported > 0:
            self.stdout.write("-" * 30)
            self.stdout.write("Procesando con IA...")
            from tariff.quality_ai import process_all_pending
            ai_ok, ai_err = process_all_pending(stdout=self.stdout)
            self.stdout.write(self.style.SUCCESS(
                f"IA: {ai_ok} procesados | {ai_err} errores"
            ))
