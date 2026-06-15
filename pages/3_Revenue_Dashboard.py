from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from utils.calculations import load_checklist, money, normalize_checklist, number, pct, summarize_uploaded_files
from utils.charts import bar_chart, line_chart
from utils.insights import forecast_performance, market_position_stats, pricing_decision_signals, trend_alerts
from utils.ui import apply_theme, callout, page_header, section_title
from utils.validation import detect_duplicate_uploads, validate_uploaded_checklist


st.set_page_config(page_title="Revenue Dashboard", layout="wide")
apply_theme()
page_header(
    "Revenue Dashboard",
    "Analyze weekly or 14-day performance with pricing, OTA, pickup, comp set, and forecast decision signals.",
    "Analytics Workspace",
)

analysis_window = st.radio(
    "Analysis Window",
    options=[7, 14],
    format_func=lambda days: f"{days}-Day Performance",
    horizontal=True,
)
callout(
    f"{analysis_window}-day analysis mode",
    f"Upload up to {analysis_window} checklist CSVs for trend, comp set, OTA, forecast, pickup, and pricing-decision analytics.",
)

uploads = st.file_uploader("Upload Checklist CSVs", type=["csv"], accept_multiple_files=True)

if uploads:
    if len(uploads) > analysis_window:
        st.error(f"Upload {analysis_window} files or fewer for the selected analysis window.")
        st.stop()
    duplicates = detect_duplicate_uploads(uploads)
    if duplicates:
        st.error(f"Duplicate uploads detected: {', '.join(duplicates)}")
        st.stop()

    loaded = []
    errors = []
    for upload in uploads:
        try:
            raw = load_checklist(upload)
        except pd.errors.EmptyDataError:
            errors.append(f"{upload.name} is empty.")
            continue
        except Exception as exc:
            errors.append(f"Unable to read {upload.name}: {exc}")
            continue
        file_errors = validate_uploaded_checklist(raw, upload.name)
        if file_errors:
            errors.extend(file_errors)
        else:
            loaded.append((upload.name, normalize_checklist(raw)))

    if errors:
        for error in errors:
            st.error(error)
        st.stop()
    if not loaded:
        st.info("Upload valid checklist CSV files to build the dashboard.")
        st.stop()

    summary = summarize_uploaded_files(loaded)
    latest = summary.iloc[-1]

    if len(summary) < analysis_window:
        st.info(f"{len(summary)} CSV file(s) uploaded. Add {analysis_window - len(summary)} more to complete the {analysis_window}-day view.")

    section_title(f"{analysis_window}-Day KPI Snapshot")
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Occupancy", pct(latest["occupancy_pct"]))
    k2.metric("ADR", money(latest["adr"]))
    k3.metric("RevPAR", money(latest["revpar"]))
    k4.metric("Rate Gap", money(latest["rate_difference_vs_comp_set_average"]))
    k5.metric("Pickup Today", number(latest["total_pickup_today"]))

    section_title(f"{analysis_window}-Day Performance Summary")
    p1, p2, p3, p4, p5 = st.columns(5)
    p1.metric("Avg Occupancy", pct(summary["occupancy_pct"].mean()))
    p2.metric("Total Revenue", money(summary["total_revenue"].sum()))
    p3.metric("Avg ADR", money(summary["adr"].mean()))
    p4.metric("Avg RevPAR", money(summary["revpar"].mean()))
    p5.metric("Total Pickup", number(summary["total_pickup_today"].sum()))

    mix_df = pd.DataFrame(
        {
            "Segment": ["Transient Revenue", "Group Revenue"],
            "Revenue": [summary["transient_revenue"].sum(), summary["group_revenue"].sum()],
        }
    )
    c1, c2 = st.columns(2)
    c1.plotly_chart(bar_chart(mix_df, "Segment", "Revenue", f"{analysis_window}-Day Revenue Mix"), use_container_width=True)
    c2.plotly_chart(
        px.scatter(
            summary,
            x="rate_difference_vs_comp_set_average",
            y="occupancy_pct",
            size="total_revenue",
            hover_data=["date", "my_property_rate", "comp_set_average_rate", "rate_rank"],
            title="Pricing Position vs Occupancy",
            labels={
                "rate_difference_vs_comp_set_average": "Rate Gap vs Comp Set",
                "occupancy_pct": "Occupancy %",
                "total_revenue": "Total Revenue",
            },
            template="plotly_white",
        ),
        use_container_width=True,
    )

    section_title("Pricing Decision Signals")
    st.dataframe(pd.DataFrame(pricing_decision_signals(summary)), use_container_width=True, hide_index=True)

    section_title("Charts and Analytics")
    trend_tab, pricing_tab, forecast_tab = st.tabs(["Performance Trends", "Pricing Position", "Forecast and Pickup"])
    with trend_tab:
        c1, c2 = st.columns(2)
        c1.plotly_chart(line_chart(summary, "date", "occupancy_pct", "Occupancy Trend"), use_container_width=True)
        c2.plotly_chart(line_chart(summary, "date", "adr", "ADR Trend"), use_container_width=True)
        c1, c2 = st.columns(2)
        c1.plotly_chart(line_chart(summary, "date", "revpar", "RevPAR Trend"), use_container_width=True)
        c2.plotly_chart(line_chart(summary, "date", ["transient_revenue", "group_revenue"], "Transient and Group Revenue Trend"), use_container_width=True)
    with pricing_tab:
        c1, c2 = st.columns(2)
        c1.plotly_chart(line_chart(summary, "date", ["expedia_rate", "booking_rate", "agoda_rate", "priceline_rate"], "OTA Pricing Trend"), use_container_width=True)
        c2.plotly_chart(line_chart(summary, "date", ["my_property_rate", "comp_set_average_rate"], "My Property Rate vs Comp Set Average"), use_container_width=True)
        st.plotly_chart(line_chart(summary, "date", "rate_difference_vs_comp_set_average", "Daily Price Gap"), use_container_width=True)
        for idx in range(1, 6):
            st.plotly_chart(
                line_chart(
                    summary,
                    "date",
                    ["my_property_rate", f"competitor_{idx}_rate"],
                    f"My Property Rate vs Competitor {idx}",
                ),
                use_container_width=True,
            )
    with forecast_tab:
        c1, c2 = st.columns(2)
        c1.plotly_chart(line_chart(summary, "date", ["forecast_total_rooms", "booked_total_rooms", "available_to_sell_total"], "Forecast, Booked, and Available To Sell"), use_container_width=True)
        c2.plotly_chart(line_chart(summary, "date", "total_pickup_today", "Pickup Trend"), use_container_width=True)

    section_title("Market Position Analytics")
    stats = market_position_stats(summary)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Days Above Market", stats["days_above_market"])
    m2.metric("Days Below Market", stats["days_below_market"])
    m3.metric("Days Matching Market", stats["days_matching_market"])
    m4.metric("Average Rate Gap", money(stats["average_rate_gap"]))
    h1, h2 = st.columns(2)
    h1.metric("Highest Priced Competitor", stats["highest_priced_competitor"] or "N/A")
    h2.metric("Lowest Priced Competitor", stats["lowest_priced_competitor"] or "N/A")
    rank_df = stats["rank_distribution"].rename_axis("Rank").reset_index(name="Days")
    st.plotly_chart(bar_chart(rank_df, "Rank", "Days", "Rate Rank Distribution"), use_container_width=True)

    section_title("Forecast Performance Analytics")
    performance = forecast_performance(summary)
    f1, f2, f3 = st.columns(3)
    f1.metric("Forecast Achievement", pct(performance["forecast_achievement_pct"]))
    f2.metric("Days Ahead of Forecast", performance["days_ahead"])
    f3.metric("Days Behind Forecast", performance["days_behind"])
    st.plotly_chart(line_chart(summary, "date", ["forecast_total_rooms", "booked_total_rooms"], "Forecast vs Booked"), use_container_width=True)

    section_title("Alerts")
    alerts = trend_alerts(summary)
    if alerts:
        for alert in alerts:
            st.warning(alert)
    else:
        st.success("No current alerts from the latest uploaded checklist.")

    section_title("Combined Data")
    st.dataframe(summary, use_container_width=True, hide_index=True)
    st.download_button(
        "Download Combined CSV",
        data=summary.to_csv(index=False).encode("utf-8"),
        file_name=f"combined_{analysis_window}_day_revenue_dashboard.csv",
        mime="text/csv",
    )
else:
    st.info(f"Upload up to {analysis_window} exported checklist CSV files to generate the revenue dashboard.")
