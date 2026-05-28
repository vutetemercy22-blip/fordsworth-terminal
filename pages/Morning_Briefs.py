import streamlit as st

from services.report_service import list_reports, read_report
from agents.morning_analyst import run_morning_analyst


st.set_page_config(page_title="Morning Briefs", page_icon="☀️", layout="wide")

st.title("Morning Analyst")
st.caption("Overnight portfolio-relevant intelligence briefs")

if st.button("Generate Test Morning Brief"):
    report = run_morning_analyst()
    st.success("Brief generated.")
    st.markdown(report)

st.divider()

reports = list_reports("morning_briefs")

if not reports:
    st.info("No Morning Analyst reports have been generated yet.")
else:
    selected_report = st.selectbox(
        "Select a briefing",
        reports,
        format_func=lambda path: path.name,
    )

    st.markdown(read_report(selected_report))