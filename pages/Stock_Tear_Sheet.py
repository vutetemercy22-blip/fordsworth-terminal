import streamlit as st
import pandas as pd

from services.portfolio_service import get_position_by_ticker
from services.news_service import fetch_company_news
from services.market_data_service import (
    fetch_stock_snapshot,
    format_large_number,
    format_number_or_na,
    format_percent_or_na,
)
from services.report_service import search_reports_for_text
from agents.deep_digger import run_deep_digger


st.set_page_config(
    page_title="Stock Tear Sheet",
    page_icon="📄",
    layout="wide",
)


# -------------------------------------------------------------------
# PAGE HEADER
# -------------------------------------------------------------------

st.title("Stock Tear Sheet")
st.caption(
    "Single-stock dashboard combining price data, thesis memory, valuation reference, "
    "recent news, and saved research."
)


# -------------------------------------------------------------------
# TICKER INPUT
# -------------------------------------------------------------------

ticker = st.text_input(
    "Enter ticker",
    placeholder="Example: AAPL, MSFT, NVDA, MELI",
).upper().strip()

if not ticker:
    st.info("Enter a ticker to generate a tear sheet.")
    st.stop()


st.divider()


# -------------------------------------------------------------------
# LOAD DATA
# -------------------------------------------------------------------

snapshot = fetch_stock_snapshot(ticker)
position = get_position_by_ticker(ticker)

if snapshot.get("error"):
    st.error(f"Market data error: {snapshot.get('error')}")
    st.stop()

company_name = snapshot.get("company_name", ticker)


# -------------------------------------------------------------------
# TITLE
# -------------------------------------------------------------------

st.subheader(f"{ticker} — {company_name}")


# -------------------------------------------------------------------
# PRICE SNAPSHOT
# -------------------------------------------------------------------

latest_close = snapshot.get("latest_close")
change = snapshot.get("change")
change_pct = snapshot.get("change_pct")

top_col1, top_col2, top_col3, top_col4, top_col5 = st.columns(5)

with top_col1:
    st.metric(
        "Latest Close",
        format_number_or_na(latest_close),
        f"{format_number_or_na(change)} / {format_number_or_na(change_pct)}%",
    )

with top_col2:
    st.metric(
        "52W High",
        format_number_or_na(snapshot.get("fifty_two_week_high")),
    )

with top_col3:
    st.metric(
        "52W Low",
        format_number_or_na(snapshot.get("fifty_two_week_low")),
    )

with top_col4:
    st.metric(
        "Market Cap",
        format_large_number(snapshot.get("market_cap")),
    )

with top_col5:
    st.metric(
        "Currency",
        snapshot.get("currency", "N/A"),
    )


st.divider()


# -------------------------------------------------------------------
# VALUATION SNAPSHOT
# -------------------------------------------------------------------

st.subheader("Market Valuation Snapshot")

fund_col1, fund_col2, fund_col3, fund_col4, fund_col5 = st.columns(5)

with fund_col1:
    st.metric(
        "Trailing P/E",
        format_number_or_na(snapshot.get("trailing_pe")),
    )

with fund_col2:
    st.metric(
        "Forward P/E",
        format_number_or_na(snapshot.get("forward_pe")),
    )

with fund_col3:
    st.metric(
        "Dividend Yield",
        format_percent_or_na(snapshot.get("dividend_yield")),
    )

with fund_col4:
    st.metric(
        "Beta",
        format_number_or_na(snapshot.get("beta")),
    )

with fund_col5:
    st.metric(
        "Sector",
        snapshot.get("sector", "N/A"),
    )


st.divider()


# -------------------------------------------------------------------
# STORED THESIS AND MONITORING
# -------------------------------------------------------------------

left, right = st.columns([1.3, 1])

with left:
    st.subheader("Stored Investment Thesis")

    if not position:
        st.warning("This ticker is not yet in the portfolio thesis library.")
        st.info("Use Portfolio Editor to add a stored thesis, or run Deep Digger below.")

    else:
        thesis = position.get("investment_thesis", {})

        st.markdown("### One-Line Thesis")
        st.write(thesis.get("one_line", "No thesis recorded."))

        st.markdown("### Core Drivers")
        core_drivers = thesis.get("core_drivers", [])

        if core_drivers:
            for item in core_drivers:
                st.write(f"- {item}")
        else:
            st.write("No core drivers recorded.")

        st.markdown("### Key Metrics to Monitor")
        metrics = thesis.get("key_metrics_to_monitor", [])

        if metrics:
            for item in metrics:
                st.write(f"- {item}")
        else:
            st.write("No metrics recorded.")

        st.markdown("### Kill Criteria")
        kill_criteria = thesis.get("kill_criteria", [])

        if kill_criteria:
            for item in kill_criteria:
                st.write(f"- {item}")
        else:
            st.write("No kill criteria recorded.")


with right:
    st.subheader("Valuation & Monitoring")

    if not position:
        st.write("No stored valuation or monitoring data.")

    else:
        valuation = position.get("valuation", {})
        monitoring = position.get("monitoring", {})

        val_col1, val_col2, val_col3 = st.columns(3)

        with val_col1:
            st.metric("Bear Case", valuation.get("bear_case", "N/A"))

        with val_col2:
            st.metric("Fair Value", valuation.get("fair_value", "N/A"))

        with val_col3:
            st.metric("Bull Case", valuation.get("bull_case", "N/A"))

        st.markdown("### Monitoring Settings")
        st.write(f"**News Priority:** {monitoring.get('overnight_news_priority', 'N/A')}")
        st.write(f"**Weekly Thesis Review:** {monitoring.get('weekly_thesis_review', 'N/A')}")
        st.write(f"**Event Calendar:** {monitoring.get('include_in_event_calendar', 'N/A')}")
        st.write(f"**Market Curator:** {monitoring.get('include_in_market_curator', 'N/A')}")

    st.markdown("### Company Profile")
    st.write(f"**Industry:** {snapshot.get('industry', 'N/A')}")
    st.write(f"**Website:** {snapshot.get('website', 'N/A')}")


st.divider()


# -------------------------------------------------------------------
# RECENT NEWS
# -------------------------------------------------------------------

st.subheader("Recent Company News")

try:
    news_context = position if position else {
        "ticker": ticker,
        "company_name": company_name,
    }

    articles = fetch_company_news(news_context, page_size=8)

    if not articles:
        st.info("No recent articles found.")

    else:
        for article in articles:
            title = article.get("title", "No title")
            source = article.get("source", "Unknown source")
            published_at = article.get("published_at", "Unknown date")
            description = article.get("description", "")
            url = article.get("url", "")

            with st.expander(f"{title} — {source}"):
                st.write(f"**Published:** {published_at}")
                st.write(description)

                if url:
                    st.write(url)

except Exception as exc:
    st.warning(f"Could not fetch recent news: {exc}")


st.divider()


# -------------------------------------------------------------------
# SAVED RESEARCH MENTIONS
# -------------------------------------------------------------------

st.subheader("Saved Research Mentions")

research_col1, research_col2 = st.columns(2)

with research_col1:
    st.markdown("### Morning Analyst Mentions")

    morning_matches = search_reports_for_text(
        report_type="morning_briefs",
        search_text=ticker,
        limit=3,
    )

    if not morning_matches:
        st.info("No Morning Analyst mentions found.")

    else:
        for match in morning_matches:
            with st.expander(match["file_name"]):
                st.markdown(match["preview"])


with research_col2:
    st.markdown("### Deep Digger Memos")

    deep_matches = search_reports_for_text(
        report_type="deep_research",
        search_text=ticker,
        limit=3,
    )

    if not deep_matches:
        st.info("No Deep Digger memos found.")

    else:
        for match in deep_matches:
            with st.expander(match["file_name"]):
                st.markdown(match["preview"])


st.divider()


# -------------------------------------------------------------------
# RUN DEEP DIGGER
# -------------------------------------------------------------------

st.subheader("Run Deep Digger")

st.caption("Generate a full investment memo for this ticker.")

if st.button(f"Run Deep Digger for {ticker}", use_container_width=True):
    with st.spinner(f"Generating Deep Digger memo for {ticker}..."):
        memo = run_deep_digger(ticker)

    st.success("Deep Digger memo generated.")
    st.markdown(memo)


st.divider()


# -------------------------------------------------------------------
# BUSINESS SUMMARY
# -------------------------------------------------------------------

st.subheader("Business Summary")

business_summary = snapshot.get("business_summary", "N/A")

if business_summary and business_summary != "N/A":
    st.write(business_summary)
else:
    st.info("No business summary available from yfinance.")


st.divider()

st.caption(
    "Data source: yfinance / Yahoo Finance for market data, NewsAPI for news, "
    "and local YAML files for stored thesis memory."
)