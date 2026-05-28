import streamlit as st

from services.portfolio_service import (
    load_all_positions,
    get_position_by_ticker,
    position_to_yaml_data,
    save_position,
    delete_position_file,
)


st.set_page_config(page_title="Portfolio Editor", page_icon="✍️", layout="wide")

st.title("Portfolio Editor")
st.caption("Create and edit portfolio thesis YAML files directly from Streamlit.")

positions = load_all_positions()
existing_tickers = [position.get("ticker") for position in positions]

mode = st.radio(
    "Choose action",
    ["Add new position", "Edit existing position", "Delete position"],
    horizontal=True,
)

st.divider()


def text_area_to_list(value: str) -> list[str]:
    """
    Convert a multiline text area into a clean list.
    """
    return [line.strip("- ").strip() for line in value.splitlines() if line.strip()]


def list_to_text_area(items: list) -> str:
    """
    Convert list values into multiline text for editing.
    """
    if not items:
        return ""
    return "\n".join(str(item) for item in items)


def build_editor_form(default_position: dict | None = None):
    default_position = default_position or {}

    default_thesis = default_position.get("investment_thesis", {})
    default_valuation = default_position.get("valuation", {})
    default_monitoring = default_position.get("monitoring", {})

    with st.form("portfolio_editor_form"):
        col1, col2 = st.columns(2)

        with col1:
            ticker = st.text_input(
                "Ticker",
                value=default_position.get("ticker", ""),
                placeholder="e.g. AAPL",
            )

            company_name = st.text_input(
                "Company name",
                value=default_position.get("company_name", ""),
                placeholder="e.g. Apple Inc.",
            )

            asset_type = st.selectbox(
                "Asset type",
                ["equity", "bond", "fund", "crypto", "commodity", "other"],
                index=["equity", "bond", "fund", "crypto", "commodity", "other"].index(
                    default_position.get("asset_type", "equity")
                    if default_position.get("asset_type", "equity")
                    in ["equity", "bond", "fund", "crypto", "commodity", "other"]
                    else "equity"
                ),
            )

            sector = st.text_input(
                "Sector",
                value=default_position.get("sector", ""),
                placeholder="e.g. Technology",
            )

            position_status = st.selectbox(
                "Position status",
                ["holding", "watchlist", "research_candidate", "sold", "avoid"],
                index=["holding", "watchlist", "research_candidate", "sold", "avoid"].index(
                    default_position.get("position_status", "holding")
                    if default_position.get("position_status", "holding")
                    in ["holding", "watchlist", "research_candidate", "sold", "avoid"]
                    else "holding"
                ),
            )

            portfolio_weight = st.number_input(
                "Portfolio weight %",
                min_value=0.0,
                max_value=100.0,
                value=float(default_position.get("portfolio_weight", 0) or 0),
                step=0.5,
            )

        with col2:
            overnight_news_priority = st.selectbox(
                "News monitoring priority",
                ["low", "normal", "high", "critical", "research"],
                index=["low", "normal", "high", "critical", "research"].index(
                    default_monitoring.get("overnight_news_priority", "normal")
                    if default_monitoring.get("overnight_news_priority", "normal")
                    in ["low", "normal", "high", "critical", "research"]
                    else "normal"
                ),
            )

            weekly_thesis_review = st.checkbox(
                "Include in weekly Thesis Tracker",
                value=bool(default_monitoring.get("weekly_thesis_review", True)),
            )

            include_in_event_calendar = st.checkbox(
                "Include in Event Calendar",
                value=bool(default_monitoring.get("include_in_event_calendar", True)),
            )

            include_in_market_curator = st.checkbox(
                "Include in Market Curator",
                value=bool(default_monitoring.get("include_in_market_curator", True)),
            )

            fair_value = st.text_input(
                "Fair value",
                value=str(default_valuation.get("fair_value", "")),
                placeholder="e.g. 245",
            )

            bear_case = st.text_input(
                "Bear case value",
                value=str(default_valuation.get("bear_case", "")),
                placeholder="e.g. 185",
            )

            bull_case = st.text_input(
                "Bull case value",
                value=str(default_valuation.get("bull_case", "")),
                placeholder="e.g. 290",
            )

            required_return_threshold = st.text_input(
                "Required return threshold",
                value=str(default_valuation.get("required_return_threshold", "")),
                placeholder="e.g. 0.12",
            )

        st.subheader("Investment Thesis")

        one_line_thesis = st.text_area(
            "One-line thesis",
            value=default_thesis.get("one_line", ""),
            height=100,
            placeholder="Write the core investment thesis in one paragraph.",
        )

        core_drivers_text = st.text_area(
            "Core thesis drivers — one per line",
            value=list_to_text_area(default_thesis.get("core_drivers", [])),
            height=140,
            placeholder="Services revenue growth\nGross margin resilience\nAI monetisation",
        )

        metrics_text = st.text_area(
            "Key metrics to monitor — one per line",
            value=list_to_text_area(default_thesis.get("key_metrics_to_monitor", [])),
            height=140,
            placeholder="Revenue growth\nGross margin\nFree cash flow",
        )

        kill_criteria_text = st.text_area(
            "Kill criteria — one per line",
            value=list_to_text_area(default_thesis.get("kill_criteria", [])),
            height=140,
            placeholder="Two consecutive quarters of thesis deterioration\nStructural margin compression",
        )

        notes_text = st.text_area(
            "Notes — one per line",
            value=list_to_text_area(default_position.get("notes", [])),
            height=120,
            placeholder="Optional notes for this position.",
        )

        submitted = st.form_submit_button("Save Position")

        if submitted:
            if not ticker.strip():
                st.error("Ticker is required.")
                return

            if not company_name.strip():
                st.error("Company name is required.")
                return

            position_data = position_to_yaml_data(
                ticker=ticker,
                company_name=company_name,
                asset_type=asset_type,
                sector=sector,
                position_status=position_status,
                portfolio_weight=portfolio_weight,
                one_line_thesis=one_line_thesis,
                core_drivers=text_area_to_list(core_drivers_text),
                key_metrics_to_monitor=text_area_to_list(metrics_text),
                kill_criteria=text_area_to_list(kill_criteria_text),
                fair_value=fair_value,
                bear_case=bear_case,
                bull_case=bull_case,
                required_return_threshold=required_return_threshold,
                overnight_news_priority=overnight_news_priority,
                weekly_thesis_review=weekly_thesis_review,
                include_in_event_calendar=include_in_event_calendar,
                include_in_market_curator=include_in_market_curator,
                notes=text_area_to_list(notes_text),
            )

            saved_path = save_position(position_data)
            st.success(f"Saved position to {saved_path.name}")
            st.info("Refresh the page to see the updated position list.")


if mode == "Add new position":
    st.subheader("Add New Position")
    build_editor_form()

elif mode == "Edit existing position":
    st.subheader("Edit Existing Position")

    if not existing_tickers:
        st.warning("No existing positions found.")
    else:
        selected_ticker = st.selectbox("Select position to edit", existing_tickers)
        position = get_position_by_ticker(selected_ticker)

        if position:
            build_editor_form(position)
        else:
            st.error("Selected position could not be loaded.")

elif mode == "Delete position":
    st.subheader("Delete Position")

    if not existing_tickers:
        st.warning("No existing positions found.")
    else:
        selected_ticker = st.selectbox("Select position to delete", existing_tickers)

        st.warning(
            f"This will delete the YAML file for {selected_ticker}. "
            "This cannot be undone from inside the app."
        )

        confirm = st.checkbox(f"I confirm I want to delete {selected_ticker}")

        if st.button("Delete Position"):
            if not confirm:
                st.error("Tick the confirmation box first.")
            else:
                deleted = delete_position_file(selected_ticker)

                if deleted:
                    st.success(f"Deleted {selected_ticker}. Refresh the page.")
                else:
                    st.error("Could not find the position file to delete.")