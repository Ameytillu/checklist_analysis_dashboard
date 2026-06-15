from __future__ import annotations

import pandas as pd

from utils.calculations import CSV_COLUMNS, OPTIONAL_CSV_COLUMNS


def validate_export_inputs(general: dict, forecast_df: pd.DataFrame, pickup_df: pd.DataFrame) -> list[str]:
    errors = []
    if not general.get("date"):
        errors.append("Date is required.")
    if general.get("total_rooms_available", 0) <= 0:
        errors.append("Total rooms available must be greater than zero.")
    if general.get("total_rooms_sold", 0) < 0:
        errors.append("Total rooms sold cannot be negative.")
    if general.get("my_property_rate", 0) <= 0:
        errors.append("My property rate must be greater than zero.")
    if not forecast_df.empty and forecast_df[
        ["stay_date", "forecast_rooms", "booked_rooms", "available_to_sell_rooms"]
    ].isna().any().any():
        errors.append("The forecast table has missing required values.")
    if pickup_df.empty:
        errors.append("Add at least one pickup tracker row.")
    elif pickup_df["pickup_time"].astype(str).str.strip().eq("").any():
        errors.append("Pickup tracker rows need a time.")
    return errors


def validate_uploaded_checklist(df: pd.DataFrame, filename: str = "uploaded file") -> list[str]:
    errors = []
    if df.empty:
        errors.append(f"{filename} is empty.")
    required_columns = [column for column in CSV_COLUMNS if column not in OPTIONAL_CSV_COLUMNS]
    missing = [column for column in required_columns if column not in df.columns]
    if missing:
        preview = ", ".join(missing[:8])
        suffix = "..." if len(missing) > 8 else ""
        errors.append(f"{filename} is missing required columns: {preview}{suffix}")
    if "date" in df.columns and pd.to_datetime(df["date"], errors="coerce").dropna().empty:
        errors.append(f"{filename} does not contain a valid checklist date.")
    return errors


def detect_duplicate_uploads(files) -> list[str]:
    names = [file.name for file in files]
    return sorted({name for name in names if names.count(name) > 1})
