from __future__ import annotations

import argparse
import shutil
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "backend" / "data"
BACKUPS_DIR = DATA_DIR / "backups"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Restore PayTrace runtime data from a demo-reset backup."
    )

    parser.add_argument(
        "backup",
        nargs="?",
        help=(
            "Backup folder name under backend/data/backups. "
            "If omitted, the newest backup is used."
        ),
    )

    args = parser.parse_args()

    if not BACKUPS_DIR.exists():
        raise SystemExit(
            "No PayTrace backup directory exists."
        )

    backups = sorted(
        [
            path
            for path in BACKUPS_DIR.iterdir()
            if path.is_dir()
        ],
        reverse=True,
    )

    if not backups:
        raise SystemExit(
            "No PayTrace demo backups were found."
        )

    if args.backup:
        backup_dir = BACKUPS_DIR / args.backup

        if not backup_dir.is_dir():
            raise SystemExit(
                f"Backup not found: {backup_dir}"
            )
    else:
        backup_dir = backups[0]

    restored = []

    for name in (
        "paytrace.db",
        "complaints.json",
        "reliability_suite.json",
    ):
        source = backup_dir / name

        if source.exists():
            shutil.copy2(
                source,
                DATA_DIR / name,
            )
            restored.append(name)

    print(
        f"Restored from: {backup_dir}"
    )

    for name in restored:
        print(f"  restored: {name}")


if __name__ == "__main__":
    main()
