# =============================================================================
# PH Agent Hub — Email Tool Factory
# =============================================================================
# Send emails via SMTP or SendGrid API.
# Credentials stored encrypted in tool.config.
#
# Dependencies: httpx (already installed), smtplib (stdlib)
# =============================================================================

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import httpx
from agent_framework import tool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_TIMEOUT: float = 30.0
SENDGRID_API_BASE: str = "https://api.sendgrid.com/v3"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_credentials(tool_config: dict) -> dict:
    """Resolve and decrypt credentials from config."""
    from ..core.encryption import decrypt

    creds = {}
    for key in ("smtp_password", "api_key", "smtp_username"):
        val = tool_config.get(key, "")
        if val:
            try:
                creds[key] = decrypt(val)
            except Exception:
                creds[key] = val

    # Pass through non-encrypted fields
    for key in ("smtp_host", "smtp_port", "from_email", "from_name", "provider"):
        if key in tool_config:
            creds[key] = tool_config[key]

    return creds


def _check_recipient_allowed(recipient: str, allowed_recipients: list[str] | None) -> bool:
    """Check if a recipient is in the allowlist. Empty list means all allowed."""
    if not allowed_recipients:
        return True

    recipient_lower = recipient.lower().strip()
    for pattern in allowed_recipients:
        pattern_lower = pattern.lower().strip()
        if pattern_lower == "*":
            return True
        # Support domain wildcards
        if pattern_lower.startswith("*@"):
            domain = pattern_lower[2:]
            if recipient_lower.endswith("@" + domain):
                return True
        if recipient_lower == pattern_lower:
            return True

    return False


def _build_email_message(
    to: str,
    subject: str,
    body: str,
    from_email: str,
    from_name: str = "",
    cc: str | None = None,
    is_html: bool = False,
) -> MIMEMultipart:
    """Build an email MIME message."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{from_email}>" if from_name else from_email
    msg["To"] = to
    if cc:
        msg["Cc"] = cc

    if is_html:
        msg.attach(MIMEText(body, "html", "utf-8"))
    else:
        # Convert plain text to simple HTML for better rendering
        html_body = body.replace("\n", "<br>\n")
        msg.attach(MIMEText(body, "plain", "utf-8"))
        msg.attach(MIMEText(
            f"<html><body><p>{html_body}</p></body></html>",
            "html", "utf-8",
        ))

    return msg


# ---------------------------------------------------------------------------
# Tool factory
# ---------------------------------------------------------------------------


def build_email_tools(tool_config: dict | None = None) -> list:
    """Return a list of MAF @tool-decorated async functions for email.

    Supports SMTP and SendGrid API.

    Args:
        tool_config: ``Tool.config`` JSON dict.  May include:
            - ``provider`` (str): "smtp" (default) or "sendgrid"
            - ``smtp_host`` (str): SMTP server hostname
            - ``smtp_port`` (int): SMTP port (default 587)
            - ``smtp_username`` (str): SMTP username (encrypted or plaintext)
            - ``smtp_password`` (str): SMTP password (encrypted or plaintext)
            - ``api_key`` (str): SendGrid API key (encrypted or plaintext)
            - ``from_email`` (str): Sender email address
            - ``from_name`` (str): Sender display name
            - ``allowed_recipients`` (list[str]): Recipient allowlist

    Returns:
        A list of callables ready to pass to ``Agent(tools=...)``.
    """
    config = tool_config or {}
    creds = _resolve_credentials(config)
    provider: str = creds.get("provider", "smtp").lower()
    from_email: str = creds.get("from_email", "")
    from_name: str = creds.get("from_name", "")
    allowed_recipients: list[str] = config.get("allowed_recipients", [])

    @tool
    async def send_email(
        to: str,
        subject: str,
        body: str,
        cc: str | None = None,
        is_html: bool = False,
    ) -> dict:
        """Send an email via SMTP or SendGrid.

        Args:
            to: Recipient email address (e.g., "user@example.com").
            subject: Email subject line.
            body: Email body content. Plain text by default; set is_html=True
                  for HTML content.
            cc: Optional CC recipient email address.
            is_html: Set to True if the body contains HTML (default False).

        Returns:
            A dict with:
            - ``to``: recipient email
            - ``subject``: email subject
            - ``status``: "ok" or "error"
            - ``error``: error message if sending failed
        """
        if not to or not to.strip():
            return {"error": "No recipient email provided", "status": "error"}
        if not subject or not subject.strip():
            return {"error": "No email subject provided", "status": "error"}
        if not body or not body.strip():
            return {"error": "No email body provided", "status": "error"}

        # Validate basic email format
        recipient = to.strip()
        if "@" not in recipient:
            return {"error": f"Invalid recipient email: {recipient}", "status": "error"}

        # Check recipient allowlist
        if not _check_recipient_allowed(recipient, allowed_recipients):
            return {
                "error": f"Recipient '{recipient}' is not in the allowed list",
                "status": "error",
            }

        # ------------------------------------------------------------------
        # SMTP path
        # ------------------------------------------------------------------
        if provider == "smtp":
            smtp_host = creds.get("smtp_host", "")
            smtp_port = int(creds.get("smtp_port", 587))
            smtp_username = creds.get("smtp_username", "")
            smtp_password = creds.get("smtp_password", "")

            if not smtp_host:
                return {
                    "error": "SMTP host not configured. Please set smtp_host in tool config.",
                    "status": "error",
                }
            if not from_email:
                return {
                    "error": "Sender email not configured. Please set from_email in tool config.",
                    "status": "error",
                }

            try:
                msg = _build_email_message(
                    to=recipient,
                    subject=subject.strip(),
                    body=body.strip(),
                    from_email=from_email,
                    from_name=from_name,
                    cc=cc.strip() if cc else None,
                    is_html=is_html,
                )

                # Send via SMTP (sync, wrapped in to_thread in the caller)
                def _smtp_send():
                    if smtp_port == 465:
                        server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=DEFAULT_TIMEOUT)
                    else:
                        server = smtplib.SMTP(smtp_host, smtp_port, timeout=DEFAULT_TIMEOUT)
                        server.starttls()

                    if smtp_username and smtp_password:
                        server.login(smtp_username, smtp_password)

                    server.send_message(msg)
                    server.quit()

                import asyncio
                await asyncio.to_thread(_smtp_send)

                logger.info("Email sent via SMTP to %s", recipient)
                return {
                    "to": recipient,
                    "subject": subject.strip(),
                    "status": "ok",
                    "provider": "smtp",
                }

            except smtplib.SMTPAuthenticationError:
                return {"error": "SMTP authentication failed. Check username and password.", "status": "error"}
            except smtplib.SMTPException as exc:
                logger.error("SMTP send failed: %s", exc)
                return {"error": f"SMTP error: {str(exc)}", "status": "error"}
            except Exception as exc:
                logger.error("Email send failed: %s", exc)
                return {"error": f"Failed to send email: {str(exc)}", "status": "error"}

        # ------------------------------------------------------------------
        # SendGrid path
        # ------------------------------------------------------------------
        elif provider == "sendgrid":
            api_key = creds.get("api_key", "")

            if not api_key:
                return {
                    "error": "SendGrid API key not configured. Please set api_key in tool config.",
                    "status": "error",
                }
            if not from_email:
                return {
                    "error": "Sender email not configured. Please set from_email in tool config.",
                    "status": "error",
                }

            payload = {
                "personalizations": [{
                    "to": [{"email": recipient}],
                    "subject": subject.strip(),
                }],
                "from": {
                    "email": from_email,
                    "name": from_name or from_email,
                },
                "content": [{
                    "type": "text/html" if is_html else "text/plain",
                    "value": body.strip(),
                }],
            }

            if cc:
                payload["personalizations"][0].setdefault("cc", []).append({"email": cc.strip()})

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }

            try:
                async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                    response = await client.post(
                        f"{SENDGRID_API_BASE}/mail/send",
                        json=payload,
                        headers=headers,
                    )

                    if response.status_code in (200, 201, 202):
                        logger.info("Email sent via SendGrid to %s", recipient)
                        return {
                            "to": recipient,
                            "subject": subject.strip(),
                            "status": "ok",
                            "provider": "sendgrid",
                        }
                    elif response.status_code == 401:
                        return {"error": "SendGrid authentication failed. Check your API key.", "status": "error"}
                    elif response.status_code == 403:
                        return {"error": "SendGrid access denied. Check your account permissions.", "status": "error"}
                    else:
                        body_text = response.text[:300]
                        logger.warning("SendGrid returned %d: %s", response.status_code, body_text)
                        return {
                            "error": f"SendGrid error (HTTP {response.status_code}): {body_text}",
                            "status": "error",
                        }

            except Exception as exc:
                logger.error("SendGrid send failed: %s", exc)
                return {"error": f"Failed to send email: {str(exc)}", "status": "error"}

        else:
            return {"error": f"Email provider '{provider}' is not supported", "status": "error"}

    return [send_email]
