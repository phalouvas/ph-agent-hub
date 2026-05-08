# =============================================================================
# PH Agent Hub — Datetime Tool Factory
# =============================================================================
# Builds a MAF @tool-decorated async function that returns the current
# date and time for a given IANA timezone (defaults to UTC).
# =============================================================================

import logging
from datetime import datetime
from zoneinfo import ZoneInfo, available_timezones

from agent_framework import tool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool factory
# ---------------------------------------------------------------------------


def build_datetime_tools(tool_config: dict | None = None) -> list:
    """Return a list containing the MAF @tool-decorated current_time function.

    Args:
        tool_config: Optional ``Tool.config`` JSON dict.  May include a
            ``default_timezone`` key to override the fallback timezone.

    Returns:
        A list with a single callable ready to pass to ``Agent(tools=...)``.
    """
    config = tool_config or {}
    default_tz = config.get("default_timezone", "UTC")

    @tool
    async def current_time(timezone: str | None = None) -> dict:
        """Get the current date and time.

        Args:
            timezone: Optional IANA timezone name (e.g. "America/New_York",
                "Europe/London", "Asia/Tokyo").  Defaults to the server's
                configured default timezone (usually UTC).

        Returns:
            A dict with keys:
            - ``iso``: ISO 8601 datetime string with timezone offset
            - ``date``: date in YYYY-MM-DD format
            - ``time``: time in HH:MM:SS format
            - ``timezone``: the IANA timezone used
            - ``utc_offset``: UTC offset string (e.g. "+05:30")
            - ``day_of_week``: full weekday name
            - ``unix_timestamp``: Unix timestamp (seconds since epoch)
        """
        tz_name = timezone or default_tz

        # Validate timezone
        if tz_name not in available_timezones():
            logger.warning(
                "current_time called with unknown timezone '%s', falling back to UTC",
                tz_name,
            )
            tz_name = "UTC"

        tz = ZoneInfo(tz_name)
        now = datetime.now(tz)

        result = {
            "iso": now.isoformat(),
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "timezone": tz_name,
            "utc_offset": now.strftime("%z"),
            "day_of_week": now.strftime("%A"),
            "unix_timestamp": int(now.timestamp()),
        }

        logger.debug("current_time(%s) → %s", timezone, result["iso"])
        return result

    return [current_time]
