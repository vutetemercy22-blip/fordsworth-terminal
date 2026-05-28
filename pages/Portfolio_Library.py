import streamlit as st
import pandas as pd

from services.portfolio_service import load_all_positions


st.set_page_config(page_title="Portfolio Library", page_icon="📚", layout="wide")

st.title("Portfolio Thesis Library")
st.caption("The memory layer used by all five agents.")

positions = load_all_positions()

if not positions:
    st.info("No portfolio YAML files found. Use Portfolio Editor to add a position.")
else:
    rows = []

    for position in positions:
        thesis = position.get("investment_thesis", {})
        valuation = position.get("valuation", {})
        monitoring = position.get("monitoring", {})

        rows.append(
            {
                "Ticker": position.get("ticker"),
                "Company": position.get("company_name"),
                "Sector": position.get("sector"),
                "Status": position.get("position_status"),
                "Weight %": position.get("portfolio_weight"),
                "Fair Value": valuation.get("fair_value"),
                "News Priority": monitoring.get("overnight_news_priority"),
                "Core Drivers": len(thesis.get("core_drivers", [])),
                "Kill Criteria": len(thesis.get("kill_criteria", [])),
            }
        )

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()

    tickers = [position.get("ticker") for position in positions]
    selected_ticker = st.selectbox("Select position", tickers)

    selected_position = next(
        position for position in positions
        if position.get("ticker") == selected_ticker
    )

    st.markdown(
        f"## {selected_position.get('ticker')} — {selected_position.get('company_name')}"
    )

    thesis = selected_position.get("investment_thesis", {})
    valuation = selected_position.get("valuation", {})
    monitoring = selected_position.get("monitoring", {})

    col1, col2 = st.columns([1.2, 1])

    with col1:
        st.markdown("### One-Line Thesis")
        st.write(thesis.get("one_line", "No thesis available."))

        st.markdown("### Core Drivers")
        for item in thesis.get("core_drivers", []):
            st.write(f"- {item}")

        st.markdown("### Metrics to Monitor")
        for item in thesis.get("key_metrics_to_monitor", []):
            st.write(f"- {item}")

        st.markdown("### Kill Criteria")
        for item in thesis.get("kill_criteria", []):
            st.write(f"- {item}")

    with col2:
        st.markdown("### Valuation")
        st.write(f"**Bear Case:** {valuation.get('bear_case')}")
        st.write(f"**Fair Value:** {valuation.get('fair_value')}")
        st.write(f"**Bull Case:** {valuation.get('bull_case')}")
        st.write(
            f"**Required Return Threshold:** "
            f"{valuation.get('required_return_threshold')}"
        )

        st.markdown("### Monitoring")
        st.write(f"**News priority:** {monitoring.get('overnight_news_priority')}")
        st.write(f"**Weekly thesis review:** {monitoring.get('weekly_thesis_review')}")
        st.write(f"**Event calendar:** {monitoring.get('include_in_event_calendar')}")
        st.write(f"**Market curator:** {monitoring.get('include_in_market_curator')}")

        st.markdown("### Source File")
        st.code(selected_position.get("_source_file", "Unknown"))

        st.markdown("### Notes")
        for item in selected_position.get("notes", []):
            st.write(f"- {item}")