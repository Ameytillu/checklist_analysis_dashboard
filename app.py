import streamlit as st


st.set_page_config(
    page_title="Hotel Revenue Command Center",
    page_icon="",
    layout="wide",
)

st.title("Hotel Revenue Command Center")
st.caption("CSV-based daily checklist, comparison, and 14-day revenue analytics.")

st.markdown(
    """
    Use the page navigation to enter today's checklist, compare two exported days,
    or upload up to 14 checklist CSVs for trend analytics.

    This application does not use a database. Exported CSV files are the only
    persistence layer.
    """
)

st.subheader("Workflow")
st.write("Daily entry -> Export CSV -> Store locally or on a drive -> Upload CSVs for analytics.")

