import os
import tempfile
import unittest
from collections import defaultdict

from hotel.manager import HotelManager
from hotel.storage import StorageError, create_sample_data


class StorageTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = self._tmp.name

    def write(self, name, text):
        with open(os.path.join(self.dir, name), "w", encoding="utf-8") as fh:
            fh.write(text)

    def test_missing_files_mean_empty_hotel(self):
        mgr = HotelManager(self.dir)
        self.assertEqual((mgr.rooms, mgr.bookings), ([], []))

    def test_wrong_columns_raise_storage_error(self):
        self.write("rooms.csv", "number,kind\n101,Single\n")
        with self.assertRaises(StorageError):
            HotelManager(self.dir)

    def test_bad_row_reports_line_number(self):
        self.write("rooms.csv", "room_no,room_type,rate\n101,Single,60\n102,Single,oops\n")
        with self.assertRaises(StorageError) as ctx:
            HotelManager(self.dir)
        self.assertIn("line 3", str(ctx.exception))

    def test_sample_data_loads_and_has_no_double_bookings(self):
        create_sample_data(self.dir)
        mgr = HotelManager(self.dir)
        self.assertEqual(len(mgr.rooms), 10)
        self.assertGreater(len(mgr.bookings), 500)
        by_room = defaultdict(list)
        for b in mgr.bookings:
            by_room[b.room_no].append(b)
        for stays in by_room.values():
            stays.sort(key=lambda b: b.check_in)
            for earlier, later in zip(stays, stays[1:]):
                self.assertLessEqual(earlier.check_out, later.check_in)


if __name__ == "__main__":
    unittest.main()
