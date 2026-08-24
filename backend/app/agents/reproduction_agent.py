from app.agents.investigator import investigate_order
from app.engines.reproduction_engine import (
    replay_webhook_handler_failure,
    unsupported_reproduction,
)


def build_reproduction_plan(order_id: str):
    investigation = investigate_order(order_id)

    if investigation.get("status") == "NOT_FOUND":
        return {
            "order_id": order_id,
            "status": "NOT_FOUND",
            "executable": False,
        }

    primary = investigation.get("primary_hypothesis")

    if not primary:
        return {
            "order_id": order_id,
            "status": "NO_REPRODUCTION_NEEDED",
            "executable": False,
            "reason": (
                "PayTrace has no active root-cause hypothesis that requires "
                "reproduction."
            ),
        }

    code = primary.get("code")

    executable = code == "WEBHOOK_HANDLER_FAILURE"

    return {
        "order_id": order_id,
        "status": "READY" if executable else "PLAN_ONLY",
        "executable": executable,
        "hypothesis": {
            "code": code,
            "title": primary.get("title"),
            "failure_boundary": primary.get("failure_boundary"),
            "confidence_label": primary.get("confidence_label"),
        },
        "test_plan": primary.get("recommended_reproduction", []),
        "execution_mode": (
            "ISOLATED_FAULT_REPLAY"
            if executable
            else "NOT_IMPLEMENTED_IN_CHECKPOINT_7"
        ),
        "safety": {
            "real_money": False,
            "production_changes": False,
            "external_customer_contact": False,
            "description": (
                "Reproduction executes only inside the PayTrace test lab."
            ),
        },
    }


def reproduce_incident(order_id: str):
    investigation = investigate_order(order_id)

    if investigation.get("status") == "NOT_FOUND":
        return {
            "order_id": order_id,
            "status": "NOT_FOUND",
            "result": "NOT_RUN",
        }

    primary = investigation.get("primary_hypothesis")

    if not primary:
        return {
            "order_id": order_id,
            "status": "NO_ACTIVE_HYPOTHESIS",
            "result": "NOT_RUN",
            "reason": (
                "PayTrace does not have a reproducible active root-cause "
                "hypothesis for this order."
            ),
        }

    hypothesis_code = primary.get("code")

    if hypothesis_code == "WEBHOOK_HANDLER_FAILURE":
        run = replay_webhook_handler_failure(
            order_id=order_id,
            investigation=investigation,
        )

        return {
            "order_id": order_id,
            "status": "COMPLETED",
            "primary_hypothesis": hypothesis_code,
            "failure_boundary": primary.get("failure_boundary"),
            "reproduction": run,
        }

    return {
        "order_id": order_id,
        "status": "COMPLETED",
        "primary_hypothesis": hypothesis_code,
        "failure_boundary": primary.get("failure_boundary"),
        "reproduction": unsupported_reproduction(
            order_id,
            hypothesis_code,
        ),
    }
