from datetime import datetime
from typing import Dict, Optional

import yfinance as yf


MARKET_TICKERS = {
    "indices": {
        "S&P 500": "^GSPC",
        "Nasdaq 100": "^NDX",
        "Dow Jones": "^DJI",
    },
    "fx": {
        "USD/ZAR": "ZAR=X",
        "EUR/USD": "EURUSD=X",
        "GBP/USD": "GBPUSD=X",
    },
    "commodities": {
        "Gold": "GC=F",
        "Brent Crude": "BZ=F",
        "Copper": "HG=F",
    },
    "rates": {
        "US 10Y Treasury Yield": "^TNX",
        "US 2Y Treasury Yield": "^IRX",
    },
}


def fetch_latest_market_point(symbol: str) -> Optional[Dict]:
    """
    Fetch the latest and previous close for one Yahoo Finance symbol.
    """
    try:
        ticker = yf.Ticker(symbol)
        history = ticker.history(period="5d", interval="1d")

        if history.empty or "Close" not in history.columns:
            return None

        closes = history["Close"].dropna()

        if len(closes) == 0:
            return None

        latest_close = float(closes.iloc[-1])

        if len(closes) >= 2:
            previous_close = float(closes.iloc[-2])
            change = latest_close - previous_close
            change_pct = (change / previous_close) * 100 if previous_close else None
        else:
            previous_close = None
            change = None
            change_pct = None

        return {
            "symbol": symbol,
            "latest_close": latest_close,
            "previous_close": previous_close,
            "change": change,
            "change_pct": change_pct,
        }

    except Exception as exc:
        return {
            "symbol": symbol,
            "error": str(exc),
        }


def format_market_value(point: Optional[Dict]) -> str:
    """
    Format one market data point for the briefing prompt.
    """
    if point is None:
        return "Data unavailable"

    if "error" in point:
        return f"Data error: {point['error']}"

    latest = point.get("latest_close")
    change = point.get("change")
    change_pct = point.get("change_pct")

    if latest is None:
        return "Data unavailable"

    if change is None or change_pct is None:
        return f"{latest:,.2f}"

    return f"{latest:,.2f} ({change:+,.2f}, {change_pct:+.2f}%)"


def fetch_market_context() -> Dict:
    """
    Fetch live market context from Yahoo Finance via yfinance.
    """
    context = {
        "as_of": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "indices": {},
        "rates": {},
        "fx": {},
        "commodities": {},
        "macro_commentary": [],
    }

    for category, items in MARKET_TICKERS.items():
        for display_name, symbol in items.items():
            point = fetch_latest_market_point(symbol)
            context[category][display_name] = format_market_value(point)

    context["macro_commentary"] = [
        "Live Yahoo Finance market data is connected via yfinance.",
        "Data may be delayed or unavailable for some instruments depending on Yahoo Finance coverage.",
        "Use this context as a morning-market guide, not as an official pricing source.",
    ]

    return context


def format_market_context_for_prompt(market_context: Dict) -> str:
    """
    Convert market context dictionary into text for the LLM prompt.
    """
    lines = []

    lines.append(f"As of: {market_context.get('as_of')}")

    lines.append("\n## Indices")
    for name, value in market_context.get("indices", {}).items():
        lines.append(f"- {name}: {value}")

    lines.append("\n## Rates")
    for name, value in market_context.get("rates", {}).items():
        lines.append(f"- {name}: {value}")

    lines.append("\n## FX")
    for name, value in market_context.get("fx", {}).items():
        lines.append(f"- {name}: {value}")

    lines.append("\n## Commodities")
    for name, value in market_context.get("commodities", {}).items():
        lines.append(f"- {name}: {value}")

    lines.append("\n## Macro Commentary")
    for item in market_context.get("macro_commentary", []):
        lines.append(f"- {item}")

    return "\n".join(lines)

def fetch_stock_snapshot(symbol: str) -> Dict:
    """
    Fetch a single-stock snapshot from Yahoo Finance via yfinance.
    """
    symbol = symbol.upper().strip()

    try:
        ticker = yf.Ticker(symbol)

        history = ticker.history(period="1y", interval="1d")

        if history.empty:
            return {
                "symbol": symbol,
                "error": "No price history returned.",
            }

        closes = history["Close"].dropna()
        latest_close = float(closes.iloc[-1])
        previous_close = float(closes.iloc[-2]) if len(closes) >= 2 else None

        change = None
        change_pct = None

        if previous_close:
            change = latest_close - previous_close
            change_pct = (change / previous_close) * 100

        fifty_two_week_high = float(history["High"].max())
        fifty_two_week_low = float(history["Low"].min())

        info = {}

        try:
            info = ticker.info or {}
        except Exception:
            info = {}

        return {
            "symbol": symbol,
            "company_name": info.get("longName") or info.get("shortName") or symbol,
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
            "currency": info.get("currency", "N/A"),
            "latest_close": latest_close,
            "previous_close": previous_close,
            "change": change,
            "change_pct": change_pct,
            "fifty_two_week_high": fifty_two_week_high,
            "fifty_two_week_low": fifty_two_week_low,
            "market_cap": info.get("marketCap", "N/A"),
            "trailing_pe": info.get("trailingPE", "N/A"),
            "forward_pe": info.get("forwardPE", "N/A"),
            "dividend_yield": info.get("dividendYield", "N/A"),
            "beta": info.get("beta", "N/A"),
            "website": info.get("website", "N/A"),
            "business_summary": info.get("longBusinessSummary", "N/A"),
        }

    except Exception as exc:
        return {
            "symbol": symbol,
            "error": str(exc),
        }


def format_large_number(value) -> str:
    """
    Format large numbers like market cap.
    """
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "N/A"

    if value >= 1_000_000_000_000:
        return f"{value / 1_000_000_000_000:.2f}T"

    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f}B"

    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"

    return f"{value:,.0f}"


def format_number_or_na(value, decimals: int = 2) -> str:
    """
    Format numeric values safely.
    """
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "N/A"

    return f"{value:,.{decimals}f}"


def format_percent_or_na(value, decimals: int = 2) -> str:
    """
    Format percentages safely.
    yfinance sometimes returns dividend yield as decimal, e.g. 0.005.
    """
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "N/A"

    return f"{value * 100:.{decimals}f}%"

def fetch_stock_snapshot(symbol: str) -> Dict:
    """
    Fetch a single-stock snapshot from Yahoo Finance via yfinance.
    """
    symbol = symbol.upper().strip()

    try:
        ticker = yf.Ticker(symbol)

        history = ticker.history(period="1y", interval="1d")

        if history.empty:
            return {
                "symbol": symbol,
                "error": "No price history returned.",
            }

        closes = history["Close"].dropna()
        latest_close = float(closes.iloc[-1])
        previous_close = float(closes.iloc[-2]) if len(closes) >= 2 else None

        change = None
        change_pct = None

        if previous_close:
            change = latest_close - previous_close
            change_pct = (change / previous_close) * 100

        fifty_two_week_high = float(history["High"].max())
        fifty_two_week_low = float(history["Low"].min())

        try:
            info = ticker.info or {}
        except Exception:
            info = {}

        return {
            "symbol": symbol,
            "company_name": info.get("longName") or info.get("shortName") or symbol,
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
            "currency": info.get("currency", "N/A"),
            "latest_close": latest_close,
            "previous_close": previous_close,
            "change": change,
            "change_pct": change_pct,
            "fifty_two_week_high": fifty_two_week_high,
            "fifty_two_week_low": fifty_two_week_low,
            "market_cap": info.get("marketCap", "N/A"),
            "trailing_pe": info.get("trailingPE", "N/A"),
            "forward_pe": info.get("forwardPE", "N/A"),
            "dividend_yield": info.get("dividendYield", "N/A"),
            "beta": info.get("beta", "N/A"),
            "website": info.get("website", "N/A"),
            "business_summary": info.get("longBusinessSummary", "N/A"),
        }

    except Exception as exc:
        return {
            "symbol": symbol,
            "error": str(exc),
        }


def format_large_number(value) -> str:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "N/A"

    if value >= 1_000_000_000_000:
        return f"{value / 1_000_000_000_000:.2f}T"

    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f}B"

    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"

    return f"{value:,.0f}"


def format_number_or_na(value, decimals: int = 2) -> str:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "N/A"

    return f"{value:,.{decimals}f}"


def format_percent_or_na(value, decimals: int = 2) -> str:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "N/A"

    return f"{value * 100:.{decimals}f}%"