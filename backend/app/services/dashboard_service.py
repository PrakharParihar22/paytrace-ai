from app.agents.fix_advisor import advise_fix
from app.agents.investigator import investigate_order
from app.engines.state_engine import analyze_order_state
from app.engines.timeline_engine import build_timeline
from app.services.order_service import get_all_orders, get_order
from app.services.reliability_service import get_latest_reliability_suite


def _timeline_event(timeline: dict, event_type: str):
    events = timeline.get("timeline", [])

    for event in reversed(events):
        if event.get("type") == event_type:
            return event

    return None


def build_order_report(order_id: str):
    order = get_order(order_id)

    if not order:
        return None

    timeline = build_timeline(order_id)
    analysis = analyze_order_state(order_id)
    investigation = investigate_order(order_id)
    fix = advise_fix(order_id)

    return {
        "order": order,
        "timeline": timeline,
        "analysis": analysis,
        "investigation": investigation,
        "fix": fix,
        "latest_reproduction": _timeline_event(
            timeline,
            "REPRODUCTION_RUN",
        ),
        "latest_regression": _timeline_event(
            timeline,
            "REGRESSION_RUN",
        ),
    }


def build_dashboard_summary():
    orders = get_all_orders()

    summary = {
        "total_orders": len(orders),
        "healthy": 0,
        "active_incidents": 0,
        "recovered": 0,
        "pending": 0,
        "reproduced": 0,
        "verified_fixes": 0,
    }

    recent = []

    for order in orders:
        order_id = order["id"]
        investigation = investigate_order(order_id)
        timeline = build_timeline(order_id)

        status = investigation.get("status")

        if status == "RECOVERED":
            summary["recovered"] += 1
        elif status == "INVESTIGATED":
            summary["active_incidents"] += 1
        elif status == "HEALTHY":
            summary["healthy"] += 1
        else:
            summary["pending"] += 1

        reproduction = _timeline_event(
            timeline,
            "REPRODUCTION_RUN",
        )

        regression = _timeline_event(
            timeline,
            "REGRESSION_RUN",
        )

        if (
            reproduction
            and reproduction.get("status") == "REPRODUCED"
        ):
            summary["reproduced"] += 1

        if (
            regression
            and regression.get("status") == "PASS"
        ):
            summary["verified_fixes"] += 1

        primary = investigation.get("primary_hypothesis") or {}

        recent.append({
            "order_id": order_id,
            "payment_id": order.get("payment_id"),
            "amount": order.get("amount"),
            "currency": order.get("currency"),
            "merchant_state": order.get("merchant_state"),
            "status": status,
            "incident_type": primary.get("code"),
            "severity": (
                "HIGH"
                if primary.get("code")
                else None
            ),
            "confidence": primary.get("confidence"),
            "failure_boundary": primary.get(
                "failure_boundary"
            ),
            "updated_at": order.get("updated_at"),
            "reproduction": (
                reproduction.get("status")
                if reproduction
                else None
            ),
            "fix_verification": (
                regression.get("status")
                if regression
                else None
            ),
        })

    recent.sort(
        key=lambda item: item.get("updated_at") or "",
        reverse=True,
    )

    # Current convergence rate measures only orders with meaningful
    # provider/merchant outcome evidence. Pending development records are
    # excluded so incomplete experiments do not distort the demo metric.
    resolved_now = summary["healthy"] + summary["recovered"]
    evaluated_orders = (
        summary["healthy"]
        + summary["recovered"]
        + summary["active_incidents"]
    )

    if evaluated_orders:
        current_convergence_rate = round(
            resolved_now / evaluated_orders * 100,
            1,
        )
    else:
        current_convergence_rate = 100.0

    latest_suite = get_latest_reliability_suite()

    reliability_score = (
        latest_suite.get("score")
        if latest_suite
        else None
    )

    reliability_passed = (
        latest_suite.get("passed")
        if latest_suite
        else 0
    )

    reliability_total = (
        latest_suite.get("total")
        if latest_suite
        else 0
    )

    return {
        "summary": summary,
        "current_health_rate": current_convergence_rate,
        "current_convergence_rate": current_convergence_rate,
        "evaluated_orders": evaluated_orders,
        "reliability_score": reliability_score,
        "reliability_passed": reliability_passed,
        "reliability_total": reliability_total,
        "reliability_last_run": (
            latest_suite.get("executed_at")
            if latest_suite
            else None
        ),
        "recent_orders": recent[:12],
    }
