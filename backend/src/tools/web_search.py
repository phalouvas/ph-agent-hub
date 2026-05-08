# =============================================================================
# PH Agent Hub — Web Search Tool Factory (DuckDuckGo / ddgs)
# =============================================================================
# Builds a MAF @tool-decorated async function that performs web searches
# via the ddgs library (Dux Distributed Global Search).
# =============================================================================

import asyncio
import json
import logging
from typing import Any

from agent_framework import tool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool factory
# ---------------------------------------------------------------------------


def build_web_search_tools(tool_config: dict | None = None) -> list:
    """Return a list containing the MAF @tool-decorated web_search function.

    Args:
        tool_config: Optional ``Tool.config`` JSON dict.  May include keys
            that override the defaults for each search parameter:

            - ``max_results`` (int, default 10): max number of results
            - ``region`` (str, default "us-en"): region code
            - ``safesearch`` (str, default "moderate"): on / moderate / off
            - ``timelimit`` (str | None, default None): d / w / m / y
            - ``backend`` (str, default "auto"): search backend(s)

    Returns:
        A list with a single callable ready to pass to ``Agent(tools=...)``.
    """
    config = tool_config or {}

    default_max_results = int(config.get("max_results", 10))
    default_region = config.get("region", "us-en")
    default_safesearch = config.get("safesearch", "moderate")
    default_timelimit = config.get("timelimit") or None
    default_backend = config.get("backend", "auto")

    @tool
    async def web_search(
        query: str,
        max_results: int | None = None,
        region: str | None = None,
        safesearch: str | None = None,
        timelimit: str | None = None,
        backend: str | None = None,
    ) -> dict:
        """Search the web using DuckDuckGo (via ddgs metasearch).

        Args:
            query: The search query string.
            max_results: Maximum number of results to return
                (default: tool config or 10).
            region: Region code such as "us-en", "uk-en", "ru-ru"
                (default: tool config or "us-en").
            safesearch: Safe search level — "on", "moderate", or "off"
                (default: tool config or "moderate").
            timelimit: Time limit — "d" (day), "w" (week), "m" (month),
                "y" (year), or None for any time.
            backend: Search backend(s) — "auto", "bing", "brave",
                "duckduckgo", "google", etc. Comma-delimited for multiple.

        Returns:
            A dict with:
            - ``query``: the search query executed
            - ``results``: list of result dicts, each with keys such as
              ``title``, ``href``, ``body``
            - ``result_count``: number of results returned
            - ``backend_used``: the backend that served results (when
              discernible)
        """
        # Resolve parameters with defaults
        resolved_max = max_results if max_results is not None else default_max_results
        resolved_region = region or default_region
        resolved_safesearch = safesearch or default_safesearch
        resolved_timelimit = timelimit if timelimit is not None else default_timelimit
        resolved_backend = backend or default_backend

        logger.info(
            "web_search query=%r max_results=%d region=%s safesearch=%s "
            "timelimit=%s backend=%s",
            query,
            resolved_max,
            resolved_region,
            resolved_safesearch,
            resolved_timelimit,
            resolved_backend,
        )

        try:
            # Run the blocking DDGS call in a thread to avoid blocking
            # the async event loop.
            results: list[dict[str, Any]] = await asyncio.to_thread(
                _do_search,
                query=query,
                region=resolved_region,
                safesearch=resolved_safesearch,
                timelimit=resolved_timelimit,
                max_results=resolved_max,
                backend=resolved_backend,
            )
        except Exception:
            logger.exception("web_search failed for query=%r", query)
            return {
                "query": query,
                "results": [],
                "result_count": 0,
                "error": "Search request failed. The search engine may be "
                "temporarily unavailable or rate-limited.",
            }

        # Try to detect which backend served the results
        backend_used = resolved_backend
        if results:
            sources = {r.get("source", "") for r in results if r.get("source")}
            if sources:
                backend_used = ", ".join(sorted(sources))

        return {
            "query": query,
            "results": results,
            "result_count": len(results),
            "backend_used": backend_used,
        }

    return [web_search]


# ---------------------------------------------------------------------------
# Synchronous search helper (called via asyncio.to_thread)
# ---------------------------------------------------------------------------


def _do_search(
    *,
    query: str,
    region: str,
    safesearch: str,
    timelimit: str | None,
    max_results: int,
    backend: str,
) -> list[dict[str, Any]]:
    """Perform the blocking DDGS text search and return a simplified
    list of result dicts."""
    from ddgs import DDGS

    ddgs = DDGS()

    raw: list[dict[str, str]] = ddgs.text(
        query=query,
        region=region,
        safesearch=safesearch,
        timelimit=timelimit,
        max_results=max_results,
        backend=backend,
    )

    # Simplify results to a consistent subset of keys
    simplified: list[dict[str, Any]] = []
    for item in raw:
        simplified.append(
            {
                "title": item.get("title", ""),
                "url": item.get("href", item.get("url", "")),
                "snippet": item.get("body", ""),
                "source": item.get("source", ""),
            }
        )

    return simplified
