import tempfile
import unittest

from hotel.manager import HotelManager
from hotel.models import ValidationError


class ManagerTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = self._tmp.name
        self.mgr = HotelManager(self.dir)
        self.mgr.add_room("101", "Single", 100)
        self.mgr.add_room("201", "Double", 200)

    def test_duplicate_room_rejected(self):
        with self.assertRaises(ValidationError):
            self.mgr.add_room("101", "Single", 100)

    def test_unknown_room_rejected(self):
        with self.assertRaises(ValidationError):
            self.mgr.add_booking("Asha", "999", "2026-01-01", "2026-01-03", "Direct")

    def test_data_persists_between_sessions(self):
        self.mgr.add_booking("Asha", "101", "2026-01-01", "2026-01-03", "Direct")
        reloaded = HotelManager(self.dir)
        self.assertEqual(len(reloaded.rooms), 2)
        self.assertEqual(reloaded.bookings[0].guest, "Asha")
        self.assertEqual(reloaded.bookings[0].nights, 2)

    def test_overlapping_booking_rejected_but_back_to_back_allowed(self):
        self.mgr.add_booking("Asha", "101", "2026-01-01", "2026-01-05", "Direct")
        with self.assertRaises(ValidationError):
            self.mgr.add_booking("Ravi", "101", "2026-01-04", "2026-01-06", "Phone")
        self.mgr.add_booking("Ravi", "101", "2026-01-05", "2026-01-06", "Phone")  # same-day turnover

    def test_cancelled_booking_frees_the_room(self):
        booking = self.mgr.add_booking("Asha", "101", "2026-01-01", "2026-01-05", "Direct")
        self.mgr.update_status(booking.booking_id, "Cancelled")
        self.mgr.add_booking("Ravi", "101", "2026-01-02", "2026-01-04", "Phone")

    def test_status_transitions(self):
        b = self.mgr.add_booking("Asha", "101", "2026-01-01", "2026-01-03", "Direct")
        self.mgr.update_status(b.booking_id, "Checked-in")
        self.mgr.update_status(b.booking_id, "Checked-out")
        with self.assertRaises(ValidationError):
            self.mgr.update_status(b.booking_id, "Confirmed")
        with self.assertRaises(ValidationError):
            self.mgr.update_status("B9999", "Cancelled")

    def test_search_filters(self):
        self.mgr.add_booking("Asha Patel", "101", "2026-01-01", "2026-01-05", "Direct")
        self.mgr.add_booking("Ravi Shah", "201", "2026-02-01", "2026-02-03", "Phone")
        self.assertEqual(len(self.mgr.search(guest="patel")), 1)
        self.assertEqual(len(self.mgr.search(room_type="Double")), 1)
        self.assertEqual(len(self.mgr.search(source="Phone", status="Confirmed")), 1)
        self.assertEqual(len(self.mgr.search(start="2026-01-04", end="2026-01-10")), 1)  # overlaps Asha only
        self.assertEqual(len(self.mgr.search(start="2026-03-01")), 0)
        with self.assertRaises(ValidationError):
            self.mgr.search(start="2026-02-01", end="2026-01-01")


if __name__ == "__main__":
    unittest.main()
