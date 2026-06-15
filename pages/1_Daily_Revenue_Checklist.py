from __future__ import annotations

from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st

from utils.calculations import (
    build_export_frame,
    calculate_comp_set,
    calculate_pickup,
    money,
    number,
)
from utils.charts import pickup_chart
from utils.ui import apply_theme, callout, page_header, section_title
from utils.validation import validate_export_inputs


st.set_page_config(page_title="Daily Revenue Checklist", layout="wide")
apply_theme()
page_header(
    "Daily Revenue Checklist",
    "Enter the morning checklist, review comp set and pickup calculations, then export a clean daily CSV.",
    "Daily Entry",
)
callout("CSV export workflow", "The form does not save to a database. Use the download button after validation to keep the daily record.")

with st.form("daily_checklist_form"):
    section_title("General Hotel Metrics")
    c1, c2, c3, c4 = st.columns(4)
    checklist_date = c1.date_input("Date", value=date.today())
    occupancy_pct = c2.number_input("Occupancy %", min_value=0.0, max_value=100.0, value=75.0, step=0.1)
    expected_arrivals = c3.number_input("Expected Arrivals", min_value=0, value=25)
    expected_departures = c4.number_input("Expected Departures", min_value=0, value=20)
    c1, c2, c3 = st.columns(3)
    out_of_order_rooms = c1.number_input("Out of Order / Out of Market Rooms", min_value=0, value=0)
    total_rooms_available = c2.number_input("Total Rooms Available", min_value=1, value=150)
    total_rooms_sold = c3.number_input("Total Rooms Sold", min_value=0, value=112)

    section_title("Previous Night Performance")
    t1, t2, t3 = st.columns(3)
    transient_rooms = t1.number_input("Transient Rooms", min_value=0, value=70)
    transient_revenue = t2.number_input("Transient Revenue", min_value=0.0, value=10500.0, step=100.0)
    transient_adr = t3.number_input("Transient ADR", min_value=0.0, value=150.0, step=1.0)
    g1, g2, g3 = st.columns(3)
    group_rooms = g1.number_input("Group Rooms", min_value=0, value=42)
    group_revenue = g2.number_input("Group Revenue", min_value=0.0, value=5460.0, step=100.0)
    group_adr = g3.number_input("Group ADR", min_value=0.0, value=130.0, step=1.0)
    o1, o2, o3 = st.columns(3)
    total_revenue = o1.number_input("Total Revenue", min_value=0.0, value=15960.0, step=100.0)
    adr = o2.number_input("ADR", min_value=0.0, value=142.5, step=1.0)
    revpar = o3.number_input("RevPAR", min_value=0.0, value=106.8, step=1.0)

    section_title("Lighthouse Data and OTA Pricing")
    l1, l2, l3, l4, l5, l6 = st.columns(6)
    demand_level = l1.selectbox("Demand Level", ["Low", "Moderate", "High", "Compression"], index=1)
    demand_score = l2.number_input("Demand Score", min_value=0.0, max_value=100.0, value=65.0, step=1.0)
    expedia_rate = l3.number_input("Expedia Rate", min_value=0.0, value=159.0, step=1.0)
    booking_rate = l4.number_input("Booking.com Rate", min_value=0.0, value=162.0, step=1.0)
    agoda_rate = l5.number_input("Agoda Rate", min_value=0.0, value=149.0, step=1.0)
    priceline_rate = l6.number_input("Priceline Rate", min_value=0.0, value=155.0, step=1.0)

    section_title("Comp Set Pricing")
    c1, c2 = st.columns(2)
    my_property_name = c1.text_input("My Property Name", value="My Hotel")
    my_property_rate = c2.number_input("My Property Rate", min_value=0.0, value=165.0, step=1.0)
    competitor_names = []
    competitor_rates = []
    for idx in range(1, 6):
        n_col, r_col = st.columns(2)
        competitor_names.append(n_col.text_input(f"Competitor {idx} Name", value=f"Competitor {idx}"))
        competitor_rates.append(r_col.number_input(f"Competitor {idx} Rate", min_value=0.0, value=150.0 + idx * 4, step=1.0))

    comp_metrics = calculate_comp_set(my_property_rate, competitor_rates)
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Comp Set Avg", money(comp_metrics.average_rate))
    k2.metric("Rate Gap", money(comp_metrics.rate_gap))
    k3.metric("Rate Rank", f"#{comp_metrics.rank}" if comp_metrics.rank else "N/A")
    k4.metric("Highest Competitor", money(comp_metrics.highest_competitor_rate))
    k5.metric("Lowest Competitor", money(comp_metrics.lowest_competitor_rate))

    section_title("14-Day Forecast")
    forecast_template = pd.DataFrame(
        {
            "stay_date": [checklist_date + timedelta(days=idx) for idx in range(14)],
            "forecast_rooms": [110 for _ in range(14)],
            "forecast_revenue": [16500.0 for _ in range(14)],
            "booked_rooms": [95 for _ in range(14)],
            "available_to_sell_rooms": [55 for _ in range(14)],
        }
    )
    forecast_df = st.data_editor(
        forecast_template,
        hide_index=True,
        num_rows="fixed",
        use_container_width=True,
        column_config={
            "stay_date": st.column_config.DateColumn("Stay Date"),
            "forecast_rooms": st.column_config.NumberColumn("Forecast Rooms", min_value=0),
            "forecast_revenue": st.column_config.NumberColumn("Forecast Revenue", min_value=0, format="$%.0f"),
            "booked_rooms": st.column_config.NumberColumn("Booked Rooms", min_value=0),
            "available_to_sell_rooms": st.column_config.NumberColumn("Available To Sell Rooms", min_value=0),
        },
    )

    section_title("Hourly Pickup Tracker")
    pickup_template = pd.DataFrame(
        {
            "pickup_time": ["09:00 AM", "10:00 AM", "11:00 AM", "12:00 PM"],
            "pickup_available_to_sell_rooms": [55, 53, 51, 49],
        }
    )
    pickup_input = st.data_editor(
        pickup_template,
        hide_index=True,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "pickup_time": st.column_config.TextColumn("Time"),
            "pickup_available_to_sell_rooms": st.column_config.NumberColumn("Available To Sell Rooms", min_value=0),
        },
    )
    submitted = st.form_submit_button("Export Today's Checklist", type="primary")

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

pickup_calculated = calculate_pickup(pickup_input)
section_title("Pickup Summary")
total_pickup = pickup_calculated["pickup_rooms"].sum() if not pickup_calculated.empty else 0
p1, p2 = st.columns([1, 3])
p1.metric("Total Pickup Today", number(total_pickup))
if not pickup_calculated.empty:
    p2.plotly_chart(pickup_chart(pickup_calculated), use_container_width=True)

if submitted:
    errors = validate_export_inputs(general, forecast_df, pickup_input)
    if errors:
        for error in errors:
            st.error(error)
    else:
        export_df = build_export_frame(general, forecast_df, pickup_input)
        filename = f"revenue_checklist_{datetime.strptime(general['date'], '%Y-%m-%d').date().isoformat()}.csv"
        st.success(f"{filename} is ready for download.")
        st.download_button(
            "Download CSV",
            data=export_df.to_csv(index=False).encode("utf-8"),
            file_name=filename,
            mime="text/csv",
        )
