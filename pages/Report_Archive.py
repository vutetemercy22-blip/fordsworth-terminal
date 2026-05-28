import streamlit as st
import pandas as pd

from services.report_service import (
    list_reports,
    read_report,
    markdown_to_docx,
    export_research_pack_to_docx,
)


st.set_page_config(page_title="Report Archive", page_icon="🗂️", layout="wide")

st.title("Report Archive")
st.caption("Central archive of all generated Portfolio Intelligence Terminal reports.")

st.divider()

st.subheader("Research Pack Export")

include_deep_digger = st.checkbox(
    "Include latest Deep Digger memo",
    value=True,
)

if st.button("Export Latest Research Pack to Word"):
    output_path = export_research_pack_to_docx(
        include_deep_digger=include_deep_digger,
    )

    st.success(f"Research Pack exported: {output_path.name}")

    with open(output_path, "rb") as file:
        st.download_button(
            label="Download Research Pack",
            data=file,
            file_name=output_path.name,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

st.divider()



REPORT_TYPES = {
    "Morning Briefs": {
        "report_type": "morning_briefs",
        "description": "Daily thesis-aware morning briefings",
    },
    "Thesis Reviews": {
        "report_type": "thesis_reviews",
        "description": "Weekly portfolio thesis health reviews",
    },
    "Event Calendars": {
        "report_type": "weekly_calendars",
        "description": "Weekly macro, earnings, and catalyst calendars",
    },
    "Market Curator Reports": {
        "report_type": "market_curator",
        "description": "End-of-day relevance filters",
    },
    "Deep Digger Memos": {
        "report_type": "deep_research",
        "description": "On-demand full investment research memos",
    },
}


def collect_all_reports():
    """
    Collect reports across all report folders.
    """
    rows = []

    for display_name, config in REPORT_TYPES.items():
        report_type = config["report_type"]

        try:
            reports = list_reports(report_type)
        except Exception:
            reports = []

        for report_path in reports:
            rows.append(
                {
                    "Category": display_name,
                    "Description": config["description"],
                    "File Name": report_path.name,
                    "Path": str(report_path),
                    "Modified": report_path.stat().st_mtime,
                    "Report Type": report_type,
                    "Report Path Object": report_path,
                }
            )

    return rows


all_reports = collect_all_reports()

if not all_reports:
    st.info("No reports have been generated yet.")
else:
    reports_df = pd.DataFrame(all_reports)

    reports_df["Modified Date"] = pd.to_datetime(
        reports_df["Modified"],
        unit="s",
    ).dt.strftime("%Y-%m-%d %H:%M:%S")

    st.subheader("Archive Summary")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Reports", len(reports_df))

    with col2:
        st.metric("Report Categories", reports_df["Category"].nunique())

    with col3:
        latest_report_time = reports_df["Modified Date"].max()
        st.metric("Latest Report", latest_report_time)

    st.divider()

    st.subheader("Filter Reports")

    selected_category = st.selectbox(
        "Report category",
        ["All"] + list(REPORT_TYPES.keys()),
    )

    if selected_category == "All":
        filtered_df = reports_df.copy()
    else:
        filtered_df = reports_df[reports_df["Category"] == selected_category].copy()

    filtered_df = filtered_df.sort_values("Modified", ascending=False)

    display_df = filtered_df[
        [
            "Category",
            "File Name",
            "Description",
            "Modified Date",
        ]
    ]

    st.dataframe(display_df, use_container_width=True, hide_index=True)

    st.divider()

    st.subheader("Open Report")

    report_options = filtered_df["File Name"].tolist()

    if not report_options:
        st.warning("No reports available for this category.")
    else:
        selected_file = st.selectbox(
            "Select report",
            report_options,
        )

        selected_row = filtered_df[
            filtered_df["File Name"] == selected_file
        ].iloc[0]

        selected_path = selected_row["Report Path Object"]

        st.markdown(
            f"""
            **Category:** {selected_row["Category"]}  
            **File:** `{selected_row["File Name"]}`  
            **Modified:** {selected_row["Modified Date"]}
            """
        )

        report_text = read_report(selected_path)

        st.markdown(report_text)
        st.divider()

        if st.button("Export Selected Report to Word"):
            output_path = markdown_to_docx(
                markdown_text=report_text,
                output_filename=selected_row["File Name"],
            )

            st.success(f"Exported to Word: {output_path.name}")

            with open(output_path, "rb") as file:
                st.download_button(
                    label="Download Word Report",
                    data=file,
                    file_name=output_path.name,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
        with st.expander("Raw Markdown"):
            st.code(report_text, language="markdown")