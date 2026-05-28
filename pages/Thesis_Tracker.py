import streamlit as st
import pandas as pd

from services.portfolio_service import load_all_positions
from services.report_service import list_reports, read_report
from agents.thesis_tracker import run_thesis_tracker


st.set_page_config(page_title="Thesis Tracker", page_icon="🧭", layout="wide")

st.title("Thesis Tracker")
st.caption("Weekly monitoring of whether each portfolio thesis is strengthening, weakening, or unchanged.")

positions = load_all_positions()


if not positions:
    st.warning("No positions loaded. Add YAML files in data/portfolio.")
else:
    rows = []

    for position in positions:
        thesis = position.get("investment_thesis", {})
        monitoring = position.get("monitoring", {})

        rows.append(
            {
                "Ticker": position.get("ticker"),
                "Company": position.get("company_name"),
                "Sector": position.get("sector"),
                "Review Enabled": monitoring.get("weekly_thesis_review"),
                "Core Drivers": len(thesis.get("core_drivers", [])),
                "Kill Criteria": len(thesis.get("kill_criteria", [])),
            }
        )

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

st.divider()

if st.button("Generate Weekly Thesis Review"):
    with st.spinner("Generating weekly thesis review..."):
        review = run_thesis_tracker()

    st.success("Weekly Thesis Review generated.")
    st.markdown(review)

st.divider()

st.subheader("Saved Thesis Reviews")

reports = list_reports("thesis_reviews")

if not reports:
    st.info("No Thesis Tracker reports have been generated yet.")
else:
    selected_report = st.selectbox(
        "Select a thesis review",
        reports,
        format_func=lambda path: path.name,
    )

    st.markdown(read_report(selected_report))