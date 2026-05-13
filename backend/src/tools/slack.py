# =============================================================================
# PH Agent Hub — Slack Tool Factory
# =============================================================================
# Send messages to Slack channels via webhook or bot token.
#
# Dependencies: httpx (already installed)
# =============================================================================

import logging
from typing import Any

import httpx
from agent_framework import tool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_TIMEOUT: float = 15.0
SLACK_API_BASE: str = "https://slack.com/api"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_token(tool_config: dict) -> str:
    """Resolve and decrypt the bot token or webhook URL from config."""
    from ..core.encryption import decrypt

    token = tool_config.get("bot_token", "") or tool_config.get("token", "")
    if not token:
        return ""

    try:
        return decrypt(token)
    except Exception:
        return token


def _resolve_webhook(tool_config: dict) -> str:
    """Resolve and decrypt the webhook URL from config."""
    from ..core.encryption import decrypt

    webhook = tool_config.get("webhook_url", "")
    if not webhook:
        return ""

    try:
        return decrypt(webhook)
    except Exception:
        return webhook


# ---------------------------------------------------------------------------
# Tool factory
# ---------------------------------------------------------------------------


def build_slack_tools(tool_config: dict | None = None) -> list:
    """Return a list of MAF @tool-decorated async functions for Slack.

    Supports both webhook URLs (simplest) and bot tokens (more features).

    Args:
        tool_config: ``Tool.config`` JSON dict.  May include:
            - ``webhook_url`` (str): Slack incoming webhook URL (encrypted or plaintext)
            - ``bot_token`` (str): Slack bot token (xoxb-...) for chat.postMessage
            - ``default_channel`` (str): default channel to send messages to
            - ``allowed_channels`` (list[str]): channel allowlist (empty = all allowed)

    Returns:
        A list of callables ready to pass to ``Agent(tools=...)``.
    """
    config = tool_config or {}
    webhook_url: str = _resolve_webhook(config)
    bot_token: str = _resolve_token(config)
    default_channel: str = config.get("default_channel", "general")
    allowed_channels: list[str] = config.get("allowed_channels", [])

    @tool
    async def send_slack_message(channel: str | None = None, text: str = "") -> dict:
        """Send a message to a Slack channel.

        Uses either a webhook URL or bot token configured in the tool settings.
        Supports Markdown formatting in messages.

        Args:
            channel: The Slack channel to send to (e.g., "#general", "@username").
                     Uses the default channel from config if not specified.
            text: The message text to send. Supports Slack mrkdwn formatting
                  (*bold*, _italic_, `code`, ```code blocks```, etc.).

        Returns:
            A dict with:
            - ``channel``: the channel the message was sent to
            - ``ts``: Slack message timestamp (if available)
            - ``status``: "ok" or "error"
            - ``error``: error message if sending failed
        """
        target_channel = channel or default_channel

        if not text or not text.strip():
            return {"error": "No message text provided", "status": "error"}

        # Check channel allowlist
        if allowed_channels:
            ch_name = target_channel.lstrip("#@")
            if ch_name not in allowed_channels and target_channel not in allowed_channels:
                return {
                    "error": f"Channel '{target_channel}' is not in the allowed list",
                    "status": "error",
                }

        # ------------------------------------------------------------------
        # Webhook path (simplest)
        # ------------------------------------------------------------------
        if webhook_url:
            if not webhook_url.startswith("https://hooks.slack.com/"):
                return {"error": "Invalid webhook URL", "status": "error"}

            payload = {
                "text": text,
            }
            if target_channel and target_channel != default_channel:
                payload["channel"] = target_channel

            try:
                async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                    response = await client.post(
                        webhook_url,
                        json=payload,
                    )

                    if response.status_code == 200:
                        logger.info("Slack message sent to %s via webhook", target_channel)
                        return {
                            "channel": target_channel,
                            "status": "ok",
                            "method": "webhook",
                        }
                    else:
                        body = response.text[:300]
                        logger.warning("Slack webhook returned %d: %s", response.status_code, body)
                        return {
                            "error": f"Slack webhook failed (HTTP {response.status_code}): {body}",
                            "status": "error",
                        }
            except Exception as exc:
                logger.error("Slack webhook failed: %s", exc)
                return {"error": f"Failed to send Slack message: {str(exc)}", "status": "error"}

        # ------------------------------------------------------------------
        # Bot token path (chat.postMessage)
        # ------------------------------------------------------------------
        if bot_token:
            if not bot_token.startswith("xoxb-"):
                return {"error": "Invalid bot token (must start with xoxb-)", "status": "error"}

            headers = {
                "Authorization": f"Bearer {bot_token}",
                "Content-Type": "application/json",
            }

            payload = {
                "channel": target_channel,
                "text": text,
                "mrkdwn": True,
            }

            try:
                async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                    response = await client.post(
                        f"{SLACK_API_BASE}/chat.postMessage",
                        json=payload,
                        headers=headers,
                    )

                    data = response.json()

                    if response.status_code == 200 and data.get("ok"):
                        logger.info("Slack message sent to %s via bot token", target_channel)
                        return {
                            "channel": data.get("channel", target_channel),
                            "ts": data.get("ts", ""),
                            "status": "ok",
                            "method": "bot_token",
                        }
                    else:
                        error_msg = data.get("error", f"HTTP {response.status_code}")
                        logger.warning("Slack API error: %s", error_msg)
                        return {
                            "error": f"Slack API error: {error_msg}",
                            "status": "error",
                        }
            except Exception as exc:
                logger.error("Slack bot token request failed: %s", exc)
                return {"error": f"Failed to send Slack message: {str(exc)}", "status": "error"}

        # ------------------------------------------------------------------
        # No credentials configured
        # ------------------------------------------------------------------
        return {
            "error": (
                "Slack is not configured. Please set either a webhook_url or "
                "bot_token in the tool config."
            ),
            "status": "error",
        }

    return [send_slack_message]
