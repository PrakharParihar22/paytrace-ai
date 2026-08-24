from app.services.event_service import get_events
from app.services.order_service import get_order


def build_evidence(order_id: str):
    """
    Convert the raw PayTrace timeline into structured investigation facts.

    V2 adds historical failure/recovery awareness so an order can be healthy
    NOW while still preserving evidence that it previously entered a broken
    payment state.
    """

    order = get_order(order_id)

    if not order:
        return {
            "order_id": order_id,
            "found": False,
            "facts": {},
            "evidence": [],
        }

    events = get_events(order_id)

    facts = {
        "merchant_state": order.get("merchant_state"),
        "payment_id": order.get("payment_id"),
        "payment_captured": False,
        "razorpay_order_paid": False,
        "checkout_callback_received": False,
        "signature_verified": False,
        "payment_captured_webhook_received": False,
        "order_paid_webhook_received": False,
        "successful_webhook_received": False,
        "webhook_processing_failed": False,
        "merchant_paid_event_seen": False,
        "merchant_non_paid_after_provider_success_seen": False,
        "recovered_after_webhook_failure": False,
        "event_count": len(events),
    }

    evidence = []
    failed_webhook_events = []
    webhook_events = []

    provider_success_seen = False
    failure_seen = False

    for event in events:
        event_type = event.get("event_type")
        source = event.get("source")
        status = event.get("status")
        metadata = event.get("metadata") or {}

        if event.get("payment_id"):
            facts["payment_id"] = event.get("payment_id")

        if event_type == "CHECKOUT_CALLBACK":
            facts["checkout_callback_received"] = True

        if event_type == "SIGNATURE_VERIFICATION" and status == "VERIFIED":
            facts["signature_verified"] = True

        if event_type == "RAZORPAY_PAYMENT_STATE" and status == "captured":
            facts["payment_captured"] = True
            provider_success_seen = True

        if event_type == "RAZORPAY_ORDER_STATE" and status == "paid":
            facts["razorpay_order_paid"] = True
            provider_success_seen = True

        if source == "RAZORPAY_WEBHOOK":
            webhook_events.append(event_type)

            if event_type == "payment.captured":
                facts["payment_captured_webhook_received"] = True
                facts["successful_webhook_received"] = True
                facts["payment_captured"] = True
                provider_success_seen = True

            if event_type == "order.paid":
                facts["order_paid_webhook_received"] = True
                facts["successful_webhook_received"] = True
                facts["razorpay_order_paid"] = True
                provider_success_seen = True

        if event_type == "WEBHOOK_PROCESSING_FAILED":
            facts["webhook_processing_failed"] = True
            failure_seen = True
            failed_webhook_events.append(
                metadata.get("trigger_event") or "unknown"
            )

        if event_type == "MERCHANT_STATE":
            if status == "PAID":
                facts["merchant_paid_event_seen"] = True

                # A PAID transition after a known webhook-processing failure
                # is explicit recovery evidence.
                if failure_seen:
                    facts["recovered_after_webhook_failure"] = True

            elif provider_success_seen:
                facts["merchant_non_paid_after_provider_success_seen"] = True

    provider_paid = facts["payment_captured"] or facts["razorpay_order_paid"]
    merchant_paid = facts["merchant_state"] == "PAID"

    facts["provider_paid"] = provider_paid
    facts["merchant_paid"] = merchant_paid
    facts["state_divergence"] = provider_paid and not merchant_paid
    facts["historical_incident_observed"] = (
        provider_paid
        and facts["webhook_processing_failed"]
        and (
            facts["merchant_non_paid_after_provider_success_seen"]
            or facts["recovered_after_webhook_failure"]
        )
    )
    facts["failed_webhook_events"] = failed_webhook_events
    facts["webhook_events"] = webhook_events

    if facts["payment_captured"]:
        evidence.append({
            "code": "PAYMENT_CAPTURED",
            "strength": "HIGH",
            "statement": "Razorpay evidence shows the payment is captured.",
        })

    if facts["razorpay_order_paid"]:
        evidence.append({
            "code": "ORDER_PAID",
            "strength": "HIGH",
            "statement": "Razorpay evidence shows the order is paid.",
        })

    if facts["successful_webhook_received"]:
        evidence.append({
            "code": "SUCCESS_WEBHOOK_RECEIVED",
            "strength": "HIGH",
            "statement": "A successful Razorpay webhook reached PayTrace.",
        })

    if facts["webhook_processing_failed"]:
        evidence.append({
            "code": "WEBHOOK_PROCESSING_FAILED",
            "strength": "HIGH",
            "statement": "The merchant webhook-processing layer recorded a failure.",
        })

    if facts["state_divergence"]:
        evidence.append({
            "code": "STATE_DIVERGENCE",
            "strength": "HIGH",
            "statement": (
                f"Provider state indicates payment success while merchant "
                f"state remains {facts['merchant_state']}."
            ),
        })

    if facts["recovered_after_webhook_failure"]:
        evidence.append({
            "code": "RECOVERED_AFTER_WEBHOOK_FAILURE",
            "strength": "HIGH",
            "statement": (
                "The merchant later reached PAID after a recorded webhook-processing failure."
            ),
        })

    if merchant_paid:
        evidence.append({
            "code": "MERCHANT_PAID",
            "strength": "HIGH",
            "statement": "The merchant application is currently PAID.",
        })

    return {
        "order_id": order_id,
        "found": True,
        "facts": facts,
        "evidence": evidence,
    }
