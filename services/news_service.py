from datetime import datetime, timedelta, timezone
from typing import Dict, List
import requests
import streamlit as st


NEWSAPI_BASE_URL = "https://newsapi.org/v2/everything"


def get_newsapi_key() -> str:
    """
    Read NewsAPI key from Streamlit secrets.
    """
    try:
        return st.secrets["NEWSAPI_KEY"]
    except Exception as exc:
        raise RuntimeError(
            "NEWSAPI_KEY is missing. Add it to .streamlit/secrets.toml"
        ) from exc


def build_company_query(position: Dict) -> str:
    """
    Create a search query using both ticker and company name.
    """
    ticker = position.get("ticker", "")
    company_name = position.get("company_name", "")

    if ticker and company_name:
        return f'"{company_name}" OR {ticker}'

    return company_name or ticker


def fetch_company_news(position: Dict, page_size: int = 5) -> List[Dict]:
    """
    Fetch recent company-relevant news from NewsAPI.
    """
    api_key = get_newsapi_key()
    query = build_company_query(position)

    now_utc = datetime.now(timezone.utc)
    yesterday_utc = now_utc - timedelta(days=1)

    params = {
        "q": query,
        "from": yesterday_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "to": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sortBy": "publishedAt",
        "language": "en",
        "pageSize": page_size,
        "apiKey": api_key,
    }

    response = requests.get(
        NEWSAPI_BASE_URL,
        params=params,
        timeout=20,
    )
    response.raise_for_status()

    payload = response.json()
    articles = payload.get("articles", [])

    cleaned_articles = []

    for article in articles:
        cleaned_articles.append(
            {
                "title": article.get("title"),
                "description": article.get("description"),
                "source": article.get("source", {}).get("name"),
                "published_at": article.get("publishedAt"),
                "url": article.get("url"),
            }
        )

    return cleaned_articles


def fetch_portfolio_news(positions: List[Dict], page_size: int = 5) -> Dict[str, List[Dict]]:
    """
    Fetch recent news for all portfolio positions.
    """
    portfolio_news = {}

    for position in positions:
        ticker = position.get("ticker", "UNKNOWN")

        try:
            portfolio_news[ticker] = fetch_company_news(
                position=position,
                page_size=page_size,
            )
        except Exception as exc:
            portfolio_news[ticker] = [
                {
                    "title": "News retrieval failed",
                    "description": str(exc),
                    "source": "System",
                    "published_at": None,
                    "url": None,
                }
            ]

    return portfolio_news