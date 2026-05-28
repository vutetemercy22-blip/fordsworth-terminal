from datetime import datetime

from services.portfolio_service import load_all_positions
from services.config_service import load_yaml_file
from services.market_data_service import fetch_market_context
from services.llm_service import generate_event_calendar_review
from services.report_service import save_markdown_report


def load_event_calendar_config() -> dict:
    """
    Load manually configured macro events and portfolio event rules.
    """
    try:
        return load_yaml_file("config/event_calendar.yaml")
    except FileNotFoundError:
        return {
            "macro_events": [],
            "portfolio_event_rules": {},
        }


def run_event_calendar() -> str:
    """
    Generate a weekly portfolio-relevant event calendar.

    Workflow:
    1. Load portfolio thesis files
    2. Load configured macro events and event rules
    3. Fetch market context
    4. Generate weekly event calendar report
    5. Save report as Markdown
    """
    positions = load_all_positions()

    if not positions:
        return "No portfolio positions were found. Add YAML files in data/portfolio."

    date_label = datetime.now().strftime("%d %B %Y")

    event_config = load_event_calendar_config()
    market_context = fetch_market_context()

    report = generate_event_calendar_review(
        positions=positions,
        event_config=event_config,
        market_context=market_context,
        date_label=date_label,
    )

    save_markdown_report(
        report_type="weekly_calendars",
        title="Weekly Event Calendar",
        content=report,
    )

    return report