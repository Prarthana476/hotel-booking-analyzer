import tempfile
import unittest

from hotel import analysis
from hotel.manager import HotelManager
from hotel.models import ValidationError


class AnalysisTests(unittest.TestCase):
    """Hand-checkable scenario: 2 rooms (Single 100/night, Double 200/night), January 2026 = 31 days."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        mgr = HotelManager(self._tmp.name)
        mgr.add_room("101", "Single", 100)
        mgr.add_room("201", "Double", 200)
        mgr.add_booking("A", "101", "2026-01-01", "2026-01-05", "Direct")         # 4 nights, all in Jan
        mgr.add_booking("B", "201", "2026-01-30", "2026-02-03", "Online Agency")  # 2 nights in Jan, 2 in Feb
        c = mgr.add_booking("C", "101", "2026-01-10", "2026-01-12", "Direct")
        mgr.update_status(c.booking_id, "Cancelled")                             # must not count
        self.rooms, self.bookings = analysis.to_frames(mgr.rooms, mgr.bookings)

    def test_january_metrics(self):
        m = analysis.period_metrics(self.bookings, self.rooms, "2026-01-01", "2026-01-31")
        self.assertEqual(m["Available room-nights"], 62)
        self.assertEqual(m["Occupied room-nights"], 6)
        self.assertEqual(m["Occupancy rate (%)"], 9.68)
        self.assertEqual(m["Revenue"], 800.0)
        self.assertEqual(m["ADR"], 133.33)
        self.assertEqual(m["RevPAR"], 12.9)
        self.assertEqual(m["Bookings"], 3)
        self.assertEqual(m["Cancellation rate (%)"], 33.33)
        self.assertEqual(m["Average stay (nights)"], 4.0)

    def test_room_type_filter(self):
        m = analysis.period_metrics(self.bookings, self.rooms, "2026-01-01", "2026-01-31", "Double")
        self.assertEqual((m["Available room-nights"], m["Occupied room-nights"], m["Revenue"]), (31, 2, 400.0))

    def test_stay_crossing_period_boundary_is_split(self):
        feb = analysis.period_metrics(self.bookings, self.rooms, "2026-02-01", "2026-02-28")
        self.assertEqual(feb["Occupied room-nights"], 2)  # nights of 1 and 2 Feb; check-out day not counted

    def test_by_source(self):
        src = analysis.by_source(self.bookings, "2026-01-01", "2026-01-31").set_index("source")
        self.assertEqual(src.loc["Direct", "revenue"], 400.0)
        self.assertEqual(src.loc["Online Agency", "nights"], 2)
        self.assertEqual(src["share_pct"].sum(), 100.0)

    def test_room_usage(self):
        usage = analysis.room_usage(self.bookings, self.rooms, "2026-01-01", "2026-01-31").set_index("room_no")
        self.assertEqual(usage.loc["101", "occupied_nights"], 4)
        self.assertEqual(usage.loc["101", "occupancy_pct"], 12.9)
        self.assertEqual(usage.loc["201", "occupancy_pct"], 6.5)

    def test_monthly_summary_has_twelve_months(self):
        monthly = analysis.monthly_summary(self.bookings, self.rooms, 2026)
        self.assertEqual(len(monthly), 12)
        self.assertEqual(monthly.loc[0, "Revenue"], 800.0)

    def test_compare_periods(self):
        cmp = analysis.compare_periods(self.bookings, self.rooms, "2026-01-01", "2026-01-31",
                                       "2026-02-01", "2026-02-28").set_index("Measure")
        self.assertEqual(cmp.loc["Occupancy rate (%)", "Period B"], 3.57)
        self.assertLess(cmp.loc["Occupancy rate (%)", "Change (%)"], 0)

    def test_room_type_comparison_has_a_row_per_type(self):
        cmp = analysis.room_type_comparison(self.bookings, self.rooms, "2026-01-01", "2026-01-31",
                                            "2026-02-01", "2026-02-28")
        self.assertEqual(list(cmp["room_type"]), ["Single", "Double"])

    def test_end_before_start_rejected(self):
        with self.assertRaises(ValidationError):
            analysis.period_metrics(self.bookings, self.rooms, "2026-02-01", "2026-01-01")

    def test_empty_hotel_does_not_crash(self):
        with tempfile.TemporaryDirectory() as empty:
            rooms, bookings = analysis.to_frames(HotelManager(empty).rooms, HotelManager(empty).bookings)
        m = analysis.period_metrics(bookings, rooms, "2026-01-01", "2026-01-31")
        self.assertEqual((m["Occupancy rate (%)"], m["Revenue"]), (0.0, 0.0))
        self.assertTrue(analysis.by_source(bookings, "2026-01-01", "2026-01-31").empty)
        self.assertIsNone(analysis.data_range(bookings))


if __name__ == "__main__":
    unittest.main()
