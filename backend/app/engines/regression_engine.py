import uuid

from app.services.event_service import log_event


def run_webhook_fix_regression(
    order_id: str,
    reproduction_result: dict,
    fix_advice: dict,
):
    """
    Run the same webhook-failure scenario with the proposed test-lab patch.

    The original incident is not mutated. This is an isolated regression lab.
    """

    regression_id = f"reg_{uuid.uuid4().hex[:12]}"

    fix = (fix_advice or {}).get("fix") or {}
    patch = fix.get("test_patch") or {}

    before = {
        "provider_paid": True,
        "webhook_received": True,
        "webhook_processing_failed": True,
        "merchant_paid": False,
        "state_divergence": True,
    }

    state = {
        "provider_payment_captured": False,
        "provider_order_paid": False,
        "webhook_received": False,
        "signature_valid": True,
        "duplicate_event": False,
        "webhook_processing_failed": False,
        "merchant_state": "CREATED",
        "acknowledged": False,
    }

    steps = []

    def record(step, action, result):
        steps.append({
            "step": step,
            "action": action,
            "result": result,
            "state": dict(state),
        })

    record(1, "Initialize clean regression scenario", "PASS")

    # Same provider success as the original incident.
    state["provider_payment_captured"] = True
    state["provider_order_paid"] = True
    record(2, "Replay provider payment success", "PASS")

    state["webhook_received"] = True
    record(3, "Deliver successful Razorpay webhook", "PASS")

    # Apply proposed fix controls.
    if patch.get("webhook_signature_required") and not state["signature_valid"]:
        state["webhook_processing_failed"] = True
        record(4, "Verify webhook signature", "BLOCKED_INVALID_SIGNATURE")
    else:
        record(4, "Verify webhook signature", "PASS")

    if not state["webhook_processing_failed"]:
        if patch.get("idempotent_processing"):
            record(5, "Apply idempotent event guard", "PASS")
        else:
            record(5, "Apply idempotent event guard", "NOT_APPLIED")

        if patch.get("state_write_succeeds"):
            state["merchant_state"] = "PAID"
            record(6, "Persist merchant state transition to PAID", "PASS")
        else:
            state["webhook_processing_failed"] = True
            record(6, "Persist merchant state transition to PAID", "FAILED")

    if (
        patch.get("ack_only_after_state_write")
        and state["merchant_state"] == "PAID"
        and not state["webhook_processing_failed"]
    ):
        state["acknowledged"] = True
        record(7, "Return HTTP 2xx after successful state persistence", "PASS")
    else:
        record(7, "Return HTTP response", "NOT_ACKNOWLEDGED")

    after = {
        "provider_paid": (
            state["provider_payment_captured"]
            or state["provider_order_paid"]
        ),
        "webhook_received": state["webhook_received"],
        "webhook_processing_failed": state["webhook_processing_failed"],
        "merchant_paid": state["merchant_state"] == "PAID",
        "state_divergence": (
            (
                state["provider_payment_captured"]
                or state["provider_order_paid"]
            )
            and state["merchant_state"] != "PAID"
        ),
    }

    verified = (
        before["state_divergence"] is True
        and after["provider_paid"] is True
        and after["merchant_paid"] is True
        and after["state_divergence"] is False
        and after["webhook_processing_failed"] is False
    )

    if verified:
        regression_status = "PASS"
        fix_status = "VERIFIED"
        summary = (
            "The same failure scenario no longer produces state divergence "
            "after applying the PayTrace test-lab webhook reliability fix."
        )
    else:
        regression_status = "FAIL"
        fix_status = "NOT_VERIFIED"
        summary = (
            "The proposed fix did not eliminate the reproduced failure."
        )

    log_event(
        order_id=order_id,
        event_type="REGRESSION_RUN",
        source="PAYTRACE_REGRESSION",
        status=regression_status,
        message=summary,
        metadata={
            "regression_id": regression_id,
            "fix_id": fix.get("fix_id"),
            "fix_status": fix_status,
            "before": before,
            "after": after,
        },
    )

    return {
        "regression_id": regression_id,
        "scenario": "WEBHOOK_HANDLER_FAILURE",
        "regression_status": regression_status,
        "fix_status": fix_status,
        "summary": summary,
        "before_fix": before,
        "after_fix": after,
        "final_simulated_state": state,
        "steps": steps,
    }
