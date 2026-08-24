import json
import threading
from pathlib import Path


_LOCK = threading.Lock()
_DATA_FILE = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "complaints.json"
)


def _ensure_store():
    _DATA_FILE.parent.mkdir(parents=True, exist_ok=True)

    if not _DATA_FILE.exists():
        _DATA_FILE.write_text(
            "[]",
            encoding="utf-8",
        )


def _load_all():
    _ensure_store()

    try:
        return json.loads(
            _DATA_FILE.read_text(encoding="utf-8")
        )
    except (json.JSONDecodeError, OSError):
        return []


def _write_all(records):
    _ensure_store()

    _DATA_FILE.write_text(
        json.dumps(
            records,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def save_complaint(record: dict):
    with _LOCK:
        records = _load_all()

        existing_index = next(
            (
                index
                for index, item in enumerate(records)
                if item.get("complaint_id")
                == record.get("complaint_id")
            ),
            None,
        )

        if existing_index is None:
            records.append(record)
        else:
            records[existing_index] = record

        _write_all(records)

    return record


def get_complaint(complaint_id: str):
    with _LOCK:
        records = _load_all()

    return next(
        (
            record
            for record in records
            if record.get("complaint_id")
            == complaint_id
        ),
        None,
    )


def list_complaints(limit: int = 50):
    with _LOCK:
        records = _load_all()

    records.sort(
        key=lambda record: record.get("created_at") or "",
        reverse=True,
    )

    return records[:limit]
