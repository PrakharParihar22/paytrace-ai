from app.engines.evidence_engine import build_evidence


def _confidence_label(score: float) -> str:
    if score >= 0.85:
        return "HIGH"
    if score >= 0.60:
        return "MEDIUM"
    return "LOW"


def _webhook_failure_plan():
    return [
        "Create a fresh Razorpay test-mode order.",
        "Complete a successful test payment.",
        "Allow Razorpay to deliver payment.captured/order.paid.",
        "Force the merchant webhook handler to fail with HTTP 500.",
        "Verify Razorpay reports payment/order success.",
        "Verify the merchant state does not reach PAID during the failure window.",
    ]


def investigate_order(order_id: str):
    """
    Root-cause hypothesis engine with ACTIVE and RECOVERED incident awareness.
    """

    bundle = build_evidence(order_id)

    if not bundle["found"]:
        return {
            "order_id": order_id,
            "status": "NOT_FOUND",
            "primary_hypothesis": None,
            "hypotheses": [],
        }

    facts = bundle["facts"]
    hypotheses = []

    # ACTIVE incident.
    if (
        facts["provider_paid"]
        and facts["state_divergence"]
        and facts["successful_webhook_received"]
        and facts["webhook_processing_failed"]
    ):
        score = 0.98

        hypotheses.append({
            "code": "WEBHOOK_HANDLER_FAILURE",
            "title": "Merchant webhook handler failed after payment success",
            "confidence": score,
            "confidence_label": _confidence_label(score),
            "failure_boundary": "MERCHANT_WEBHOOK_PROCESSING",
            "incident_phase": "ACTIVE",
            "reason": (
                "Razorpay reports payment/order success, a success webhook reached "
                "the application, webhook processing failed, and merchant state "
                "has not reached PAID."
            ),
            "supporting_evidence": [
                "Provider payment/order evidence indicates success.",
                "At least one success webhook reached the application.",
                "Webhook-processing failure evidence exists.",
                f"Merchant state remains {facts['merchant_state']}.",
            ],
            "contradicting_evidence": [],
            "recommended_reproduction": _webhook_failure_plan(),
        })

    # RECOVERED incident.
    elif facts["historical_incident_observed"] and facts["merchant_paid"]:
        score = 0.95

        hypotheses.append({
            "code": "WEBHOOK_HANDLER_FAILURE",
            "title": "Merchant webhook handler failed, then later recovered",
            "confidence": score,
            "confidence_label": _confidence_label(score),
            "failure_boundary": "MERCHANT_WEBHOOK_PROCESSING",
            "incident_phase": "RECOVERED",
            "reason": (
                "The timeline contains payment success, webhook-processing failure, "
                "and a later merchant transition to PAID. The current state is healthy, "
                "but the earlier failure remains reproducible historical evidence."
            ),
            "supporting_evidence": [
                "Provider payment/order evidence indicates success.",
                "A success webhook reached the application.",
                "Webhook-processing failure evidence exists.",
                "Merchant later transitioned to PAID.",
            ],
            "contradicting_evidence": [
                "The merchant is currently PAID, so there is no active divergence."
            ],
            "recommended_reproduction": _webhook_failure_plan(),
        })

    # Missing webhook case.
    elif (
        facts["provider_paid"]
        and not facts["merchant_paid"]
        and not facts["successful_webhook_received"]
    ):
        score = 0.86
        hypotheses.append({
            "code": "WEBHOOK_NOT_RECEIVED",
            "title": "Successful Razorpay webhook was not observed",
            "confidence": score,
            "confidence_label": _confidence_label(score),
            "failure_boundary": "WEBHOOK_DELIVERY_OR_CONFIGURATION",
            "incident_phase": "ACTIVE",
            "reason": (
                "Provider state indicates success, but no successful webhook "
                "evidence exists and merchant state is not PAID."
            ),
            "supporting_evidence": [
                "Provider state indicates successful payment.",
                "No successful payment webhook is present.",
                f"Merchant state remains {facts['merchant_state']}.",
            ],
            "contradicting_evidence": [],
            "recommended_reproduction": [],
        })

    hypotheses.sort(
        key=lambda item: item["confidence"],
        reverse=True,
    )

    if hypotheses:
        primary = hypotheses[0]
        status = (
            "RECOVERED"
            if primary.get("incident_phase") == "RECOVERED"
            else "INVESTIGATED"
        )
    elif facts["provider_paid"] and facts["merchant_paid"]:
        primary = None
        status = "HEALTHY"
    else:
        primary = None
        status = "INSUFFICIENT_EVIDENCE"

    return {
        "order_id": order_id,
        "status": status,
        "primary_hypothesis": primary,
        "hypotheses": hypotheses,
        "facts": facts,
        "evidence": bundle["evidence"],
    }
