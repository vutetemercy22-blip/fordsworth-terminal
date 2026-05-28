from datetime import datetime

from services.portfolio_service import load_all_positions
from services.news_service import fetch_portfolio_news
from services.market_data_service import fetch_market_context
from services.llm_service import generate_thesis_tracker_review
from services.report_service import save_markdown_report


def run_thesis_tracker() -> str:
    """
    Generate a weekly thesis tracker review.

    Workflow:
    1. Load portfolio thesis files
    2. Fetch recent company news
    3. Fetch market context
    4. Generate thesis status review
    5. Save report as Markdown
    """
    positions = load_all_positions()

    if not positions:
        return "No portfolio positions were found. Add YAML files in data/portfolio."

    date_label = datetime.now().strftime("%d %B %Y")

    portfolio_news = fetch_portfolio_news(
        positions=positions,
        page_size=10,
    )

    market_context = fetch_market_context()

    review = generate_thesis_tracker_review(
        positions=positions,
        portfolio_news=portfolio_news,
        market_context=market_context,
        date_label=date_label,
    )

    save_markdown_report(
        report_type="thesis_reviews",
        title="Weekly Thesis Tracker",
        content=review,
    )

    return review