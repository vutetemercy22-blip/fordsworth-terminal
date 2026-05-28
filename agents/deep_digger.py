from datetime import datetime

from services.portfolio_service import load_all_positions, get_position_by_ticker
from services.news_service import fetch_company_news
from services.market_data_service import fetch_market_context
from services.llm_service import generate_deep_digger_memo
from services.report_service import save_markdown_report


def run_deep_digger(company_or_ticker: str) -> str:
    """
    Generate an on-demand full investment memo.

    Workflow:
    1. Accept ticker or company name
    2. Check whether it already exists in the portfolio YAML library
    3. Fetch recent company news if possible
    4. Fetch market context
    5. Generate full investment memo
    6. Save memo as Markdown
    """
    query = company_or_ticker.strip()

    if not query:
        return "Please enter a company or ticker."

    date_label = datetime.now().strftime("%d %B %Y")

    existing_position = get_position_by_ticker(query.upper())

    if existing_position:
        company_context = existing_position
    else:
        company_context = {
            "ticker": query.upper(),
            "company_name": query,
            "asset_type": "equity",
            "sector": "Unknown",
            "position_status": "research_candidate",
            "portfolio_weight": 0,
            "investment_thesis": {
                "one_line": "No stored thesis available. Treat this as a new research candidate.",
                "core_drivers": [],
                "key_metrics_to_monitor": [],
                "kill_criteria": [],
            },
            "valuation": {
                "fair_value": "To be assessed",
                "bear_case": "To be assessed",
                "bull_case": "To be assessed",
                "required_return_threshold": "To be assessed",
            },
            "monitoring": {
                "overnight_news_priority": "research",
                "weekly_thesis_review": False,
                "include_in_event_calendar": False,
                "include_in_market_curator": False,
            },
            "notes": [
                "This company is not yet in the stored portfolio thesis library."
            ],
        }

    try:
        recent_news = fetch_company_news(company_context, page_size=10)
    except Exception as exc:
        recent_news = [
            {
                "title": "News retrieval failed",
                "description": str(exc),
                "source": "System",
                "published_at": None,
                "url": None,
            }
        ]

    market_context = fetch_market_context()

    memo = generate_deep_digger_memo(
        company_or_ticker=query,
        company_context=company_context,
        recent_news=recent_news,
        market_context=market_context,
        date_label=date_label,
    )

    save_markdown_report(
        report_type="deep_research",
        title=f"Deep Digger {query}",
        content=memo,
    )

    return memo