import streamlit as st

from utils.ui import apply_theme, callout, page_header, section_title


st.set_page_config(
    page_title="Hotel Revenue Command Center",
    layout="wide",
)

apply_theme()
page_header(
    "Hotel Revenue Command Center",
    "A CSV-first workspace for daily checklist entry, pickup monitoring, comp set pricing, and revenue decision support.",
    "Command Center",
)

section_title("Daily Workflow")
callout(
    "No database required",
    "Enter the day, export the CSV, store it locally or on a shared drive, then upload files when analysis is needed.",
)

c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Daily Entry", "Checklist")
    st.write("Capture hotel metrics, OTA rates, comp set rates, forecast, and pickup in one structured form.")
    st.page_link("pages/1_Daily_Revenue_Checklist.py", label="Open Daily Checklist")
with c2:
    st.metric("Day Comparison", "2 CSVs")
    st.write("Compare performance, pricing movement, market position, and forecast pace between two exported days.")
    st.page_link("pages/2_Compare_Two_Days.py", label="Compare Two Days")
with c3:
    st.metric("Trend Analytics", "7 or 14 Days")
    st.write("Upload a weekly or 14-day file set to review revenue trends, pickup, comp set position, and pricing signals.")
    st.page_link("pages/3_Revenue_Dashboard.py", label="Open Revenue Dashboard")
