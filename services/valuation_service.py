from datetime import datetime
from typing import Dict, List
import math

import yfinance as yf


def safe_float(value, default=None):
    try:
        if value in [None, "", "N/A"]:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def get_financial_value(statement, possible_labels: List[str]):
    """
    Try to retrieve a financial statement value from yfinance financial statements.
    """
    if statement is None or statement.empty:
        return None

    for label in possible_labels:
        if label in statement.index:
            series = statement.loc[label].dropna()
            if not series.empty:
                return safe_float(series.iloc[0])

    return None


def fetch_valuation_inputs(ticker_symbol: str) -> Dict:
    """
    Fetch available market and financial data for valuation assumptions.
    """
    ticker_symbol = ticker_symbol.upper().strip()
    ticker = yf.Ticker(ticker_symbol)

    try:
        info = ticker.info or {}
    except Exception:
        info = {}

    try:
        financials = ticker.financials
    except Exception:
        financials = None

    try:
        balance_sheet = ticker.balance_sheet
    except Exception:
        balance_sheet = None

    try:
        cashflow = ticker.cashflow
    except Exception:
        cashflow = None

    revenue = get_financial_value(
        financials,
        ["Total Revenue", "Operating Revenue", "Revenue"],
    )

    ebit = get_financial_value(
        financials,
        ["EBIT", "Operating Income"],
    )

    tax_provision = get_financial_value(
        financials,
        ["Tax Provision", "Income Tax Expense"],
    )

    pretax_income = get_financial_value(
        financials,
        ["Pretax Income", "Income Before Tax"],
    )

    free_cash_flow = get_financial_value(
        cashflow,
        ["Free Cash Flow"],
    )

    total_debt = get_financial_value(
        balance_sheet,
        ["Total Debt", "Long Term Debt", "Short Long Term Debt Total"],
    )

    cash = get_financial_value(
        balance_sheet,
        ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"],
    )

    current_price = info.get("currentPrice") or info.get("regularMarketPrice")
    shares_outstanding = info.get("sharesOutstanding")
    market_cap = info.get("marketCap")
    beta = info.get("beta")
    trailing_pe = info.get("trailingPE")
    forward_pe = info.get("forwardPE")

    if total_debt is None:
        total_debt = info.get("totalDebt")

    if cash is None:
        cash = info.get("totalCash")

    net_debt = None
    if total_debt is not None or cash is not None:
        net_debt = safe_float(total_debt, 0) - safe_float(cash, 0)

    return {
        "ticker": ticker_symbol,
        "company_name": info.get("longName") or info.get("shortName") or ticker_symbol,
        "sector": info.get("sector", "N/A"),
        "industry": info.get("industry", "N/A"),
        "currency": info.get("currency", "N/A"),
        "current_price": current_price,
        "market_cap": market_cap,
        "shares_outstanding": shares_outstanding,
        "beta": beta,
        "trailing_pe": trailing_pe,
        "forward_pe": forward_pe,
        "revenue": revenue,
        "ebit": ebit,
        "pretax_income": pretax_income,
        "tax_provision": tax_provision,
        "free_cash_flow": free_cash_flow,
        "total_debt": total_debt,
        "cash": cash,
        "net_debt": net_debt,
    }


def suggest_assumptions(data: Dict) -> Dict:
    """
    Create system-suggested assumptions from available data.
    These are deliberately conservative and editable by the analyst.
    """
    revenue = safe_float(data.get("revenue"), 0)
    ebit = safe_float(data.get("ebit"), None)
    pretax_income = safe_float(data.get("pretax_income"), None)
    tax_provision = safe_float(data.get("tax_provision"), None)
    beta = safe_float(data.get("beta"), 1.0)

    if revenue and ebit is not None:
        ebit_margin = max(min(ebit / revenue, 0.50), -0.10)
    else:
        ebit_margin = 0.15

    if pretax_income and tax_provision is not None and pretax_income > 0:
        tax_rate = max(min(abs(tax_provision) / pretax_income, 0.35), 0.10)
    else:
        tax_rate = 0.21

    risk_free_rate = 0.045
    equity_risk_premium = 0.055
    cost_of_equity = risk_free_rate + beta * equity_risk_premium

    # Simple WACC proxy, intentionally conservative.
    wacc = max(min(cost_of_equity, 0.14), 0.075)

    return {
        "base_revenue": revenue,
        "forecast_years": 5,
        "bear_revenue_growth": 0.03,
        "base_revenue_growth": 0.07,
        "bull_revenue_growth": 0.11,
        "bear_ebit_margin": max(ebit_margin - 0.04, 0.02),
        "base_ebit_margin": ebit_margin,
        "bull_ebit_margin": min(ebit_margin + 0.04, 0.45),
        "tax_rate": tax_rate,
        "reinvestment_rate": 0.35,
        "bear_wacc": min(wacc + 0.015, 0.16),
        "base_wacc": wacc,
        "bull_wacc": max(wacc - 0.010, 0.065),
        "terminal_growth": 0.025,
        "net_debt": safe_float(data.get("net_debt"), 0),
        "shares_outstanding": safe_float(data.get("shares_outstanding"), 0),
        "rationale": {
            "base_revenue": "Latest available revenue from yfinance financial statements.",
            "ebit_margin": "Estimated from latest available EBIT divided by revenue; defaulted where unavailable.",
            "tax_rate": "Estimated from tax provision divided by pretax income; defaulted where unavailable.",
            "wacc": "Estimated using a simple CAPM-style proxy from beta, risk-free rate, and equity risk premium.",
            "terminal_growth": "Default long-term nominal terminal growth assumption.",
            "reinvestment_rate": "Default reinvestment assumption used to convert NOPAT into free cash flow.",
        },
    }


def project_dcf_case(
    base_revenue: float,
    revenue_growth: float,
    ebit_margin: float,
    tax_rate: float,
    reinvestment_rate: float,
    wacc: float,
    terminal_growth: float,
    net_debt: float,
    shares_outstanding: float,
    forecast_years: int,
) -> Dict:
    """
    Simple DCF calculation using revenue, EBIT margin, tax, reinvestment and terminal value.
    """
    if not base_revenue or base_revenue <= 0:
        return {
            "error": "Base revenue is missing or zero. Cannot calculate DCF.",
        }

    if not shares_outstanding or shares_outstanding <= 0:
        return {
            "error": "Shares outstanding is missing or zero. Cannot calculate value per share.",
        }

    if wacc <= terminal_growth:
        return {
            "error": "WACC must be greater than terminal growth.",
        }

    projections = []
    present_value_fcf = 0

    revenue = base_revenue

    for year in range(1, int(forecast_years) + 1):
        revenue = revenue * (1 + revenue_growth)
        ebit = revenue * ebit_margin
        nopat = ebit * (1 - tax_rate)
        free_cash_flow = nopat * (1 - reinvestment_rate)
        discount_factor = (1 + wacc) ** year
        pv_fcf = free_cash_flow / discount_factor

        present_value_fcf += pv_fcf

        projections.append(
            {
                "year": year,
                "revenue": revenue,
                "ebit": ebit,
                "nopat": nopat,
                "free_cash_flow": free_cash_flow,
                "pv_fcf": pv_fcf,
            }
        )

    final_fcf = projections[-1]["free_cash_flow"]
    terminal_value = final_fcf * (1 + terminal_growth) / (wacc - terminal_growth)
    pv_terminal_value = terminal_value / ((1 + wacc) ** forecast_years)

    enterprise_value = present_value_fcf + pv_terminal_value
    equity_value = enterprise_value - net_debt
    value_per_share = equity_value / shares_outstanding

    return {
        "projections": projections,
        "present_value_fcf": present_value_fcf,
        "terminal_value": terminal_value,
        "pv_terminal_value": pv_terminal_value,
        "enterprise_value": enterprise_value,
        "net_debt": net_debt,
        "equity_value": equity_value,
        "shares_outstanding": shares_outstanding,
        "value_per_share": value_per_share,
    }


def run_three_case_dcf(assumptions: Dict) -> Dict:
    """
    Run bear, base and bull DCF cases.
    """
    common = {
        "base_revenue": safe_float(assumptions.get("base_revenue"), 0),
        "tax_rate": safe_float(assumptions.get("tax_rate"), 0.21),
        "reinvestment_rate": safe_float(assumptions.get("reinvestment_rate"), 0.35),
        "terminal_growth": safe_float(assumptions.get("terminal_growth"), 0.025),
        "net_debt": safe_float(assumptions.get("net_debt"), 0),
        "shares_outstanding": safe_float(assumptions.get("shares_outstanding"), 0),
        "forecast_years": int(safe_float(assumptions.get("forecast_years"), 5)),
    }

    results = {
        "Bear": project_dcf_case(
            revenue_growth=safe_float(assumptions.get("bear_revenue_growth"), 0.03),
            ebit_margin=safe_float(assumptions.get("bear_ebit_margin"), 0.10),
            wacc=safe_float(assumptions.get("bear_wacc"), 0.11),
            **common,
        ),
        "Base": project_dcf_case(
            revenue_growth=safe_float(assumptions.get("base_revenue_growth"), 0.07),
            ebit_margin=safe_float(assumptions.get("base_ebit_margin"), 0.15),
            wacc=safe_float(assumptions.get("base_wacc"), 0.095),
            **common,
        ),
        "Bull": project_dcf_case(
            revenue_growth=safe_float(assumptions.get("bull_revenue_growth"), 0.11),
            ebit_margin=safe_float(assumptions.get("bull_ebit_margin"), 0.20),
            wacc=safe_float(assumptions.get("bull_wacc"), 0.085),
            **common,
        ),
    }

    return results


def format_currency_value(value) -> str:
    value = safe_float(value)

    if value is None:
        return "N/A"

    if abs(value) >= 1_000_000_000_000:
        return f"{value / 1_000_000_000_000:.2f}T"

    if abs(value) >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f}B"

    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"

    return f"{value:,.2f}"


def build_valuation_markdown_report(
    ticker: str,
    company_name: str,
    assumptions: Dict,
    dcf_results: Dict,
    current_price=None,
) -> str:
    """
    Build a Markdown valuation report to save.
    """
    now = datetime.now().strftime("%d %B %Y %H:%M")

    lines = []

    lines.append(f"# Valuation Lab Report — {ticker} — {company_name}")
    lines.append("")
    lines.append(f"Generated: {now}")
    lines.append("")
    lines.append("## 1. Valuation Summary")
    lines.append("")
    lines.append("| Case | Value Per Share | Enterprise Value | Equity Value |")
    lines.append("|---|---:|---:|---:|")

    for case_name, result in dcf_results.items():
        if result.get("error"):
            lines.append(f"| {case_name} | Error: {result['error']} | N/A | N/A |")
        else:
            lines.append(
                f"| {case_name} | "
                f"{result['value_per_share']:,.2f} | "
                f"{format_currency_value(result['enterprise_value'])} | "
                f"{format_currency_value(result['equity_value'])} |"
            )

    lines.append("")
    lines.append("## 2. Current Market Reference")
    lines.append("")
    lines.append(f"- Current price: {current_price if current_price else 'N/A'}")
    lines.append("")
    lines.append("## 3. Analyst-Reviewed Assumptions")
    lines.append("")
    lines.append("| Assumption | Value |")
    lines.append("|---|---:|")

    for key, value in assumptions.items():
        if key == "rationale":
            continue
        lines.append(f"| {key} | {value} |")

    lines.append("")
    lines.append("## 4. Assumption Rationale")
    lines.append("")

    rationale = assumptions.get("rationale", {})

    if rationale:
        for key, value in rationale.items():
            lines.append(f"- {key}: {value}")
    else:
        lines.append("- No rationale recorded.")

    lines.append("")
    lines.append("## 5. Important Limitation")
    lines.append("")
    lines.append(
        "This valuation is based on system-suggested assumptions that should be reviewed by an analyst. "
        "It is not an official valuation, investment recommendation, or guarantee of fair value."
    )

    return "\n".join(lines)