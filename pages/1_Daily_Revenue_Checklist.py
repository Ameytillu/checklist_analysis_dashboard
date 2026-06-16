from __future__ import annotations

from datetime import date, datetime, timedelta
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from utils.calculations import (
    FORECAST_FIELDS,
    build_export_frame,
    calculate_comp_set,
    calculate_pickup,
    money,
    number,
)
from utils.charts import pickup_chart
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


def default_hourly_pickup_rows(pickup_day: date, forecast_rooms: int = 0) -> list[dict]:
    return [
        {
            "pickup_date": pickup_day.isoformat(),
            "pickup_time": (datetime.combine(pickup_day, datetime.min.time()) + timedelta(hours=hour)).strftime("%I:00 %p"),
            "pickup_forecast_rooms_to_sell": forecast_rooms,
            "pickup_available_to_sell_rooms": 0,
        }
        for hour in range(24)
    ]


def pickup_rows_for_day(rows: list[dict] | None, pickup_day: date, forecast_rooms: int = 0) -> pd.DataFrame:
    defaults = pd.DataFrame(default_hourly_pickup_rows(pickup_day, forecast_rooms))
    if not isinstance(rows, list) or not rows:
        return defaults

    saved = pd.DataFrame(rows)
    if "pickup_date" not in saved.columns:
        saved["pickup_date"] = pickup_day.isoformat()
    saved["pickup_date"] = pd.to_datetime(saved["pickup_date"], errors="coerce").dt.date.astype(str)
    day_rows = saved[saved["pickup_date"] == pickup_day.isoformat()].copy()
    if day_rows.empty:
        return defaults

    for column in ["pickup_time", "pickup_available_to_sell_rooms"]:
        if column not in day_rows.columns:
            day_rows[column] = defaults[column]
    day_rows["pickup_forecast_rooms_to_sell"] = forecast_rooms
    return day_rows[["pickup_date", "pickup_time", "pickup_forecast_rooms_to_sell", "pickup_available_to_sell_rooms"]]


def combine_pickup_rows(
    pickup_days: list[date],
    forecast_by_day: dict[str, int],
    saved_rows: list[dict] | None,
    editor_prefix: str,
) -> pd.DataFrame:
    day_frames = []
    pickup_cache = st.session_state.get(f"{editor_prefix}_cache", {})
    for pickup_day in pickup_days:
        day_key = pickup_day.isoformat()
        if day_key in pickup_cache:
            day_frame = pd.DataFrame(pickup_cache[day_key])
            day_frame["pickup_date"] = day_key
            day_frame["pickup_forecast_rooms_to_sell"] = forecast_by_day.get(day_key, 0)
        else:
            day_frame = pickup_rows_for_day(saved_rows, pickup_day, forecast_by_day.get(day_key, 0))
        day_frames.append(day_frame)
    return pd.concat(day_frames, ignore_index=True) if day_frames else pd.DataFrame()


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
    "Enter the start date once above. This section creates the next 14 stay dates, then lets you update one day's hourly pickup at a time."
)
forecast_template = normalize_forecast_rows(draft.get("forecast_rows"), checklist_date)
forecast_input = st.data_editor(
    forecast_template,
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
    column_config={
        "stay_date": st.column_config.DateColumn("Stay Date", disabled=True),
        "forecast_rooms": st.column_config.NumberColumn("Forecast Rooms", min_value=0),
        "forecast_revenue": st.column_config.NumberColumn("Forecast Revenue", min_value=0, format="$%.0f"),
        "booked_rooms": st.column_config.NumberColumn("Booked Rooms", min_value=0),
        "available_to_sell_rooms": st.column_config.NumberColumn("Available To Sell Rooms", min_value=0),
    },
    key=f"forecast_input_{draft_key}",
)

forecast_df = forecast_input.copy()
forecast_df["stay_date"] = pd.to_datetime(forecast_df["stay_date"], errors="coerce").dt.date.astype(str)
forecast_by_day = {
    row["stay_date"]: int(row["forecast_rooms"]) if pd.notna(row["forecast_rooms"]) else 0
    for _, row in forecast_df.iterrows()
}
forecast_rooms_to_sell_today = forecast_by_day.get(checklist_date.isoformat(), 0)

pickup_days = forecast_window(checklist_date)
day_options = {day.strftime("%a %b %d"): day for day in pickup_days}
summary_day_col, metric_col_1, metric_col_2, metric_col_3 = st.columns([2, 1, 1, 1])
selected_day_label = summary_day_col.selectbox(
    "Hourly Pickup Date",
    options=list(day_options.keys()),
    key=f"pickup_day_selector_{draft_key}",
)
selected_pickup_day = day_options[selected_day_label]
selected_day_key = selected_pickup_day.isoformat()
selected_forecast_rooms = forecast_by_day.get(selected_day_key, 0)
selected_forecast_row = forecast_df[forecast_df["stay_date"] == selected_day_key].iloc[0]
metric_col_1.metric("Forecast Rooms", number(selected_forecast_rooms))
metric_col_2.metric("Booked Rooms", number(selected_forecast_row["booked_rooms"]))
metric_col_3.metric("Available", number(selected_forecast_row["available_to_sell_rooms"]))

pickup_template = pickup_rows_for_day(draft.get("pickup_rows"), selected_pickup_day, selected_forecast_rooms)
pickup_input = st.data_editor(
    pickup_template[["pickup_time", "pickup_available_to_sell_rooms"]],
    hide_index=True,
    num_rows="fixed",
    use_container_width=True,
    column_config={
        "pickup_time": st.column_config.TextColumn("Time", disabled=True),
        "pickup_available_to_sell_rooms": st.column_config.NumberColumn("Available To Sell Rooms", min_value=0),
    },
    key=f"pickup_input_{draft_key}_{selected_day_key}",
)
pickup_input["pickup_date"] = selected_day_key
pickup_input["pickup_forecast_rooms_to_sell"] = selected_forecast_rooms
pickup_cache_key = f"pickup_input_{draft_key}_cache"
if pickup_cache_key not in st.session_state:
    st.session_state[pickup_cache_key] = {}
st.session_state[pickup_cache_key][selected_day_key] = pickup_input.to_dict("records")

pickup_calculated = calculate_pickup(pickup_input, selected_forecast_rooms)
if not pickup_calculated.empty:
    pickup_status = pickup_calculated[
        [
            "pickup_date",
            "pickup_time",
            "pickup_forecast_rooms_to_sell",
            "pickup_available_to_sell_rooms",
            "pickup_rooms",
            "forecast_rooms_remaining",
        ]
    ].rename(
        columns={
            "pickup_date": "Date",
            "pickup_time": "Time",
            "pickup_forecast_rooms_to_sell": "Forecast Rooms",
            "pickup_available_to_sell_rooms": "Available To Sell Rooms",
            "pickup_rooms": "Pickup Rooms",
            "forecast_rooms_remaining": "Forecast Rooms Remaining",
        }
    )
    st.dataframe(pickup_status, use_container_width=True, hide_index=True)

all_pickup_input = combine_pickup_rows(
    pickup_days,
    forecast_by_day,
    draft.get("pickup_rows"),
    f"pickup_input_{draft_key}",
)

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
all_pickup_calculated = calculate_pickup(all_pickup_input, forecast_rooms_to_sell_today)
selected_day_calculated = all_pickup_calculated[all_pickup_calculated["pickup_date"].astype(str) == selected_day_key]
selected_day_pickup = selected_day_calculated["pickup_rooms"].sum() if not selected_day_calculated.empty else 0
total_pickup = all_pickup_calculated["pickup_rooms"].sum() if not all_pickup_calculated.empty else 0
p1, p2, p3, p4 = st.columns([1, 1, 1, 3])
p1.metric("Selected Day Pickup", number(selected_day_pickup))
selected_remaining_forecast = max(selected_forecast_rooms - selected_day_pickup, 0)
p2.metric("Selected Forecast Remaining", number(selected_remaining_forecast))
p3.metric("14-Day Pickup", number(total_pickup))
if not pickup_calculated.empty:
    p4.plotly_chart(pickup_chart(pickup_calculated), use_container_width=True)

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
