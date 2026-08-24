from app.services.event_service import get_events
from app.services.order_service import get_order


def analyze_order_state(order_id: str):
    """
    Deterministic V1 state-divergence detector.

    This engine intentionally does not use an LLM. Payment and order states
    are factual system evidence, so deterministic rules are safer and easier
    to verify. AI reasoning can be layered on top later for root-cause
    explanation.
    """

    order = get_order(order_id)

    if not order:
        return {
            "health": "UNKNOWN",
            "incident": False,
            "incident_type": None,
            "severity": None,
            "order_id": order_id,
            "message": "Order not found.",
            "evidence": [],
        }

    events = get_events(order_id)

    merchant_state = order["merchant_state"]
    provider_payment_captured = False
    provider_order_paid = False
    webhook_failure_detected = False
    payment_id = order.get("payment_id")
    evidence = []

    for event in events:
        event_type = event.get("event_type")
        source = event.get("source")
        status = event.get("status")

        if event.get("payment_id"):
            payment_id = event.get("payment_id")

        if (
            event_type == "RAZORPAY_PAYMENT_STATE"
            and status == "captured"
        ):
            provider_payment_captured = True

        if (
            event_type == "RAZORPAY_ORDER_STATE"
            and status == "paid"
        ):
            provider_order_paid = True

        if (
            source == "RAZORPAY_WEBHOOK"
            and event_type == "payment.captured"
        ):
            provider_payment_captured = True

        if (
            source == "RAZORPAY_WEBHOOK"
            and event_type == "order.paid"
        ):
            provider_order_paid = True

        if event_type == "WEBHOOK_PROCESSING_FAILED":
            webhook_failure_detected = True

    provider_paid = (
        provider_payment_captured
        or provider_order_paid
    )

    if provider_paid and merchant_state != "PAID":
        if provider_payment_captured:
            evidence.append(
                "Razorpay evidence shows the payment is captured."
            )

        if provider_order_paid:
            evidence.append(
                "Razorpay evidence shows the order is paid."
            )

        evidence.append(
            f"Merchant application state is {merchant_state}, not PAID."
        )

        if webhook_failure_detected:
            evidence.append(
                "A merchant webhook-processing failure was recorded."
            )

        return {
            "health": "INCIDENT",
            "incident": True,
            "incident_type": "STATE_DIVERGENCE",
            "severity": "HIGH",
            "order_id": order_id,
            "payment_id": payment_id,
            "provider_state": {
                "payment_captured": provider_payment_captured,
                "order_paid": provider_order_paid,
            },
            "merchant_state": merchant_state,
            "webhook_failure_detected": webhook_failure_detected,
            "evidence": evidence,
            "recommended_next_step": (
                "Inspect webhook-processing evidence and reconcile the "
                "merchant order only after validating authoritative "
                "Razorpay payment/order state."
            ),
        }

    if provider_paid and merchant_state == "PAID":
        return {
            "health": "HEALTHY",
            "incident": False,
            "incident_type": None,
            "severity": None,
            "order_id": order_id,
            "payment_id": payment_id,
            "provider_state": {
                "payment_captured": provider_payment_captured,
                "order_paid": provider_order_paid,
            },
            "merchant_state": merchant_state,
            "webhook_failure_detected": webhook_failure_detected,
            "evidence": [
                "Provider payment/order evidence indicates successful payment.",
                "Merchant application state is PAID.",
            ],
            "recommended_next_step": None,
        }

    return {
        "health": "PENDING",
        "incident": False,
        "incident_type": None,
        "severity": None,
        "order_id": order_id,
        "payment_id": payment_id,
        "provider_state": {
            "payment_captured": provider_payment_captured,
            "order_paid": provider_order_paid,
        },
        "merchant_state": merchant_state,
        "webhook_failure_detected": webhook_failure_detected,
        "evidence": [
            "PayTrace has not yet observed provider evidence proving a paid order.",
            f"Current merchant application state is {merchant_state}.",
        ],
        "recommended_next_step": (
            "Wait for additional payment or webhook evidence."
        ),
    }
