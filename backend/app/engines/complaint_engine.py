import re

from app.services.dashboard_service import build_order_report
from app.services.order_service import get_all_orders, get_order


ORDER_PATTERN = re.compile(
    r"\border_[A-Za-z0-9]+\b",
    re.IGNORECASE,
)

PAYMENT_PATTERN = re.compile(
    r"\bpay_[A-Za-z0-9]+\b",
    re.IGNORECASE,
)

AMOUNT_PATTERN = re.compile(
    r"(?:₹|rs\.?|inr)\s*([0-9,]+(?:\.[0-9]{1,2})?)",
    re.IGNORECASE,
)


def extract_complaint_signals(message: str):
    normalized = " ".join(
        message.lower().split()
    )

    order_match = ORDER_PATTERN.search(message)
    payment_match = PAYMENT_PATTERN.search(message)
    amount_match = AMOUNT_PATTERN.search(message)

    amount_paise = None

    if amount_match:
        amount_rupees = float(
            amount_match.group(1).replace(",", "")
        )
        amount_paise = int(
            round(amount_rupees * 100)
        )

    issue_type = classify_reported_issue(
        normalized
    )

    return {
        "reported_issue_type": issue_type,
        "extracted_order_id": (
            order_match.group(0)
            if order_match
            else None
        ),
        "extracted_payment_id": (
            payment_match.group(0)
            if payment_match
            else None
        ),
        "reported_amount": amount_paise,
    }


def classify_reported_issue(
    normalized_message: str,
):
    duplicate_terms = (
        "duplicate",
        "twice",
        "double charged",
        "charged two times",
    )

    refund_terms = (
        "refund",
        "refunded",
        "refund pending",
    )

    debit_terms = (
        "deducted",
        "debited",
        "charged",
        "money taken",
        "amount taken",
    )

    failure_terms = (
        "failed",
        "failure",
        "declined",
        "unsuccessful",
    )

    pending_terms = (
        "pending",
        "not showing",
        "not received",
        "not confirmed",
        "not updated",
        "unconfirmed",
        "still processing",
    )

    if any(
        term in normalized_message
        for term in duplicate_terms
    ):
        return "DUPLICATE_CHARGE_REPORTED"

    if any(
        term in normalized_message
        for term in refund_terms
    ):
        return "REFUND_DELAY_REPORTED"

    has_debit = any(
        term in normalized_message
        for term in debit_terms
    )

    has_failure = any(
        term in normalized_message
        for term in failure_terms
    )

    has_pending = any(
        term in normalized_message
        for term in pending_terms
    )

    if has_debit and has_failure:
        return "DEBITED_BUT_FAILED_REPORTED"

    if has_debit and has_pending:
        return (
            "PROVIDER_MERCHANT_STATE_MISMATCH_REPORTED"
        )

    if has_pending:
        return "PAYMENT_PENDING_REPORTED"

    return "GENERAL_PAYMENT_ISSUE"


def _order_by_payment_id(payment_id: str):
    if not payment_id:
        return None

    for order in get_all_orders():
        if order.get("payment_id") == payment_id:
            return order

    return None


def _candidate_summary(order: dict):
    report = build_order_report(
        order["id"]
    )

    investigation = (
        report.get("investigation", {})
        if report
        else {}
    )

    primary = (
        investigation.get("primary_hypothesis")
        or {}
    )

    return {
        "order_id": order.get("id"),
        "payment_id": order.get("payment_id"),
        "amount": order.get("amount"),
        "currency": order.get("currency"),
        "merchant_state": order.get(
            "merchant_state"
        ),
        "investigation_status": (
            investigation.get("status")
        ),
        "root_cause": primary.get("code"),
        "updated_at": order.get("updated_at"),
    }


def correlate_complaint(
    message: str,
    provided_order_id: str | None = None,
    provided_payment_id: str | None = None,
):
    signals = extract_complaint_signals(
        message
    )

    order_id = (
        provided_order_id
        or signals["extracted_order_id"]
    )

    payment_id = (
        provided_payment_id
        or signals["extracted_payment_id"]
    )

    # --------------------------------------------------
    # Highest-trust correlation: explicit order ID.
    # --------------------------------------------------

    if order_id:
        order = get_order(order_id)

        if order:
            return _matched_result(
                order=order,
                signals=signals,
                confidence="HIGH",
                confidence_score=1.0,
                basis="EXACT_ORDER_ID",
            )

        return {
            "status": "UNRESOLVED",
            "confidence": "HIGH",
            "confidence_score": 1.0,
            "basis": "ORDER_ID_NOT_FOUND",
            "signals": signals,
            "matched_order": None,
            "candidates": [],
            "message": (
                "The complaint contains an order ID, "
                "but PayTrace does not have that order."
            ),
        }

    # --------------------------------------------------
    # Payment ID is also an exact identifier.
    # --------------------------------------------------

    if payment_id:
        order = _order_by_payment_id(
            payment_id
        )

        if order:
            return _matched_result(
                order=order,
                signals=signals,
                confidence="HIGH",
                confidence_score=1.0,
                basis="EXACT_PAYMENT_ID",
            )

        return {
            "status": "UNRESOLVED",
            "confidence": "HIGH",
            "confidence_score": 1.0,
            "basis": "PAYMENT_ID_NOT_FOUND",
            "signals": signals,
            "matched_order": None,
            "candidates": [],
            "message": (
                "The complaint contains a payment ID, "
                "but PayTrace does not have a matching order."
            ),
        }

    # --------------------------------------------------
    # Medium-trust correlation: amount + unique relevant
    # test order. Never silently guess if multiple match.
    # --------------------------------------------------

    reported_amount = signals.get(
        "reported_amount"
    )

    if reported_amount is not None:
        amount_matches = [
            order
            for order in get_all_orders()
            if order.get("amount")
            == reported_amount
        ]

        relevant = []

        for order in amount_matches:
            report = build_order_report(
                order["id"]
            )

            investigation = (
                report.get("investigation", {})
                if report
                else {}
            )

            if investigation.get("status") in {
                "INVESTIGATED",
                "RECOVERED",
            }:
                relevant.append(order)

        if len(relevant) == 1:
            return _matched_result(
                order=relevant[0],
                signals=signals,
                confidence="MEDIUM",
                confidence_score=0.72,
                basis=(
                    "UNIQUE_AMOUNT_AND_INCIDENT_MATCH"
                ),
            )

        candidates = (
            relevant
            if relevant
            else amount_matches
        )

        if candidates:
            return {
                "status": "NEEDS_CONFIRMATION",
                "confidence": "LOW",
                "confidence_score": 0.35,
                "basis": "AMBIGUOUS_AMOUNT_MATCH",
                "signals": signals,
                "matched_order": None,
                "candidates": [
                    _candidate_summary(order)
                    for order in candidates[:5]
                ],
                "message": (
                    "Multiple PayTrace orders match the "
                    "reported amount. Confirm an order or "
                    "payment ID before correlating."
                ),
            }

    # --------------------------------------------------
    # No trustworthy correlation. Surface candidates but
    # do not invent a match.
    # --------------------------------------------------

    active_candidates = []

    for order in get_all_orders():
        report = build_order_report(
            order["id"]
        )

        if not report:
            continue

        status = (
            report.get("investigation", {})
            .get("status")
        )

        if status == "INVESTIGATED":
            active_candidates.append(
                _candidate_summary(order)
            )

    return {
        "status": "UNRESOLVED",
        "confidence": "LOW",
        "confidence_score": 0.0,
        "basis": "NO_RELIABLE_IDENTIFIER",
        "signals": signals,
        "matched_order": None,
        "candidates": active_candidates[:5],
        "message": (
            "PayTrace needs an order ID or payment ID "
            "to make a trustworthy correlation."
        ),
    }


def _matched_result(
    order: dict,
    signals: dict,
    confidence: str,
    confidence_score: float,
    basis: str,
):
    report = build_order_report(
        order["id"]
    )

    investigation = (
        report.get("investigation", {})
        if report
        else {}
    )

    analysis = (
        report.get("analysis", {})
        if report
        else {}
    )

    primary = (
        investigation.get("primary_hypothesis")
        or {}
    )

    investigation_status = (
        investigation.get("status")
    )

    if investigation_status == "INVESTIGATED":
        evidence_status = (
            "SUPPORTED_ACTIVE_INCIDENT"
        )
        complaint_status = (
            "CORRELATED_ACTIVE_INCIDENT"
        )
    elif investigation_status == "RECOVERED":
        evidence_status = (
            "SUPPORTED_RECOVERED_INCIDENT"
        )
        complaint_status = (
            "CORRELATED_RECOVERED"
        )
    elif investigation_status == "HEALTHY":
        evidence_status = (
            "CURRENT_STATE_CONSISTENT"
        )
        complaint_status = (
            "CORRELATED_HEALTHY"
        )
    else:
        evidence_status = (
            "INSUFFICIENT_SYSTEM_EVIDENCE"
        )
        complaint_status = "CORRELATED_PENDING"

    provider_state = {
        "payment_captured": (
            analysis.get(
                "provider_state",
                {},
            ).get(
                "payment_captured"
            )
        ),
        "order_paid": (
            analysis.get(
                "provider_state",
                {},
            ).get(
                "order_paid"
            )
        ),
    }

    system_truth = {
        "provider_state": provider_state,
        "merchant_state": (
            order.get("merchant_state")
        ),
        "state_divergence": (
            analysis.get(
                "state_divergence",
                False,
            )
        ),
        "investigation_status": (
            investigation_status
        ),
        "root_cause": primary.get("code"),
        "failure_boundary": primary.get(
            "failure_boundary"
        ),
        "confidence": primary.get(
            "confidence"
        ),
    }

    return {
        "status": complaint_status,
        "confidence": confidence,
        "confidence_score": (
            confidence_score
        ),
        "basis": basis,
        "signals": signals,
        "matched_order": {
            "order_id": order.get("id"),
            "payment_id": order.get(
                "payment_id"
            ),
            "amount": order.get("amount"),
            "currency": order.get(
                "currency"
            ),
        },
        "candidates": [],
        "evidence_status": evidence_status,
        "system_truth": system_truth,
        "recommended_action": (
            "OPEN_INCIDENT_WORKSPACE"
            if investigation_status
            in {"INVESTIGATED", "RECOVERED"}
            else "REVIEW_ORDER_EVIDENCE"
        ),
    }
