import streamlit as st

from agents.deep_digger import run_deep_digger
from services.report_service import list_reports, read_report


st.set_page_config(page_title="Deep Digger", page_icon="🔎", layout="wide")

st.title("Deep Digger")
st.caption("On-demand investment memo engine")

company_or_ticker = st.text_input(
    "Company or ticker",
    placeholder="e.g. AAPL, MSFT, NVDA, MELI, ASML",
)

if st.button("Generate Deep Digger Memo"):
    if not company_or_ticker.strip():
        st.warning("Enter a company or ticker first.")
    else:
        with st.spinner("Generating Deep Digger investment memo..."):
            memo = run_deep_digger(company_or_ticker)

        st.success("Deep Digger memo generated.")
        st.markdown(memo)

st.divider()

st.subheader("Saved Deep Digger Memos")

reports = list_reports("deep_research")

if not reports:
    st.info("No Deep Digger memos have been generated yet.")
else:
    selected_report = st.selectbox(
        "Select a Deep Digger memo",
        reports,
        format_func=lambda path: path.name,
    )

    st.markdown(read_report(selected_report))