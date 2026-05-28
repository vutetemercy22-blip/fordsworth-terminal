import streamlit as st
from apscheduler.schedulers.background import BackgroundScheduler

from services.config_service import load_schedules, load_settings
from scheduler.jobs import (
    morning_analyst_job,
    thesis_tracker_job,
    event_calendar_job,
    market_curator_job,
)


def build_scheduler() -> BackgroundScheduler:
    """
    Build the background scheduler from config/schedules.yaml.
    """
    settings = load_settings()
    schedules = load_schedules()["schedules"]

    timezone = settings["timezone"]["default"]

    scheduler = BackgroundScheduler(
        timezone=timezone,
        job_defaults={
            "coalesce": True,
            "max_instances": 1,
        },
    )

    morning_config = schedules["morning_analyst"]
    if morning_config["enabled"]:
        scheduler.add_job(
            morning_analyst_job,
            trigger="cron",
            day_of_week=morning_config["day_of_week"],
            hour=morning_config["hour"],
            minute=morning_config["minute"],
            id="morning_analyst_job",
            replace_existing=True,
        )

    curator_config = schedules["market_curator"]
    if curator_config["enabled"]:
        scheduler.add_job(
            market_curator_job,
            trigger="cron",
            day_of_week=curator_config["day_of_week"],
            hour=curator_config["hour"],
            minute=curator_config["minute"],
            id="market_curator_job",
            replace_existing=True,
        )

    event_config = schedules["event_calendar"]
    if event_config["enabled"]:
        scheduler.add_job(
            event_calendar_job,
            trigger="cron",
            day_of_week=event_config["day_of_week"],
            hour=event_config["hour"],
            minute=event_config["minute"],
            id="event_calendar_job",
            replace_existing=True,
        )

    tracker_config = schedules["thesis_tracker"]
    if tracker_config["enabled"]:
        scheduler.add_job(
            thesis_tracker_job,
            trigger="cron",
            day_of_week=tracker_config["day_of_week"],
            hour=tracker_config["hour"],
            minute=tracker_config["minute"],
            id="thesis_tracker_job",
            replace_existing=True,
        )

    return scheduler


def get_or_start_scheduler() -> BackgroundScheduler:
    """
    Start the scheduler once per Streamlit session.
    """
    if "portfolio_scheduler" not in st.session_state:
        scheduler = build_scheduler()
        scheduler.start()
        st.session_state["portfolio_scheduler"] = scheduler

    return st.session_state["portfolio_scheduler"]


def stop_scheduler() -> None:
    """
    Stop scheduler if running.
    """
    scheduler = st.session_state.get("portfolio_scheduler")

    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)

    if "portfolio_scheduler" in st.session_state:
        del st.session_state["portfolio_scheduler"]


def get_scheduler_jobs():
    """
    Return scheduled jobs for dashboard display.
    """
    scheduler = st.session_state.get("portfolio_scheduler")

    if not scheduler:
        return []

    return scheduler.get_jobs()