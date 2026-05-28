import streamlit as st

from agents.event_calendar import run_event_calendar
from services.report_service import list_reports, read_report


st.set_page_config(page_title="Event Calendar", page_icon="📅", layout="wide")

st.title("Event Calendar")
st.caption("Weekly portfolio-relevant earnings, macro releases, and catalysts.")

if st.button("Generate Weekly Event Calendar"):
    with st.spinner("Generating weekly event calendar..."):
        report = run_event_calendar()

    st.success("Weekly Event Calendar generated.")
    st.markdown(report)

st.divider()

st.subheader("Saved Event Calendars")

reports = list_reports("weekly_calendars")

if not reports:
    st.info("No Event Calendar reports have been generated yet.")
else:
    selected_report = st.selectbox(
        "Select an event calendar",
        reports,
        format_func=lambda path: path.name,
    )

    st.markdown(read_report(selected_report))