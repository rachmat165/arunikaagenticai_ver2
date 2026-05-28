import asyncio
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from src.config import settings


def _build_message(
    to: str | list[str],
    subject: str,
    body: str,
    cc: str | list[str] | None = None,
    reply_to: str | None = None,
    attachment_path: str | None = None,
) -> tuple[MIMEMultipart, list[str]]:
    # Use "mixed" when there's an attachment, otherwise "alternative"
    msg = MIMEMultipart("mixed" if attachment_path else "alternative")
    msg["From"] = formataddr(("Corsec ATG", settings.email_user))
    msg["To"] = ", ".join(to) if isinstance(to, list) else to
    msg["Subject"] = subject
    if cc:
        msg["Cc"] = ", ".join(cc) if isinstance(cc, list) else cc
    if reply_to:
        msg["Reply-To"] = reply_to

    msg.attach(MIMEText(body, "plain", "utf-8"))

    if attachment_path:
        from email.mime.base import MIMEBase
        from email import encoders
        import os
        with open(attachment_path, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f'attachment; filename="{os.path.basename(attachment_path)}"',
        )
        msg.attach(part)

    recipients: list[str] = list(to) if isinstance(to, list) else [to]
    if cc:
        recipients += list(cc) if isinstance(cc, list) else [cc]
    return msg, recipients


async def send_email(
    to: str | list[str],
    subject: str,
    body: str,
    cc: str | list[str] | None = None,
    attachment_path: str | None = None,
) -> dict:
    """Send email via SMTP SSL. Returns {'success': True} or {'error': str}."""

    def _send():
        msg, recipients = _build_message(to, subject, body, cc,
                                         attachment_path=attachment_path)
        with smtplib.SMTP_SSL(settings.email_host, settings.email_port, timeout=30) as server:
            server.login(settings.email_user, settings.email_password)
            server.sendmail(settings.email_user, recipients, msg.as_string())

    try:
        await asyncio.to_thread(_send)
        return {"success": True}
    except smtplib.SMTPAuthenticationError:
        return {"error": "Autentikasi gagal. Cek EMAIL_USER dan EMAIL_PASSWORD di .env"}
    except smtplib.SMTPRecipientsRefused as e:
        return {"error": f"Penerima ditolak: {e}"}
    except Exception as e:
        return {"error": str(e)}


async def test_smtp_connection() -> dict:
    """Test SMTP connection without sending email."""
    def _test():
        with smtplib.SMTP_SSL(settings.email_host, settings.email_port, timeout=10) as server:
            server.login(settings.email_user, settings.email_password)
            return server.noop()

    try:
        await asyncio.to_thread(_test)
        return {"success": True, "host": settings.email_host, "user": settings.email_user}
    except Exception as e:
        return {"error": str(e)}
