import streamlit as st

from agents.market_curator import run_market_curator
from services.report_service import list_reports, read_report


st.set_page_config(page_title="Market Curator", page_icon="📰", layout="wide")

st.title("Market Curator")
st.caption("End-of-day relevance filter: what happened today that matters for tomorrow.")

if st.button("Generate Market Curator Report"):
    with st.spinner("Generating end-of-day market curator report..."):
        report = run_market_curator()

    st.success("Market Curator report generated.")
    st.markdown(report)

st.divider()

st.subheader("Saved Market Curator Reports")

reports = list_reports("market_curator")

if not reports:
    st.info("No Market Curator reports have been generated yet.")
else:
    selected_report = st.selectbox(
        "Select a Market Curator report",
        reports,
        format_func=lambda path: path.name,
    )

    st.markdown(read_report(selected_report))