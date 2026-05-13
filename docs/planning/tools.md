# PH Agent Hub — Tool Expansion Plan

> High-level planning document for new tool additions. Each section covers
> the motivation, implementation complexity, and architectural notes.

---

## Current State (28 tools)

### Built-in Tools (always active, not configurable)

| # | Tool | Type key | Category |
|---|------|----------|----------|
| 1 | File List | `file_list` | System — list/read uploaded files |
| 2 | Memory | `memory` | System — cross-session key-value persistence |

### User-Configurable Tools (created via Admin → Tools)

#### Utility
| # | Tool | Type key | Functions |
|---|------|----------|-----------|
| 3 | Calculator | `calculator` | Safe AST expression evaluator |
| 4 | Code Interpreter | `code_interpreter` | Docker-sandboxed Python execution (pandas, numpy, matplotlib, plotly) |
| 5 | Datetime | `datetime` | Timezone-aware date/time queries |
| 6 | Document Generation | `document_generation` | Markdown→PDF, list→Excel, list→CSV (output to MinIO/S3) |
| 7 | Weather | `weather` | Weather via wttr.in |

#### Web
| # | Tool | Type key | Functions |
|---|------|----------|-----------|
| 8 | Browser | `browser` | Playwright headless Chromium — screenshot, extract text, extract tables |
| 9 | Fetch URL | `fetch_url` | HTTP GET with HTML→text conversion |
| 10 | RAG Search | `rag_search` | Semantic search across uploaded documents (embedding API + fallback TF-IDF) |
| 11 | RSS Feed | `rss_feed` | RSS/Atom feed reader |
| 12 | Web Search | `web_search` | SearXNG-backed web search |
| 13 | Wikipedia | `wikipedia` | Article lookup and summary |

#### Financial / Investor (zero API keys)
| # | Tool | Type key | Functions |
|---|------|----------|-----------|
| 14 | Currency Exchange | `currency_exchange` | Exchange rates via frankfurter.app (ECB data) |
| 15 | ETF Data | `etf_data` | ETF holdings, profile (yfinance) |
| 16 | Market Overview | `market_overview` | Global index quotes, market movers (yfinance) |
| 17 | Portfolio | `portfolio` | Portfolio analysis, optimization, efficient frontier (numpy+scipy) |
| 18 | SEC Filings | `sec_filings` | SEC EDGAR filing search and retrieval |
| 19 | Stock Data | `stock_data` | Quotes, historical prices, financials, analyst ratings (yfinance) |

#### Enterprise
| # | Tool | Type key | Functions |
|---|------|----------|-----------|
| 20 | ERPNext | `erpnext` | Full CRUD, file upload, doctype metadata |
| 21 | Membrane | `membrane` | Membrane framework integration |
| 22 | SQL Query | `sql_query` | Read-only SQL against tenant-configured DB (PostgreSQL, MySQL, MariaDB) |

#### Integrations
| # | Tool | Type key | Functions |
|---|------|----------|-----------|
| 23 | Calendar | `calendar` | Google Calendar — list/create events, find free slots |
| 24 | Email | `email` | Send emails via SMTP or SendGrid API |
| 25 | GitHub | `github` | Search code, list issues/PRs, read files, create issues (GitHub + GitLab) |
| 26 | Image Generation | `image_generation` | DALL·E 3 / Stable Diffusion via API → image URL in MinIO/S3 |
| 27 | Slack | `slack` | Send messages to Slack channels (webhook or bot token) |

#### Extensibility
| # | Tool | Type key | Functions |
|---|------|----------|-----------|
| 28 | Custom | `custom` | Admin-authored sandboxed Python tools |

---

## Comparison With Other Agentic Platforms

When comparing with ChatGPT, Claude, Gemini, Copilot, and LangChain/CrewAI, 
PH Agent Hub now matches or exceeds all major capabilities:

- **✅ Code execution** — `code_interpreter` (Docker-sandboxed Python, AST-validated)
- **✅ Image generation** — `image_generation` (DALL·E 3, Stable Diffusion)
- **✅ Database queries** — `sql_query` (read-only SQL, multi-backend, encrypted connections)
- **✅ Document generation** — `document_generation` (PDF/Excel/CSV export to MinIO/S3)
- **✅ Browser automation** — `browser` (Playwright headless Chromium, screenshots, text/table extraction)
- **✅ Git/DevOps** — `github` (GitHub + GitLab: search code, issues, PRs, files)
- **✅ Calendar / Scheduling** — `calendar` (Google Calendar: list/create events, find free slots)
- **✅ Vector / RAG search** — `rag_search` (semantic search over uploaded documents)
- **✅ Communication** — `slack` + `email` (Slack webhook/bot, SMTP/SendGrid)

All gaps identified in the original comparison have been addressed.

---

## Implementation Status

All proposed tools have been implemented. Each tool module lives at
`backend/src/tools/TOOL_NAME.py` and follows the standard factory pattern
(detailed below).

### Priority 1 — Financial / Investor Tools ✅
| Tool | Implemented | Module |
|------|-------------|--------|
| `stock_data` | ✅ | `backend/src/tools/stock_data.py` |
| `market_overview` | ✅ | `backend/src/tools/market_overview.py` |
| `etf_data` | ✅ | `backend/src/tools/etf_data.py` |
| `sec_filings` | ✅ | `backend/src/tools/sec_filings.py` |
| `portfolio` | ✅ | `backend/src/tools/portfolio.py` |

### Priority 2 — General Tools ✅
| Tool | Implemented | Module |
|------|-------------|--------|
| `code_interpreter` | ✅ | `backend/src/tools/code_interpreter.py` |
| `sql_query` | ✅ | `backend/src/tools/sql_query.py` |
| `document_generation` | ✅ | `backend/src/tools/document_generation.py` |
| `browser` | ✅ | `backend/src/tools/browser.py` |
| `rag_search` | ✅ | `backend/src/tools/rag_search.py` |
| `github` | ✅ | `backend/src/tools/github.py` |
| `calendar` | ✅ | `backend/src/tools/calendar.py` |
| `image_generation` | ✅ | `backend/src/tools/image_generation.py` |
| `slack` | ✅ | `backend/src/tools/slack.py` |
| `email` | ✅ | `backend/src/tools/email.py` |

### Priority 3 — Nice to Have
> Not yet implemented. See GitHub Issue #160 for tracking.
| Tool | Status |
|------|--------|
| `translation` | ⬜ Planned |
| `youtube` | ⬜ Planned |
| `maps` | ⬜ Planned |
| `qrcode` | ⬜ Planned |

---

## Implementation Pattern (How to Add Any Tool)

Every new tool follows this 5-step pattern already established in the codebase:

### Step 1 — Create the tool module

```
backend/src/tools/NEW_TOOL.py
```

```python
# Standard factory pattern:
def build_NEW_TOOL_tools(tool_config: dict | None = None) -> list:
    config = tool_config or {}
    # ... parse config ...

    @tool
    async def tool_function(param: str) -> dict:
        """Docstring becomes the tool description for the LLM."""
        # ... implementation ...
        return {}

    return [tool_function]
```

### Step 2 — Register the type string

In `backend/src/services/tool_service.py`, add to `VALID_TOOL_TYPES`:
```python
VALID_TOOL_TYPES = {
    "erpnext", "membrane", "custom", "datetime", "web_search",
    "fetch_url", "weather", "calculator", "wikipedia", "rss_feed",
    "currency_exchange", "new_tool",  # ← add here
}
```

### Step 3 — Add DB enum migration

Create an Alembic migration that adds the new type to the `tool_type_enum`
in PostgreSQL:
```python
op.execute("ALTER TYPE tool_type_enum ADD VALUE 'new_tool'")
```

### Step 4 — Add dispatch branch in runner.py

In `_build_tool_callables()` in `backend/src/agents/runner.py`:
```python
elif tool.type == "new_tool":
    from ..tools.NEW_TOOL import build_NEW_TOOL_tools
    return build_NEW_TOOL_tools(tool.config or {})
```

### Step 5 — (Optional) Add admin UI config fields

If the tool has configurable parameters, add form fields in:
- `frontend/src/features/admin/resources/tools/ToolForm.tsx`

---

## Financial / Investor Tools

> All tools in this section use **zero-cost, zero-API-key** data sources.
> No registration, no paid tiers, no rate-limit anxiety.

### Data Sources

| Source | What it provides | Scope | Library |
|--------|-----------------|-------|---------|
| **Yahoo Finance** | Stock quotes, history, financials, metrics, ETFs, indices | Global (~60 exchanges) | `yfinance` (pip) |
| **SEC EDGAR** | Official company filings (10-K, 10-Q, 8-K) | US companies + ADRs | `httpx` (already installed) |
| **numpy + scipy** | Portfolio math (returns, risk, optimization) | Computation-only | `numpy`, `scipy`, `pandas` |

---

###  1. Stock Data — `stock_data`

**Data source**: yfinance (global, free, no key)

**Functions**:

| Function | Description |
|----------|-------------|
| `get_stock_quote(symbol)` | Current price, change %, volume, market cap, day range, 52-week range, bid/ask |
| `get_historical_prices(symbol, from_date, to_date, interval)` | OHLCV data with daily/weekly/monthly granularity |
| `get_financials(symbol, statement, period)` | Income statement, balance sheet, cash flow (annual/quarterly) |
| `get_key_metrics(symbol)` | P/E, P/B, P/S, PEG, debt/equity, ROE, ROA, profit margin, dividend yield, beta |
| `get_company_info(symbol)` | Sector, industry, employees, CEO, headquarters, IPO date, business summary |
| `get_dividends(symbol)` | Dividend history with amounts and dates |
| `get_earnings_history(symbol)` | Historical EPS surprises (beat/miss/meet) |
| `get_analyst_ratings(symbol)` | Consensus rating (buy/hold/sell), median price target, number of analysts |

**International coverage**: US stocks (no suffix), European (`.L`, `.DE`, `.PA`, `.MI`, `.AS`, `.MC`, `.SW`, `.ST`, `.CO`), Asian (`.T`, `.HK`, `.SS`, `.SZ`, `.NS`, `.SI`, `.KS`, `.TW`), Australian (`.AX`).

**Config**: `{ "timeout": 15 }`

**Effort**: Medium

---

### 2. Market Overview — `market_overview`

**Data source**: yfinance (global, free, no key)

**Functions**:

| Function | Description |
|----------|-------------|
| `get_index_quote(index)` | S&P 500 (^GSPC), Nasdaq (^IXIC), Dow (^DJI), Russell 2000 (^RUT), VIX (^VIX), FTSE 100 (^FTSE), DAX (^GDAXI), Nikkei 225 (^N225), Hang Seng (^HSI), Shanghai (000001.SS), Nifty 50 (^NSEI), ASX 200 (^AXJO), and others |
| `get_market_movers()` | Day's top gainers and losers across major markets |

**Config**: `{ "timeout": 15 }`

**Effort**: Low

---

### 3. ETF Data — `etf_data`

**Data source**: yfinance (global, free, no key)

**Functions**:

| Function | Description |
|----------|-------------|
| `get_etf_holdings(symbol, top_n)` | Top N holdings with ticker, name, and weight % |
| `get_etf_profile(symbol)` | Category, expense ratio, AUM, inception date, investment strategy description |

**Config**: `{ "timeout": 15 }`

**Effort**: Low

---

### 4. SEC Filings — `sec_filings`

**Data source**: sec.gov (US only, free by law, no key)

> ⚠️ **US-market only**. Covers companies filing with the SEC, including foreign
> companies with US ADRs (BABA, SONY, ASML, TM, etc.). Not applicable to
> purely domestic European/Asian stocks without US listings.

**Functions**:

| Function | Description |
|----------|-------------|
| `list_filings(symbol, type, limit)` | Recent filings: 10-K (annual report), 10-Q (quarterly), 8-K (material events), S-1 (IPO registration), DEF 14A (proxy). Returns date, type, description, and filing URL |
| `get_filing_text(filing_url)` | Extract readable text from an HTML SEC filing. Strips navigation, tables of contents, XBRL tags. Returns sections as structured text. Uses httpx for fetching + BeautifulSoup for extraction |

**Implementation notes**:
- SEC EDGAR API endpoint: `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type={type}`
- Filing text: fetched from `sec.gov/Archives/edgar/data/{cik}/{accession-number}/{primary-document}.htm`
- Need to respect SEC's fair access policy: 10 requests/second max, include User-Agent header
- CIK-to-ticker mapping can be built from the SEC's company_tickers.json (freely downloadable)

**Config**: `{ "timeout": 30, "max_filing_text_chars": 50000 }`

**Effort**: Medium

---

### 5. Portfolio Analysis — `portfolio`

**Data source**: None (pure computation with numpy + scipy)

> This tool does **not** pull data. The agent first fetches price history via
> `stock_data.get_historical_prices()`, then passes the data here for math.

**Functions**:

| Function | Description |
|----------|-------------|
| `analyze_portfolio(holdings, benchmark, risk_free_rate)` | Comprehensive portfolio analysis returning: annual return, annual volatility, Sharpe ratio, Sortino ratio, max drawdown (with duration), Value at Risk (95%), beta, alpha (Jensen's), correlation matrix, diversification score (0–100) |
| `optimize_portfolio(holdings, objective)` | Find optimal weights using scipy.optimize.minimize. Objectives: `"sharpe"` (best return/risk), `"min_volatility"` (safest), `"max_return"` (most aggressive). Constraints: weights sum to 1.0, each ≥ 0 |
| `efficient_frontier(holdings, num_portfolios)` | Generate 1,000+ random valid portfolios and return the efficient frontier points (volatility, return pairs on the Markowitz bullet). Enough data for chart rendering if a frontend chart is added later |

**Input format** (`holdings`):
```json
[
  {
    "ticker": "AAPL",
    "weight": 0.30,
    "prices": [150.23, 151.10, 149.87, ...]
  }
]
```

**Output example** (`analyze_portfolio`):
```json
{
  "annual_return": 0.142,
  "annual_volatility": 0.18,
  "sharpe_ratio": 0.51,
  "sortino_ratio": 0.72,
  "max_drawdown": -0.23,
  "max_drawdown_days": 45,
  "var_95": -0.022,
  "beta": 1.15,
  "alpha": 0.02,
  "correlation_matrix": {"AAPL-MSFT": 0.68, "AAPL-GOOGL": 0.52, ...},
  "diversification_score": 62
}
```

**Under the hood**:
- `numpy` — vectorized log returns, covariance matrices, correlation
- `scipy.optimize.minimize` — constrained portfolio optimization (SLSQP)
- `pandas` — date alignment, resampling, NaN handling across tickers

**Config**: `{ "risk_free_rate": 0.05, "benchmark": "^GSPC" }`

**Effort**: Medium

---

### Financial Tools — Summary Table

| # | Module | Type Key | Source | Scope | Effort |
|---|--------|----------|--------|-------|--------|
| 1 | `stock_data` | `stock_data` | yfinance | Global | Medium |
| 2 | `market_overview` | `market_overview` | yfinance | Global | Low |
| 3 | `etf_data` | `etf_data` | yfinance | Global | Low |
| 4 | `sec_filings` | `sec_filings` | sec.gov | US only | Medium |
| 5 | `portfolio` | `portfolio` | numpy + scipy | N/A (computation) | Medium |

---

## Dependencies to Pre-install

For the proposed tools, these packages would be added to `backend/requirements.txt`:

| Package | Needed For |
|---------|------------|
| `yfinance` | Financial tools (stock_data, market_overview, etf_data) |
| `numpy` | Portfolio analysis (vectorized math) |
| `scipy` | Portfolio optimization (constrained minimization) |
| `pandas` | Date alignment and data handling across tickers |
| `beautifulsoup4` | SEC filing text extraction |
| `weasyprint` | PDF generation |
| `markdown` | Markdown → HTML (for PDF) |
| `openpyxl` | ✅ Already installed (Office uploads) |
| `PyGithub` | GitHub integration |
| `python-gitlab` | GitLab integration |
| `sentence-transformers` | Local embeddings (alternative to API) |
| `pgvector` | PostgreSQL vector extension (if using pgvector) |
| `qrcode` | QR code generation |
| `pillow` | Image processing / QR codes |
| `youtube-transcript-api` | YouTube transcripts |
| `playwright` | Browser automation (needs `playwright install chromium`) |

---

## Quick Wins (Low Effort, High Value)

If starting from scratch, these give the most bang for the buck:

1. **Financial Tools** — `market_overview` + `etf_data` first (~2 days, zero cost), then `stock_data` + `portfolio` (~4 days), then `sec_filings` (~3 days). All free, no API keys, global coverage
2. **Image Generation** — ~1 day, pure API wrapper, very visible to users
3. **Document Generation (PDF/Excel)** — ~2 days, reuses existing `openpyxl`
4. **Translation** — ~half day, pure API wrapper
5. **QR Code** — ~half day, pure library, zero external dependencies

The **Code Interpreter** is the most impactful but also the most complex —
start planning the sandbox infrastructure early.
