"""
Management command: migrate_calidad_emails

One-time migration: reads ALL emails with label "Calidad" from
diana@aliwenincoming.com.ar, runs AI analysis, and auto-confirms
feedbacks where possible.

Auto-confirm rules per target_type:
  supplier    → match existing supplier or create provisional → auto-confirm
  user        → match existing user → auto-confirm (skip if not found)
  aliwen_team → auto-confirm (assigns trip seller + operator)
  guide       → auto-confirm ONLY if guide_id already matched by AI
  dh          → auto-confirm ONLY if dh_id already matched by AI
  entity      → auto-confirm ONLY if entity_id already matched by AI

  If ANY target requires creating a NEW guide / DH / entity,
  the entire inbox item is left as pending for manual review.

Usage:
    python manage.py migrate_calidad_emails \\
        --username diana@aliwenincoming.com.ar \\
        --password <app-password> \\
        [--server imap.gmail.com] \\
        [--dry-run] \\
        [--skip-import] \\
        [--skip-ai] \\
        [--skip-confirm]
"""

import os
import re
from datetime import timezone as dt_timezone

from django.core.management.base import BaseCommand
from dotenv import load_dotenv

QUALITY_LABEL = "Calidad"

# ── Email helpers ────────────────────────────────────────────────────────────

def _get_message_id(msg):
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


# ── Auto-confirm logic ───────────────────────────────────────────────────────

def _get_or_create_provisional_supplier(name):
    from tariff.models import Supplier
    s, _ = Supplier.objects.get_or_create(
        name=name, is_provisional=True,
        defaults={
            'code': '', 'children_ranking': 1, 'disabled_ranking': 1,
            'sustentability_ranking': 1, 'order': 9999,
            'margin': 0, 'margin_info': 'Regular', 'group': None, 'note': '',
        }
    )
    return s


def _needs_manual_creation(t):
    """Return True if this target requires creating a brand-new guide/dh/entity."""
    target_type = t.get('target_type')
    if target_type == 'guide' and not t.get('guide_id'):
        return True
    if target_type == 'dh' and not t.get('dh_id'):
        return True
    if target_type == 'entity' and not t.get('entity_id'):
        return True
    return False


def _resolve_target(t, dry_run=False):
    """
    Resolve a single target dict for auto-confirm.
    Returns an updated copy of t with IDs filled in, or None if unresolvable.
    Also returns a human-readable status string.
    """
    from tariff.quality_ai import try_match_supplier, try_match_user_by_name
    from intranet.models import Guide, DestinationHost
    from tariff.models import FeedbackEntity

    t = dict(t)
    target_type = t.get('target_type')

    if target_type == 'supplier':
        sid = t.get('supplier_id')
        supplier = None
        if sid:
            from tariff.models import Supplier
            supplier = Supplier.objects.filter(pk=sid).first()
        if not supplier:
            supplier = try_match_supplier(t.get('name', ''))
        if supplier:
            t['supplier_id'] = supplier.pk
            return t, f"proveedor → {supplier.name}{'(provisional)' if supplier.is_provisional else ''}"
        else:
            # Create provisional
            name = (t.get('name') or 'Proveedor sin identificar').strip()
            if not dry_run:
                supplier = _get_or_create_provisional_supplier(name)
                t['supplier_id'] = supplier.pk
            return t, f"proveedor → PROVISIONAL: {name}"

    elif target_type == 'user':
        uid = t.get('user_id')
        user = None
        if uid:
            from intranet.models import User
            user = User.objects.filter(pk=uid).first()
        if not user:
            user = try_match_user_by_name(t.get('name', ''))
        if user:
            t['user_id'] = user.pk
            return t, f"usuario → {user.get_full_name() or user.username}"
        else:
            return None, f"usuario '{t.get('name')}' no encontrado — target omitido"

    elif target_type == 'aliwen_team':
        return t, "equipo Aliwen → auto-asignado"

    elif target_type == 'guide':
        gid = t.get('guide_id')
        if gid and Guide.objects.filter(pk=gid).exists():
            return t, f"guía id={gid} ya vinculado"
        return None, f"guía '{t.get('name')}' no vinculado — requiere creación manual"

    elif target_type == 'dh':
        dhid = t.get('dh_id')
        if dhid and DestinationHost.objects.filter(pk=dhid).exists():
            return t, f"DH id={dhid} ya vinculado"
        return None, f"DH '{t.get('name')}' no vinculado — requiere creación manual"

    elif target_type == 'entity':
        eid = t.get('entity_id')
        if eid and FeedbackEntity.objects.filter(pk=eid).exists():
            return t, f"entidad id={eid} ya vinculada"
        return None, f"entidad '{t.get('name')}' no vinculada — requiere creación manual"

    return t, f"tipo '{target_type}' → incluido"


def auto_confirm_item(item, dry_run=False, stdout=None):
    """
    Attempt to auto-confirm one FeedbackInboxItem.

    Returns:
      'confirmed'  – feedbacks created
      'partial'    – some targets confirmed, some skipped (guide/dh/entity unresolved)
      'skipped'    – all targets require manual creation
      'no_targets' – ai_analysis has no targets
    """
    from tariff.quality_ai import create_feedbacks_from_inbox

    analysis = item.ai_analysis or {}
    targets = analysis.get('targets', [])
    if not targets:
        return 'no_targets'

    confirmed_targets = []
    skipped_count = 0

    for t in targets:
        if _needs_manual_creation(t):
            skipped_count += 1
            if stdout:
                stdout.write(
                    f"      ⚠ {t.get('target_type')} '{t.get('name')}' — requiere creación manual (pendiente)"
                )
            continue

        resolved, status_msg = _resolve_target(t, dry_run=dry_run)
        if stdout:
            prefix = "      [dry-run] " if dry_run else "      "
            stdout.write(f"{prefix}↳ {status_msg}")
        if resolved is not None:
            confirmed_targets.append(resolved)

    if not confirmed_targets:
        return 'skipped'

    if not dry_run:
        create_feedbacks_from_inbox(item, confirmed_targets)

    if skipped_count > 0:
        return 'partial'
    return 'confirmed'


# ── Command ──────────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = (
        "Migración masiva: importa todos los emails del label 'Calidad' de "
        "diana@aliwenincoming.com.ar, analiza con IA y crea feedbacks automáticamente."
    )

    def add_arguments(self, parser):
        parser.add_argument('--username', default='', help='Email IMAP (default: CALIDAD_MAIL_USERNAME env)')
        parser.add_argument('--password', default='', help='Contraseña de app (default: CALIDAD_MAIL_PASSWORD env)')
        parser.add_argument('--server',   default='imap.gmail.com', help='Servidor IMAP (default: imap.gmail.com)')
        parser.add_argument('--dry-run',      action='store_true', help='Simula sin crear nada en la BD')
        parser.add_argument('--skip-import',  action='store_true', help='No conecta al buzón; usa items ya importados')
        parser.add_argument('--skip-ai',      action='store_true', help='No llama a la IA; usa análisis ya guardados')
        parser.add_argument('--force-ai',     action='store_true', help='Reananliza con IA incluso los items que ya tienen análisis')
        parser.add_argument('--skip-confirm', action='store_true', help='Solo importa + analiza, no crea feedbacks')

    def handle(self, *args, **options):
        load_dotenv(override=True)

        dry_run      = options['dry_run']
        skip_import  = options['skip_import']
        skip_ai      = options['skip_ai']
        force_ai     = options['force_ai']
        skip_confirm = options['skip_confirm']

        username = options['username'] or os.environ.get('CALIDAD_MAIL_USERNAME', '')
        password = options['password'] or os.environ.get('CALIDAD_MAIL_PASSWORD', '')
        server   = options['server']   or os.environ.get('CALIDAD_MAIL_SERVER', 'imap.gmail.com')

        if dry_run:
            self.stdout.write(self.style.WARNING("=== MODO DRY-RUN: no se guardará nada ==="))

        # ── Step 1: Import emails ────────────────────────────────────────────
        imported = skipped = errors = 0

        if not skip_import:
            if not username or not password:
                self.stderr.write(
                    "Faltan credenciales. Usá --username / --password "
                    "o las variables de entorno CALIDAD_MAIL_USERNAME / CALIDAD_MAIL_PASSWORD."
                )
                return

            self.stdout.write(f"\n── Paso 1: Importando emails de {username} (label: {QUALITY_LABEL}) ──")
            from imap_tools import MailBox
            from tariff.models import FeedbackInboxItem

            try:
                with MailBox(server).login(username, password, QUALITY_LABEL) as mb:
                    to_archive = []
                    for msg in mb.fetch(mark_seen=False, bulk=True):
                        message_id = _get_message_id(msg)

                        if FeedbackInboxItem.objects.filter(gmail_message_id=message_id).exists():
                            skipped += 1
                            to_archive.append(msg.uid)
                            continue

                        from_raw = msg.from_ or ""
                        m = re.search(r"<([^>]+)>", from_raw)
                        sender = m.group(1).lower() if m else from_raw.lower().strip()

                        received_at = msg.date
                        if received_at and received_at.tzinfo is None:
                            received_at = received_at.replace(tzinfo=dt_timezone.utc)

                        self.stdout.write(f"  + {sender} — {(msg.subject or '')[:70]}")

                        if not dry_run:
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
                            except Exception as e:
                                errors += 1
                                self.stderr.write(f"    ! Error guardando: {e}")
                        else:
                            imported += 1

                    if to_archive and not dry_run:
                        try:
                            mb.move(to_archive, '[Gmail]/All Mail')
                            self.stdout.write(f"  Archivados en Gmail: {len(to_archive)} emails")
                        except Exception as e:
                            self.stderr.write(f"  ! Error archivando emails: {e}")

            except Exception as e:
                self.stderr.write(f"Error conectando al buzón: {e}")
                return

            self.stdout.write(self.style.SUCCESS(
                f"  Importados: {imported} | Ya existían: {skipped} | Errores: {errors}"
            ))
        else:
            self.stdout.write("── Paso 1 omitido (--skip-import) ──")

        # ── Step 2: AI analysis ──────────────────────────────────────────────
        ai_ok = ai_err = 0

        if not skip_ai:
            self.stdout.write("\n── Paso 2: Análisis con IA ──")
            if force_ai:
                self.stdout.write(self.style.WARNING("  (--force-ai: reanaliza items ya procesados)"))
            from tariff.quality_ai import process_all_pending
            ai_ok, ai_err = process_all_pending(stdout=self.stdout, force=force_ai)
            self.stdout.write(self.style.SUCCESS(
                f"  IA: {ai_ok} procesados | {ai_err} errores"
            ))
        else:
            self.stdout.write("── Paso 2 omitido (--skip-ai) ──")

        # ── Step 3: Auto-confirm ─────────────────────────────────────────────
        if skip_confirm:
            self.stdout.write("── Paso 3 omitido (--skip-confirm) ──")
            return

        self.stdout.write("\n── Paso 3: Auto-confirmación de feedbacks ──")
        from tariff.models import FeedbackInboxItem

        pending = FeedbackInboxItem.objects.filter(
            status='pendiente',
            ai_analysis__isnull=False,
        )

        n_confirmed = n_partial = n_skipped = n_no_targets = 0

        for item in pending:
            subject = (item.email_subject or '(sin asunto)')[:60]
            self.stdout.write(f"\n  [{item.pk}] {subject}")

            result = auto_confirm_item(item, dry_run=dry_run, stdout=self.stdout)

            if result == 'confirmed':
                n_confirmed += 1
                self.stdout.write(self.style.SUCCESS("    → Confirmado"))
            elif result == 'partial':
                n_partial += 1
                self.stdout.write(self.style.WARNING("    → Confirmado parcialmente (algunos targets quedan pendientes)"))
            elif result == 'skipped':
                n_skipped += 1
                self.stdout.write(self.style.WARNING("    → Omitido (todos los targets requieren creación manual)"))
            elif result == 'no_targets':
                n_no_targets += 1
                self.stdout.write("    → Sin targets en análisis IA")

        self.stdout.write(self.style.SUCCESS(
            f"\n── Resumen auto-confirmación ──\n"
            f"  Confirmados:          {n_confirmed}\n"
            f"  Confirmados parcial:  {n_partial}\n"
            f"  Requieren revisión:   {n_skipped}\n"
            f"  Sin análisis IA:      {n_no_targets}\n"
        ))
