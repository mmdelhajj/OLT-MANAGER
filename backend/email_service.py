"""Transactional email — provider-agnostic (Phase 2.6).

Switch providers by setting EMAIL_PROVIDER to one of: postmark, resend,
smtp, console (default for dev).

All callers use::

    from email_service import send_email
    send_email(
        to="alice@example.com",
        template="verify_email",
        context={"verify_url": "https://app.oltmanager.io/verify/xyz"},
    )

Templates live under `backend/templates/email/<name>.html` and
`<name>.subject.txt`. Both are Jinja2 strings rendered with `context`.
"""
from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER", "console").lower()
EMAIL_FROM = os.getenv("EMAIL_FROM", "OLT Manager <noreply@oltmanager.io>")

TEMPLATES_DIR = Path(__file__).parent / "templates" / "email"


def _render(name: str, context: dict) -> tuple[str, str]:
    """Render <name>.subject.txt and <name>.html with the given context."""
    try:
        from jinja2 import Environment, FileSystemLoader, select_autoescape
    except ImportError:
        # Jinja2 ships with FastAPI as a transitive dep; if it's missing,
        # fall back to plain string formatting so dev still works.
        subject = (TEMPLATES_DIR / f"{name}.subject.txt").read_text().strip()
        body = (TEMPLATES_DIR / f"{name}.html").read_text()
        return subject % context, body % context

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    subject = env.get_template(f"{name}.subject.txt").render(**context).strip()
    body = env.get_template(f"{name}.html").render(**context)
    return subject, body


def send_email(to: str, template: str, context: Optional[dict] = None) -> bool:
    """Send a templated email. Returns True on apparent success.

    On the `console` provider this just logs the rendered message — perfect
    for dev and CI without needing real SMTP credentials.
    """
    context = context or {}
    try:
        subject, body = _render(template, context)
    except Exception as e:
        logger.error(f"[email] Failed to render template {template}: {e}")
        return False

    provider = EMAIL_PROVIDER
    try:
        if provider == "postmark":
            return _send_postmark(to, subject, body)
        elif provider == "resend":
            return _send_resend(to, subject, body)
        elif provider == "smtp":
            return _send_smtp(to, subject, body)
        else:
            logger.info(
                f"[email/console] To: {to}\n  Subject: {subject}\n  Body:\n{body}"
            )
            return True
    except Exception as e:
        logger.error(f"[email/{provider}] Send to {to} failed: {e}")
        return False


def _send_postmark(to: str, subject: str, html: str) -> bool:
    import requests

    token = os.environ["POSTMARK_API_TOKEN"]
    r = requests.post(
        "https://api.postmarkapp.com/email",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Postmark-Server-Token": token,
        },
        json={
            "From": EMAIL_FROM,
            "To": to,
            "Subject": subject,
            "HtmlBody": html,
            "MessageStream": "outbound",
        },
        timeout=10,
    )
    r.raise_for_status()
    return True


def _send_resend(to: str, subject: str, html: str) -> bool:
    import requests

    token = os.environ["RESEND_API_KEY"]
    r = requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {token}"},
        json={"from": EMAIL_FROM, "to": [to], "subject": subject, "html": html},
        timeout=10,
    )
    r.raise_for_status()
    return True


def _send_smtp(to: str, subject: str, html: str) -> bool:
    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")

    msg = EmailMessage()
    msg["From"] = EMAIL_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content("HTML email — please use an HTML-capable client.")
    msg.add_alternative(html, subtype="html")

    with smtplib.SMTP(host, port) as s:
        s.starttls()
        if user and password:
            s.login(user, password)
        s.send_message(msg)
    return True
