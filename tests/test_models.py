import unittest
from datetime import date

from hotel.models import Booking, Room, ValidationError, parse_date


class ParseDateTests(unittest.TestCase):
    def test_valid_date(self):
        self.assertEqual(parse_date("2026-03-05"), date(2026, 3, 5))

    def test_invalid_format_rejected(self):
        with self.assertRaises(ValidationError):
            parse_date("05/03/2026")

    def test_impossible_date_rejected(self):
        with self.assertRaises(ValidationError):
            parse_date("2026-02-30")


class RoomTests(unittest.TestCase):
    def test_valid_room(self):
        room = Room(" 101 ", "Single", "60")
        self.assertEqual((room.room_no, room.rate), ("101", 60.0))

    def test_bad_values_rejected(self):
        for args in [("", "Single", 60), ("101", "Penthouse", 60), ("101", "Single", "abc"),
                     ("101", "Single", 0), ("101", "Single", -5)]:
            with self.subTest(args=args), self.assertRaises(ValidationError):
                Room(*args)


class BookingTests(unittest.TestCase):
    def make(self, **overrides):
        data = dict(booking_id="B0001", guest="Asha", room_no="101",
                    check_in="2026-03-01", check_out="2026-03-04", source="Direct")
        data.update(overrides)
        return Booking(**data)

    def test_nights(self):
        self.assertEqual(self.make().nights, 3)

    def test_checkout_must_be_after_checkin(self):
        for out in ("2026-03-01", "2026-02-28"):
            with self.subTest(out=out), self.assertRaises(ValidationError):
                self.make(check_out=out)

    def test_guest_required(self):
        with self.assertRaises(ValidationError):
            self.make(guest="   ")

    def test_unknown_source_and_status_rejected(self):
        with self.assertRaises(ValidationError):
            self.make(source="Carrier pigeon")
        with self.assertRaises(ValidationError):
            self.make(status="Lost")


if __name__ == "__main__":
    unittest.main()
