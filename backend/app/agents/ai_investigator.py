import json
import os
import traceback

from app.agents.investigator import investigate_order

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.7-flash")


def _fallback(inv):
    primary = inv.get("primary_hypothesis")
    if inv.get("status") == "HEALTHY":
        return "PayTrace found no active incident. Provider and merchant state are consistent."
    if not primary:
        return "PayTrace does not yet have enough verified evidence for a root-cause explanation."
    return (
        f"Primary hypothesis: {primary.get('title')}. "
        f"Confidence: {primary.get('confidence_label')}. "
        f"Failure boundary: {primary.get('failure_boundary')}."
    )


def generate_ai_investigation(order_id: str):
    inv = investigate_order(order_id)

    if inv.get("status") == "NOT_FOUND":
        return {
            "order_id": order_id,
            "ai_status": "NOT_RUN",
            "provider": "GEMINI",
            "reason": "Order not found.",
            "deterministic_investigation": inv,
        }

    primary = inv.get("primary_hypothesis")

    if inv.get("status") == "HEALTHY":
        return {
            "order_id": order_id,
            "ai_status": "SKIPPED",
            "provider": "GEMINI",
            "reason": "No active incident requires generative explanation.",
            "explanation": _fallback(inv),
            "deterministic_investigation": inv,
        }

    if not primary:
        return {
            "order_id": order_id,
            "ai_status": "SKIPPED",
            "provider": "GEMINI",
            "reason": "Insufficient deterministic evidence for AI explanation.",
            "explanation": _fallback(inv),
            "deterministic_investigation": inv,
        }

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {
            "order_id": order_id,
            "ai_status": "DISABLED",
            "provider": "GEMINI",
            "reason": "GEMINI_API_KEY is not configured.",
            "explanation": _fallback(inv),
            "deterministic_investigation": inv,
        }

    payload = {
        "order_id": inv.get("order_id"),
        "facts": inv.get("facts"),
        "primary_hypothesis": inv.get("primary_hypothesis"),
        "alternative_hypotheses": inv.get("hypotheses", [])[1:],
        "evidence": inv.get("evidence"),
    }

    prompt = f"""
You are PayTrace's AI incident investigator for Razorpay test-mode payments.

Use ONLY the verified JSON below. Never invent payment states, logs, IDs,
timestamps, HTTP responses, customer facts, or Razorpay behavior.
Do not override deterministic PayTrace state.
Separate facts from hypotheses.
Do not claim a production fix has been applied.
Do not recommend moving, charging, or refunding real money.

Return a concise technical report with exactly these headings:
Incident Summary
Most Likely Root Cause
Why PayTrace Thinks This
Failure Boundary
Reproduction Plan
Fix Direction
Confidence / Uncertainty

VERIFIED PAYTRACE EVIDENCE:
{json.dumps(payload, indent=2)}
"""

    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=DEFAULT_MODEL,
            contents=prompt,
        )

        text = (response.text or "").strip()
        if not text:
            raise RuntimeError("Gemini returned an empty explanation.")

        return {
            "order_id": order_id,
            "ai_status": "GENERATED",
            "provider": "GEMINI",
            "model": DEFAULT_MODEL,
            "explanation": text,
            "deterministic_investigation": inv,
        }

    except Exception as error:
        print("\n========== PAYTRACE GEMINI ERROR ==========")
        print(f"Error type: {type(error).__name__}")
        print(f"Error: {error}")
        traceback.print_exc()
        print("===========================================\n")

        return {
            "order_id": order_id,
            "ai_status": "DEGRADED",
            "provider": "GEMINI",
            "model": DEFAULT_MODEL,
            "reason": "Gemini explanation failed. Deterministic PayTrace investigation remains available.",
            "error_type": type(error).__name__,
            "explanation": _fallback(inv),
            "deterministic_investigation": inv,
        }
