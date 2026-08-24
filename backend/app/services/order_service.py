from datetime import datetime, timezone

from app.db import get_connection


def now():
    return datetime.now(timezone.utc).isoformat()


def create_order_record(
    order_id,
    amount,
    currency,
    receipt
):

    connection = get_connection()
    cursor = connection.cursor()

    timestamp = now()

    cursor.execute(
        """
        INSERT INTO merchant_orders (
            id,
            amount,
            currency,
            receipt,
            merchant_state,
            payment_id,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            order_id,
            amount,
            currency,
            receipt,
            "CREATED",
            None,
            timestamp,
            timestamp
        )
    )

    connection.commit()
    connection.close()


def get_order(order_id):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM merchant_orders
        WHERE id = ?
        """,
        (order_id,)
    )

    row = cursor.fetchone()

    connection.close()

    if row is None:
        return None

    return dict(row)


def update_order_state(
    order_id,
    merchant_state,
    payment_id=None
):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE merchant_orders
        SET
            merchant_state = ?,
            payment_id = COALESCE(?, payment_id),
            updated_at = ?
        WHERE id = ?
        """,
        (
            merchant_state,
            payment_id,
            now(),
            order_id
        )
    )

    connection.commit()
    connection.close()


def get_all_orders():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM merchant_orders
        ORDER BY created_at DESC
        """
    )

    rows = cursor.fetchall()

    connection.close()

    return [
        dict(row)
        for row in rows
    ]