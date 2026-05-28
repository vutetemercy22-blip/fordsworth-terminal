from datetime import datetime
from pathlib import Path

from agents.morning_analyst import run_morning_analyst
from agents.thesis_tracker import run_thesis_tracker
from agents.event_calendar import run_event_calendar
from agents.market_curator import run_market_curator
from services.config_service import BASE_DIR


LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "scheduler.log"


def write_scheduler_log(message: str) -> None:
    """
    Write scheduler activity to logs/scheduler.log.
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(LOG_FILE, "a", encoding="utf-8") as file:
        file.write(f"[{timestamp}] {message}\n")


def morning_analyst_job():
    try:
        write_scheduler_log("Morning Analyst job started.")
        run_morning_analyst()
        write_scheduler_log("Morning Analyst job completed.")
    except Exception as exc:
        write_scheduler_log(f"Morning Analyst job failed: {exc}")


def thesis_tracker_job():
    try:
        write_scheduler_log("Thesis Tracker job started.")
        run_thesis_tracker()
        write_scheduler_log("Thesis Tracker job completed.")
    except Exception as exc:
        write_scheduler_log(f"Thesis Tracker job failed: {exc}")


def event_calendar_job():
    try:
        write_scheduler_log("Event Calendar job started.")
        run_event_calendar()
        write_scheduler_log("Event Calendar job completed.")
    except Exception as exc:
        write_scheduler_log(f"Event Calendar job failed: {exc}")


def market_curator_job():
    try:
        write_scheduler_log("Market Curator job started.")
        run_market_curator()
        write_scheduler_log("Market Curator job completed.")
    except Exception as exc:
        write_scheduler_log(f"Market Curator job failed: {exc}")