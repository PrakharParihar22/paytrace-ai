from app.agents.investigator import investigate_order


FIX_LIBRARY = {
    "WEBHOOK_HANDLER_FAILURE": {
        "fix_id": "FIX_WEBHOOK_RELIABILITY_V1",
        "title": "Harden merchant webhook processing",
        "failure_boundary": "MERCHANT_WEBHOOK_PROCESSING",
        "summary": (
            "Keep Razorpay payment truth authoritative, make webhook handling "
            "idempotent, and ensure the merchant state update succeeds before "
            "the handler acknowledges the event."
        ),
        "changes": [
            {
                "priority": 1,
                "change": "Verify the Razorpay webhook signature before processing.",
                "why": "Prevents untrusted events from mutating merchant state.",
            },
            {
                "priority": 2,
                "change": (
                    "Process payment success idempotently using the Razorpay "
                    "event/payment identifier."
                ),
                "why": (
                    "Razorpay may retry webhooks, so duplicate delivery must "
                    "not create duplicate business actions."
                ),
            },
            {
                "priority": 3,
                "change": (
                    "Persist the merchant PAID transition successfully before "
                    "returning HTTP 2xx."
                ),
                "why": (
                    "Acknowledging before state persistence can lose the only "
                    "successful processing opportunity."
                ),
            },
            {
                "priority": 4,
                "change": (
                    "Return non-2xx on genuine processing failure so the event "
                    "can be retried instead of being silently dropped."
                ),
                "why": (
                    "The failure remains observable and recoverable."
                ),
            },
            {
                "priority": 5,
                "change": (
                    "Add reconciliation for orders whose provider state is paid "
                    "but merchant state is not PAID."
                ),
                "why": (
                    "Provides a recovery path even if asynchronous processing "
                    "was interrupted."
                ),
            },
        ],
        "test_patch": {
            "webhook_signature_required": True,
            "idempotent_processing": True,
            "state_write_succeeds": True,
            "ack_only_after_state_write": True,
            "reconciliation_enabled": True,
        },
        "safety": {
            "auto_modify_production_code": False,
            "move_real_money": False,
            "refund_real_money": False,
            "test_lab_only": True,
        },
    }
}


def advise_fix(order_id: str):
    investigation = investigate_order(order_id)

    if investigation.get("status") == "NOT_FOUND":
        return {
            "order_id": order_id,
            "status": "NOT_FOUND",
            "fix": None,
        }

    primary = investigation.get("primary_hypothesis")

    if not primary:
        return {
            "order_id": order_id,
            "status": "NO_FIX_REQUIRED",
            "fix": None,
            "reason": (
                "PayTrace has no active or historical root-cause hypothesis "
                "that requires a test-lab fix."
            ),
        }

    hypothesis_code = primary.get("code")
    fix = FIX_LIBRARY.get(hypothesis_code)

    if not fix:
        return {
            "order_id": order_id,
            "status": "NO_FIX_AVAILABLE",
            "hypothesis": hypothesis_code,
            "fix": None,
        }

    return {
        "order_id": order_id,
        "status": "FIX_AVAILABLE",
        "incident_status": investigation.get("status"),
        "hypothesis": {
            "code": hypothesis_code,
            "title": primary.get("title"),
            "confidence_label": primary.get("confidence_label"),
            "failure_boundary": primary.get("failure_boundary"),
        },
        "fix": fix,
    }
