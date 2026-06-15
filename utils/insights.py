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


def pricing_decision_signals(summary: pd.DataFrame) -> list[dict]:
    if summary.empty:
        return []

    latest = summary.iloc[-1]
    my_rate = to_number(latest["my_property_rate"])
    comp_avg = to_number(latest["comp_set_average_rate"])
    rate_gap = to_number(latest["rate_difference_vs_comp_set_average"])
    occupancy = to_number(latest["occupancy_pct"])
    demand_score = to_number(latest.get("demand_score", 0))
    forecast_gap = to_number(latest.get("booked_total_rooms", 0)) - to_number(latest.get("forecast_total_rooms", 0))
    pickup = to_number(latest.get("total_pickup_today", 0))
    pickup_avg = summary["total_pickup_today"].apply(to_number).mean() if "total_pickup_today" in summary else 0
    revpar = to_number(latest["revpar"])
    revpar_avg = summary["revpar"].apply(to_number).mean() if "revpar" in summary else 0

    ota_rates = {
        "Expedia": to_number(latest["expedia_rate"]),
        "Booking.com": to_number(latest["booking_rate"]),
        "Agoda": to_number(latest["agoda_rate"]),
        "Priceline": to_number(latest["priceline_rate"]),
    }
    undercutters = [
        f"{name} ({money(my_rate - rate)} below BAR)"
        for name, rate in ota_rates.items()
        if rate and rate < my_rate
    ]

    signals = []
    if occupancy >= 85 and demand_score >= 70 and forecast_gap >= 0:
        cue = "Consider a controlled rate increase or tighter discount controls."
        status = "Strong demand"
    elif occupancy < 65 or forecast_gap < -10:
        cue = "Review value-adds, fenced offers, or tactical pricing to build pace."
        status = "Pace risk"
    else:
        cue = "Hold pricing unless comp set movement or pickup changes."
        status = "Stable"
    signals.append(
        {
            "Signal": "Demand and Pace",
            "Current Read": f"{pct(occupancy)} occupancy, forecast gap {number(forecast_gap)} rooms",
            "Decision Cue": cue,
            "Status": status,
        }
    )

    if rate_gap < -10:
        cue = f"Property is meaningfully below market; test moving closer to {money(comp_avg)} if demand supports it."
        status = "Below market"
    elif rate_gap > 10:
        cue = "Monitor conversion and pickup closely; premium pricing needs demand support."
        status = "Above market"
    else:
        cue = "Property is close to comp set average; pricing position is balanced."
        status = "In line"
    signals.append(
        {
            "Signal": "Comp Set Position",
            "Current Read": f"My rate {money(my_rate)} vs comp average {money(comp_avg)}",
            "Decision Cue": cue,
            "Status": status,
        }
    )

    if undercutters:
        cue = "Check channel parity and suppress/adjust undercutting OTA rates before changing BAR."
        status = "Parity issue"
        current_read = "; ".join(undercutters)
    else:
        cue = "OTA rates are not undercutting BAR on the latest uploaded day."
        status = "Aligned"
        current_read = "No OTA below BAR"
    signals.append(
        {
            "Signal": "OTA Parity",
            "Current Read": current_read,
            "Decision Cue": cue,
            "Status": status,
        }
    )

    if pickup_avg and pickup > pickup_avg:
        pickup_cue = "Pickup is above the uploaded-period average; rate resistance appears lower."
        pickup_status = "Positive"
    elif pickup_avg and pickup < pickup_avg:
        pickup_cue = "Pickup is below the uploaded-period average; avoid aggressive increases without more demand."
        pickup_status = "Soft"
    else:
        pickup_cue = "Pickup is aligned with the uploaded-period average."
        pickup_status = "Neutral"
    signals.append(
        {
            "Signal": "Pickup Momentum",
            "Current Read": f"Latest pickup {number(pickup)} rooms vs average {number(pickup_avg)}",
            "Decision Cue": pickup_cue,
            "Status": pickup_status,
        }
    )

    if revpar_avg and revpar > revpar_avg:
        revpar_cue = "RevPAR is outperforming the uploaded-period average; protect rate quality."
        revpar_status = "Improving"
    elif revpar_avg and revpar < revpar_avg:
        revpar_cue = "RevPAR trails the uploaded-period average; inspect occupancy, ADR, and mix before changing price."
        revpar_status = "Trailing"
    else:
        revpar_cue = "RevPAR is aligned with the uploaded-period average."
        revpar_status = "Neutral"
    signals.append(
        {
            "Signal": "RevPAR Quality",
            "Current Read": f"Latest RevPAR {money(revpar)} vs average {money(revpar_avg)}",
            "Decision Cue": revpar_cue,
            "Status": revpar_status,
        }
    )

    return signals
