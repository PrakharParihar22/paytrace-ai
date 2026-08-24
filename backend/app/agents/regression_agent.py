from app.agents.fix_advisor import advise_fix
from app.agents.reproduction_agent import reproduce_incident
from app.engines.regression_engine import run_webhook_fix_regression


def verify_fix(order_id: str):
    fix_advice = advise_fix(order_id)

    if fix_advice.get("status") != "FIX_AVAILABLE":
        return {
            "order_id": order_id,
            "status": "NOT_RUN",
            "reason": fix_advice.get("reason") or "No fix is available.",
            "fix_advice": fix_advice,
        }

    reproduction = reproduce_incident(order_id)

    reproduction_payload = reproduction.get("reproduction") or {}

    if (
        reproduction.get("status") != "COMPLETED"
        or reproduction_payload.get("result") != "REPRODUCED"
        or reproduction_payload.get("hypothesis_status") != "CONFIRMED"
    ):
        return {
            "order_id": order_id,
            "status": "NOT_RUN",
            "reason": (
                "PayTrace will not verify a fix until the original failure "
                "has been reproduced and the hypothesis confirmed."
            ),
            "reproduction": reproduction,
            "fix_advice": fix_advice,
        }

    hypothesis = reproduction.get("primary_hypothesis")

    if hypothesis != "WEBHOOK_HANDLER_FAILURE":
        return {
            "order_id": order_id,
            "status": "NOT_RUN",
            "reason": (
                f"No executable regression exists yet for {hypothesis}."
            ),
            "reproduction": reproduction,
            "fix_advice": fix_advice,
        }

    regression = run_webhook_fix_regression(
        order_id=order_id,
        reproduction_result=reproduction,
        fix_advice=fix_advice,
    )

    return {
        "order_id": order_id,
        "status": "COMPLETED",
        "hypothesis": hypothesis,
        "fix": fix_advice["fix"],
        "reproduction": {
            "result": reproduction_payload.get("result"),
            "hypothesis_status": reproduction_payload.get(
                "hypothesis_status"
            ),
            "incident_phase": reproduction_payload.get("incident_phase"),
        },
        "regression": regression,
        "final_verdict": (
            "FIX_VERIFIED"
            if regression.get("fix_status") == "VERIFIED"
            else "FIX_NOT_VERIFIED"
        ),
    }
