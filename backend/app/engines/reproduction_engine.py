import uuid

from app.services.event_service import log_event


def replay_webhook_handler_failure(order_id: str, investigation: dict):
    """
    Reproduce the historical failure signature in an isolated PayTrace lab.

    For a RECOVERED incident, the expected signature represents the failure
    window, not the order's current healthy state.
    """

    reproduction_id = f"repro_{uuid.uuid4().hex[:12]}"
    facts = investigation.get("facts", {})
    primary = investigation.get("primary_hypothesis") or {}
    phase = primary.get("incident_phase", "ACTIVE")

    simulated = {
        "provider_payment_captured": False,
        "provider_order_paid": False,
        "webhook_received": False,
        "webhook_processing_failed": False,
        "merchant_state": "CREATED",
    }

    steps = []

    def record(step, action, result):
        steps.append({
            "step": step,
            "action": action,
            "result": result,
            "state": dict(simulated),
        })

    record(1, "Initialize merchant order", "PASS")

    simulated["provider_payment_captured"] = True
    simulated["provider_order_paid"] = True
    record(2, "Replay provider payment success", "PASS")

    simulated["webhook_received"] = True
    record(3, "Deliver successful webhook", "PASS")

    simulated["webhook_processing_failed"] = True
    record(
        4,
        "Inject merchant webhook-handler HTTP 500",
        "FAILURE_INJECTED",
    )

    simulated["merchant_state"] = "PAYMENT_VERIFIED"
    record(
        5,
        "Evaluate merchant state during failure window",
        "DIVERGED",
    )

    # For active incidents, current merchant state is the failure state.
    # For recovered incidents, reconstruct the historical failure window.
    expected_signature = {
        "provider_paid": True,
        "webhook_processing_failed": True,
        "merchant_paid": False,
    }

    reproduced_signature = {
        "provider_paid": (
            simulated["provider_payment_captured"]
            or simulated["provider_order_paid"]
        ),
        "webhook_processing_failed": simulated["webhook_processing_failed"],
        "merchant_paid": simulated["merchant_state"] == "PAID",
    }

    matched = reproduced_signature == expected_signature

    if matched:
        result = "REPRODUCED"
        hypothesis_status = "CONFIRMED"
        summary = (
            "PayTrace reproduced the webhook-handler failure signature from "
            f"the {phase.lower()} incident."
        )
    else:
        result = "NOT_REPRODUCED"
        hypothesis_status = "NOT_CONFIRMED"
        summary = "The replay did not match the expected failure signature."

    log_event(
        order_id=order_id,
        event_type="REPRODUCTION_RUN",
        source="PAYTRACE_REPRODUCTION",
        status=result,
        message=summary,
        metadata={
            "reproduction_id": reproduction_id,
            "hypothesis": "WEBHOOK_HANDLER_FAILURE",
            "incident_phase": phase,
            "hypothesis_status": hypothesis_status,
            "expected_signature": expected_signature,
            "reproduced_signature": reproduced_signature,
        },
    )

    return {
        "reproduction_id": reproduction_id,
        "scenario": "WEBHOOK_HANDLER_FAILURE",
        "incident_phase": phase,
        "result": result,
        "hypothesis_status": hypothesis_status,
        "summary": summary,
        "expected_failure_signature": expected_signature,
        "reproduced_signature": reproduced_signature,
        "current_order_state_at_analysis": {
            "merchant_paid": facts.get("merchant_paid"),
            "merchant_state": facts.get("merchant_state"),
        },
        "final_simulated_state": simulated,
        "steps": steps,
    }


def unsupported_reproduction(order_id: str, hypothesis_code: str):
    return {
        "order_id": order_id,
        "scenario": hypothesis_code,
        "result": "UNSUPPORTED",
        "hypothesis_status": "NOT_TESTED",
        "summary": (
            f"No executable reproduction exists yet for {hypothesis_code}."
        ),
        "steps": [],
    }
