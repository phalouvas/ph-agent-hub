# PH Agent Hub — Tool Expansion Plan

> High-level planning document for new tool additions. Each section covers
> the motivation, implementation complexity, and architectural notes.

---

## Current State (13 tools)

| # | Tool | Type key | Category |
|---|------|----------|----------|
| 1 | Calculator | `calculator` | Math — safe AST expression evaluator |
| 2 | Currency Exchange | `currency_exchange` | Finance — exchange rates |
| 3 | Custom Tool Executor | `custom` | Extensibility — admin-authored sandboxed Python |
| 4 | Datetime | `datetime` | Utility — timezone-aware date/time |
| 5 | ERPNext | `erpnext` | Enterprise — full CRUD, file upload, doctype meta |
| 6 | Fetch URL | `fetch_url` | Web — HTTP GET fetching |
| 7 | File List | `file_list` | Built-in — list/read uploaded files (always active) |
| 8 | Membrane | `membrane` | Enterprise — Membrane integration |
| 9 | Memory | `memory` | Built-in — cross-session key-value persistence |
| 10 | RSS Feed | `rss_feed` | Web — RSS/Atom feed reader |
| 11 | Weather | `weather` | Utility — weather via wttr.in |
| 12 | Web Search | `web_search` | Web — SearXNG-backed search |
| 13 | Wikipedia | `wikipedia` | Knowledge — article lookup |

---

## Comparison With Other Agentic Platforms

When comparing with ChatGPT, Claude, Gemini, Copilot, and LangChain/CrewAI, 
the main gaps are:

- **Code execution** — ChatGPT Code Interpreter, Claude artifacts, Gemini code exec
- **Image generation** — DALL·E, Imagen
- **Database queries** — LangChain SQL toolkit, Claude MCP Postgres
- **Document generation** — PDF/Excel export
- **Browser automation** — Claude computer use, Playwright-based tools
- **Git/DevOps** — Copilot, Claude MCP GitHub
- **Calendar / Scheduling** — Gemini Google Calendar, Office 365 integrations
- **Vector / RAG search** — Semantic search over uploaded documents
- **Communication** — Slack, Teams, Email sending

---

## Proposed Tools (Prioritized)

### 🔴 Priority 1 — Financial / Investor Tools

> **Zero API keys, zero cost, zero registration.** All data from yfinance (global, free)
> and SEC EDGAR (US government, free by law), plus pure Python computation.

####  1a. Stock Data — `stock_data`

**Data source**: yfinance (global, free, no key)

**Functions**: `get_stock_quote`, `get_historical_prices`, `get_financials`, `get_key_metrics`, `get_company_info`, `get_dividends`, `get_earnings_history`, `get_analyst_ratings`

**Effort**: Medium

---

#### 1b. Market Overview — `market_overview`

**Data source**: yfinance (global, free, no key)

**Functions**: `get_index_quote` (S&P 500, Nasdaq, Dow, VIX, FTSE, DAX, Nikkei, Hang Seng, Nifty, ASX), `get_market_movers` (day's gainers/losers)

**Effort**: Low

---

#### 1c. ETF Data — `etf_data`

**Data source**: yfinance (global, free, no key)

**Functions**: `get_etf_holdings`, `get_etf_profile`

**Effort**: Low

---

#### 1d. SEC Filings — `sec_filings`

**Data source**: sec.gov (US only, free by law, no key)

**Functions**: `list_filings` (10-K, 10-Q, 8-K), `get_filing_text`

**Effort**: Medium

---

#### 1e. Portfolio Analysis — `portfolio`

**Data source**: None (pure numpy + scipy computation)

**Functions**: `analyze_portfolio` (returns, volatility, Sharpe/Sortino, drawdown, VaR, beta, alpha, correlation, diversification), `optimize_portfolio` (Sharpe/min vol/max return), `efficient_frontier`

**Effort**: Medium

---

### 🟡 Priority 2 — General Tools

#### 2a. Code Interpreter — `code_interpreter`

**Motivation**: The single biggest gap vs. ChatGPT, Claude, and Gemini.
Users constantly ask agents to do data analysis, transform files, generate
charts, run calculations too complex for the calculator tool. This is
*agent-authored* code (different from `custom` tools, which are admin-authored).

**What it provides**:
- `@tool async def execute_python(code: str) -> dict` — run Python in a
  sandbox, return stdout/stderr + any generated base64 images
- Session-scoped persistent virtual filesystem (pip packages survive within a
  session)
- Common data-science libs pre-installed: pandas, numpy, matplotlib, plotly

**Security model** (already proven in `custom_tool_executor.py`):
- Docker container per tenant or per session (gVisor/Firecracker for stronger
  isolation, or a simple `subprocess`-in-Docker approach)
- CPU/memory limits, no network egress by default, 60s timeout
- AST validation rejects `os`, `sys`, `subprocess`, `eval`, `exec`, `importlib`,
  `__builtins__` manipulation

**Architecture notes**:
- Config in `tools.config`: `{ "timeout": 60, "allow_network": false, "packages": ["pandas","numpy"] }`
- The executor process lives in the same Docker Compose network, exposed via a
  simple HTTP API, or spawned as a subprocess inside the backend container if
  the backend runs with sufficient isolation
- Output artifacts (PNG, CSV) written to MinIO/S3, returned as download URLs

**Effort**: High (sandbox infrastructure + new microservice or container)

---

### 🟡 Priority 2 — General Tools (continued)

#### 2b. SQL Database Query — `sql_query`

**Motivation**: Huge enterprise value. "How many orders did we have last month?",
"Show me top 10 customers by revenue", "What's the average response time this
week?" — business users live in databases.

**What it provides**:
- `@tool async def sql_query(query: str) -> dict` — execute a read-only SQL
  query against a tenant-configured database
- `@tool async def list_tables() -> list[str]` — schema discovery so the agent
  knows what to query
- `@tool async def describe_table(table: str) -> list[dict]` — column names,
  types, and sample values

**Security model**:
- AST parsing rejects DML (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`,
  `TRUNCATE`, `CREATE`, `GRANT`, `REVOKE`)
- Read-only transaction (`SET TRANSACTION READ ONLY` before execution)
- Configurable row limit (default 1000)
- Per-tenant connection string stored encrypted in `tools.config.connection_string`

**Architecture notes**:
- Connection strings encrypted via existing `core/encryption.py` before DB storage
- SQLAlchemy async engine created once, cached per tool instance
- Supported backends: PostgreSQL, MySQL/MariaDB, SQLite (file upload)
- Fits multi-tenant architecture — each tenant connects to their own DB

**Effort**: Medium (SQL parsing safety + encrypted connection strings)

---

### 🟡 Priority 2 (continued)

#### 2c. Image Generation — `image_generation`

**Motivation**: DALL·E / Stable Diffusion / Flux. Users frequently ask agents
to "create an image of X" for presentations, marketing, or creative work.

**What it provides**:
- `@tool async def generate_image(prompt: str, size: str = "1024x1024", style: str = "natural") -> dict`
  — returns `{ "url": "...", "width": 1024, "height": 1024 }`
- Images stored in MinIO/S3 (reuse existing `storage/s3.py`)
- Multiple model backends configurable in `tools.config.provider`:
  `openai` (DALL·E 3), `stability` (Stable Diffusion), `replicate` (Flux),
  or a self-hosted ComfyUI endpoint

**Architecture notes**:
- Stateless HTTP API calls to the provider — no infrastructure changes needed
- Reuses existing `models/` provider abstractions if OpenAI path is taken
- Config: `{ "provider": "openai", "model": "dall-e-3", "default_size": "1024x1024" }`

**Effort**: Low (API wrapper only)

---

#### 2d. Document Generation — `document_generation`

**Motivation**: "Create a PDF report from this analysis", "Export this data as
an Excel spreadsheet", "Generate a Word document from this outline". Very
common enterprise need.

**What it provides**:
- `@tool async def generate_pdf(markdown: str, title: str = "Report") -> dict`
  — Markdown → PDF via weasyprint or markdown2 + WeasyPrint
- `@tool async def generate_excel(data: list[dict], sheet_name: str = "Sheet1") -> dict`
  — list-of-dicts → .xlsx via openpyxl (already installed for markitdown)
- `@tool async def generate_csv(data: list[dict]) -> dict`
- All generated files stored in MinIO/S3, returned as download URLs

**Architecture notes**:
- `openpyxl` already in `requirements.txt` (from the Office upload fix)
- Add `weasyprint` and `markdown` to `requirements.txt`
- Config: `{ "default_format": "pdf", "company_logo_url": "https://..." }`

**Effort**: Low-Medium (library integration + S3 upload)

---

#### 2e. Browser Automation — `browser`

**Motivation**: `fetch_url` only works for server-rendered pages. Many modern
sites require JavaScript execution. Also enables: taking screenshots, filling
forms, extracting rendered content, automated testing.

**What it provides**:
- `@tool async def take_screenshot(url: str, selector: str | None = None) -> dict`
  — returns base64 PNG screenshot of a page or element
- `@tool async def extract_text(url: str) -> dict`
  — returns rendered text content (after JS execution)
- `@tool async def extract_table(url: str, table_index: int = 0) -> dict`
  — extract HTML tables as structured data

**Security model**:
- Playwright in a separate sandbox container (already Dockerized)
- Request filtering: only allow HTTP/HTTPS, block private IP ranges (10.x,
  172.16.x, 192.168.x, 127.x)
- 30s timeout, 10MB max response
- Screenshots stored in MinIO/S3

**Architecture notes**:
- Playwright Python bindings + headless Chromium
- Could be a sidecar container to keep the backend stateless
- Config: `{ "timeout": 30, "viewport_width": 1280, "viewport_height": 720 }`

**Effort**: High (new container + security boundaries)

---

#### 2f. GitHub / GitLab Integration — `github`

**Motivation**: Developer-focused enterprises need this. Search code, list
issues, create PRs, review pull requests, read repository structure.

**What it provides**:
- `@tool async def search_code(query: str, repo: str) -> list[dict]`
- `@tool async def list_issues(repo: str, state: str = "open") -> list[dict]`
- `@tool async def get_file_content(repo: str, path: str, ref: str = "main") -> dict`
- `@tool async def list_pull_requests(repo: str, state: str = "open") -> list[dict]`
- `@tool async def create_issue(repo: str, title: str, body: str) -> dict`

**Security model**:
- Personal Access Token or GitHub App installation token stored encrypted in
  `tools.config`
- Rate-limit aware (returns remaining quota in response)
- Repo allowlist in config: `{ "allowed_repos": ["org/*"] }`

**Architecture notes**:
- GitHub: use `PyGithub` or raw REST API via httpx
- GitLab: use `python-gitlab` or raw REST API
- Config: `{ "provider": "github", "token": "...", "api_url": "https://api.github.com" }`

**Effort**: Medium (API wrappers, multiple endpoints)

---

#### 2g. Calendar / Scheduling — `calendar`

**Motivation**: "Schedule a meeting next Tuesday at 2pm", "What's on my
calendar tomorrow?", "Find a time when everyone is free".

**What it provides**:
- `@tool async def list_events(date_from: str, date_to: str) -> list[dict]`
- `@tool async def create_event(summary: str, start: str, end: str, attendees: list[str] | None = None) -> dict`
- `@tool async def find_free_slots(date: str, duration_minutes: int = 60) -> list[dict]`

**Architecture notes**:
- Google Calendar API (service account at tenant level, or OAuth per user)
- CalDAV for generic calendar servers (Nextcloud, iCloud)
- OAuth flow would need new frontend components and backend endpoints —
  significantly more work than API-key-based tools
- Config: `{ "provider": "google", "credentials": {...}, "calendar_id": "primary" }`

**Effort**: Medium-High (OAuth flow adds complexity)

---

#### 2h. Vector DB / RAG Search — `rag_search`

**Motivation**: Let agents semantically search uploaded documents. Users upload
PDFs, Office docs, and text files — currently agents can only read them
sequentially with `read_file_content`. RAG would let agents answer "What does
our company policy say about vacation days?" across all uploaded documents.

**What it provides**:
- `@tool async def search_documents(query: str, top_k: int = 5) -> list[dict]`
  — semantic search returning relevant chunks with source filenames
- `@tool async def build_index() -> dict`
  — manually trigger re-indexing of uploaded files (also done automatically on upload)

**Architecture notes**:
- Embedding model: OpenAI `text-embedding-3-small`, or a local model via
  sentence-transformers, or the same model provider used for chat
- Vector store: pgvector (PostgreSQL extension) or Qdrant (existing Docker
  service) or ChromaDB
- Chunking strategy: recursive character text splitter, ~500 tokens per chunk
- Already have `markitdown` for text extraction from Office/PDF files
- Config: `{ "provider": "openai", "embedding_model": "text-embedding-3-small", "chunk_size": 500 }`

**Effort**: Medium (embedding + vector store + chunking pipeline)

---

#### 2i. Communication — `slack` / `email`

**Motivation**: "Send this summary to the #general channel", "Email this report
to the team".

**What it provides**:
- Slack: `@tool async def send_slack_message(channel: str, text: str) -> dict`
- Email: `@tool async def send_email(to: str, subject: str, body: str) -> dict`
  via SMTP, SendGrid, or Resend API

**Architecture notes**:
- Slack webhook URL or bot token in `tools.config`
- SMTP credentials or API key encrypted in config
- Optional recipient allowlist for security

**Effort**: Low (simple HTTP API calls)

---

### 🟢 Priority 3 — Nice to Have

---

#### 3a. Translation — `translation`
- DeepL or LibreTranslate API
- `@tool async def translate(text: str, target_lang: str, source_lang: str = "auto") -> dict`
- Effort: Low

#### 3b. YouTube Transcript — `youtube`
- `youtube-transcript-api` library or Invidious API
- `@tool async def get_transcript(video_url: str) -> dict`
- Effort: Low

#### 3c. Maps / Geocoding — `maps`
- OpenStreetMap Nominatim (free) or Google Maps API
- `@tool async def geocode(address: str) -> dict`
- `@tool async def reverse_geocode(lat: float, lon: float) -> dict`
- Effort: Low

#### 3d. QR Code / Barcode Generation — `qrcode`
- `qrcode` + `pillow` Python libraries
- `@tool async def generate_qrcode(data: str) -> dict` → returns image URL
- Effort: Very Low

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
