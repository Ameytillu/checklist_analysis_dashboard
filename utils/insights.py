from __future__ import annotations

import pandas as pd

from utils.calculations import compare_values, money, number, pct, to_number


def comparison_summary(day_1: pd.Series, day_2: pd.Series) -> str:
    occ_change, _ = compare_values(day_2["occupancy_pct"], day_1["occupancy_pct"])
    transient_change, _ = compare_values(day_2["transient_revenue"], day_1["transient_revenue"])
    group_change, _ = compare_values(day_2["group_revenue"], day_1["group_revenue"])
    rate_gap = to_number(day_2["rate_difference_vs_comp_set_average"])
    agoda_gap = to_number(day_2["agoda_rate"]) - to_number(day_2["my_property_rate"])
    booked = to_number(day_2.get("booked_total_rooms", 0))
    forecast = to_number(day_2.get("forecast_total_rooms", 0))
    pace_gap = booked - forecast

    position = "above" if rate_gap > 0 else "below" if rate_gap < 0 else "at"
    agoda_text = (
        f"Agoda is pricing {money(abs(agoda_gap))} {'above' if agoda_gap > 0 else 'below'} BAR"
        if agoda_gap
        else "Agoda is aligned with BAR"
    )
    pace_text = "ahead of" if pace_gap > 0 else "behind" if pace_gap < 0 else "aligned with"

    return (
        f"Occupancy changed by {occ_change:.1f} points compared with the previous file. "
        f"Transient revenue changed by {money(transient_change)} while group revenue changed by {money(group_change)}. "
        f"The hotel is priced {money(abs(rate_gap))} {position} the comp set average. "
        f"{agoda_text}. Pickup and booking pace is {number(abs(pace_gap))} rooms {pace_text} forecast."
    )


def trend_alerts(summary: pd.DataFrame) -> list[str]:
    alerts = []
    if summary.empty:
        return alerts
    latest = summary.iloc[-1]
    my_rate = to_number(latest["my_property_rate"])
    for ota_column, label in [
        ("expedia_rate", "Expedia"),
        ("booking_rate", "Booking.com"),
        ("agoda_rate", "Agoda"),
        ("priceline_rate", "Priceline"),
    ]:
        ota_rate = to_number(latest[ota_column])
        if ota_rate and ota_rate < my_rate:
            alerts.append(f"OTA Undercutting Alert: {label} rate is {money(my_rate - ota_rate)} lower than BAR.")
    rate_gap = to_number(latest["rate_difference_vs_comp_set_average"])
    if rate_gap < 0:
        alerts.append(f"Market Pricing Alert: Property rate is {money(abs(rate_gap))} below comp set average.")
    elif rate_gap > 0:
        alerts.append(f"Market Pricing Alert: Property rate is {money(rate_gap)} above comp set average.")
    forecast_gap = to_number(latest.get("booked_total_rooms", 0)) - to_number(latest.get("forecast_total_rooms", 0))
    if forecast_gap < 0:
        alerts.append(f"Forecast Alert: Booked rooms are currently {number(abs(forecast_gap))} rooms behind forecast.")
    elif forecast_gap > 0:
        alerts.append(f"Forecast Alert: Booked rooms are currently {number(forecast_gap)} rooms ahead of forecast.")
    if len(summary) > 1:
        prior_avg = summary.iloc[:-1]["total_pickup_today"].tail(7).mean()
        latest_pickup = to_number(latest["total_pickup_today"])
        if prior_avg and latest_pickup < prior_avg:
            alerts.append("Pickup Alert: Pickup pace is slower than the previous 7-day average.")
    return alerts


def market_position_stats(summary: pd.DataFrame) -> dict:
    gaps = summary["rate_difference_vs_comp_set_average"].apply(to_number)
    ranks = summary["rate_rank"].astype(int)
    competitor_columns = [f"competitor_{idx}_rate" for idx in range(1, 6)]
    competitor_totals = {
        column: summary[column].apply(to_number).mean()
        for column in competitor_columns
        if column in summary
    }
    highest = max(competitor_totals, key=competitor_totals.get) if competitor_totals else ""
    lowest = min(competitor_totals, key=competitor_totals.get) if competitor_totals else ""
    return {
        "days_above_market": int((gaps > 0).sum()),
        "days_below_market": int((gaps < 0).sum()),
        "days_matching_market": int((gaps == 0).sum()),
        "average_rate_gap": gaps.mean() if not gaps.empty else 0,
        "highest_priced_competitor": highest.replace("_rate", "").replace("_", " ").title(),
        "lowest_priced_competitor": lowest.replace("_rate", "").replace("_", " ").title(),
        "rank_distribution": ranks.value_counts().sort_index(),
    }


def forecast_performance(summary: pd.DataFrame) -> dict:
    forecast = summary["forecast_total_rooms"].apply(to_number)
    booked = summary["booked_total_rooms"].apply(to_number)
    achievement = (booked.sum() / forecast.sum() * 100) if forecast.sum() else 0
    gap = booked - forecast
    return {
        "forecast_achievement_pct": achievement,
        "days_ahead": int((gap > 0).sum()),
        "days_behind": int((gap < 0).sum()),
    }

