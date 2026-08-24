from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
DATA_DIR = BACKEND_DIR / "data"

DB_PATH = DATA_DIR / "paytrace.db"
COMPLAINTS_PATH = DATA_DIR / "complaints.json"
RELIABILITY_PATH = DATA_DIR / "reliability_suite.json"
BACKUPS_DIR = DATA_DIR / "backups"


def backup_runtime_data() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = BACKUPS_DIR / timestamp
    backup_dir.mkdir(parents=True, exist_ok=False)

    for path in (
        DB_PATH,
        COMPLAINTS_PATH,
        RELIABILITY_PATH,
    ):
        if path.exists():
            shutil.copy2(
                path,
                backup_dir / path.name,
            )

    return backup_dir


def reset_sqlite() -> tuple[int, int]:
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"PayTrace database was not found: {DB_PATH}"
        )

    connection = sqlite3.connect(DB_PATH)

    try:
        cursor = connection.cursor()

        cursor.execute(
            "SELECT COUNT(*) FROM payment_events"
        )
        event_count = int(cursor.fetchone()[0])

        cursor.execute(
            "SELECT COUNT(*) FROM merchant_orders"
        )
        order_count = int(cursor.fetchone()[0])

        # Delete child/event rows first.
        cursor.execute(
            "DELETE FROM payment_events"
        )
        cursor.execute(
            "DELETE FROM merchant_orders"
        )

        # Reset SQLite AUTOINCREMENT only for the event table.
        cursor.execute(
            """
            DELETE FROM sqlite_sequence
            WHERE name = 'payment_events'
            """
        )

        connection.commit()
    finally:
        connection.close()

    return order_count, event_count


def reset_complaints() -> int:
    previous_count = 0

    if COMPLAINTS_PATH.exists():
        try:
            payload = json.loads(
                COMPLAINTS_PATH.read_text(
                    encoding="utf-8"
                )
            )

            if isinstance(payload, list):
                previous_count = len(payload)
        except (json.JSONDecodeError, OSError):
            pass

    COMPLAINTS_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    COMPLAINTS_PATH.write_text(
        "[]\n",
        encoding="utf-8",
    )

    return previous_count


def reset_reliability() -> None:
    RELIABILITY_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    RELIABILITY_PATH.write_text(
        json.dumps(
            {
                "latest_run": None,
                "history": [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Reset PayTrace demo payment/incident data "
            "while preserving the executable reliability score."
        )
    )

    parser.add_argument(
        "--clear-reliability",
        action="store_true",
        help=(
            "Also clear reliability_suite.json. "
            "By default the 5/5 suite result is preserved."
        ),
    )

    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip the automatic runtime-data backup.",
    )

    args = parser.parse_args()

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    backup_dir = None

    if not args.no_backup:
        backup_dir = backup_runtime_data()

    order_count, event_count = reset_sqlite()
    complaint_count = reset_complaints()

    reliability_action = "preserved"

    if args.clear_reliability:
        reset_reliability()
        reliability_action = "cleared"

    print()
    print("PayTrace demo reset complete.")
    print("--------------------------------")
    print(f"Orders removed:      {order_count}")
    print(f"Events removed:      {event_count}")
    print(f"Complaints removed:  {complaint_count}")
    print(f"Reliability suite:   {reliability_action}")

    if backup_dir:
        print(f"Backup created:      {backup_dir}")

    print()
    print("Expected judge-ready Overview:")
    print("  Transactions      0")
    print("  Active incidents  0")
    print("  Recovered         0")
    print("  Fixes verified    0")

    if not args.clear_reliability:
        print("  Reliability score preserved (e.g. 100 / 5 of 5)")

    print()


if __name__ == "__main__":
    main()
