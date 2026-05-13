# =============================================================================
# PH Agent Hub — Stock Data Tool Factory (yfinance)
# =============================================================================
# Builds MAF @tool-decorated async functions for stock quotes, historical
# prices, financial statements, key metrics, company info, dividends,
# earnings history, and analyst ratings. Uses yfinance — free, no API key.
# =============================================================================

import asyncio
import logging
from datetime import datetime, timezone

from agent_framework import tool

logger = logging.getLogger(__name__)

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


def _df_to_dicts(df, date_key: str = "date") -> list[dict]:
    """Convert a pandas DataFrame to a list of dicts, with date index as key."""
    import pandas as pd

    if df is None or (isinstance(df, pd.DataFrame) and df.empty):
        return []
    records = df.reset_index().to_dict(orient="records")
    # Convert Timestamps to strings
    clean = []
    for r in records:
        item = {}
        for k, v in r.items():
            if isinstance(v, pd.Timestamp):
                item[k] = v.isoformat()
            elif isinstance(v, (int, float)):
                # Replace NaN/Inf with None
                if pd.isna(v) or (isinstance(v, float) and not pd.isna(v) and v == float("inf")):
                    item[k] = None
                else:
                    item[k] = v
            else:
                item[k] = v
        clean.append(item)
    return clean


# ---------------------------------------------------------------------------
# Tool factory
# ---------------------------------------------------------------------------


def build_stock_data_tools(tool_config: dict | None = None) -> list:
    """Return a list of MAF @tool-decorated stock data functions.

    Provides:
    - ``get_stock_quote``: real-time stock quote
    - ``get_historical_prices``: OHLCV historical data
    - ``get_financials``: income statement, balance sheet, cash flow
    - ``get_key_metrics``: P/E, P/B, ROE, etc.
    - ``get_company_info``: company profile and description
    - ``get_dividends``: dividend history
    - ``get_earnings_history``: earnings history
    - ``get_analyst_ratings``: analyst recommendations and price targets

    Args:
        tool_config: Optional ``Tool.config`` JSON dict. Currently unused.

    Returns:
        A list of callables ready to pass to ``Agent(tools=...)``.
    """
    _ = tool_config

    @tool
    async def get_stock_quote(symbol: str) -> dict:
        """Get a real-time stock quote with key trading data.

        Uses yfinance — free, no API key required.

        Args:
            symbol: Stock ticker symbol (e.g. "AAPL", "MSFT", "GOOGL").

        Returns:
            A dict with: ``symbol``, ``name``, ``price``, ``previous_close``,
            ``change``, ``change_pct``, ``day_high``, ``day_low``,
            ``day_open``, ``volume``, ``avg_volume``, ``market_cap``,
            ``bid``, ``ask``, ``fifty_two_week_high``,
            ``fifty_two_week_low``, ``currency``, ``exchange``,
            ``market_state``, ``source``.
        """
        import yfinance as yf

        sym = symbol.upper().strip()
        logger.info("get_stock_quote: %s", sym)

        try:
            t = await asyncio.to_thread(yf.Ticker, sym)
            info = {}
            try:
                info = t.info or {}
            except Exception:
                pass

            price = (
                _safe_float(info.get("regularMarketPrice"))
                or _safe_float(info.get("currentPrice"))
                or _safe_float(info.get("previousClose"))
            )
            prev_close = _safe_float(info.get("previousClose")) or _safe_float(
                info.get("regularMarketPreviousClose")
            )
            change = None
            change_pct = None
            if price is not None and prev_close is not None and prev_close != 0:
                change = round(price - prev_close, 2)
                change_pct = round((change / prev_close) * 100, 2)

            return {
                "symbol": sym,
                "name": info.get("shortName") or info.get("longName") or sym,
                "price": price,
                "previous_close": prev_close,
                "change": change,
                "change_pct": change_pct,
                "day_high": _safe_float(info.get("regularMarketDayHigh") or info.get("dayHigh")),
                "day_low": _safe_float(info.get("regularMarketDayLow") or info.get("dayLow")),
                "day_open": _safe_float(info.get("regularMarketOpen") or info.get("open")),
                "volume": _safe_float(info.get("regularMarketVolume") or info.get("volume")),
                "avg_volume": _safe_float(info.get("averageVolume") or info.get("averageDailyVolume10Day")),
                "market_cap": _safe_float(info.get("marketCap")),
                "bid": _safe_float(info.get("bid")),
                "ask": _safe_float(info.get("ask")),
                "fifty_two_week_high": _safe_float(info.get("fiftyTwoWeekHigh")),
                "fifty_two_week_low": _safe_float(info.get("fiftyTwoWeekLow")),
                "currency": info.get("currency", ""),
                "exchange": info.get("exchange") or info.get("fullExchangeName") or "",
                "market_state": info.get("marketState", ""),
                "source": "yfinance",
            }

        except Exception as exc:
            logger.exception("get_stock_quote failed for %s", sym)
            return {"symbol": sym, "error": str(exc)}

    @tool
    async def get_historical_prices(
        symbol: str,
        period: str = "1mo",
        interval: str = "1d",
    ) -> dict:
        """Get historical OHLCV price data for a stock.

        Uses yfinance — free, no API key required.

        Args:
            symbol: Stock ticker symbol (e.g. "AAPL").
            period: Time period — "1d", "5d", "1mo", "3mo", "6mo", "1y",
                "2y", "5y", "10y", "ytd", "max". Default "1mo".
            interval: Data interval — "1m", "5m", "15m", "30m", "1h",
                "1d", "1wk", "1mo". Default "1d".
                Note: minute-level intervals only available for recent periods.

        Returns:
            A dict with:
            - ``symbol``: the stock ticker
            - ``period``, ``interval``: as requested
            - ``prices``: list of OHLCV dicts with ``date``, ``open``,
              ``high``, ``low``, ``close``, ``volume``, ``dividends``,
              ``stock_splits``
            - ``count``: number of data points
            - ``source``: "yfinance"
        """
        import yfinance as yf

        sym = symbol.upper().strip()
        logger.info("get_historical_prices: %s period=%s interval=%s", sym, period, interval)

        try:
            t = await asyncio.to_thread(yf.Ticker, sym)
            df = await asyncio.to_thread(
                t.history, period=period, interval=interval
            )
            prices = _df_to_dicts(df)
            return {
                "symbol": sym,
                "period": period,
                "interval": interval,
                "prices": prices,
                "count": len(prices),
                "source": "yfinance",
            }

        except Exception as exc:
            logger.exception("get_historical_prices failed for %s", sym)
            return {"symbol": sym, "error": str(exc)}

    @tool
    async def get_financials(
        symbol: str,
        statement_type: str = "income",
        period: str = "annual",
    ) -> dict:
        """Get financial statements for a company.

        Uses yfinance — free, no API key required.

        Args:
            symbol: Stock ticker symbol (e.g. "AAPL").
            statement_type: "income" (income statement), "balance"
                (balance sheet), or "cash" (cash flow). Default "income".
            period: "annual" or "quarterly". Default "annual".

        Returns:
            A dict with:
            - ``symbol``: the stock ticker
            - ``statement_type``: the type of statement
            - ``period``: annual or quarterly
            - ``statements``: list of statement dicts, each with ``date``
              and financial line items
            - ``source``: "yfinance"
        """
        import yfinance as yf

        sym = symbol.upper().strip()
        logger.info(
            "get_financials: %s type=%s period=%s", sym, statement_type, period
        )

        valid_types = {"income", "balance", "cash"}
        stype = statement_type.lower().strip()
        if stype not in valid_types:
            return {
                "symbol": sym,
                "error": f"Invalid statement_type '{statement_type}'. "
                f"Must be one of: income, balance, cash",
            }

        is_quarterly = period.lower().strip() == "quarterly"

        try:
            t = await asyncio.to_thread(yf.Ticker, sym)

            if stype == "income":
                attr = "quarterly_income_stmt" if is_quarterly else "income_stmt"
            elif stype == "balance":
                attr = "quarterly_balance_sheet" if is_quarterly else "balance_sheet"
            else:
                attr = "quarterly_cashflow" if is_quarterly else "cashflow"

            df = await asyncio.to_thread(getattr, t, attr)
            if df is None:
                return {
                    "symbol": sym,
                    "statement_type": stype,
                    "period": period,
                    "statements": [],
                    "source": "yfinance",
                }

            # Transpose so dates are rows and line items are columns
            import pandas as pd
            if isinstance(df, pd.DataFrame):
                df_t = df.transpose()
                statements = _df_to_dicts(df_t)
            else:
                statements = []

            return {
                "symbol": sym,
                "statement_type": stype,
                "period": period,
                "statements": statements,
                "count": len(statements),
                "source": "yfinance",
            }

        except Exception as exc:
            logger.exception("get_financials failed for %s", sym)
            return {"symbol": sym, "error": str(exc)}

    @tool
    async def get_key_metrics(symbol: str) -> dict:
        """Get key valuation and profitability metrics for a stock.

        Uses yfinance — free, no API key required.

        Args:
            symbol: Stock ticker symbol (e.g. "AAPL").

        Returns:
            A dict with: ``symbol``, ``name``, and metrics including
            ``pe_ratio`` (trailing), ``forward_pe``, ``peg_ratio``,
            ``pb_ratio``, ``ps_ratio``, ``roe``, ``roa``, ``debt_to_equity``,
            ``current_ratio``, ``quick_ratio``, ``gross_margins``,
            ``operating_margins``, ``profit_margins``, ``eps_trailing``,
            ``eps_forward``, ``dividend_yield``, ``payout_ratio``,
            ``beta``, ``revenue_growth``, ``earnings_growth``,
            ``free_cashflow``, ``enterprise_value``, ``ev_to_revenue``,
            ``ev_to_ebitda``, ``short_ratio``, and ``source``.
        """
        import yfinance as yf

        sym = symbol.upper().strip()
        logger.info("get_key_metrics: %s", sym)

        try:
            t = await asyncio.to_thread(yf.Ticker, sym)
            info = {}
            try:
                info = t.info or {}
            except Exception:
                pass

            return {
                "symbol": sym,
                "name": info.get("shortName") or info.get("longName") or sym,
                "pe_ratio": _safe_float(info.get("trailingPE")),
                "forward_pe": _safe_float(info.get("forwardPE")),
                "peg_ratio": _safe_float(info.get("pegRatio")),
                "pb_ratio": _safe_float(info.get("priceToBook")),
                "ps_ratio": _safe_float(info.get("priceToSalesTrailing12Months")),
                "roe": _safe_float(info.get("returnOnEquity")),
                "roa": _safe_float(info.get("returnOnAssets")),
                "debt_to_equity": _safe_float(info.get("debtToEquity")),
                "current_ratio": _safe_float(info.get("currentRatio")),
                "quick_ratio": _safe_float(info.get("quickRatio")),
                "gross_margins": _safe_float(info.get("grossMargins")),
                "operating_margins": _safe_float(info.get("operatingMargins")),
                "profit_margins": _safe_float(info.get("profitMargins")),
                "eps_trailing": _safe_float(info.get("trailingEps")),
                "eps_forward": _safe_float(info.get("forwardEps")),
                "revenue_per_share": _safe_float(info.get("revenuePerShare")),
                "dividend_yield": _safe_float(info.get("dividendYield")),
                "payout_ratio": _safe_float(info.get("payoutRatio")),
                "beta": _safe_float(info.get("beta")),
                "revenue_growth": _safe_float(info.get("revenueGrowth")),
                "earnings_growth": _safe_float(info.get("earningsGrowth")),
                "free_cashflow": _safe_float(info.get("freeCashflow")),
                "enterprise_value": _safe_float(info.get("enterpriseValue")),
                "ev_to_revenue": _safe_float(info.get("enterpriseToRevenue")),
                "ev_to_ebitda": _safe_float(info.get("enterpriseToEbitda")),
                "short_ratio": _safe_float(info.get("shortRatio")),
                "short_pct_float": _safe_float(info.get("shortPercentOfFloat")),
                "source": "yfinance",
            }

        except Exception as exc:
            logger.exception("get_key_metrics failed for %s", sym)
            return {"symbol": sym, "error": str(exc)}

    @tool
    async def get_company_info(symbol: str) -> dict:
        """Get detailed company profile and business description.

        Uses yfinance — free, no API key required.

        Args:
            symbol: Stock ticker symbol (e.g. "AAPL").

        Returns:
            A dict with: ``symbol``, ``name``, ``description``,
            ``sector``, ``industry``, ``website``, ``country``,
            ``state``, ``city``, ``employees``, ``ipo_date``,
            ``exchange``, ``currency``, ``phone``, ``fax``,
            ``address``, ``officers`` (list), ``source``.
        """
        import yfinance as yf

        sym = symbol.upper().strip()
        logger.info("get_company_info: %s", sym)

        try:
            t = await asyncio.to_thread(yf.Ticker, sym)
            info = {}
            try:
                info = t.info or {}
            except Exception:
                pass

            # Company officers
            officers = []
            raw_officers = info.get("companyOfficers") or []
            if isinstance(raw_officers, list):
                for o in raw_officers:
                    if isinstance(o, dict):
                        officers.append({
                            "name": o.get("name", ""),
                            "title": o.get("title", ""),
                            "age": o.get("age"),
                            "year_born": o.get("yearBorn"),
                        })

            return {
                "symbol": sym,
                "name": info.get("shortName") or info.get("longName") or sym,
                "description": info.get("longBusinessSummary", ""),
                "sector": info.get("sector", ""),
                "industry": info.get("industry", ""),
                "website": info.get("website", ""),
                "country": info.get("country", ""),
                "state": info.get("state", ""),
                "city": info.get("city", ""),
                "employees": _safe_float(info.get("fullTimeEmployees")),
                "ipo_date": str(info.get("ipoDate", "")),
                "exchange": info.get("exchange") or info.get("fullExchangeName") or "",
                "currency": info.get("currency", ""),
                "phone": info.get("phone", ""),
                "fax": info.get("fax", ""),
                "address": (
                    f"{info.get('address1', '')} {info.get('address2', '')}".strip()
                    if info.get("address1")
                    else ""
                ),
                "officers": officers,
                "source": "yfinance",
            }

        except Exception as exc:
            logger.exception("get_company_info failed for %s", sym)
            return {"symbol": sym, "error": str(exc)}

    @tool
    async def get_dividends(symbol: str, period: str = "5y") -> dict:
        """Get dividend history for a stock.

        Uses yfinance — free, no API key required.

        Args:
            symbol: Stock ticker symbol (e.g. "AAPL").
            period: Time period for dividend history: "1y", "2y",
                "5y", "10y", "max". Default "5y".

        Returns:
            A dict with:
            - ``symbol``: the stock ticker
            - ``dividend_yield``: current dividend yield
            - ``dividend_rate``: annual dividend rate
            - ``payout_ratio``: dividend payout ratio
            - ``ex_dividend_date``: next ex-dividend date
            - ``history``: list of dicts with ``date`` and ``dividend``
            - ``count``: number of dividend payments
            - ``source``: "yfinance"
        """
        import yfinance as yf

        sym = symbol.upper().strip()
        logger.info("get_dividends: %s period=%s", sym, period)

        try:
            t = await asyncio.to_thread(yf.Ticker, sym)
            info = {}
            try:
                info = t.info or {}
            except Exception:
                pass

            divs = await asyncio.to_thread(t.dividends)
            import pandas as pd

            history = []
            if isinstance(divs, pd.Series) and not divs.empty:
                # Filter by period
                if period != "max":
                    now = pd.Timestamp.now(tz=divs.index.tz)
                    if period == "1y":
                        cutoff = now - pd.DateOffset(years=1)
                    elif period == "2y":
                        cutoff = now - pd.DateOffset(years=2)
                    elif period == "5y":
                        cutoff = now - pd.DateOffset(years=5)
                    elif period == "10y":
                        cutoff = now - pd.DateOffset(years=10)
                    else:
                        cutoff = None
                    if cutoff is not None:
                        divs = divs[divs.index >= cutoff]

                for dt, val in divs.items():
                    history.append({
                        "date": dt.isoformat() if hasattr(dt, "isoformat") else str(dt),
                        "dividend": _safe_float(val),
                    })

            return {
                "symbol": sym,
                "dividend_yield": _safe_float(info.get("dividendYield")),
                "dividend_rate": _safe_float(info.get("dividendRate")),
                "payout_ratio": _safe_float(info.get("payoutRatio")),
                "ex_dividend_date": str(info.get("exDividendDate", "")),
                "history": history,
                "count": len(history),
                "source": "yfinance",
            }

        except Exception as exc:
            logger.exception("get_dividends failed for %s", sym)
            return {"symbol": sym, "error": str(exc)}

    @tool
    async def get_earnings_history(symbol: str) -> dict:
        """Get historical and upcoming earnings data for a stock.

        Uses yfinance — free, no API key required.

        Args:
            symbol: Stock ticker symbol (e.g. "AAPL").

        Returns:
            A dict with:
            - ``symbol``: the stock ticker
            - ``earnings_history``: list of past earnings with ``date``,
              ``eps_estimate``, ``eps_actual``, ``surprise_pct``
            - ``upcoming_earnings``: list of future earnings dates
              with ``date``, ``eps_estimate``, ``revenue_estimate``
            - ``earnings_per_share``: trailing and forward EPS
            - ``source``: "yfinance"
        """
        import yfinance as yf

        sym = symbol.upper().strip()
        logger.info("get_earnings_history: %s", sym)

        try:
            t = await asyncio.to_thread(yf.Ticker, sym)
            info = {}
            try:
                info = t.info or {}
            except Exception:
                pass

            # Earnings history (past)
            earnings_history = []
            try:
                raw_history = t.earnings_history
                if raw_history is not None:
                    if hasattr(raw_history, "to_dict"):
                        import pandas as pd
                        if isinstance(raw_history, pd.DataFrame) and not raw_history.empty:
                            for _, row in raw_history.iterrows():
                                earnings_history.append({
                                    "date": str(row.get("EPSReportDate", row.get("date", ""))),
                                    "eps_estimate": _safe_float(row.get("EPSEstimate", row.get("epsEstimate"))),
                                    "eps_actual": _safe_float(row.get("EPSActual", row.get("epsActual"))),
                                    "surprise_pct": _safe_float(row.get("Surprise(%)", row.get("surprisePercent"))),
                                })
                    elif isinstance(raw_history, dict):
                        earnings_history = raw_history.get("earnings", [])
            except Exception:
                pass

            # Earnings dates (upcoming)
            upcoming = []
            try:
                cal = t.calendar
                if cal is not None:
                    if hasattr(cal, "to_dict"):
                        import pandas as pd
                        if isinstance(cal, pd.DataFrame) and not cal.empty:
                            for _, row in cal.iterrows():
                                upcoming.append({
                                    "date": str(row.get("Earnings Date", "")),
                                    "eps_estimate": _safe_float(row.get("Earnings Average", row.get("epsEstimate"))),
                                    "revenue_estimate": _safe_float(row.get("Revenue Average", row.get("revenueEstimate"))),
                                })
                    elif isinstance(cal, dict):
                        upcoming.append({
                            "date": str(cal.get("Earnings Date", "")),
                            "eps_estimate": _safe_float(cal.get("Earnings Average")),
                            "revenue_estimate": _safe_float(cal.get("Revenue Average")),
                        })
            except Exception:
                pass

            return {
                "symbol": sym,
                "earnings_history": earnings_history,
                "upcoming_earnings": upcoming,
                "eps_trailing": _safe_float(info.get("trailingEps")),
                "eps_forward": _safe_float(info.get("forwardEps")),
                "source": "yfinance",
            }

        except Exception as exc:
            logger.exception("get_earnings_history failed for %s", sym)
            return {"symbol": sym, "error": str(exc)}

    @tool
    async def get_analyst_ratings(symbol: str) -> dict:
        """Get analyst recommendations and price targets for a stock.

        Uses yfinance — free, no API key required.

        Args:
            symbol: Stock ticker symbol (e.g. "AAPL").

        Returns:
            A dict with:
            - ``symbol``: the stock ticker
            - ``recommendation``: overall rating (e.g. "buy", "hold", "sell")
            - ``target_mean``: average analyst price target
            - ``target_high``: highest price target
            - ``target_low``: lowest price target
            - ``target_median``: median price target
            - ``number_of_analysts``: number of analysts covering
            - ``recommendations``: list of rating changes with ``date``,
              ``firm``, ``to_grade``, ``from_grade``, ``action``
            - ``source``: "yfinance"
        """
        import yfinance as yf

        sym = symbol.upper().strip()
        logger.info("get_analyst_ratings: %s", sym)

        try:
            t = await asyncio.to_thread(yf.Ticker, sym)
            info = {}
            try:
                info = t.info or {}
            except Exception:
                pass

            # Analyst recommendations trend
            recommendations = []
            try:
                recs = t.recommendations
                if recs is not None:
                    import pandas as pd
                    if isinstance(recs, pd.DataFrame) and not recs.empty:
                        for _, row in recs.head(20).iterrows():
                            recommendations.append({
                                "date": str(row.get("Date", row.get("date", ""))),
                                "firm": str(row.get("Firm", row.get("firm", ""))),
                                "to_grade": str(row.get("To Grade", row.get("toGrade", ""))),
                                "from_grade": str(row.get("From Grade", row.get("fromGrade", ""))),
                                "action": str(row.get("Action", row.get("action", ""))),
                            })
            except Exception:
                pass

            return {
                "symbol": sym,
                "recommendation": info.get("recommendationKey", info.get("recommendationMean", "")),
                "target_mean": _safe_float(info.get("targetMeanPrice")),
                "target_high": _safe_float(info.get("targetHighPrice")),
                "target_low": _safe_float(info.get("targetLowPrice")),
                "target_median": _safe_float(info.get("targetMedianPrice")),
                "number_of_analysts": _safe_float(info.get("numberOfAnalystOpinions")),
                "recommendations": recommendations,
                "source": "yfinance",
            }

        except Exception as exc:
            logger.exception("get_analyst_ratings failed for %s", sym)
            return {"symbol": sym, "error": str(exc)}

    return [
        get_stock_quote,
        get_historical_prices,
        get_financials,
        get_key_metrics,
        get_company_info,
        get_dividends,
        get_earnings_history,
        get_analyst_ratings,
    ]
