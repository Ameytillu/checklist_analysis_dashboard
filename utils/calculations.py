from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd


GENERAL_FIELDS = [
    "date",
    "occupancy_pct",
    "expected_arrivals",
    "expected_departures",
    "out_of_order_rooms",
    "total_rooms_available",
    "total_rooms_sold",
    "transient_rooms",
    "transient_revenue",
    "transient_adr",
    "group_rooms",
    "group_revenue",
    "group_adr",
    "total_revenue",
    "adr",
    "revpar",
    "demand_level",
    "demand_score",
    "expedia_rate",
    "booking_rate",
    "agoda_rate",
    "priceline_rate",
    "my_property_name",
    "my_property_rate",
    "competitor_1_name",
    "competitor_1_rate",
    "competitor_2_name",
    "competitor_2_rate",
    "competitor_3_name",
    "competitor_3_rate",
    "competitor_4_name",
    "competitor_4_rate",
    "competitor_5_name",
    "competitor_5_rate",
    "comp_set_average_rate",
    "rate_difference_vs_comp_set_average",
    "rate_rank",
    "highest_competitor_rate",
    "lowest_competitor_rate",
]

FORECAST_FIELDS = [
    "stay_date",
    "forecast_rooms",
    "forecast_revenue",
    "booked_rooms",
    "available_to_sell_rooms",
]

PICKUP_FIELDS = ["pickup_time", "pickup_available_to_sell_rooms", "pickup_rooms"]

COMPETITOR_RATE_FIELDS = [f"competitor_{idx}_rate" for idx in range(1, 6)]
OTA_RATE_FIELDS = ["expedia_rate", "booking_rate", "agoda_rate", "priceline_rate"]
PERFORMANCE_FIELDS = [
    "occupancy_pct",
    "expected_arrivals",
    "expected_departures",
    "out_of_order_rooms",
    "transient_rooms",
    "transient_revenue",
    "transient_adr",
    "group_rooms",
    "group_revenue",
    "group_adr",
    "total_revenue",
    "adr",
    "revpar",
]
CSV_COLUMNS = GENERAL_FIELDS + FORECAST_FIELDS + PICKUP_FIELDS


@dataclass(frozen=True)
class CompSetMetrics:
    average_rate: float
    rate_gap: float
    rank: int
    highest_competitor_rate: float
    lowest_competitor_rate: float


def money(value: float | int | None) -> str:
    if pd.isna(value):
        return "$0"
    return f"${float(value):,.0f}"


def number(value: float | int | None) -> str:
    if pd.isna(value):
        return "0"
    return f"{float(value):,.0f}"


def pct(value: float | int | None) -> str:
    if pd.isna(value):
        return "0.0%"
    return f"{float(value):.1f}%"


def to_number(value, default: float = 0.0) -> float:
    converted = pd.to_numeric(value, errors="coerce")
    if pd.isna(converted):
        return default
    return float(converted)


def calculate_comp_set(my_rate: float, competitor_rates: Iterable[float]) -> CompSetMetrics:
    rates = [to_number(rate) for rate in competitor_rates if to_number(rate) > 0]
    my_rate = to_number(my_rate)
    average = sum(rates) / len(rates) if rates else 0.0
    all_rates = rates + ([my_rate] if my_rate > 0 else [])
    ranked = sorted(all_rates, reverse=True)
    rank = ranked.index(my_rate) + 1 if my_rate > 0 and my_rate in ranked else 0
    return CompSetMetrics(
        average_rate=average,
        rate_gap=my_rate - average if average else 0.0,
        rank=rank,
        highest_competitor_rate=max(rates) if rates else 0.0,
        lowest_competitor_rate=min(rates) if rates else 0.0,
    )


def calculate_pickup(pickup_df: pd.DataFrame) -> pd.DataFrame:
    df = pickup_df.copy()
    if df.empty:
        return pd.DataFrame(columns=PICKUP_FIELDS)
    df["pickup_available_to_sell_rooms"] = pd.to_numeric(
        df["pickup_available_to_sell_rooms"], errors="coerce"
    ).fillna(0)
    df["pickup_rooms"] = (
        df["pickup_available_to_sell_rooms"].shift(1) - df["pickup_available_to_sell_rooms"]
    ).fillna(0)
    return df


def build_export_frame(general: dict, forecast_df: pd.DataFrame, pickup_df: pd.DataFrame) -> pd.DataFrame:
    max_rows = max(len(forecast_df), len(pickup_df), 1)
    rows = []
    pickup_df = calculate_pickup(pickup_df)
    for idx in range(max_rows):
        row = dict(general)
        if idx < len(forecast_df):
            row.update(forecast_df.iloc[idx].to_dict())
        else:
            row.update({field: "" for field in FORECAST_FIELDS})
        if idx < len(pickup_df):
            row.update(pickup_df.iloc[idx].to_dict())
        else:
            row.update({field: "" for field in PICKUP_FIELDS})
        rows.append(row)
    return pd.DataFrame(rows, columns=CSV_COLUMNS)


def load_checklist(file) -> pd.DataFrame:
    return pd.read_csv(file)


def normalize_checklist(df: pd.DataFrame) -> pd.DataFrame:
    clean = df.copy()
    for column in CSV_COLUMNS:
        if column not in clean.columns:
            clean[column] = pd.NA
    date_columns = ["date", "stay_date"]
    for column in date_columns:
        clean[column] = pd.to_datetime(clean[column], errors="coerce")
    numeric_columns = [
        column
        for column in CSV_COLUMNS
        if column not in {"date", "stay_date", "demand_level", "my_property_name"}
        and not column.endswith("_name")
        and column != "pickup_time"
    ]
    for column in numeric_columns:
        clean[column] = pd.to_numeric(clean[column], errors="coerce").fillna(0)
    return clean


def daily_record(df: pd.DataFrame) -> pd.Series:
    clean = normalize_checklist(df)
    return clean.iloc[0]


def forecast_rows(df: pd.DataFrame) -> pd.DataFrame:
    clean = normalize_checklist(df)
    return clean.dropna(subset=["stay_date"])[FORECAST_FIELDS].copy()


def pickup_rows(df: pd.DataFrame) -> pd.DataFrame:
    clean = normalize_checklist(df)
    pickup = clean[clean["pickup_time"].notna() & (clean["pickup_time"].astype(str) != "")]
    return pickup[PICKUP_FIELDS].copy()


def summarize_uploaded_files(files: list[tuple[str, pd.DataFrame]]) -> pd.DataFrame:
    rows = []
    for filename, df in files:
        record = daily_record(df).to_dict()
        record["source_file"] = filename
        forecast = forecast_rows(df)
        pickup = pickup_rows(df)
        record["forecast_total_rooms"] = forecast["forecast_rooms"].sum()
        record["booked_total_rooms"] = forecast["booked_rooms"].sum()
        record["available_to_sell_total"] = forecast["available_to_sell_rooms"].sum()
        record["total_pickup_today"] = pickup["pickup_rooms"].sum() if not pickup.empty else 0
        rows.append(record)
    summary = pd.DataFrame(rows)
    if "date" in summary:
        summary = summary.sort_values("date")
    return summary


def compare_values(new_value: float, old_value: float) -> tuple[float, float]:
    change = to_number(new_value) - to_number(old_value)
    pct_change = (change / old_value * 100) if old_value else 0.0
    return change, pct_change

