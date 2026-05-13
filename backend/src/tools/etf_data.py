# =============================================================================
# PH Agent Hub — ETF Data Tool Factory (yfinance)
# =============================================================================
# Builds MAF @tool-decorated async functions for ETF holdings and profile
# using the free yfinance library. No API key required.
# =============================================================================

import asyncio
import logging

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


def _safe_int(val) -> int | None:
    """Convert a value to int, returning None on failure."""
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Tool factory
# ---------------------------------------------------------------------------


def build_etf_data_tools(tool_config: dict | None = None) -> list:
    """Return a list of MAF @tool-decorated ETF data functions.

    Provides:
    - ``get_etf_holdings``: get top holdings by weight
    - ``get_etf_profile``: get ETF profile (category, expense ratio, AUM, etc.)

    Args:
        tool_config: Optional ``Tool.config`` JSON dict. May include:
            - ``default_top_n`` (int): default number of top holdings (default 10)

    Returns:
        A list of callables ready to pass to ``Agent(tools=...)``.
    """
    config = tool_config or {}
    default_top_n: int = int(config.get("default_top_n", 10))

    @tool
    async def get_etf_holdings(
        symbol: str,
        top_n: int | None = None,
    ) -> dict:
        """Get the top holdings of an ETF by portfolio weight.

        Uses yfinance — free, no API key required.

        Args:
            symbol: ETF ticker symbol (e.g. "SPY", "QQQ", "IWM", "VTI").
            top_n: Number of top holdings to return. Defaults to 10.

        Returns:
            A dict with:
            - ``symbol``: the ETF ticker
            - ``name``: ETF full name
            - ``holdings``: list of holding dicts, each with ``symbol``,
              ``name``, ``weight_pct``, ``shares`` (if available)
            - ``holdings_count``: number of holdings returned
            - ``source``: "yfinance"
        """
        import yfinance as yf

        limit = top_n if top_n is not None else default_top_n
        sym = symbol.upper().strip()
        logger.info("get_etf_holdings: %s (top_n=%d)", sym, limit)

        try:
            t = await asyncio.to_thread(yf.Ticker, sym)
            info = {}
            try:
                info = t.info or {}
            except Exception:
                pass

            etf_name = info.get("shortName") or info.get("longName") or sym

            holdings_list: list[dict] = []

            # Primary: use funds_data.top_holdings (yfinance >= 1.3.0)
            try:
                funds = t.funds_data
                if funds is not None:
                    top_holdings = getattr(funds, "top_holdings", None)
                    if top_holdings is not None:
                        import pandas as pd
                        if isinstance(top_holdings, pd.DataFrame) and not top_holdings.empty:
                            for idx, row in top_holdings.head(limit).iterrows():
                                holding = {"symbol": str(idx)}
                                row_dict = row.to_dict()
                                # Map column names
                                for col_name, val in row_dict.items():
                                    if col_name == "Name":
                                        holding["name"] = str(val) if val else ""
                                    elif "Percent" in col_name or "Weight" in col_name or "pct" in col_name.lower():
                                        holding["weight_pct"] = _safe_float(val)
                                    elif "Share" in col_name or "Holding" in col_name:
                                        holding["shares"] = _safe_float(val)
                                if "name" not in holding:
                                    holding["name"] = ""
                                holdings_list.append(holding)
            except Exception as exc:
                logger.debug("get_etf_holdings: funds_data failed: %s", exc)

            # Fallback: try sector_weightings / equity_holdings from funds_data
            if not holdings_list:
                try:
                    funds = t.funds_data
                    if funds is not None:
                        eq_holdings = getattr(funds, "equity_holdings", None)
                        if eq_holdings is not None:
                            import pandas as pd
                            if isinstance(eq_holdings, pd.DataFrame) and not eq_holdings.empty:
                                for idx, row in eq_holdings.head(limit).iterrows():
                                    holding = {"symbol": str(idx)}
                                    row_dict = row.to_dict()
                                    for col_name, val in row_dict.items():
                                        if "Name" in col_name:
                                            holding["name"] = str(val) if val else ""
                                        elif "Percent" in col_name or "Weight" in col_name:
                                            holding["weight_pct"] = _safe_float(val)
                                    if "name" not in holding:
                                        holding["name"] = ""
                                    holdings_list.append(holding)
                except Exception as exc:
                    logger.debug("get_etf_holdings: equity_holdings failed: %s", exc)

            # Fallback: try info fields
            if not holdings_list:
                top_holdings_info = info.get("topHoldings") or info.get("holdings") or []
                if isinstance(top_holdings_info, list):
                    for h in top_holdings_info[:limit]:
                        if isinstance(h, dict):
                            holdings_list.append({
                                "symbol": h.get("symbol", h.get("ticker", "")),
                                "name": h.get("holdingName", h.get("name", "")),
                                "weight_pct": _safe_float(
                                    h.get("holdingPercent", h.get("weight", None))
                                ),
                            })

            return {
                "symbol": sym,
                "name": etf_name,
                "holdings": holdings_list,
                "holdings_count": len(holdings_list),
                "source": "yfinance",
            }

        except Exception as exc:
            logger.exception("get_etf_holdings failed for %s", sym)
            return {"symbol": sym, "error": str(exc)}

    @tool
    async def get_etf_profile(symbol: str) -> dict:
        """Get detailed profile information for an ETF.

        Uses yfinance — free, no API key required.

        Args:
            symbol: ETF ticker symbol (e.g. "SPY", "QQQ", "VTI").

        Returns:
            A dict with:
            - ``symbol``: the ETF ticker
            - ``name``: ETF full name
            - ``category``: ETF category/type
            - ``description``: fund description/summary
            - ``expense_ratio``: annual expense ratio (%)
            - ``total_assets``: assets under management (AUM)
            - ``nav_price``: net asset value
            - ``currency``: trading currency
            - ``exchange``: primary exchange
            - ``inception_date``: fund inception date
            - ``yield_pct``: distribution yield if available
            - ``morningstar_rating``: Morningstar rating if available
            - ``source``: "yfinance"
        """
        import yfinance as yf

        sym = symbol.upper().strip()
        logger.info("get_etf_profile: %s", sym)

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
                "category": info.get("category") or info.get("fundCategory") or "",
                "description": info.get("longBusinessSummary") or info.get("description") or "",
                "expense_ratio": _safe_float(
                    info.get("annualReportExpenseRatio")
                    or info.get("expenseRatio")
                    or info.get("totalExpenseRatio")
                ),
                "total_assets": _safe_float(info.get("totalAssets")),
                "nav_price": _safe_float(info.get("navPrice") or info.get("previousClose")),
                "currency": info.get("currency", ""),
                "exchange": info.get("exchange") or info.get("fullExchangeName") or "",
                "inception_date": str(info.get("fundInceptionDate", "")),
                "yield_pct": _safe_float(info.get("yield") or info.get("trailingAnnualDividendYield")),
                "morningstar_rating": info.get("morningStarRiskRating") or info.get("morningstarOverallRating"),
                "source": "yfinance",
            }

        except Exception as exc:
            logger.exception("get_etf_profile failed for %s", sym)
            return {"symbol": sym, "error": str(exc)}

    return [get_etf_holdings, get_etf_profile]
