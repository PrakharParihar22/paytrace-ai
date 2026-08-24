import json
import threading
from pathlib import Path

from app.engines.reliability_suite import run_reliability_suite


_LOCK = threading.Lock()

_DATA_FILE = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "reliability_suite.json"
)


def _ensure_store():
    _DATA_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not _DATA_FILE.exists():
        _DATA_FILE.write_text(
            json.dumps(
                {
                    "latest_run": None,
                    "history": [],
                },
                indent=2,
            ),
            encoding="utf-8",
        )


def _load():
    _ensure_store()

    try:
        return json.loads(
            _DATA_FILE.read_text(
                encoding="utf-8"
            )
        )
    except (json.JSONDecodeError, OSError):
        return {
            "latest_run": None,
            "history": [],
        }


def _write(payload):
    _DATA_FILE.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def execute_reliability_suite():
    result = run_reliability_suite()

    with _LOCK:
        payload = _load()

        history = payload.get(
            "history",
            [],
        )

        history.insert(0, result)

        payload = {
            "latest_run": result,
            "history": history[:20],
        }

        _write(payload)

    return result


def get_latest_reliability_suite():
    with _LOCK:
        return _load().get(
            "latest_run"
        )


def get_reliability_history(
    limit: int = 10,
):
    with _LOCK:
        history = _load().get(
            "history",
            [],
        )

    return history[:limit]
