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
    "ph-agent-hub/1.0 (phalouvas@gmail.com)"
)
DEFAULT_LIMIT: int = 10
DEFAULT_MAX_CHARS: int = 500_000
RETRY_DELAY: float = 2.0  # seconds between SEC API retries
MAX_RETRIES: int = 2

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


def _extract_filing_links(html_content: str, cik_no_pad: str = "") -> list[dict]:
    """Parse the EDGAR browse page to extract filing entries.

    When *cik_no_pad* is provided, also builds ``document_url`` and
    extracts ``accession_number`` from the detail link.
    """
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

            # Extract accession number from detail URL.
            # Two URL patterns:
            #   A) Viewer query:   …?accession_number=0001564590-22-026876
            #   B) Browse path:    …/data/789019/000156459022026876/0001564590-22-026876-index.htm
            accession_number = ""
            document_url = ""
            if doc_link:
                import re as _re
                # Pattern A: query parameter
                _m = _re.search(r"accession_number=([^&]+)", doc_link)
                if _m:
                    accession_number = _m.group(1)
                else:
                    # Pattern B: path segment  …/data/CIK/ACCNODASHES/ACC-ESSION-NUMBER-index.htm
                    _m = _re.search(
                        r"/data/\d+/([^/]+)/(\d{10}-\d{2}-\d{6})-index\.h",
                        doc_link,
                    )
                    if _m:
                        accession_number = _m.group(2)
                # Build direct document URL when we have all pieces
                if accession_number and cik_no_pad and description and description != "Documents":
                    acc_num_f = accession_number.replace("-", "")
                    document_url = (
                        f"{SEC_BASE}/Archives/edgar/data/"
                        f"{cik_no_pad}/{acc_num_f}/{description}"
                    )

            if doc_link:
                filings.append({
                    "filing_type": filing_type,
                    "description": description,
                    "filing_date": filing_date,
                    "detail_url": doc_link,
                    "accession_number": accession_number,
                    "document_url": document_url,
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


async def _fetch_filings_via_browse(
    cik_no_pad: str,
    headers: dict,
    timeout: float,
    form_types: list[str] | None,
    limit: int,
    filing_date_from: str | None,
) -> list[dict]:
    """Fetch filings via the EDGAR browse endpoint (HTML-based).

    The browse endpoint supports date filtering and type filtering,
    making it suitable for older filings that have fallen out of
    the submissions API 'recent' window.
    """
    params: dict[str, str] = {
        "action": "getcompany",
        "CIK": cik_no_pad,
        "owner": "exclude",
        "count": str(min(limit, 100)),
    }
    if form_types:
        # Browse endpoint only accepts a single type; use the first one
        params["type"] = form_types[0]
    if filing_date_from:
        # EDGAR browse expects YYYYMMDD format for dateb
        params["dateb"] = filing_date_from.replace("-", "")

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(
            SEC_CIK_LOOKUP,
            params=params,
            headers=headers,
            follow_redirects=True,
        )
        resp.raise_for_status()

    # _extract_filing_links now accepts cik_no_pad for building document URLs
    filings = _extract_filing_links(resp.text, cik_no_pad)

    # Apply client-side form type filter if multiple types were requested
    if form_types and len(form_types) > 1:
        ft_upper = [f.upper() for f in form_types]
        filings = [f for f in filings if f["filing_type"].upper() in ft_upper]

    return filings[:limit]


def _split_filing_sections(text: str) -> dict[str, str]:
    """Split cleaned filing text into named sections based on SEC headings.

    Recognises Part I–IV and Item 1–16 patterns common in 10-K, 10-Q,
    8-K and S-1 filings.  Returns a dict mapping section name → text.
    If no headings are detected, returns ``{"_full": text}``.
    """
    # Pattern: "Part I", "Part II", …, "Item 1.", "Item 1A.", …
    heading = re.compile(
        r"^\s*(PART\s+(?:I|II|III|IV|V)[\s.\-]*.*|Item\s+\d+[A-Z]?[\s.\-]*.*)$",
        re.IGNORECASE | re.MULTILINE,
    )
    matches = list(heading.finditer(text))
    if not matches:
        return {"_full": text}

    sections: dict[str, str] = {}
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        name = m.group(1).strip().rstrip(".-")
        body = text[start:end].strip()
        # Deduplicate section names (e.g. multiple "Item 1" across Parts)
        key = name
        counter = 2
        while key in sections:
            key = f"{name} ({counter})"
            counter += 1
        sections[key] = body
    return sections


async def _fetch_and_clean_filing(
    url: str,
    headers: dict,
    timeout: float,
) -> tuple[str, str]:
    """Fetch an SEC filing page and return ``(cleaned_text, resolved_url)``.

    Handles the viewer → iframe → document URL resolution transparently.
    """
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url, headers=headers, follow_redirects=True)
        response.raise_for_status()

    html_content = response.text

    # -- Resolve indirect URLs to the actual filing document -----------------

    # Case 1: SEC viewer page — follow the iframe to the real document
    if "/cgi-bin/viewer" in url and "document/archive" not in url:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html_content, "html.parser")
        iframe = soup.find("iframe")
        if iframe and iframe.get("src"):
            doc_url = iframe["src"]
            if doc_url.startswith("/"):
                doc_url = f"{SEC_BASE}{doc_url}"
            async with httpx.AsyncClient(timeout=timeout) as client2:
                doc_resp = await client2.get(
                    doc_url, headers=headers, follow_redirects=True
                )
                doc_resp.raise_for_status()
                html_content = doc_resp.text
                url = doc_url

    # Case 2: EDGAR filing detail page (…-index.htm) — find the primary
    #          filing document link and follow it
    elif "-index.htm" in url or "-index.html" in url:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html_content, "html.parser")
        # Scan all table cells for any link whose *href* (not text)
        # ends with .htm / .html, skipping XBRL exhibits and data files.
        doc_link: str | None = None
        for table in soup.find_all("table"):
            for row in table.find_all("tr"):
                for cell in row.find_all("td"):
                    link = cell.find("a")
                    if not link:
                        continue
                    href = (link.get("href") or "").strip()
                    if not href:
                        continue
                    # Exclude XBRL taxonomy files, XML, XSD, raw text
                    _lo = href.lower()
                    if _lo.endswith((
                        "_cal.xml", "_def.xml", "_lab.xml", "_pre.xml",
                        ".xsd", ".txt", ".xml",
                    )):
                        continue
                    if _lo.endswith((".htm", ".html")):
                        if href.startswith("/"):
                            doc_link = f"{SEC_BASE}{href}"
                        elif href.startswith("http"):
                            doc_link = href
                        else:
                            # Relative to the index page directory
                            base = url.rsplit("/", 1)[0]
                            doc_link = f"{base}/{href}"
                        break
                if doc_link:
                    break
            if doc_link:
                break

        if doc_link:
            async with httpx.AsyncClient(timeout=timeout) as client2:
                doc_resp = await client2.get(
                    doc_link, headers=headers, follow_redirects=True
                )
                doc_resp.raise_for_status()
                html_content = doc_resp.text
                url = doc_link

    text = await asyncio.to_thread(_clean_html, html_content)
    return text, url


# ---------------------------------------------------------------------------
# Tool factory
# ---------------------------------------------------------------------------


def build_sec_filings_tools(tool_config: dict | None = None) -> list:
    """Return a list of MAF @tool-decorated SEC filing functions.

    Provides:
    - ``list_sec_filings``: list recent SEC filings for a company
    - ``get_filing_text``: extract readable text from a filing HTML page
    - ``get_filing_section``: extract a named section from a filing

    Args:
        tool_config: Optional ``Tool.config`` JSON dict. May include:
            - ``user_agent`` (str): custom User-Agent for SEC requests
            - ``timeout`` (float): request timeout (default 30)
            - ``default_limit`` (int): default max filings to list (default 10)
            - ``max_chars`` (int): max chars for ``get_filing_text``
              (default 500 000; set to 0 for no limit)

    Returns:
        A list of callables ready to pass to ``Agent(tools=...)``.
    """
    config = tool_config or {}
    user_agent: str = config.get("user_agent", DEFAULT_USER_AGENT)
    timeout: float = float(config.get("timeout", DEFAULT_TIMEOUT))
    default_limit: int = int(config.get("default_limit", DEFAULT_LIMIT))
    max_chars_cfg: int = int(config.get("max_chars", DEFAULT_MAX_CHARS))

    @tool
    async def list_sec_filings(
        ticker: str,
        form_types: list[str] | None = None,
        limit: int | None = None,
        filing_date_from: str | None = None,
    ) -> dict:
        """List SEC EDGAR filings for a US-listed company.

        Data from sec.gov — free by US law, no API key required.
        Only works for US-listed companies.

        Args:
            ticker: Stock ticker symbol (e.g. "AAPL", "MSFT").
            form_types: Optional list of form types to filter by.
                Common types: "10-K" (annual report), "10-Q" (quarterly),
                "8-K" (material events), "S-1" (IPO registration),
                "DEF 14A" (proxy statement). Default returns all types.
            limit: Max filings to return (default 10, max 50).
            filing_date_from: Earliest filing date in YYYY-MM-DD format
                (e.g. "2024-01-01").  When provided, the tool uses the
                EDGAR browse endpoint which supports date filtering
                and can reach filings older than the submissions API
                window.  Use this to find annual reports (10-K) from
                prior fiscal years.

        Returns:
            A dict with:
            - ``ticker``, ``cik``
            - ``filings``: list of dicts with ``filing_type``,
              ``description``, ``filing_date``, ``detail_url``,
              ``document_url``, ``accession_number``
            - ``count``: number of filings returned
            - ``source``: "SEC EDGAR"
        """
        lim = limit if limit is not None else default_limit
        lim = min(lim, 50)

        sym = ticker.upper().strip()
        logger.info(
            "list_sec_filings: %s (limit=%d, date_from=%s)",
            sym, lim, filing_date_from,
        )

        headers = {
            "User-Agent": user_agent,
            "Accept": "application/json, text/plain, */*",
        }

        # ---- helpers inside the closure for retry-aware SEC calls ----
        async def _try_submissions_api(
            client: httpx.AsyncClient, cik: str
        ) -> dict | None:
            """Call the EDGAR submissions API.  Returns parsed JSON or None."""
            submissions_url = f"{SEC_SUBMISSIONS}/CIK{cik}.json"
            resp = await client.get(submissions_url, headers=headers)
            if resp.status_code == 429:
                logger.warning("SEC rate limit (429) for %s, will retry", sym)
                return None
            resp.raise_for_status()
            return resp.json()

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                # Resolve ticker to CIK (with retry)
                cik = None
                for attempt in range(MAX_RETRIES + 1):
                    cik = await _resolve_cik(sym, client, headers)
                    if cik:
                        break
                    if attempt < MAX_RETRIES:
                        await asyncio.sleep(RETRY_DELAY * (attempt + 1))

                if not cik:
                    return {
                        "ticker": sym,
                        "error": f"Could not resolve ticker '{sym}' to a CIK. "
                        "Check that it is a valid US-listed company ticker.",
                    }

                cik_no_pad = cik.lstrip("0")

                # ---- Path A: with filing_date_from → use browse endpoint ----
                if filing_date_from:
                    filings = await _fetch_filings_via_browse(
                        cik_no_pad=cik_no_pad,
                        headers=headers,
                        timeout=timeout,
                        form_types=form_types,
                        limit=lim,
                        filing_date_from=filing_date_from,
                    )
                    return {
                        "ticker": sym,
                        "cik": cik,
                        "filings": filings,
                        "count": len(filings),
                        "source": "SEC EDGAR (browse)",
                    }

                # ---- Path B: submissions API with retry ----
                data = None
                for attempt in range(MAX_RETRIES + 1):
                    data = await _try_submissions_api(client, cik)
                    if data is not None:
                        break
                    if attempt < MAX_RETRIES:
                        await asyncio.sleep(RETRY_DELAY * (attempt + 1))

                if data is None:
                    return {
                        "ticker": sym,
                        "cik": cik,
                        "error": "SEC EDGAR rate limit — please retry shortly.",
                    }

                filings_raw = data.get("filings", {}).get("recent", {})
                if not filings_raw:
                    # Empty recent — could be rate-limiting; retry once
                    await asyncio.sleep(RETRY_DELAY)
                    async with httpx.AsyncClient(timeout=timeout) as client2:
                        data2 = await _try_submissions_api(client2, cik)
                    if data2:
                        filings_raw = data2.get("filings", {}).get("recent", {})

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

                for i in range(min(len(form_list), lim * 3)):
                    form = form_list[i] if i < len(form_list) else ""
                    if ft_upper and form.upper() not in ft_upper:
                        continue

                    acc_num = acc_list[i] if i < len(acc_list) else ""
                    acc_num_f = acc_num.replace("-", "") if acc_num else ""
                    primary_doc = desc_list[i] if i < len(desc_list) else ""

                    detail_url = ""
                    if acc_num and cik_no_pad:
                        detail_url = (
                            f"{SEC_BASE}/cgi-bin/viewer?"
                            f"action=view&cik={cik_no_pad}&"
                            f"accession_number={acc_num}"
                        )

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
    async def get_filing_text(url: str, max_chars: int | None = None) -> dict:
        """Extract readable text from an SEC filing HTML page.

        Fetches the filing from sec.gov, cleans HTML, and returns
        plain text. Use in conjunction with list_sec_filings to first
        find filings, then read their contents.

        For large filings (10-K, 10-Q) prefer ``get_filing_section``
        to retrieve only the sections you need.

        Args:
            url: The URL of the SEC filing page. Can be the detail_url
                returned by list_sec_filings, or a direct link to the
                filing document (.htm, .html).
            max_chars: Override the configured character limit.
                Set to 0 for no limit.  Default uses the tool config
                (default 500 000).

        Returns:
            A dict with:
            - ``url``: the URL fetched
            - ``text``: cleaned plain text of the filing
            - ``text_length``: character count of the text
            - ``truncated``: whether the text was truncated
            - ``source``: "SEC EDGAR"
        """
        logger.info("get_filing_text: %s", url)

        # Validate URL
        if not (url.startswith("https://www.sec.gov/") or url.startswith("http://www.sec.gov/")):
            return {
                "url": url,
                "error": "Only sec.gov URLs are supported for filing text extraction.",
            }

        limit = max_chars_cfg if max_chars is None else max_chars
        headers = {
            "User-Agent": user_agent,
            "Accept": "text/html, application/xhtml+xml, */*",
        }

        try:
            text, resolved_url = await _fetch_and_clean_filing(
                url, headers, timeout
            )
            truncated = limit > 0 and len(text) > limit
            if truncated:
                text = text[:limit]

            return {
                "url": resolved_url,
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

    @tool
    async def get_filing_section(url: str, section: str) -> dict:
        """Extract a specific named section from an SEC filing.

        Fetches the filing, splits it into sections by SEC headings
        (Part I–IV, Item 1–16), and returns only the requested
        section.  This avoids truncation on large filings like 10-K
        and 10-Q.

        Args:
            url: The URL of the SEC filing page (same as for
                ``get_filing_text``).
            section: Name of the section to extract.  Case-insensitive
                partial match, e.g. ``"Item 2"``, ``"Risk Factors"``,
                ``"Part I"``.  If the section is not found the response
                includes ``available_sections`` so you can retry.

        Returns:
            A dict with:
            - ``url``: the URL fetched
            - ``section``: the matched section name
            - ``text``: cleaned plain text of that section only
            - ``text_length``: character count
            - ``available_sections``: list of all detected section names
            - ``source``: "SEC EDGAR"
        """
        logger.info("get_filing_section: %s [section=%s]", url, section)

        if not (url.startswith("https://www.sec.gov/") or url.startswith("http://www.sec.gov/")):
            return {
                "url": url,
                "error": "Only sec.gov URLs are supported for filing text extraction.",
            }

        headers = {
            "User-Agent": user_agent,
            "Accept": "text/html, application/xhtml+xml, */*",
        }

        try:
            text, resolved_url = await _fetch_and_clean_filing(
                url, headers, timeout
            )
            sections = _split_filing_sections(text)
            available = list(sections.keys())

            # Match: case-insensitive substring search
            target = section.strip().lower()
            matched_key: str | None = None
            for key in available:
                if target in key.lower():
                    matched_key = key
                    break

            if matched_key is None:
                return {
                    "url": resolved_url,
                    "section": section,
                    "error": (
                        f"Section '{section}' not found. "
                        f"Available sections: {available}"
                    ),
                    "available_sections": available,
                    "source": "SEC EDGAR",
                }

            return {
                "url": resolved_url,
                "section": matched_key,
                "text": sections[matched_key],
                "text_length": len(sections[matched_key]),
                "available_sections": available,
                "source": "SEC EDGAR",
            }

        except httpx.HTTPStatusError as exc:
            logger.warning(
                "get_filing_section: HTTP %d for %s",
                exc.response.status_code,
                url,
            )
            return {
                "url": url,
                "error": f"SEC EDGAR returned HTTP {exc.response.status_code}",
            }
        except httpx.TimeoutException:
            logger.warning("get_filing_section: timeout for %s", url)
            return {"url": url, "error": "Request timed out"}
        except Exception as exc:
            logger.exception("get_filing_section failed for %s", url)
            return {"url": url, "error": str(exc)}

    return [list_sec_filings, get_filing_text, get_filing_section]
