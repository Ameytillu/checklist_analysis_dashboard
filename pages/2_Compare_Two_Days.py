from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.calculations import (
    OTA_RATE_FIELDS,
    PERFORMANCE_FIELDS,
    compare_values,
    daily_record,
    forecast_rows,
    load_checklist,
    money,
    normalize_checklist,
    number,
    pct,
)
from utils.charts import comparison_bar
from utils.insights import comparison_summary
from utils.validation import validate_uploaded_checklist


st.set_page_config(page_title="Compare Two Days", layout="wide")
st.title("Compare Two Days")
st.caption("Upload two exported checklist CSVs to compare performance, OTA rates, comp set position, and forecast pace.")

day_1_file = st.file_uploader("CSV Day 1", type=["csv"], key="day1")
day_2_file = st.file_uploader("CSV Day 2", type=["csv"], key="day2")

if day_1_file and day_2_file:
    try:
        raw_day_1 = load_checklist(day_1_file)
        raw_day_2 = load_checklist(day_2_file)
    except pd.errors.EmptyDataError:
        st.error("One of the uploaded CSV files is empty.")
        st.stop()
    except Exception as exc:
        st.error(f"Unable to read the uploaded CSV files: {exc}")
        st.stop()

    errors = validate_uploaded_checklist(raw_day_1, day_1_file.name) + validate_uploaded_checklist(raw_day_2, day_2_file.name)
    if errors:
        for error in errors:
            st.error(error)
        st.stop()

    day_1_df = normalize_checklist(raw_day_1)
    day_2_df = normalize_checklist(raw_day_2)
    day_1 = daily_record(day_1_df)
    day_2 = daily_record(day_2_df)

    st.subheader("Executive Summary")
    f1 = forecast_rows(day_1_df)
    f2 = forecast_rows(day_2_df)
    enriched_day_1 = day_1.copy()
    enriched_day_2 = day_2.copy()
    enriched_day_1["forecast_total_rooms"] = f1["forecast_rooms"].sum()
    enriched_day_1["booked_total_rooms"] = f1["booked_rooms"].sum()
    enriched_day_2["forecast_total_rooms"] = f2["forecast_rooms"].sum()
    enriched_day_2["booked_total_rooms"] = f2["booked_rooms"].sum()
    st.info(comparison_summary(enriched_day_1, enriched_day_2))

    st.subheader("Metric Comparisons")
    metric_rows = []
    for field in PERFORMANCE_FIELDS:
        change, pct_change = compare_values(day_2[field], day_1[field])
        metric_rows.append(
            {
                "metric": field.replace("_", " ").title(),
                "day_1": day_1[field],
                "day_2": day_2[field],
                "change": change,
                "pct_change": pct_change,
            }
        )
    metrics_df = pd.DataFrame(metric_rows)
    st.plotly_chart(comparison_bar(metric_rows, "Day 1 vs Day 2 Performance"), use_container_width=True)
    st.dataframe(metrics_df, use_container_width=True, hide_index=True)

    st.subheader("OTA Comparison")
    ota_rows = []
    for field in OTA_RATE_FIELDS:
        change, pct_change = compare_values(day_2[field], day_1[field])
        ota_rows.append(
            {
                "OTA": field.replace("_rate", "").replace("_", " ").title(),
                "Day 1": money(day_1[field]),
                "Day 2": money(day_2[field]),
                "Dollar Change": money(change),
                "Percentage Change": pct(pct_change),
            }
        )
    st.dataframe(pd.DataFrame(ota_rows), use_container_width=True, hide_index=True)

    st.subheader("Comp Set Comparison")
    comp_fields = ["my_property_rate"] + [f"competitor_{idx}_rate" for idx in range(1, 6)] + ["comp_set_average_rate"]
    comp_rows = []
    for field in comp_fields:
        change, pct_change = compare_values(day_2[field], day_1[field])
        comp_rows.append(
            {
                "Rate": field.replace("_rate", "").replace("_", " ").title(),
                "Day 1": money(day_1[field]),
                "Day 2": money(day_2[field]),
                "Increase / Decrease": money(change),
                "Change %": pct(pct_change),
            }
        )
    rank_change = int(day_2["rate_rank"] - day_1["rate_rank"])
    c1, c2, c3 = st.columns(3)
    c1.metric("Market Position Change", money(day_2["rate_difference_vs_comp_set_average"] - day_1["rate_difference_vs_comp_set_average"]))
    c2.metric("Rank Change", f"{rank_change:+d}")
    c3.metric("Current Rank", f"#{int(day_2['rate_rank'])}" if day_2["rate_rank"] else "N/A")
    st.dataframe(pd.DataFrame(comp_rows), use_container_width=True, hide_index=True)

    st.subheader("Forecast Comparison")
    forecast_compare = f1.merge(f2, on="stay_date", how="outer", suffixes=("_day_1", "_day_2")).fillna(0)
    forecast_compare["pickup_difference"] = forecast_compare["booked_rooms_day_2"] - forecast_compare["booked_rooms_day_1"]
    forecast_compare["pace_difference"] = forecast_compare["available_to_sell_rooms_day_1"] - forecast_compare["available_to_sell_rooms_day_2"]
    k1, k2 = st.columns(2)
    k1.metric("Total Pickup Difference", number(forecast_compare["pickup_difference"].sum()))
    k2.metric("Total Pace Difference", number(forecast_compare["pace_difference"].sum()))
    st.dataframe(forecast_compare, use_container_width=True, hide_index=True)
else:
    st.info("Upload two checklist CSV files to generate the comparison dashboard.")

