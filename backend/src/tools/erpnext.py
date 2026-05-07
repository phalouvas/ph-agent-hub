# =============================================================================
# PH Agent Hub — ERPNext Tool Factory
# =============================================================================
# Builds MAF @tool-decorated async functions bound to a specific ERPNext
# instance.  All ERPNext HTTP logic lives in this module.
# =============================================================================

import json
import logging
from typing import Any

import httpx
from agent_framework import tool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------


def _build_auth_header(api_key: str, api_secret: str) -> dict[str, str]:
    """Return the Authorization header dict for ERPNext REST API."""
    return {"Authorization": f"token {api_key}:{api_secret}"}


# ---------------------------------------------------------------------------
# Tool factories
# ---------------------------------------------------------------------------


def build_erpnext_tools(
    base_url: str,
    api_key: str,
    api_secret: str,
) -> list:
    """Return a list of MAF @tool-decorated async functions bound to an
    ERPNext instance.

    Args:
        base_url: ERPNext site URL (e.g. ``https://erp.example.com``).
        api_key: ERPNext API key.
        api_secret: ERPNext API secret.

    Returns:
        A list of callables ready to pass to ``Agent(tools=...)``.
    """
    auth_header = _build_auth_header(api_key, api_secret)
    client = httpx.AsyncClient(
        base_url=base_url.rstrip("/"),
        headers=auth_header,
    )

    # ------------------------------------------------------------------
    @tool
    async def get_doc(doctype: str, name: str) -> dict:
        """Retrieve a single ERPNext document by doctype and name.

        Args:
            doctype: The DocType name (e.g. "Sales Order").
            name: The document name/id.
        """
        url = f"/api/resource/{doctype}/{name}"
        resp = await client.get(url)
        resp.raise_for_status()
        data: dict = resp.json()
        logger.debug("get_doc %s/%s → %d bytes", doctype, name, len(json.dumps(data)))
        return data

    # ------------------------------------------------------------------
    @tool
    async def get_list(
        doctype: str,
        filters: dict | None = None,
        fields: list[str] | None = None,
        limit_page_length: int | None = None,
    ) -> list[dict]:
        """Retrieve a list of ERPNext documents.

        Args:
            doctype: The DocType name (e.g. "Sales Order").
            filters: Optional ERPNext filter dict.
            fields: Optional list of field names to return.
            limit_page_length: Optional max number of records.
        """
        params: dict[str, Any] = {}
        if filters:
            params["filters"] = json.dumps(filters)
        if fields:
            params["fields"] = json.dumps(fields)
        if limit_page_length is not None:
            params["limit_page_length"] = limit_page_length

        url = f"/api/resource/{doctype}"
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data: dict = resp.json()
        results: list[dict] = data.get("data", [])
        logger.debug(
            "get_list %s (filters=%s) → %d records",
            doctype,
            filters,
            len(results),
        )
        return results

    return [get_doc, get_list]
