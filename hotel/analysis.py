"""Booking analysis with NumPy and pandas.

Assumptions (shown in the GUI and README):
1. A stay occupies the nights from check-in up to, but not including, the check-out date.
2. Only Confirmed, Checked-in and Checked-out bookings occupy a room; Cancelled ones do not.
3. Available room-nights = rooms x days in the period (both end dates included).
4. Revenue = occupied nights x the room's nightly rate (taxes and extras ignored).
5. Occupancy % = occupied / available room-nights x 100.
6. ADR = revenue / occupied room-nights;  RevPAR = revenue / available room-nights.
7. Booking count, average stay and cancellation rate assign a booking to the
   period containing its check-in date.
"""
import calendar
from dataclasses import asdict
from datetime import date

import numpy as np
import pandas as pd

from .models import ACTIVE_STATUSES, ROOM_TYPES, ValidationError, parse_date

ASSUMPTIONS = (
    "A stay occupies the nights from check-in up to (not including) check-out.",
    "Cancelled bookings do not occupy rooms.",
    "Available room-nights = rooms x days in the period.",
    "Revenue = occupied nights x nightly room rate.",
    "Occupancy % = occupied / available room-nights.",
    "ADR = revenue / occupied nights; RevPAR = revenue / available nights.",
    "Booking count, average stay and cancellation rate use the check-in date.",
)

ROOM_COLS = ["room_no", "room_type", "rate"]
BOOKING_COLS = ["booking_id", "guest", "room_no", "check_in", "check_out", "source", "status"]


def to_frames(rooms, bookings):
    """Convert Room/Booking objects into (rooms_df, bookings_df) DataFrames."""
    rooms_df = pd.DataFrame([asdict(r) for r in rooms], columns=ROOM_COLS)
    rooms_df["rate"] = rooms_df["rate"].astype(float)
    df = pd.DataFrame([asdict(b) for b in bookings], columns=BOOKING_COLS)
    df = df.merge(rooms_df[["room_no", "room_type", "rate"]], on="room_no", how="left")
    df["check_in"] = pd.to_datetime(df["check_in"])
    df["check_out"] = pd.to_datetime(df["check_out"])
    df["nights"] = (df["check_out"] - df["check_in"]).dt.days
    df["rate"] = df["rate"].astype(float).fillna(0.0)
    return rooms_df, df


def _period(start, end):
    s, e = parse_date(start), parse_date(end)
    if e < s:
        raise ValidationError("The end date cannot be before the start date.")
    return s, e


def _ratio(numerator, denominator):
    return round(numerator / denominator, 2) if denominator else 0.0


def nights_in_period(df, start, end):
    """NumPy: nights of each booking that fall inside [start, end] (inclusive)."""
    if df.empty:
        return np.zeros(0, dtype=int)
    first = np.datetime64(start, "D")
    stop = np.datetime64(end, "D") + 1
    check_in = df["check_in"].values.astype("datetime64[D]")
    check_out = df["check_out"].values.astype("datetime64[D]")
    days = (np.minimum(check_out, stop) - np.maximum(check_in, first)).astype(int)
    return np.clip(days, 0, None)


def period_metrics(bookings, rooms, start, end, room_type=None):
    """Headline occupancy and revenue measures for a period (optionally one room type)."""
    start, end = _period(start, end)
    room_count = len(rooms) if not room_type else int((rooms["room_type"] == room_type).sum())
    available = room_count * ((end - start).days + 1)
    scope = bookings if not room_type else bookings[bookings["room_type"] == room_type]
    active = scope[scope["status"].isin(ACTIVE_STATUSES)]
    nights = nights_in_period(active, start, end)
    occupied = int(nights.sum())
    revenue = float((nights * active["rate"].to_numpy()).sum())
    placed = scope[(scope["check_in"] >= pd.Timestamp(start)) & (scope["check_in"] <= pd.Timestamp(end))]
    placed_active = placed[placed["status"].isin(ACTIVE_STATUSES)]
    cancelled = len(placed) - len(placed_active)
    return {
        "Available room-nights": available,
        "Occupied room-nights": occupied,
        "Occupancy rate (%)": _ratio(100 * occupied, available),
        "Revenue": round(revenue, 2),
        "ADR": _ratio(revenue, occupied),
        "RevPAR": _ratio(revenue, available),
        "Bookings": len(placed),
        "Cancellation rate (%)": _ratio(100 * cancelled, len(placed)),
        "Average stay (nights)": round(float(placed_active["nights"].mean()), 2) if len(placed_active) else 0.0,
    }


def _period_table(bookings, start, end):
    """Active bookings with the nights/revenue that fall inside the period."""
    active = bookings[bookings["status"].isin(ACTIVE_STATUSES)].copy()
    active["p_nights"] = nights_in_period(active, start, end)
    active["p_revenue"] = active["p_nights"] * active["rate"]
    return active[active["p_nights"] > 0]


def by_source(bookings, start, end):
    """Bookings, nights, revenue and share per booking source."""
    start, end = _period(start, end)
    table = _period_table(bookings, start, end)
    out = (table.groupby("source")
           .agg(bookings=("booking_id", "count"), nights=("p_nights", "sum"), revenue=("p_revenue", "sum"))
           .reset_index().sort_values("bookings", ascending=False))
    total = out["bookings"].sum()
    out["share_pct"] = (100 * out["bookings"] / total).round(1) if total else 0.0
    return out.reset_index(drop=True)


def room_usage(bookings, rooms, start, end):
    """Occupied nights and occupancy % for every room."""
    start, end = _period(start, end)
    used = _period_table(bookings, start, end).groupby("room_no")["p_nights"].sum()
    out = rooms[["room_no", "room_type"]].copy()
    out["occupied_nights"] = out["room_no"].map(used).fillna(0).astype(int)
    out["occupancy_pct"] = (100 * out["occupied_nights"] / ((end - start).days + 1)).round(1)
    return out.sort_values("room_no").reset_index(drop=True)


def by_room_type(bookings, rooms, start, end):
    """One row of metrics per room type that exists in the hotel."""
    rows = [{"room_type": kind, **period_metrics(bookings, rooms, start, end, kind)}
            for kind in ROOM_TYPES if (rooms["room_type"] == kind).any()]
    return pd.DataFrame(rows)


def monthly_summary(bookings, rooms, year):
    """Occupancy and revenue for each month of a year (seasonal demand)."""
    rows = []
    for month in range(1, 13):
        last = calendar.monthrange(year, month)[1]
        m = period_metrics(bookings, rooms, date(year, month, 1), date(year, month, last))
        rows.append({"month": calendar.month_abbr[month],
                     "Occupancy rate (%)": m["Occupancy rate (%)"], "Revenue": m["Revenue"]})
    return pd.DataFrame(rows)


def compare_periods(bookings, rooms, a_start, a_end, b_start, b_end, room_type=None):
    """Side-by-side metrics for two periods with the percentage change (A -> B)."""
    a = period_metrics(bookings, rooms, a_start, a_end, room_type)
    b = period_metrics(bookings, rooms, b_start, b_end, room_type)
    rows = [{"Measure": key, "Period A": a[key], "Period B": b[key],
             "Change (%)": round(100 * (b[key] - a[key]) / a[key], 1) if a[key] else np.nan}
            for key in a]
    return pd.DataFrame(rows)


def room_type_comparison(bookings, rooms, a_start, a_end, b_start, b_end):
    """Occupancy and revenue per room type for two periods."""
    rows = []
    for kind in ROOM_TYPES:
        if not (rooms["room_type"] == kind).any():
            continue
        a = period_metrics(bookings, rooms, a_start, a_end, kind)
        b = period_metrics(bookings, rooms, b_start, b_end, kind)
        rows.append({"room_type": kind,
                     "occ_a": a["Occupancy rate (%)"], "occ_b": b["Occupancy rate (%)"],
                     "revenue_a": a["Revenue"], "revenue_b": b["Revenue"]})
    return pd.DataFrame(rows)


def data_range(bookings):
    """(first night, last night) covered by the data, or None if there are no bookings."""
    if bookings.empty:
        return None
    return (bookings["check_in"].min().date(),
            (bookings["check_out"].max() - pd.Timedelta(days=1)).date())
