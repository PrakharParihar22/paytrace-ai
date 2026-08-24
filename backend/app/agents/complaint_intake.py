from datetime import datetime, timezone
import uuid

from app.engines.complaint_engine import correlate_complaint
from app.services.complaint_service import (
    get_complaint,
    list_complaints,
    save_complaint,
)


def _now():
    return datetime.now(
        timezone.utc
    ).isoformat()


def intake_complaint(
    message: str,
    order_id: str | None = None,
    payment_id: str | None = None,
):
    correlation = correlate_complaint(
        message=message,
        provided_order_id=order_id,
        provided_payment_id=payment_id,
    )

    complaint = {
        "complaint_id": (
            f"cmp_{uuid.uuid4().hex[:12]}"
        ),
        "created_at": _now(),
        "last_checked_at": _now(),
        "message": message,
        "provided_order_id": order_id,
        "provided_payment_id": payment_id,
        "reported_issue_type": (
            correlation.get("signals", {})
            .get("reported_issue_type")
        ),
        "reported_amount": (
            correlation.get("signals", {})
            .get("reported_amount")
        ),
        "correlation": correlation,
    }

    save_complaint(complaint)

    return complaint


def recheck_complaint(
    complaint_id: str,
):
    complaint = get_complaint(
        complaint_id
    )

    if not complaint:
        return None

    correlation = correlate_complaint(
        message=complaint["message"],
        provided_order_id=(
            complaint.get(
                "provided_order_id"
            )
        ),
        provided_payment_id=(
            complaint.get(
                "provided_payment_id"
            )
        ),
    )

    complaint["last_checked_at"] = _now()
    complaint["reported_issue_type"] = (
        correlation.get("signals", {})
        .get("reported_issue_type")
    )
    complaint["reported_amount"] = (
        correlation.get("signals", {})
        .get("reported_amount")
    )
    complaint["correlation"] = correlation

    save_complaint(complaint)

    return complaint


def get_complaint_record(
    complaint_id: str,
):
    return get_complaint(
        complaint_id
    )


def get_recent_complaints(
    limit: int = 50,
):
    return list_complaints(limit)
