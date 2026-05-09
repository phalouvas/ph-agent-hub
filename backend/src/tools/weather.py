# =============================================================================
# PH Agent Hub — Weather Tool Factory (wttr.in)
# =============================================================================
# Builds a MAF @tool-decorated async function that fetches current weather
# conditions and a forecast from the free, no-key wttr.in JSON API.
# =============================================================================

import logging
from urllib.parse import quote

import httpx
from agent_framework import tool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
WTTR_BASE: str = "https://wttr.in"
DEFAULT_TIMEOUT: float = 15.0


# ---------------------------------------------------------------------------
# Tool factory
# ---------------------------------------------------------------------------


def build_weather_tools(tool_config: dict | None = None) -> list:
    """Return a list containing the MAF @tool-decorated get_weather function.

    Args:
        tool_config: Optional ``Tool.config`` JSON dict.  May include:
            - ``timeout`` (float): request timeout in seconds (default 15)

    Returns:
        A list with a single callable ready to pass to ``Agent(tools=...)``.
    """
    config = tool_config or {}
    timeout: float = float(config.get("timeout", DEFAULT_TIMEOUT))

    @tool
    async def get_weather(location: str) -> dict:
        """Get current weather conditions and a short forecast for a location.

        Uses the free wttr.in service — no API key required.

        Args:
            location: City name (e.g. "London"), optionally with country code
                (e.g. "Paris,FR"), US ZIP code, airport code (e.g. "JFK"),
                or coordinates (e.g. "48.8566,2.3522").

        Returns:
            A dict with:
            - ``location``: resolved location name
            - ``current``: current conditions dict with keys like
              ``temp_C``, ``temp_F``, ``humidity``, ``weatherDesc``,
              ``windspeedKmph``, ``winddir16Point``, ``pressure``,
              ``visibility``, ``feelsLikeC``, ``uvIndex``
            - ``forecast``: list of daily forecast dicts (up to 3 days),
              each with ``date``, ``mintempC``, ``maxtempC``,
              ``avgtempC``, ``sunHour``, ``hourly`` list
            - ``source``: "wttr.in"
        """
        url = f"{WTTR_BASE}/{quote(location)}?format=j1"
        logger.info("get_weather: %s", location)

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(
                    url,
                    headers={"User-Agent": "ph-agent-hub/1.0"},
                )
            response.raise_for_status()
            data = response.json()
        except httpx.TimeoutException:
            logger.warning("get_weather timeout for %s", location)
            return {"location": location, "error": "Request timed out"}
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "get_weather HTTP %d for %s", exc.response.status_code, location
            )
            return {
                "location": location,
                "error": f"Location not found or API error (HTTP {exc.response.status_code})",
            }
        except Exception as exc:
            logger.exception("get_weather failed for %s", location)
            return {"location": location, "error": str(exc)}

        # Extract current conditions
        current_condition = data.get("current_condition", [{}])
        current = current_condition[0] if current_condition else {}

        # Normalize current fields to reasonable types
        def _float(v):
            try:
                return float(v)
            except (TypeError, ValueError):
                return None

        current_clean = {
            "temp_C": _float(current.get("temp_C")),
            "temp_F": _float(current.get("temp_F")),
            "feelsLikeC": _float(current.get("FeelsLikeC")),
            "humidity": _float(current.get("humidity")),
            "pressure": _float(current.get("pressure")),
            "visibility": _float(current.get("visibility")),
            "uvIndex": _float(current.get("uvIndex")),
            "windspeedKmph": _float(current.get("windspeedKmph")),
            "winddir16Point": current.get("winddir16Point", ""),
            "weatherDesc": (
                current.get("weatherDesc", [{}])[0].get("value", "")
                if current.get("weatherDesc")
                else ""
            ),
        }

        # Extract forecast (up to 3 days)
        weather_data = data.get("weather", [])[:3]
        forecast = []
        for day in weather_data:
            hourly = []
            for h in day.get("hourly", []):
                hourly.append({
                    "time": f"{h.get('time', '0')}00".zfill(4),
                    "tempC": _float(h.get("tempC")),
                    "weatherDesc": (
                        h.get("weatherDesc", [{}])[0].get("value", "")
                        if h.get("weatherDesc")
                        else ""
                    ),
                    "chanceofrain": _float(h.get("chanceofrain")),
                })
            forecast.append({
                "date": day.get("date", ""),
                "mintempC": _float(day.get("mintempC")),
                "maxtempC": _float(day.get("maxtempC")),
                "avgtempC": _float(day.get("avgtempC")),
                "sunHour": _float(day.get("sunHour")),
                "hourly": hourly,
            })

        return {
            "location": data.get("nearest_area", [{}])[0].get("areaName", [{}])[0].get("value", location)
            if data.get("nearest_area")
            else location,
            "country": data.get("nearest_area", [{}])[0].get("country", [{}])[0].get("value", "")
            if data.get("nearest_area")
            else "",
            "current": current_clean,
            "forecast": forecast,
            "source": "wttr.in",
        }

    return [get_weather]
