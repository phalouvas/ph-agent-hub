# =============================================================================
# PH Agent Hub — SEC Filings Tool Factory (sec.gov EDGAR)
# =============================================================================
# Builds MAF @tool-decorated async functions for listing and reading SEC
# EDGAR filings. Uses direct HTTPS requests to sec.gov — free by US law,
# no API key required. Uses beautifulsoup4 for HTML parsing.
# =============================================================================

import asyncio
import logging
import re

import httpx
from agent_framework import tool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SEC_BASE: str = "https://www.sec.gov"
SEC_CIK_LOOKUP: str = "https://www.sec.gov/cgi-bin/browse-edgar"
SEC_SUBMISSIONS: str = "https://data.sec.gov/submissions"
DEFAULT_TIMEOUT: float = 30.0
DEFAULT_USER_AGENT: str = (
    "ph-agent-hub/1.0 (contact@example.com)"
)
DEFAULT_LIMIT: int = 10

# SEC requires a User-Agent with contact info per fair access rules
# See: https://www.sec.gov/privacy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_float(val) -> float | None:
    """Convert a value to float, returning None on failure."""
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _clean_html(html_text: str) -> str:
    """Extract readable text from SEC filing HTML.

    Uses beautifulsoup4 to parse and extract text, removing tables
    and scripts while preserving document structure.
    """
    from bs4 import BeautifulSoup

    try:
        soup = BeautifulSoup(html_text, "html.parser")

        # Remove script, style, and hidden elements
        for tag in soup(["script", "style", "noscript", "meta", "link"]):
            tag.decompose()

        # Remove hidden divs
        for tag in soup.find_all(attrs={"style": re.compile(r"display\s*:\s*none", re.I)}):
            tag.decompose()

        # Get text with reasonable formatting
        text = soup.get_text(separator="\n", strip=True)

        # Clean up: remove excessive blank lines
        lines = [line.strip() for line in text.split("\n")]
        lines = [line for line in lines if line]
        # Remove lines that are just punctuation or very short
        cleaned = []
        for line in lines:
            if len(line) > 2 or line.isdigit():
                cleaned.append(line)

        return "\n".join(cleaned)
    except Exception:
        # Fallback: basic tag stripping
        text = re.sub(r"<[^>]+>", " ", html_text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()


def _extract_filing_links(html_content: str, base_url: str) -> list[dict]:
    """Parse the EDGAR browse page to extract filing entries."""
    from bs4 import BeautifulSoup

    filings = []
    try:
        soup = BeautifulSoup(html_content, "html.parser")

        # Find the filings table
        table = soup.find("table", class_="tableFile2")
        if not table:
            table = soup.find("table", summary="Results")

        if not table:
            return filings

        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 4:
                continue

            # Filing type
            filing_type = cells[0].get_text(strip=True) if len(cells) > 0 else ""

            # Description / link
            desc_cell = cells[1] if len(cells) > 1 else None
            description = ""
            doc_link = ""
            if desc_cell:
                link = desc_cell.find("a")
                if link:
                    description = link.get_text(strip=True)
                    href = link.get("href", "")
                    if href.startswith("/"):
                        doc_link = f"{SEC_BASE}{href}"
                    elif href.startswith("http"):
                        doc_link = href

            # Filing date
            filing_date = cells[3].get_text(strip=True) if len(cells) > 3 else ""

            # Try to get the actual document link
            if doc_link:
                # The link usually goes to the filing detail page
                # We construct the direct document URL pattern
                filings.append({
                    "filing_type": filing_type,
                    "description": description,
                    "filing_date": filing_date,
                    "detail_url": doc_link,
                })

    except Exception as exc:
        logger.warning("_extract_filing_links parse error: %s", exc)

    return filings


async def _resolve_cik(
    ticker: str, client: httpx.AsyncClient, headers: dict
) -> str | None:
    """Resolve a ticker symbol to a CIK number.

    SEC requires a 10-digit zero-padded CIK for API calls.
    """
    # Use the SEC company tickers JSON
    url = "https://www.sec.gov/files/company_tickers.json"
    try:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()

        ticker_upper = ticker.upper().strip()
        for company_id, info in data.items():
            if info.get("ticker", "").upper() == ticker_upper:
                cik = str(info.get("cik_str", ""))
                return cik.zfill(10)

    except Exception as exc:
        logger.warning("_resolve_cik: company_tickers.json failed: %s", exc)

    return None


# ---------------------------------------------------------------------------
# Tool factory
# ---------------------------------------------------------------------------


def build_sec_filings_tools(tool_config: dict | None = None) -> list:
    """Return a list of MAF @tool-decorated SEC filing functions.

    Provides:
    - ``list_sec_filings``: list recent SEC filings for a company
    - ``get_filing_text``: extract readable text from a filing HTML page

    Args:
        tool_config: Optional ``Tool.config`` JSON dict. May include:
            - ``user_agent`` (str): custom User-Agent for SEC requests
            - ``timeout`` (float): request timeout (default 30)
            - ``default_limit`` (int): default max filings to list (default 10)

    Returns:
        A list of callables ready to pass to ``Agent(tools=...)``.
    """
    config = tool_config or {}
    user_agent: str = config.get("user_agent", DEFAULT_USER_AGENT)
    timeout: float = float(config.get("timeout", DEFAULT_TIMEOUT))
    default_limit: int = int(config.get("default_limit", DEFAULT_LIMIT))

    @tool
    async def list_sec_filings(
        ticker: str,
        form_types: list[str] | None = None,
        limit: int | None = None,
    ) -> dict:
        """List recent SEC EDGAR filings for a US-listed company.

        Data from sec.gov — free by US law, no API key required.
        Only works for US-listed companies.

        Args:
            ticker: Stock ticker symbol (e.g. "AAPL", "MSFT").
            form_types: Optional list of form types to filter by.
                Common types: "10-K" (annual report), "10-Q" (quarterly),
                "8-K" (material events), "S-1" (IPO registration),
                "DEF 14A" (proxy statement). Default returns all types.
            limit: Max filings to return (default 10, max 50).

        Returns:
            A dict with:
            - ``ticker``, ``cik``
            - ``filings``: list of dicts with ``filing_type``,
              ``description``, ``filing_date``, ``detail_url``
            - ``count``: number of filings returned
            - ``source``: "SEC EDGAR"
        """
        lim = limit if limit is not None else default_limit
        lim = min(lim, 50)

        sym = ticker.upper().strip()
        logger.info("list_sec_filings: %s (limit=%d)", sym, lim)

        headers = {
            "User-Agent": user_agent,
            "Accept": "application/json, text/plain, */*",
        }

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                # Resolve ticker to CIK
                cik = await _resolve_cik(sym, client, headers)

                if not cik:
                    return {
                        "ticker": sym,
                        "error": f"Could not resolve ticker '{sym}' to a CIK. "
                        "Check that it is a valid US-listed company ticker.",
                    }

                # Use the EDGAR submissions API for recent filings
                cik_no_pad = cik.lstrip("0")
                submissions_url = f"{SEC_SUBMISSIONS}/CIK{cik}.json"
                resp = await client.get(submissions_url, headers=headers)
                resp.raise_for_status()
                data = resp.json()

                filings_raw = data.get("filings", {}).get("recent", {})
                if not filings_raw:
                    return {
                        "ticker": sym,
                        "cik": cik,
                        "filings": [],
                        "count": 0,
                        "source": "SEC EDGAR",
                    }

                # Build filing list
                form_list = filings_raw.get("form", [])
                desc_list = filings_raw.get("primaryDocument", [])
                date_list = filings_raw.get("filingDate", [])
                acc_list = filings_raw.get("accessionNumber", [])

                filings = []
                ft_upper = [f.upper() for f in (form_types or [])]

                for i in range(min(len(form_list), lim * 3)):  # search more to account for filtering
                    form = form_list[i] if i < len(form_list) else ""
                    if ft_upper and form.upper() not in ft_upper:
                        continue

                    acc_num = acc_list[i] if i < len(acc_list) else ""
                    acc_num_f = acc_num.replace("-", "") if acc_num else ""
                    primary_doc = desc_list[i] if i < len(desc_list) else ""

                    # Build detail URL (SEC viewer)
                    detail_url = ""
                    if acc_num and cik_no_pad:
                        detail_url = (
                            f"{SEC_BASE}/cgi-bin/viewer?"
                            f"action=view&cik={cik_no_pad}&"
                            f"accession_number={acc_num}"
                        )

                    # Build direct document URL
                    document_url = ""
                    if acc_num_f and cik_no_pad and primary_doc:
                        document_url = (
                            f"{SEC_BASE}/Archives/edgar/data/"
                            f"{cik_no_pad}/{acc_num_f}/{primary_doc}"
                        )

                    filings.append({
                        "filing_type": form,
                        "description": primary_doc,
                        "filing_date": date_list[i] if i < len(date_list) else "",
                        "accession_number": acc_num,
                        "detail_url": detail_url,
                        "document_url": document_url,
                    })

                    if len(filings) >= lim:
                        break

                return {
                    "ticker": sym,
                    "cik": cik,
                    "company_name": data.get("name", ""),
                    "filings": filings,
                    "count": len(filings),
                    "source": "SEC EDGAR",
                }

        except httpx.HTTPStatusError as exc:
            logger.warning(
                "list_sec_filings: HTTP %d for %s",
                exc.response.status_code,
                sym,
            )
            return {
                "ticker": sym,
                "error": f"SEC EDGAR returned HTTP {exc.response.status_code}",
            }
        except httpx.TimeoutException:
            logger.warning("list_sec_filings: timeout for %s", sym)
            return {"ticker": sym, "error": "Request timed out"}
        except Exception as exc:
            logger.exception("list_sec_filings failed for %s", sym)
            return {"ticker": sym, "error": str(exc)}

    @tool
    async def get_filing_text(url: str) -> dict:
        """Extract readable text from an SEC filing HTML page.

        Fetches the filing from sec.gov, cleans HTML, and returns
        plain text. Use in conjunction with list_sec_filings to first
        find filings, then read their contents.

        Args:
            url: The URL of the SEC filing page. Can be the detail_url
                returned by list_sec_filings, or a direct link to the
                filing document (.htm, .html).

        Returns:
            A dict with:
            - ``url``: the URL fetched
            - ``text``: cleaned plain text of the filing
            - ``text_length``: character count of the text
            - ``truncated``: whether the text was truncated (max ~100k chars)
            - ``source``: "SEC EDGAR"
        """
        logger.info("get_filing_text: %s", url)

        # Validate URL
        if not (url.startswith("https://www.sec.gov/") or url.startswith("http://www.sec.gov/")):
            return {
                "url": url,
                "error": "Only sec.gov URLs are supported for filing text extraction.",
            }

        max_chars = 100_000
        headers = {
            "User-Agent": user_agent,
            "Accept": "text/html, application/xhtml+xml, */*",
        }

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(url, headers=headers, follow_redirects=True)
                response.raise_for_status()

            html_content = response.text

            # If the detail page was given (viewer), try to find the actual document link
            if "/cgi-bin/viewer" in url and "document/archive" not in url:
                # Try to extract the direct document URL
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html_content, "html.parser")

                # Look for the iframe or direct document link
                iframe = soup.find("iframe")
                if iframe and iframe.get("src"):
                    doc_url = iframe["src"]
                    if doc_url.startswith("/"):
                        doc_url = f"{SEC_BASE}{doc_url}"
                    # Fetch the actual document
                    async with httpx.AsyncClient(timeout=timeout) as client2:
                        doc_resp = await client2.get(doc_url, headers=headers, follow_redirects=True)
                        doc_resp.raise_for_status()
                        html_content = doc_resp.text
                        url = doc_url

            # Clean the HTML
            text = await asyncio.to_thread(_clean_html, html_content)
            truncated = len(text) > max_chars
            if truncated:
                text = text[:max_chars]

            return {
                "url": url,
                "text": text,
                "text_length": len(text),
                "truncated": truncated,
                "source": "SEC EDGAR",
            }

        except httpx.HTTPStatusError as exc:
            logger.warning(
                "get_filing_text: HTTP %d for %s",
                exc.response.status_code,
                url,
            )
            return {
                "url": url,
                "error": f"SEC EDGAR returned HTTP {exc.response.status_code}",
            }
        except httpx.TimeoutException:
            logger.warning("get_filing_text: timeout for %s", url)
            return {"url": url, "error": "Request timed out"}
        except Exception as exc:
            logger.exception("get_filing_text failed for %s", url)
            return {"url": url, "error": str(exc)}

    return [list_sec_filings, get_filing_text]
