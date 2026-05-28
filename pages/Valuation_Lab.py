import streamlit as st
import pandas as pd

from services.valuation_service import (
    fetch_valuation_inputs,
    suggest_assumptions,
    run_three_case_dcf,
    build_valuation_markdown_report,
    format_currency_value,
)
from services.report_service import save_markdown_report


st.set_page_config(
    page_title="Valuation Lab",
    page_icon="🧮",
    layout="wide",
)

st.title("Valuation / DCF Lab")
st.caption(
    "Auto-suggested valuation assumptions with analyst review and override."
)

ticker = st.text_input(
    "Enter ticker",
    placeholder="Example: AAPL, MSFT, NVDA, MELI",
).upper().strip()

if not ticker:
    st.info("Enter a ticker to start the valuation.")
    st.stop()

st.divider()

with st.spinner("Fetching available valuation data..."):
    raw_data = fetch_valuation_inputs(ticker)

company_name = raw_data.get("company_name", ticker)

st.subheader(f"{ticker} — {company_name}")

top_col1, top_col2, top_col3, top_col4 = st.columns(4)

with top_col1:
    st.metric("Current Price", raw_data.get("current_price", "N/A"))

with top_col2:
    st.metric("Market Cap", format_currency_value(raw_data.get("market_cap")))

with top_col3:
    st.metric("Forward P/E", raw_data.get("forward_pe", "N/A"))

with top_col4:
    st.metric("Beta", raw_data.get("beta", "N/A"))

st.divider()

st.subheader("System-Suggested Assumptions")

suggested = suggest_assumptions(raw_data)

st.info(
    "These assumptions are system-suggested using available yfinance data and defaults. "
    "Review and edit them before using the valuation."
)

with st.form("valuation_assumptions_form"):
    col1, col2, col3 = st.columns(3)

    with col1:
        base_revenue = st.number_input(
            "Base revenue",
            value=float(suggested.get("base_revenue") or 0),
            step=1_000_000.0,
            format="%.2f",
        )

        forecast_years = st.number_input(
            "Forecast years",
            min_value=3,
            max_value=10,
            value=int(suggested.get("forecast_years", 5)),
            step=1,
        )

        tax_rate = st.number_input(
            "Tax rate",
            min_value=0.0,
            max_value=0.5,
            value=float(suggested.get("tax_rate", 0.21)),
            step=0.01,
            format="%.4f",
        )

        reinvestment_rate = st.number_input(
            "Reinvestment rate",
            min_value=0.0,
            max_value=0.9,
            value=float(suggested.get("reinvestment_rate", 0.35)),
            step=0.01,
            format="%.4f",
        )

    with col2:
        bear_revenue_growth = st.number_input(
            "Bear revenue growth",
            value=float(suggested.get("bear_revenue_growth", 0.03)),
            step=0.01,
            format="%.4f",
        )

        base_revenue_growth = st.number_input(
            "Base revenue growth",
            value=float(suggested.get("base_revenue_growth", 0.07)),
            step=0.01,
            format="%.4f",
        )

        bull_revenue_growth = st.number_input(
            "Bull revenue growth",
            value=float(suggested.get("bull_revenue_growth", 0.11)),
            step=0.01,
            format="%.4f",
        )

        terminal_growth = st.number_input(
            "Terminal growth",
            min_value=0.0,
            max_value=0.06,
            value=float(suggested.get("terminal_growth", 0.025)),
            step=0.005,
            format="%.4f",
        )

    with col3:
        bear_ebit_margin = st.number_input(
            "Bear EBIT margin",
            value=float(suggested.get("bear_ebit_margin", 0.10)),
            step=0.01,
            format="%.4f",
        )

        base_ebit_margin = st.number_input(
            "Base EBIT margin",
            value=float(suggested.get("base_ebit_margin", 0.15)),
            step=0.01,
            format="%.4f",
        )

        bull_ebit_margin = st.number_input(
            "Bull EBIT margin",
            value=float(suggested.get("bull_ebit_margin", 0.20)),
            step=0.01,
            format="%.4f",
        )

        net_debt = st.number_input(
            "Net debt",
            value=float(suggested.get("net_debt") or 0),
            step=1_000_000.0,
            format="%.2f",
        )

    col4, col5, col6 = st.columns(3)

    with col4:
        bear_wacc = st.number_input(
            "Bear WACC",
            min_value=0.01,
            max_value=0.30,
            value=float(suggested.get("bear_wacc", 0.11)),
            step=0.005,
            format="%.4f",
        )

    with col5:
        base_wacc = st.number_input(
            "Base WACC",
            min_value=0.01,
            max_value=0.30,
            value=float(suggested.get("base_wacc", 0.095)),
            step=0.005,
            format="%.4f",
        )

    with col6:
        bull_wacc = st.number_input(
            "Bull WACC",
            min_value=0.01,
            max_value=0.30,
            value=float(suggested.get("bull_wacc", 0.085)),
            step=0.005,
            format="%.4f",
        )

    shares_outstanding = st.number_input(
        "Shares outstanding",
        value=float(suggested.get("shares_outstanding") or 0),
        step=1_000_000.0,
        format="%.2f",
    )

    analyst_notes = st.text_area(
        "Analyst assumption notes / rationale",
        placeholder="Explain why you accepted or changed the suggested assumptions.",
        height=120,
    )

    submitted = st.form_submit_button("Run Bear / Base / Bull DCF")

if submitted:
    assumptions = {
        "base_revenue": base_revenue,
        "forecast_years": forecast_years,
        "bear_revenue_growth": bear_revenue_growth,
        "base_revenue_growth": base_revenue_growth,
        "bull_revenue_growth": bull_revenue_growth,
        "bear_ebit_margin": bear_ebit_margin,
        "base_ebit_margin": base_ebit_margin,
        "bull_ebit_margin": bull_ebit_margin,
        "tax_rate": tax_rate,
        "reinvestment_rate": reinvestment_rate,
        "bear_wacc": bear_wacc,
        "base_wacc": base_wacc,
        "bull_wacc": bull_wacc,
        "terminal_growth": terminal_growth,
        "net_debt": net_debt,
        "shares_outstanding": shares_outstanding,
        "rationale": suggested.get("rationale", {}),
        "analyst_notes": analyst_notes,
    }

    dcf_results = run_three_case_dcf(assumptions)

    st.divider()
    st.subheader("Valuation Output")

    result_rows = []

    for case_name, result in dcf_results.items():
        if result.get("error"):
            result_rows.append(
                {
                    "Case": case_name,
                    "Value Per Share": result["error"],
                    "Enterprise Value": "N/A",
                    "Equity Value": "N/A",
                }
            )
        else:
            result_rows.append(
                {
                    "Case": case_name,
                    "Value Per Share": f"{result['value_per_share']:,.2f}",
                    "Enterprise Value": format_currency_value(result["enterprise_value"]),
                    "Equity Value": format_currency_value(result["equity_value"]),
                }
            )

    result_df = pd.DataFrame(result_rows)
    st.dataframe(result_df, use_container_width=True, hide_index=True)

    current_price = raw_data.get("current_price")

    if current_price:
        st.subheader("Upside / Downside vs Current Price")

        upside_rows = []

        for case_name, result in dcf_results.items():
            if not result.get("error"):
                value_per_share = result["value_per_share"]
                upside = (value_per_share / float(current_price) - 1) * 100

                upside_rows.append(
                    {
                        "Case": case_name,
                        "Value Per Share": f"{value_per_share:,.2f}",
                        "Current Price": f"{float(current_price):,.2f}",
                        "Upside / Downside": f"{upside:.1f}%",
                    }
                )

        if upside_rows:
            st.dataframe(
                pd.DataFrame(upside_rows),
                use_container_width=True,
                hide_index=True,
            )

    report = build_valuation_markdown_report(
        ticker=ticker,
        company_name=company_name,
        assumptions=assumptions,
        dcf_results=dcf_results,
        current_price=current_price,
    )

    saved_path = save_markdown_report(
        report_type="valuation_reports",
        title=f"Valuation Lab {ticker}",
        content=report,
    )

    st.success(f"Valuation report saved: {saved_path.name}")

    with st.expander("Open valuation report markdown"):
        st.markdown(report)

st.divider()

st.subheader("Assumption Rationale")

rationale = suggested.get("rationale", {})

for key, value in rationale.items():
    st.write(f"**{key}:** {value}")

st.caption(
    "This module uses auto-suggested assumptions from available data, but final valuation "
    "depends on analyst review and judgement."
)