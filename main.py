"""Entry point: python main.py [--data-dir data] [--sample-data]"""
import argparse
import sys

from hotel.manager import HotelManager
from hotel.storage import StorageError, create_sample_data


def main():
    parser = argparse.ArgumentParser(description="Hotel booking manager and analyser")
    parser.add_argument("--data-dir", default="data", help="folder holding rooms.csv and bookings.csv")
    parser.add_argument("--sample-data", action="store_true",
                        help="generate demo data first (overwrites the files in --data-dir)")
    args = parser.parse_args()
    try:
        if args.sample_data:
            create_sample_data(args.data_dir)
        manager = HotelManager(args.data_dir)
    except StorageError as exc:
        print(f"Data error: {exc}", file=sys.stderr)
        return 1
    from hotel.gui import HotelApp  # imported here so data errors print before any window opens
    HotelApp(manager).mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
