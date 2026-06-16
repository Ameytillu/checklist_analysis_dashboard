from __future__ import annotations

from datetime import date, datetime, timedelta
import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.calculations import (
    FORECAST_FIELDS,
    build_export_frame,
    calculate_comp_set,
    calculate_pickup,
    money,
    number,
)
from utils.ui import apply_theme, callout, page_header, section_title
from utils.validation import validate_export_inputs


def calculate_adr(revenue: float, rooms: int) -> float:
    return round(revenue / rooms, 2) if rooms else 0.0


def draft_path(checklist_day: date) -> Path:
    return Path("drafts") / f"checklist_{checklist_day.isoformat()}.json"


def load_draft(checklist_day: date) -> dict:
    path = draft_path(checklist_day)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_draft(checklist_day: date, payload: dict) -> Path:
    path = draft_path(checklist_day)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path


def draft_value(draft: dict, key: str, default):
    value = draft.get(key, default)
    return default if value is None else value


def int_value(draft: dict, key: str, default: int) -> int:
    try:
        return int(draft_value(draft, key, default))
    except (TypeError, ValueError):
        return default


def float_value(draft: dict, key: str, default: float) -> float:
    try:
        return float(draft_value(draft, key, default))
    except (TypeError, ValueError):
        return default


def safe_int(value, default: int = 0) -> int:
    converted = pd.to_numeric(value, errors="coerce")
    if pd.isna(converted):
        return default
    return int(converted)


def format_saved_time(saved_at: str | None) -> str:
    if not saved_at:
        return "Not saved yet"
    try:
        return datetime.fromisoformat(saved_at).strftime("%Y-%m-%d %I:%M %p")
    except ValueError:
        return saved_at


def forecast_window(start_day: date, days: int = 14) -> list[date]:
    return [start_day + timedelta(days=offset) for offset in range(days)]


def default_forecast_rows(start_day: date) -> list[dict]:
    return [
        {
            "stay_date": forecast_day.isoformat(),
            "forecast_rooms": 0,
            "forecast_revenue": 0.0,
            "booked_rooms": 0,
            "available_to_sell_rooms": 0,
        }
        for forecast_day in forecast_window(start_day)
    ]


def normalize_forecast_rows(rows: list[dict] | None, start_day: date) -> pd.DataFrame:
    defaults = pd.DataFrame(default_forecast_rows(start_day))
    if not isinstance(rows, list) or not rows:
        return defaults

    saved = pd.DataFrame(rows)
    if "stay_date" not in saved.columns:
        return defaults

    saved["stay_date"] = pd.to_datetime(saved["stay_date"], errors="coerce").dt.date.astype(str)
    merged = defaults[["stay_date"]].merge(saved, on="stay_date", how="left", suffixes=("", "_saved"))
    for column in ["forecast_rooms", "forecast_revenue", "booked_rooms", "available_to_sell_rooms"]:
        if column not in merged.columns:
            merged[column] = defaults[column]
        merged[column] = pd.to_numeric(merged[column], errors="coerce").fillna(defaults[column])
    return merged[["stay_date", "forecast_rooms", "forecast_revenue", "booked_rooms", "available_to_sell_rooms"]]


def pickup_hour_labels() -> list[str]:
    return [
        (datetime.combine(date.today(), datetime.min.time()) + timedelta(hours=8, minutes=30) + timedelta(hours=offset)).strftime("%I:%M %p")
        for offset in range(9)
    ]


def pickup_date_label(pickup_day: date) -> str:
    return pickup_day.strftime("%b %d")


def build_pickup_matrix(
    pickup_days: list[date],
    forecast_rows: pd.DataFrame,
    saved_pickup_rows: list[dict] | None,
) -> pd.DataFrame:
    row_labels = ["Forecasted Rooms"] + pickup_hour_labels()
    matrix = pd.DataFrame({"Time": row_labels})
    forecast_by_day = {
        str(row["stay_date"]): int(row["forecast_rooms"]) if pd.notna(row["forecast_rooms"]) else 0
        for _, row in forecast_rows.iterrows()
    }
    pickup_by_day_time: dict[tuple[str, str], int] = {}

    if isinstance(saved_pickup_rows, list) and saved_pickup_rows:
        saved = pd.DataFrame(saved_pickup_rows)
        if "pickup_date" not in saved.columns:
            saved["pickup_date"] = pickup_days[0].isoformat()
        if "pickup_time" in saved.columns and "pickup_available_to_sell_rooms" in saved.columns:
            saved["pickup_date"] = pd.to_datetime(saved["pickup_date"], errors="coerce").dt.date.astype(str)
            saved["pickup_available_to_sell_rooms"] = pd.to_numeric(
                saved["pickup_available_to_sell_rooms"], errors="coerce"
            ).fillna(0)
            pickup_by_day_time = {
                (row["pickup_date"], str(row["pickup_time"])): int(row["pickup_available_to_sell_rooms"])
                for _, row in saved.iterrows()
            }

    for pickup_day in pickup_days:
        day_key = pickup_day.isoformat()
        column = pickup_date_label(pickup_day)
        matrix[column] = [
            forecast_by_day.get(day_key, 0),
            *[pickup_by_day_time.get((day_key, hour), 0) for hour in row_labels[1:]],
        ]
    return matrix


def matrix_to_forecast_rows(matrix: pd.DataFrame, pickup_days: list[date]) -> pd.DataFrame:
    rows = []
    for pickup_day in pickup_days:
        column = pickup_date_label(pickup_day)
        forecast_rooms = safe_int(matrix.loc[0, column])
        hourly_matrix = matrix.iloc[1:].copy()
        hourly_matrix = hourly_matrix[hourly_matrix["Time"].astype(str).str.strip().ne("")]
        hourly_values = pd.to_numeric(hourly_matrix[column], errors="coerce").fillna(0)
        rows.append(
            {
                "stay_date": pickup_day.isoformat(),
                "forecast_rooms": forecast_rooms,
                "forecast_revenue": 0.0,
                "booked_rooms": 0,
                "available_to_sell_rooms": int(hourly_values.iloc[-1]) if not hourly_values.empty else 0,
            }
        )
    return pd.DataFrame(rows, columns=FORECAST_FIELDS)


def matrix_to_pickup_rows(matrix: pd.DataFrame, pickup_days: list[date]) -> pd.DataFrame:
    rows = []
    hourly_matrix = matrix.iloc[1:].copy()
    hourly_matrix = hourly_matrix[hourly_matrix["Time"].astype(str).str.strip().ne("")]
    for pickup_day in pickup_days:
        column = pickup_date_label(pickup_day)
        forecast_rooms = safe_int(matrix.loc[0, column])
        for row_idx, pickup_time in hourly_matrix["Time"].items():
            available_rooms = safe_int(matrix.loc[row_idx, column])
            rows.append(
                {
                    "pickup_date": pickup_day.isoformat(),
                    "pickup_time": pickup_time,
                    "pickup_forecast_rooms_to_sell": forecast_rooms,
                    "pickup_available_to_sell_rooms": available_rooms,
                }
            )
    return pd.DataFrame(rows)


TOTAL_HOTEL_ROOMS = 433


st.set_page_config(page_title="Daily Revenue Checklist", layout="wide")
apply_theme()
page_header(
    "Daily Revenue Checklist",
    "Enter the morning checklist, review comp set and pickup calculations, then export a clean daily CSV.",
    "Daily Entry",
)
callout(
    "CSV export workflow",
    "The form does not save to a database. Use the download button after validation to keep the daily record.",
)

section_title("General Hotel Metrics")
c1, c2, c3, c4 = st.columns(4)
checklist_date = c1.date_input("Date", value=date.today())
draft = load_draft(checklist_date)
draft_key = checklist_date.isoformat()
c1.caption(f"Last saved: {format_saved_time(draft.get('saved_at'))}")
occupancy_pct = c2.number_input(
    "Occupancy %",
    min_value=0.0,
    max_value=100.0,
    value=float_value(draft, "occupancy_pct", 75.0),
    step=0.1,
    key=f"occupancy_pct_{draft_key}",
)
expected_arrivals = c3.number_input(
    "Expected Arrivals",
    min_value=0,
    value=int_value(draft, "expected_arrivals", 25),
    key=f"expected_arrivals_{draft_key}",
)
expected_departures = c4.number_input(
    "Expected Departures",
    min_value=0,
    value=int_value(draft, "expected_departures", 20),
    key=f"expected_departures_{draft_key}",
)
c1, c2, c3 = st.columns(3)
out_of_order_rooms = c1.number_input(
    "Out of Order / Out of Market Rooms",
    min_value=0,
    value=int_value(draft, "out_of_order_rooms", 0),
    key=f"out_of_order_rooms_{draft_key}",
)
total_rooms_available = c2.number_input(
    "Total Rooms Available",
    min_value=1,
    value=int_value(draft, "total_rooms_available", 150),
    key=f"total_rooms_available_{draft_key}",
)
total_rooms_sold = c3.number_input(
    "Total Rooms Sold",
    min_value=0,
    value=int_value(draft, "total_rooms_sold", 112),
    key=f"total_rooms_sold_{draft_key}",
)

section_title("Previous Night Performance")
t1, t2, t3 = st.columns(3)
transient_rooms = t1.number_input(
    "Transient Rooms",
    min_value=0,
    value=int_value(draft, "transient_rooms", 70),
    key=f"transient_rooms_{draft_key}",
)
transient_revenue = t2.number_input(
    "Transient Revenue",
    min_value=0.0,
    value=float_value(draft, "transient_revenue", 10500.0),
    step=100.0,
    key=f"transient_revenue_{draft_key}",
)
transient_adr = calculate_adr(transient_revenue, transient_rooms)
t3.number_input(
    "Transient ADR",
    min_value=0.0,
    value=transient_adr,
    step=1.0,
    disabled=True,
    help="Automatically calculated as Transient Revenue divided by Transient Rooms.",
    key=f"transient_adr_{draft_key}",
)

g1, g2, g3 = st.columns(3)
group_rooms = g1.number_input(
    "Group Rooms",
    min_value=0,
    value=int_value(draft, "group_rooms", 42),
    key=f"group_rooms_{draft_key}",
)
group_revenue = g2.number_input(
    "Group Revenue",
    min_value=0.0,
    value=float_value(draft, "group_revenue", 5460.0),
    step=100.0,
    key=f"group_revenue_{draft_key}",
)
group_adr = calculate_adr(group_revenue, group_rooms)
g3.number_input(
    "Group ADR",
    min_value=0.0,
    value=group_adr,
    step=1.0,
    disabled=True,
    help="Automatically calculated as Group Revenue divided by Group Rooms.",
    key=f"group_adr_{draft_key}",
)

o1, o2, o3 = st.columns(3)
total_revenue = o1.number_input(
    "Total Revenue",
    min_value=0.0,
    value=float_value(draft, "total_revenue", 15960.0),
    step=100.0,
    key=f"total_revenue_{draft_key}",
)
adr = calculate_adr(total_revenue, TOTAL_HOTEL_ROOMS)
o2.number_input(
    "ADR",
    min_value=0.0,
    value=adr,
    step=1.0,
    disabled=True,
    help="Automatically calculated as Total Revenue divided by 433 hotel rooms.",
    key=f"adr_{draft_key}",
)
revpar = o3.number_input(
    "RevPAR",
    min_value=0.0,
    value=float_value(draft, "revpar", 106.8),
    step=1.0,
    key=f"revpar_{draft_key}",
)

section_title("Lighthouse Data and OTA Pricing")
l1, l2, l3, l4, l5, l6 = st.columns(6)
demand_options = ["Low", "Moderate", "High", "Compression"]
demand_level = l1.selectbox(
    "Demand Level",
    demand_options,
    index=demand_options.index(draft_value(draft, "demand_level", "Moderate"))
    if draft_value(draft, "demand_level", "Moderate") in demand_options
    else 1,
    key=f"demand_level_{draft_key}",
)
demand_score = l2.number_input(
    "Demand Score",
    min_value=0.0,
    max_value=100.0,
    value=float_value(draft, "demand_score", 65.0),
    step=1.0,
    key=f"demand_score_{draft_key}",
)
expedia_rate = l3.number_input(
    "Expedia Rate",
    min_value=0.0,
    value=float_value(draft, "expedia_rate", 159.0),
    step=1.0,
    key=f"expedia_rate_{draft_key}",
)
booking_rate = l4.number_input(
    "Booking.com Rate",
    min_value=0.0,
    value=float_value(draft, "booking_rate", 162.0),
    step=1.0,
    key=f"booking_rate_{draft_key}",
)
agoda_rate = l5.number_input(
    "Agoda Rate",
    min_value=0.0,
    value=float_value(draft, "agoda_rate", 149.0),
    step=1.0,
    key=f"agoda_rate_{draft_key}",
)
priceline_rate = l6.number_input(
    "Priceline Rate",
    min_value=0.0,
    value=float_value(draft, "priceline_rate", 155.0),
    step=1.0,
    key=f"priceline_rate_{draft_key}",
)

section_title("Comp Set Pricing")
c1, c2 = st.columns(2)
my_property_name = c1.text_input(
    "My Property Name",
    value=draft_value(draft, "my_property_name", "My Hotel"),
    key=f"my_property_name_{draft_key}",
)
my_property_rate = c2.number_input(
    "My Property Rate",
    min_value=0.0,
    value=float_value(draft, "my_property_rate", 165.0),
    step=1.0,
    key=f"my_property_rate_{draft_key}",
)
competitor_names = []
competitor_rates = []
for idx in range(1, 6):
    n_col, r_col = st.columns(2)
    competitor_names.append(
        n_col.text_input(
            f"Competitor {idx} Name",
            value=draft_value(draft, f"competitor_{idx}_name", f"Competitor {idx}"),
            key=f"competitor_{idx}_name_{draft_key}",
        )
    )
    competitor_rates.append(
        r_col.number_input(
            f"Competitor {idx} Rate",
            min_value=0.0,
            value=float_value(draft, f"competitor_{idx}_rate", 150.0 + idx * 4),
            step=1.0,
            key=f"competitor_{idx}_rate_{draft_key}",
        )
    )

comp_metrics = calculate_comp_set(my_property_rate, competitor_rates)
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Comp Set Avg", money(comp_metrics.average_rate))
k2.metric("Rate Gap", money(comp_metrics.rate_gap))
k3.metric("Rate Rank", f"#{comp_metrics.rank}" if comp_metrics.rank else "N/A")
k4.metric("Highest Competitor", money(comp_metrics.highest_competitor_rate))
k5.metric("Lowest Competitor", money(comp_metrics.lowest_competitor_rate))

section_title("Hourly Pickup Tracker")
st.caption(
    "Each date is a column. Enter forecasted rooms in the first row, then enter hourly available-to-sell rooms below."
)
pickup_days = forecast_window(checklist_date)
forecast_template = normalize_forecast_rows(draft.get("forecast_rows"), checklist_date)
pickup_matrix_template = build_pickup_matrix(pickup_days, forecast_template, draft.get("pickup_rows"))
pickup_column_config = {
    "Time": st.column_config.TextColumn("Time", width="medium"),
}
for pickup_day in pickup_days:
    pickup_column_config[pickup_date_label(pickup_day)] = st.column_config.NumberColumn(
        pickup_day.strftime("%b %d"),
        min_value=0,
        step=1,
        width="small",
    )

pickup_matrix_input = st.data_editor(
    pickup_matrix_template,
    hide_index=True,
    num_rows="dynamic",
    use_container_width=True,
    column_config=pickup_column_config,
    key=f"pickup_matrix_{draft_key}",
)
pickup_matrix_input.loc[0, "Time"] = "Forecasted Rooms"
forecast_df = matrix_to_forecast_rows(pickup_matrix_input, pickup_days)
forecast_rooms_to_sell_today = safe_int(forecast_df.loc[0, "forecast_rooms"]) if not forecast_df.empty else 0
all_pickup_input = matrix_to_pickup_rows(pickup_matrix_input, pickup_days)
all_pickup_calculated = calculate_pickup(all_pickup_input, forecast_rooms_to_sell_today)

general = {
    "date": checklist_date.isoformat(),
    "occupancy_pct": occupancy_pct,
    "expected_arrivals": expected_arrivals,
    "expected_departures": expected_departures,
    "out_of_order_rooms": out_of_order_rooms,
    "total_rooms_available": total_rooms_available,
    "total_rooms_sold": total_rooms_sold,
    "transient_rooms": transient_rooms,
    "transient_revenue": transient_revenue,
    "transient_adr": transient_adr,
    "group_rooms": group_rooms,
    "group_revenue": group_revenue,
    "group_adr": group_adr,
    "total_revenue": total_revenue,
    "adr": adr,
    "revpar": revpar,
    "demand_level": demand_level,
    "demand_score": demand_score,
    "expedia_rate": expedia_rate,
    "booking_rate": booking_rate,
    "agoda_rate": agoda_rate,
    "priceline_rate": priceline_rate,
    "forecast_rooms_to_sell_today": forecast_rooms_to_sell_today,
    "my_property_name": my_property_name,
    "my_property_rate": my_property_rate,
    "comp_set_average_rate": comp_metrics.average_rate,
    "rate_difference_vs_comp_set_average": comp_metrics.rate_gap,
    "rate_rank": comp_metrics.rank,
    "highest_competitor_rate": comp_metrics.highest_competitor_rate,
    "lowest_competitor_rate": comp_metrics.lowest_competitor_rate,
}
for idx, (name, rate) in enumerate(zip(competitor_names, competitor_rates), start=1):
    general[f"competitor_{idx}_name"] = name
    general[f"competitor_{idx}_rate"] = rate

section_title("Pickup Summary")
total_pickup = all_pickup_calculated["pickup_rooms"].sum() if not all_pickup_calculated.empty else 0
total_forecast = forecast_df["forecast_rooms"].sum() if not forecast_df.empty else 0
total_remaining = max(total_forecast - total_pickup, 0)
today_key = checklist_date.isoformat()
today_forecast_rows = forecast_df.loc[forecast_df["stay_date"] == today_key, "forecast_rooms"]
today_forecast = safe_int(today_forecast_rows.iloc[0]) if not today_forecast_rows.empty else 0
today_pickup_rows = all_pickup_calculated[all_pickup_calculated["pickup_date"].astype(str) == today_key]
today_pickup = today_pickup_rows["pickup_rooms"].sum() if not today_pickup_rows.empty else 0
today_remaining = max(today_forecast - today_pickup, 0)
p1, p2, p3, p4 = st.columns(4)
p1.metric("14-Day Forecast", number(total_forecast))
p2.metric("14-Day Pickup", number(total_pickup))
p3.metric("Forecast Remaining", number(total_remaining))
p4.metric("Today Pickup", number(today_pickup), delta=f"{number(today_remaining)} rooms away")

pickup_monitoring_rows = []
for pickup_day in pickup_days:
    day_key = pickup_day.isoformat()
    day_forecast_rows = forecast_df.loc[forecast_df["stay_date"] == day_key, "forecast_rooms"]
    day_forecast = safe_int(day_forecast_rows.iloc[0]) if not day_forecast_rows.empty else 0
    day_pickup_rows = all_pickup_calculated[all_pickup_calculated["pickup_date"].astype(str) == day_key]
    day_pickup = day_pickup_rows["pickup_rooms"].sum() if not day_pickup_rows.empty else 0
    pickup_monitoring_rows.append(
        {
            "date": pickup_day.strftime("%b %d"),
            "forecast_rooms": day_forecast,
            "pickup_rooms": day_pickup,
            "remaining_rooms": max(day_forecast - day_pickup, 0),
        }
    )

pickup_monitoring_df = pd.DataFrame(pickup_monitoring_rows)
pickup_monitoring_chart = go.Figure()
pickup_monitoring_chart.add_bar(
    x=pickup_monitoring_df["date"],
    y=pickup_monitoring_df["pickup_rooms"],
    name="Pickup Rooms",
    marker_color="#2563eb",
)
pickup_monitoring_chart.add_scatter(
    x=pickup_monitoring_df["date"],
    y=pickup_monitoring_df["forecast_rooms"],
    name="Forecast Rooms",
    mode="lines+markers",
    line=dict(color="#111827", width=3),
)
pickup_monitoring_chart.add_scatter(
    x=pickup_monitoring_df["date"],
    y=pickup_monitoring_df["remaining_rooms"],
    name="Rooms Away",
    mode="lines+markers",
    line=dict(color="#f59e0b", width=3),
)
pickup_monitoring_chart.update_layout(
    title="Pickup Monitoring",
    barmode="group",
    template="plotly_white",
    legend_title_text="",
    margin=dict(l=10, r=10, t=55, b=10),
    xaxis_title="Date",
    yaxis_title="Rooms",
)
st.plotly_chart(pickup_monitoring_chart, use_container_width=True)

draft_payload = {
    **general,
    "forecast_rows": forecast_df.to_dict("records"),
    "pickup_rows": all_pickup_input.to_dict("records"),
    "saved_at": datetime.now().isoformat(timespec="seconds"),
}

save_col, export_col = st.columns([1, 3])
if save_col.button("Save Draft", key=f"save_draft_{draft_key}"):
    saved_path = save_draft(checklist_date, draft_payload)
    st.success(f"Draft saved at {format_saved_time(draft_payload['saved_at'])}.")
    st.caption(f"Saved locally to {saved_path}")

submitted = export_col.button("Export Today's Checklist", type="primary", key=f"export_checklist_{draft_key}")
if submitted:
    errors = validate_export_inputs(general, forecast_df, all_pickup_input)
    if errors:
        for error in errors:
            st.error(error)
    else:
        export_df = build_export_frame(general, forecast_df, all_pickup_input)
        filename = f"revenue_checklist_{datetime.strptime(general['date'], '%Y-%m-%d').date().isoformat()}.csv"
        st.success(f"{filename} is ready for download.")
        st.download_button(
            "Download CSV",
            data=export_df.to_csv(index=False).encode("utf-8"),
            file_name=filename,
            mime="text/csv",
        )
