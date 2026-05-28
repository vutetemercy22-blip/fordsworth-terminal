import streamlit as st
import pandas as pd

from scheduler.scheduler_engine import (
    get_or_start_scheduler,
    stop_scheduler,
    get_scheduler_jobs,
)

from scheduler.jobs import LOG_FILE
from agents.morning_analyst import run_morning_analyst
from agents.thesis_tracker import run_thesis_tracker
from agents.event_calendar import run_event_calendar
from agents.market_curator import run_market_curator


st.set_page_config(page_title="Scheduler Control", page_icon="⏰", layout="wide")

st.title("Scheduler Control")
st.caption("Manage automatic agent runs and review scheduler activity logs.")

st.divider()

st.subheader("Scheduler Status")

col1, col2, col3 = st.columns(3)

scheduler_running = False
scheduler = st.session_state.get("portfolio_scheduler")

if scheduler and scheduler.running:
    scheduler_running = True

with col1:
    st.metric("Scheduler Running", "Yes" if scheduler_running else "No")

with col2:
    jobs = get_scheduler_jobs()
    st.metric("Scheduled Jobs", len(jobs))

with col3:
    st.metric("Scheduler Mode", "Local Streamlit Process")

st.divider()

st.subheader("Controls")

control_col1, control_col2 = st.columns(2)

with control_col1:
    if st.button("Start Scheduler", use_container_width=True):
        scheduler = get_or_start_scheduler()
        st.success("Scheduler started.")

with control_col2:
    if st.button("Stop Scheduler", use_container_width=True):
        stop_scheduler()
        st.warning("Scheduler stopped.")

st.divider()

st.subheader("Scheduled Jobs")

jobs = get_scheduler_jobs()

if not jobs:
    st.info("Scheduler is not running or no jobs are currently scheduled.")
else:
    job_rows = []

    for job in jobs:
        job_rows.append(
            {
                "Job ID": job.id,
                "Next Run Time": str(job.next_run_time),
                "Trigger": str(job.trigger),
            }
        )

    jobs_df = pd.DataFrame(job_rows)
    st.dataframe(jobs_df, use_container_width=True, hide_index=True)

st.divider()

st.subheader("Manual Run")

st.caption("Use these buttons to test scheduled agents immediately.")

run_col1, run_col2, run_col3, run_col4 = st.columns(4)

with run_col1:
    if st.button("Run Morning Analyst", use_container_width=True):
        with st.spinner("Running Morning Analyst..."):
            report = run_morning_analyst()
        st.success("Morning Analyst completed.")
        st.markdown(report)

with run_col2:
    if st.button("Run Thesis Tracker", use_container_width=True):
        with st.spinner("Running Thesis Tracker..."):
            report = run_thesis_tracker()
        st.success("Thesis Tracker completed.")
        st.markdown(report)

with run_col3:
    if st.button("Run Event Calendar", use_container_width=True):
        with st.spinner("Running Event Calendar..."):
            report = run_event_calendar()
        st.success("Event Calendar completed.")
        st.markdown(report)

with run_col4:
    if st.button("Run Market Curator", use_container_width=True):
        with st.spinner("Running Market Curator..."):
            report = run_market_curator()
        st.success("Market Curator completed.")
        st.markdown(report)

st.divider()

st.subheader("Scheduler Log")

if not LOG_FILE.exists():
    st.info("No scheduler log file found yet. Start the scheduler or run a job first.")
else:
    log_text = LOG_FILE.read_text(encoding="utf-8")

    if not log_text.strip():
        st.info("Scheduler log is empty.")
    else:
        lines = log_text.splitlines()
        latest_lines = lines[-100:]

        st.text_area(
            "Latest log entries",
            value="\n".join(latest_lines),
            height=350,
        )

        with st.expander("Full scheduler log"):
            st.code(log_text)

st.divider()

st.warning(
    "The scheduler runs only while this Streamlit app is open and your computer is on. "
    "For true overnight automation, use Windows Task Scheduler or deploy the app to a server."
)