from datetime import datetime

from services.portfolio_service import load_all_positions
from services.news_service import fetch_portfolio_news
from services.market_data_service import fetch_market_context
from services.llm_service import generate_morning_briefing
from services.report_service import save_markdown_report


def run_morning_analyst() -> str:
    """
    Generate a thesis-aware morning briefing.

    Workflow:
    1. Load portfolio thesis files
    2. Fetch company-relevant news from the last 24 hours
    3. Fetch broad market context
    4. Send thesis + news + market context to the LLM
    5. Generate the briefing
    6. Save it as Markdown
    """
    positions = load_all_positions()

    if not positions:
        return "No portfolio positions were found. Add YAML files in data/portfolio."

    date_label = datetime.now().strftime("%d %B %Y")

    portfolio_news = fetch_portfolio_news(
        positions=positions,
        page_size=5,
    )

    market_context = fetch_market_context()

    briefing = generate_morning_briefing(
        positions=positions,
        portfolio_news=portfolio_news,
        market_context=market_context,
        date_label=date_label,
    )

    save_markdown_report(
        report_type="morning_briefs",
        title="Morning Analyst Briefing",
        content=briefing,
    )

    return briefing