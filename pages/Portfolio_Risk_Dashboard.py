import streamlit as st
import pandas as pd

from services.portfolio_service import load_all_positions
from services.report_service import export_portfolio_risk_report_to_docx


st.set_page_config(
    page_title="Portfolio Risk Dashboard",
    page_icon="⚠️",
    layout="wide",
)

st.title("Portfolio Risk Dashboard")
st.caption("Portfolio concentration, thesis risk, monitoring priority, and kill-criteria exposure.")

positions = load_all_positions()

if not positions:
    st.info("No portfolio positions found. Add positions in Portfolio Editor.")
    st.stop()


def safe_float(value, default=0.0):
    try:
        if value in [None, ""]:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def thesis_completeness_score(position: dict) -> int:
    """
    Score how complete the stored thesis file is out of 100.
    """
    thesis = position.get("investment_thesis", {})
    valuation = position.get("valuation", {})
    monitoring = position.get("monitoring", {})

    score = 0

    if position.get("ticker"):
        score += 10

    if position.get("company_name"):
        score += 10

    if thesis.get("one_line"):
        score += 15

    if len(thesis.get("core_drivers", [])) >= 3:
        score += 15
    elif len(thesis.get("core_drivers", [])) > 0:
        score += 7

    if len(thesis.get("key_metrics_to_monitor", [])) >= 3:
        score += 15
    elif len(thesis.get("key_metrics_to_monitor", [])) > 0:
        score += 7

    if len(thesis.get("kill_criteria", [])) >= 2:
        score += 15
    elif len(thesis.get("kill_criteria", [])) > 0:
        score += 7

    if valuation.get("fair_value"):
        score += 10

    if monitoring.get("overnight_news_priority"):
        score += 10

    return min(score, 100)


def monitoring_priority_score(priority: str) -> int:
    priority = str(priority or "").lower()

    mapping = {
        "low": 1,
        "normal": 2,
        "research": 3,
        "high": 4,
        "critical": 5,
    }

    return mapping.get(priority, 2)


rows = []

for position in positions:
    thesis = position.get("investment_thesis", {})
    monitoring = position.get("monitoring", {})
    valuation = position.get("valuation", {})

    weight = safe_float(position.get("portfolio_weight", 0))
    kill_count = len(thesis.get("kill_criteria", []))
    driver_count = len(thesis.get("core_drivers", []))
    metric_count = len(thesis.get("key_metrics_to_monitor", []))
    completeness = thesis_completeness_score(position)
    priority = monitoring.get("overnight_news_priority", "normal")
    priority_score = monitoring_priority_score(priority)

    risk_score = 0

    if weight >= 10:
        risk_score += 3
    elif weight >= 5:
        risk_score += 2
    elif weight > 0:
        risk_score += 1

    if priority_score >= 5:
        risk_score += 3
    elif priority_score >= 4:
        risk_score += 2
    elif priority_score >= 3:
        risk_score += 1

    if kill_count >= 4:
        risk_score += 2
    elif kill_count >= 2:
        risk_score += 1

    if completeness < 50:
        risk_score += 3
    elif completeness < 75:
        risk_score += 1

    if risk_score >= 7:
        risk_band = "High"
    elif risk_score >= 4:
        risk_band = "Medium"
    else:
        risk_band = "Low"

    rows.append(
        {
            "Ticker": position.get("ticker"),
            "Company": position.get("company_name"),
            "Sector": position.get("sector", "Unknown"),
            "Status": position.get("position_status", "Unknown"),
            "Weight %": weight,
            "News Priority": priority,
            "Priority Score": priority_score,
            "Core Drivers": driver_count,
            "Metrics": metric_count,
            "Kill Criteria": kill_count,
            "Thesis Completeness %": completeness,
            "Risk Score": risk_score,
            "Risk Band": risk_band,
            "Fair Value": valuation.get("fair_value", "N/A"),
        }
    )


df = pd.DataFrame(rows)

total_weight = df["Weight %"].sum()
largest_position = df.sort_values("Weight %", ascending=False).iloc[0]
high_risk_count = len(df[df["Risk Band"] == "High"])
medium_risk_count = len(df[df["Risk Band"] == "Medium"])
average_completeness = df["Thesis Completeness %"].mean()
st.divider()

st.subheader("Export Portfolio Risk Report")

if st.button("Export Portfolio Risk Report to Word"):
    output_path = export_portfolio_risk_report_to_docx(
        risk_df=df,
        positions=positions,
    )

    st.success(f"Portfolio Risk Report exported: {output_path.name}")

    with open(output_path, "rb") as file:
        st.download_button(
            label="Download Portfolio Risk Report",
            data=file,
            file_name=output_path.name,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
st.divider()

metric_col1, metric_col2, metric_col3, metric_col4, metric_col5 = st.columns(5)

with metric_col1:
    st.metric("Positions", len(df))

with metric_col2:
    st.metric("Mapped Weight", f"{total_weight:.1f}%")

with metric_col3:
    st.metric("Largest Position", f"{largest_position['Ticker']} / {largest_position['Weight %']:.1f}%")

with metric_col4:
    st.metric("High Risk Positions", high_risk_count)

with metric_col5:
    st.metric("Avg Thesis Completeness", f"{average_completeness:.0f}%")

st.divider()

left, right = st.columns([1.2, 1])

with left:
    st.subheader("Risk Dashboard Table")

    display_df = df[
        [
            "Ticker",
            "Company",
            "Sector",
            "Weight %",
            "News Priority",
            "Kill Criteria",
            "Thesis Completeness %",
            "Risk Score",
            "Risk Band",
        ]
    ].sort_values(["Risk Score", "Weight %"], ascending=[False, False])

    st.dataframe(display_df, use_container_width=True, hide_index=True)

with right:
    st.subheader("Risk Summary")

    st.write(f"**Largest position:** {largest_position['Ticker']} at {largest_position['Weight %']:.1f}%")
    st.write(f"**High-risk positions:** {high_risk_count}")
    st.write(f"**Medium-risk positions:** {medium_risk_count}")
    st.write(f"**Average thesis completeness:** {average_completeness:.0f}%")

    if high_risk_count > 0:
        st.warning("There are high-risk positions that need review.")
    else:
        st.success("No high-risk positions identified from current YAML data.")

st.divider()

chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.subheader("Position Weights")

    weight_df = df[["Ticker", "Weight %"]].sort_values("Weight %", ascending=False)
    st.bar_chart(weight_df.set_index("Ticker"))

with chart_col2:
    st.subheader("Sector Exposure")

    sector_df = (
        df.groupby("Sector", as_index=False)["Weight %"]
        .sum()
        .sort_values("Weight %", ascending=False)
    )

    st.bar_chart(sector_df.set_index("Sector"))

st.divider()

chart_col3, chart_col4 = st.columns(2)

with chart_col3:
    st.subheader("Risk Score by Position")

    risk_df = df[["Ticker", "Risk Score"]].sort_values("Risk Score", ascending=False)
    st.bar_chart(risk_df.set_index("Ticker"))

with chart_col4:
    st.subheader("Thesis Completeness")

    completeness_df = df[["Ticker", "Thesis Completeness %"]].sort_values(
        "Thesis Completeness %",
        ascending=True,
    )
    st.bar_chart(completeness_df.set_index("Ticker"))

st.divider()

st.subheader("High and Medium Risk Review")

review_df = df[df["Risk Band"].isin(["High", "Medium"])].sort_values(
    ["Risk Score", "Weight %"],
    ascending=[False, False],
)

if review_df.empty:
    st.success("No high or medium risk positions identified.")
else:
    for _, row in review_df.iterrows():
        with st.expander(f"{row['Ticker']} — {row['Risk Band']} Risk"):
            st.write(f"**Company:** {row['Company']}")
            st.write(f"**Sector:** {row['Sector']}")
            st.write(f"**Weight:** {row['Weight %']:.1f}%")
            st.write(f"**News priority:** {row['News Priority']}")
            st.write(f"**Kill criteria count:** {row['Kill Criteria']}")
            st.write(f"**Thesis completeness:** {row['Thesis Completeness %']}%")
            st.write(f"**Risk score:** {row['Risk Score']}")

            position = next(
                item for item in positions
                if item.get("ticker") == row["Ticker"]
            )

            thesis = position.get("investment_thesis", {})

            st.markdown("### Kill Criteria")
            kill_items = thesis.get("kill_criteria", [])

            if kill_items:
                for item in kill_items:
                    st.write(f"- {item}")
            else:
                st.write("No kill criteria recorded.")

            st.markdown("### Suggested Action")
            if row["Thesis Completeness %"] < 75:
                st.write("- Improve the thesis file in Portfolio Editor.")
            if row["Weight %"] >= 10:
                st.write("- Review concentration risk and position sizing.")
            if str(row["News Priority"]).lower() in ["high", "critical"]:
                st.write("- Monitor this position closely in Morning Analyst and Market Curator.")
            if row["Kill Criteria"] >= 3:
                st.write("- Review whether any kill criteria are close to being triggered.")

st.divider()

st.subheader("Risk Methodology")

st.markdown(
    """
    The risk score is based on the information currently stored in the portfolio YAML files.

    **Risk factors considered:**

    - Position weight
    - Monitoring priority
    - Number of kill criteria
    - Thesis completeness

    This is not a market-risk VaR model. It is a **portfolio governance and thesis-risk dashboard**.
    """
)