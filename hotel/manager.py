"""Business logic: room and booking records, search/filter and status updates."""
from . import storage
from .models import STATUSES, TRANSITIONS, Booking, Room, ValidationError, parse_date


class HotelManager:
    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
        self.rooms = storage.load_rooms(data_dir)
        self.bookings = storage.load_bookings(data_dir)

    # ------------------------------------------------------------- rooms
    def get_room(self, room_no):
        room_no = str(room_no).strip()
        return next((r for r in self.rooms if r.room_no == room_no), None)

    def add_room(self, room_no, room_type, rate):
        room = Room(room_no, room_type, rate)
        if self.get_room(room.room_no):
            raise ValidationError(f"Room {room.room_no} already exists.")
        self.rooms.append(room)
        storage.save_rooms(self.data_dir, self.rooms)
        return room

    # ---------------------------------------------------------- bookings
    def get_booking(self, booking_id):
        return next((b for b in self.bookings if b.booking_id == booking_id), None)

    def _next_id(self):
        numbers = [int(b.booking_id[1:]) for b in self.bookings
                   if b.booking_id[1:].isdigit()]
        return f"B{max(numbers, default=0) + 1:04d}"

    def has_conflict(self, room_no, check_in, check_out, ignore_id=None):
        """True if an active booking already holds the room during these nights."""
        return any(
            b.room_no == room_no and b.status != "Cancelled" and b.booking_id != ignore_id
            and b.check_in < check_out and check_in < b.check_out
            for b in self.bookings)

    def add_booking(self, guest, room_no, check_in, check_out, source):
        room_no = str(room_no).strip()
        if not self.get_room(room_no):
            raise ValidationError(f"Room '{room_no}' does not exist.")
        booking = Booking(self._next_id(), guest, room_no, check_in, check_out, source)
        if self.has_conflict(room_no, booking.check_in, booking.check_out):
            raise ValidationError(f"Room {room_no} is already booked for some of those nights.")
        self.bookings.append(booking)
        storage.save_bookings(self.data_dir, self.bookings)
        return booking

    def update_status(self, booking_id, new_status):
        booking = self.get_booking(booking_id)
        if booking is None:
            raise ValidationError(f"Booking {booking_id} not found.")
        if new_status not in STATUSES:
            raise ValidationError(f"Status must be one of: {', '.join(STATUSES)}.")
        if new_status == booking.status:
            return booking
        if new_status not in TRANSITIONS[booking.status]:
            raise ValidationError(f"A {booking.status} booking cannot become {new_status}.")
        booking.status = new_status
        storage.save_bookings(self.data_dir, self.bookings)
        return booking

    def search(self, guest="", room_type="", status="", source="", start=None, end=None):
        """Filter bookings. Dates select stays that overlap the range [start, end]."""
        start = parse_date(start) if start else None
        end = parse_date(end) if end else None
        if start and end and end < start:
            raise ValidationError("The 'To' date cannot be before the 'From' date.")
        found = []
        for b in self.bookings:
            room = self.get_room(b.room_no)
            if guest and guest.lower() not in b.guest.lower():
                continue
            if room_type and (room is None or room.room_type != room_type):
                continue
            if status and b.status != status:
                continue
            if source and b.source != source:
                continue
            if start and b.check_out <= start:
                continue
            if end and b.check_in > end:
                continue
            found.append(b)
        return found
