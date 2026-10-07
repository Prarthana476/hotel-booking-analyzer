"""File handling: persistent CSV storage plus a demo-data generator."""
import csv
import os
import random
import tempfile
from dataclasses import asdict
from datetime import date, timedelta

from .models import Booking, Room, ValidationError

ROOM_FIELDS = ["room_no", "room_type", "rate"]
BOOKING_FIELDS = ["booking_id", "guest", "room_no", "check_in", "check_out", "source", "status"]


class StorageError(Exception):
    """Raised when a data file cannot be read, written or understood."""


def _read_rows(path, fields):
    if not os.path.exists(path):
        return []
    try:
        with open(path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames != fields:
                raise StorageError(f"{os.path.basename(path)} has unexpected columns (expected {fields}).")
            return list(reader)
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        raise StorageError(f"Could not read {path}: {exc}") from exc


def _write_rows(path, fields, rows):
    folder = os.path.dirname(path) or "."
    try:
        os.makedirs(folder, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=folder, suffix=".tmp")
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        os.replace(tmp, path)  # atomic: a crash never leaves a half-written file
    except OSError as exc:
        raise StorageError(f"Could not write {path}: {exc}") from exc


def _load(cls, path, fields):
    items = []
    for line_no, row in enumerate(_read_rows(path, fields), start=2):
        try:
            items.append(cls(**row))
        except (ValidationError, TypeError) as exc:
            raise StorageError(f"{os.path.basename(path)} line {line_no}: {exc}") from exc
    return items


def load_rooms(data_dir):
    return _load(Room, os.path.join(data_dir, "rooms.csv"), ROOM_FIELDS)


def load_bookings(data_dir):
    return _load(Booking, os.path.join(data_dir, "bookings.csv"), BOOKING_FIELDS)


def save_rooms(data_dir, rooms):
    _write_rows(os.path.join(data_dir, "rooms.csv"), ROOM_FIELDS, [asdict(r) for r in rooms])


def save_bookings(data_dir, bookings):
    _write_rows(os.path.join(data_dir, "bookings.csv"), BOOKING_FIELDS, [asdict(b) for b in bookings])


# ---------------------------------------------------------------- demo data
_LAYOUT = [("101", "Single"), ("102", "Single"), ("103", "Single"), ("104", "Single"),
           ("201", "Double"), ("202", "Double"), ("203", "Double"), ("204", "Double"),
           ("301", "Suite"), ("302", "Suite")]
_RATES = {"Single": 60.0, "Double": 90.0, "Suite": 160.0}
# Chance that a free day gets a booking: high in summer and December, low in winter.
_SEASON = {1: .55, 2: .50, 3: .55, 4: .65, 5: .70, 6: .85,
           7: .95, 8: .95, 9: .75, 10: .65, 11: .50, 12: .85}
_SOURCE_WEIGHTS = {"Direct": 25, "Online Agency": 40, "Phone": 10, "Walk-in": 10, "Corporate": 15}
_FIRST = ["Asha", "Ravi", "Meera", "Karan", "Priya", "Neil", "Sara", "Omar", "Li", "Ana", "Tom", "Zoya"]
_LAST = ["Patel", "Shah", "Mehta", "Khan", "Rao", "Smith", "Silva", "Chen", "Nair", "Joshi"]


def create_sample_data(data_dir, seed=42, reference=date(2026, 9, 1), last_day=date(2026, 10, 31)):
    """Write realistic demo data (10 rooms, ~20 months of bookings) to data_dir."""
    rng = random.Random(seed)
    rooms = [Room(no, kind, _RATES[kind]) for no, kind in _LAYOUT]
    raw = []
    for room in rooms:
        cursor = date(2025, 1, 1)
        while cursor < last_day:
            if rng.random() < _SEASON[cursor.month]:
                check_out = cursor + timedelta(days=rng.randint(1, 5))
                if check_out <= reference:
                    status = "Cancelled" if rng.random() < .10 else "Checked-out"
                elif cursor <= reference:
                    status = "Checked-in"
                else:
                    status = "Cancelled" if rng.random() < .05 else "Confirmed"
                source = rng.choices(list(_SOURCE_WEIGHTS), weights=list(_SOURCE_WEIGHTS.values()))[0]
                guest = f"{rng.choice(_FIRST)} {rng.choice(_LAST)}"
                raw.append((cursor, check_out, room.room_no, guest, source, status))
                cursor = check_out + timedelta(days=rng.randint(0, 2))
            else:
                cursor += timedelta(days=rng.randint(1, 3))
    raw.sort(key=lambda r: (r[0], r[2]))
    bookings = [Booking(f"B{n:04d}", guest, room_no, ci, co, source, status)
                for n, (ci, co, room_no, guest, source, status) in enumerate(raw, start=1)]
    save_rooms(data_dir, rooms)
    save_bookings(data_dir, bookings)
    return rooms, bookings
