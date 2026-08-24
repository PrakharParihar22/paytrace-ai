import json
from datetime import datetime, timezone

from app.db import get_connection


def now():
    return datetime.now(timezone.utc).isoformat()


def log_event(
    order_id,
    event_type,
    source,
    status=None,
    message=None,
    payment_id=None,
    metadata=None
):

    connection = get_connection()
    cursor = connection.cursor()

    metadata_json = None

    if metadata is not None:
        metadata_json = json.dumps(metadata)

    cursor.execute(
        """
        INSERT INTO payment_events (
            order_id,
            payment_id,
            event_type,
            source,
            status,
            message,
            metadata,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            order_id,
            payment_id,
            event_type,
            source,
            status,
            message,
            metadata_json,
            now()
        )
    )

    connection.commit()
    connection.close()


def get_events(order_id):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM payment_events
        WHERE order_id = ?
        ORDER BY created_at ASC, id ASC
        """,
        (order_id,)
    )

    rows = cursor.fetchall()

    connection.close()

    events = []

    for row in rows:

        event = dict(row)

        if event["metadata"]:
            event["metadata"] = json.loads(
                event["metadata"]
            )

        events.append(event)

    return events