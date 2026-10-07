"""Data structures, constants and validation rules for the hotel system."""
from dataclasses import dataclass
from datetime import date, datetime

ROOM_TYPES = ("Single", "Double", "Suite")
SOURCES = ("Direct", "Online Agency", "Phone", "Walk-in", "Corporate")
STATUSES = ("Confirmed", "Checked-in", "Checked-out", "Cancelled")
# Only these statuses occupy a room; a cancelled booking frees it.
ACTIVE_STATUSES = ("Confirmed", "Checked-in", "Checked-out")
# Allowed status changes: current status -> statuses it may move to.
TRANSITIONS = {
    "Confirmed": {"Checked-in", "Cancelled"},
    "Checked-in": {"Checked-out"},
    "Checked-out": set(),
    "Cancelled": set(),
}
DATE_FORMAT = "%Y-%m-%d"


class ValidationError(ValueError):
    """Raised when input breaks a business rule (bad date, unknown room, ...)."""


def parse_date(value):
    """Return a date from a date/datetime object or a 'YYYY-MM-DD' string."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value).strip(), DATE_FORMAT).date()
    except ValueError:
        raise ValidationError(f"'{value}' is not a valid date (use YYYY-MM-DD).") from None


def _choice(value, allowed, label):
    if value not in allowed:
        raise ValidationError(f"{label} must be one of: {', '.join(allowed)}.")
    return value


@dataclass
class Room:
    room_no: str
    room_type: str
    rate: float  # nightly rate

    def __post_init__(self):
        self.room_no = str(self.room_no).strip()
        if not self.room_no:
            raise ValidationError("Room number is required.")
        _choice(self.room_type, ROOM_TYPES, "Room type")
        try:
            self.rate = float(self.rate)
        except (TypeError, ValueError):
            raise ValidationError("Nightly rate must be a number.") from None
        if self.rate <= 0:
            raise ValidationError("Nightly rate must be greater than zero.")


@dataclass
class Booking:
    booking_id: str
    guest: str
    room_no: str
    check_in: date
    check_out: date
    source: str
    status: str = "Confirmed"

    def __post_init__(self):
        self.guest = str(self.guest or "").strip()
        if not self.guest:
            raise ValidationError("Guest name is required.")
        self.room_no = str(self.room_no or "").strip()
        if not self.room_no:
            raise ValidationError("Room number is required.")
        self.check_in = parse_date(self.check_in)
        self.check_out = parse_date(self.check_out)
        if self.check_out <= self.check_in:
            raise ValidationError("Check-out must be after check-in.")
        _choice(self.source, SOURCES, "Booking source")
        _choice(self.status, STATUSES, "Status")

    @property
    def nights(self):
        return (self.check_out - self.check_in).days
