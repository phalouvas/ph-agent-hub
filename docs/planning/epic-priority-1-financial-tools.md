# Epic: Financial / Investor Tools (Priority 1)

> Zero API keys, zero cost, zero registration. yfinance (global) + SEC EDGAR (US, free by law) + numpy/scipy (pure computation).

## Checklist

### Phase 1a — Quick Wins (~2 days)
- [ ] **`market_overview`** — index quotes (S&P 500, Nasdaq, Dow, VIX, FTSE, DAX, Nikkei, Hang Seng, Nifty, ASX) + market movers (gainers/losers)
- [ ] **`etf_data`** — ETF holdings (top N by weight) + ETF profile (category, expense ratio, AUM)

### Phase 1b — Core Tools (~4 days)
- [ ] **`stock_data`** — stock quotes, historical prices (OHLCV), financial statements (income/balance sheet/cash flow), key metrics (P/E, P/B, ROE, etc.), company info, dividends, earnings history, analyst ratings
- [ ] **`portfolio`** — portfolio analysis (returns, volatility, Sharpe/Sortino, drawdown, VaR, beta, alpha, correlation, diversification score) + portfolio optimization (Sharpe/min vol/max return) + efficient frontier

### Phase 1c — Filings (~3 days)
- [ ] **`sec_filings`** — list recent filings (10-K, 10-Q, 8-K) + extract readable text from filing HTML

## Key Constraints
- ❌ No API keys, no paid services, no registration
- ❌ No new infrastructure (no new containers, no new services)
- ✅ yfinance pip package (free, scrapes Yahoo Finance)
- ✅ sec.gov HTTP requests (free by law, httpx already installed)
- ✅ numpy + scipy + pandas (pure computation, pip install)

## New Dependencies
```txt
yfinance
numpy
scipy
pandas
beautifulsoup4
```

## Implementation Pattern
Each tool follows the standard 5-step pattern:
1. Create `backend/src/tools/TOOL_NAME.py` with `build_TOOL_NAME_tools(tool_config)` factory
2. Add type string to `VALID_TOOL_TYPES` in `backend/src/services/tool_service.py`
3. Create Alembic migration: `ALTER TYPE tool_type_enum ADD VALUE 'new_type'`
4. Add `elif tool.type == "new_type":` branch in `_build_tool_callables()` in `backend/src/agents/runner.py`
5. (Optional) Add config fields in `frontend/src/features/admin/resources/tools/ToolForm.tsx`

## Reference
Full details in `docs/planning/tools.md` → Financial / Investor Tools section.
