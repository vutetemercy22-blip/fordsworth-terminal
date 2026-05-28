from datetime import datetime

from services.portfolio_service import load_all_positions
from services.news_service import fetch_portfolio_news
from services.market_data_service import fetch_market_context
from services.llm_service import generate_market_curator_review
from services.report_service import save_markdown_report


def run_market_curator() -> str:
    """
    Generate an end-of-day market curator report.

    Workflow:
    1. Load portfolio thesis files
    2. Fetch same-day / recent company news
    3. Fetch market context
    4. Generate an end-of-day relevance filter
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

    report = generate_market_curator_review(
        positions=positions,
        portfolio_news=portfolio_news,
        market_context=market_context,
        date_label=date_label,
    )

    save_markdown_report(
        report_type="market_curator",
        title="Market Curator",
        content=report,
    )

    return report