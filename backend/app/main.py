from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path
import json
import os
import traceback
import uuid

import razorpay
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from app.db import init_db
from app.engines.state_engine import analyze_order_state
from app.engines.evidence_engine import build_evidence
from app.agents.investigator import investigate_order
from app.agents.ai_investigator import generate_ai_investigation
from app.agents.reproduction_agent import (
    build_reproduction_plan,
    reproduce_incident,
)
from app.agents.fix_advisor import advise_fix
from app.agents.complaint_intake import (
    get_complaint_record,
    get_recent_complaints,
    intake_complaint,
    recheck_complaint,
)
from app.agents.regression_agent import verify_fix
from app.engines.timeline_engine import build_timeline
from app.services.event_service import log_event
from app.services.dashboard_service import (
    build_dashboard_summary,
    build_order_report,
)
from app.services.reliability_service import (
    execute_reliability_suite,
    get_latest_reliability_suite,
    get_reliability_history,
)
from app.services.report_export_service import (
    generate_incident_report_pdf,
)
from app.services.order_service import (
    create_order_record,
    get_all_orders,
    get_order,
    update_order_state,
)
from app.services.webhook_guard import (
    is_webhook_processed,
    mark_webhook_processed,
)

BACKEND_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = BACKEND_DIR / ".env"

# Load the exact backend/.env file and let it override any stale
# CORS_ORIGINS value inherited from an older PowerShell/process.
load_dotenv(
    dotenv_path=ENV_FILE,
    override=True,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(
    title="PayTrace AI",
    description="Agentic Payment Reliability Engineer",
    version="1.3.2",
    lifespan=lifespan,
)

DEFAULT_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
]

CORS_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in os.getenv(
        "CORS_ORIGINS",
        ",".join(DEFAULT_CORS_ORIGINS),
    ).split(",")
    if origin.strip()
]

# Buildathon/local development can use a different Vite port if 5173
# is already occupied. This regex allows localhost / 127.0.0.1 on any
# local port while keeping deployed origins explicit via CORS_ORIGINS.
ALLOW_LOCALHOST_CORS = os.getenv(
    "ALLOW_LOCALHOST_CORS",
    "true",
).strip().lower() in {"1", "true", "yes", "on"}

LOCALHOST_ORIGIN_REGEX = (
    r"^https?://(?:localhost|127\.0\.0\.1)(?::\d+)?$"
    if ALLOW_LOCALHOST_CORS
    else None
)

print(
    "[CONFIG] Loaded env:",
    ENV_FILE,
)
print(
    "[CONFIG] CORS origins:",
    CORS_ORIGINS,
)
print(
    "[CONFIG] Localhost CORS:",
    ALLOW_LOCALHOST_CORS,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_origin_regex=LOCALHOST_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _is_allowed_origin(origin: str | None) -> bool:
    if not origin:
        return False

    normalized = origin.rstrip("/")

    if normalized in CORS_ORIGINS:
        return True

    if ALLOW_LOCALHOST_CORS:
        import re

        return bool(
            re.fullmatch(
                r"https?://(?:localhost|127\.0\.0\.1)(?::\d+)?",
                normalized,
            )
        )

    return False


@app.middleware("http")
async def ensure_local_dev_cors(request: Request, call_next):
    """
    Defensive CORS layer for local Buildathon development.

    Starlette CORSMiddleware remains the primary CORS implementation.
    This middleware guarantees that localhost/127.0.0.1 Vite origins
    receive the expected response headers even if a local environment,
    reload process, or middleware-version mismatch prevents the normal
    header from being attached.
    """
    origin = request.headers.get("origin")
    allowed = _is_allowed_origin(origin)

    # Handle browser preflight explicitly.
    if request.method == "OPTIONS" and allowed:
        response = Response(status_code=204)
    else:
        response = await call_next(request)

    if allowed:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "*"
        response.headers["Vary"] = "Origin"

    return response


RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET")

if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
    raise RuntimeError(
        "Razorpay credentials are missing. "
        "Add RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET to .env"
    )

if not RAZORPAY_WEBHOOK_SECRET:
    raise RuntimeError(
        "RAZORPAY_WEBHOOK_SECRET is missing from .env"
    )

razorpay_client = razorpay.Client(
    auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET)
)

FAULT_CONFIG = {
    "webhook_processing_failure": False,
}

SUCCESS_WEBHOOK_EVENTS = {
    "payment.captured",
    "order.paid",
}

class OrderRequest(BaseModel):
    amount: int

class PaymentVerificationRequest(BaseModel):
    razorpay_payment_id: str
    razorpay_order_id: str
    razorpay_signature: str


class ComplaintRequest(BaseModel):
    message: str
    order_id: str | None = None
    payment_id: str | None = None

@app.get("/")
def root():
    return {
        "project": "PayTrace AI",
        "status": "running",
        "version": "1.3.2",
        "fault_mode": FAULT_CONFIG,
    }

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "fault_mode": FAULT_CONFIG,
    }

@app.get("/api/faults")
def get_faults():
    return {"faults": FAULT_CONFIG}

@app.post("/api/faults/webhook/enable")
def enable_webhook_fault():
    FAULT_CONFIG["webhook_processing_failure"] = True
    return {
        "success": True,
        "webhook_processing_failure": True,
        "message": (
            "Controlled webhook-processing failure is ENABLED. "
            "Successful payment webhooks will fail after evidence is recorded."
        ),
    }

@app.post("/api/faults/webhook/disable")
def disable_webhook_fault():
    FAULT_CONFIG["webhook_processing_failure"] = False
    return {
        "success": True,
        "webhook_processing_failure": False,
        "message": "Controlled webhook-processing failure is DISABLED.",
    }

@app.post("/api/webhooks/razorpay")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str = Header(None),
    x_razorpay_event_id: str = Header(None),
):
    try:
        raw_body = await request.body()

        if not x_razorpay_signature:
            raise HTTPException(
                status_code=400,
                detail="Missing Razorpay webhook signature",
            )

        try:
            razorpay_client.utility.verify_webhook_signature(
                raw_body.decode("utf-8"),
                x_razorpay_signature,
                RAZORPAY_WEBHOOK_SECRET,
            )
        except razorpay.errors.SignatureVerificationError:
            raise HTTPException(
                status_code=400,
                detail="Invalid Razorpay webhook signature",
            )

        payload = json.loads(raw_body.decode("utf-8"))
        event_name = payload.get("event")

        payment_entity = (
            payload.get("payload", {})
            .get("payment", {})
            .get("entity", {})
        )

        order_entity = (
            payload.get("payload", {})
            .get("order", {})
            .get("entity", {})
        )

        payment_id = payment_entity.get("id")
        order_id = payment_entity.get("order_id") or order_entity.get("id")

        if not order_id:
            return {
                "success": True,
                "message": "Webhook received but no order id was found.",
            }

        stored_order = get_order(order_id)

        if not stored_order:
            return {
                "success": True,
                "message": "Webhook received for an order not managed by PayTrace.",
            }

        # Idempotency guard:
        # only events that were SUCCESSFULLY processed are marked complete.
        # Failed events remain retryable.
        if (
            x_razorpay_event_id
            and is_webhook_processed(
                x_razorpay_event_id
            )
        ):
            log_event(
                order_id=order_id,
                payment_id=payment_id,
                event_type="WEBHOOK_DUPLICATE_IGNORED",
                source="PAYTRACE_WEBHOOK_GUARD",
                status="IGNORED",
                message=(
                    f"Duplicate Razorpay webhook ignored: "
                    f"{event_name}"
                ),
                metadata={
                    "event_id": x_razorpay_event_id,
                    "trigger_event": event_name,
                },
            )

            current = get_order(order_id)

            return {
                "success": True,
                "event": event_name,
                "event_id": x_razorpay_event_id,
                "duplicate": True,
                "merchant_state": (
                    current["merchant_state"]
                    if current
                    else None
                ),
            }

        log_event(
            order_id=order_id,
            payment_id=payment_id,
            event_type=event_name or "UNKNOWN_WEBHOOK",
            source="RAZORPAY_WEBHOOK",
            status=payment_entity.get("status"),
            message=f"Webhook received: {event_name}",
            metadata={
                "event_id": x_razorpay_event_id,
                "payment_status": payment_entity.get("status"),
                "order_status": order_entity.get("status"),
            },
        )

        print(f"[WEBHOOK] {event_name} order={order_id} payment={payment_id}")

        if (
            FAULT_CONFIG["webhook_processing_failure"]
            and event_name in SUCCESS_WEBHOOK_EVENTS
        ):
            log_event(
                order_id=order_id,
                payment_id=payment_id,
                event_type="WEBHOOK_PROCESSING_FAILED",
                source="MERCHANT_WEBHOOK_HANDLER",
                status="FAILED",
                message=(
                    f"Injected merchant webhook-handler failure while "
                    f"processing {event_name}."
                ),
                metadata={
                    "fault_injected": True,
                    "trigger_event": event_name,
                    "event_id": x_razorpay_event_id,
                },
            )

            print(
                f"[FAULT] Injected webhook failure for "
                f"{event_name} order={order_id}"
            )

            raise HTTPException(
                status_code=500,
                detail="Injected merchant webhook processing failure",
            )

        if event_name in SUCCESS_WEBHOOK_EVENTS:
            current_order = get_order(order_id)

            if current_order and current_order["merchant_state"] != "PAID":
                update_order_state(
                    order_id=order_id,
                    merchant_state="PAID",
                    payment_id=payment_id,
                )

                log_event(
                    order_id=order_id,
                    payment_id=payment_id,
                    event_type="MERCHANT_STATE",
                    source="MERCHANT_WEBHOOK_HANDLER",
                    status="PAID",
                    message=(
                        f"Merchant order transitioned to PAID after "
                        f"processing {event_name}."
                    ),
                    metadata={
                        "trigger_event": event_name,
                        "event_id": x_razorpay_event_id,
                    },
                )

        # Mark complete only after business processing succeeds.
        # If processing raised HTTP 500 above, this line is never reached,
        # which keeps the event eligible for a genuine retry.
        mark_webhook_processed(
            x_razorpay_event_id
        )

        current = get_order(order_id)

        return {
            "success": True,
            "event": event_name,
            "event_id": x_razorpay_event_id,
            "duplicate": False,
            "merchant_state": current["merchant_state"] if current else None,
        }

    except HTTPException:
        raise

    except Exception as error:
        print("\n========== PAYTRACE WEBHOOK ERROR ==========")
        print(type(error).__name__)
        print(str(error))
        traceback.print_exc()
        print("============================================\n")

        raise HTTPException(
            status_code=500,
            detail=f"Webhook processing failed: {str(error)}",
        )

@app.post("/api/orders")
def create_order(request: OrderRequest):
    if request.amount <= 0:
        raise HTTPException(
            status_code=400,
            detail="Amount must be greater than zero",
        )

    try:
        receipt_id = f"paytrace_{uuid.uuid4().hex[:12]}"

        order_data = {
            "amount": request.amount,
            "currency": "INR",
            "receipt": receipt_id,
            "notes": {
                "project": "PayTrace AI",
                "environment": "test",
            },
        }

        razorpay_order = razorpay_client.order.create(data=order_data)

        create_order_record(
            order_id=razorpay_order["id"],
            amount=razorpay_order["amount"],
            currency=razorpay_order["currency"],
            receipt=receipt_id,
        )

        log_event(
            order_id=razorpay_order["id"],
            event_type="ORDER_CREATED",
            source="RAZORPAY",
            status=razorpay_order["status"],
            message="Razorpay test order created.",
            metadata={
                "amount": razorpay_order["amount"],
                "currency": razorpay_order["currency"],
            },
        )

        log_event(
            order_id=razorpay_order["id"],
            event_type="MERCHANT_STATE",
            source="MERCHANT",
            status="CREATED",
            message="Merchant order entered CREATED state.",
        )

        return {
            "success": True,
            "order": {
                "id": razorpay_order["id"],
                "amount": razorpay_order["amount"],
                "currency": razorpay_order["currency"],
                "receipt": razorpay_order.get("receipt"),
                "status": razorpay_order["status"],
            },
            "key_id": RAZORPAY_KEY_ID,
        }

    except HTTPException:
        raise

    except Exception as error:
        print("\n========== PAYTRACE ORDER ERROR ==========")
        print(f"Error type: {type(error).__name__}")
        print(f"Error: {error}")
        traceback.print_exc()
        print("==========================================\n")

        raise HTTPException(
            status_code=500,
            detail=f"Order creation failed: {str(error)}",
        )

@app.post("/api/payments/verify")
def verify_payment(request: PaymentVerificationRequest):
    try:
        stored_order = get_order(request.razorpay_order_id)

        if not stored_order:
            raise HTTPException(
                status_code=404,
                detail="Order does not exist in PayTrace merchant state",
            )

        stored_order_id = stored_order["id"]

        log_event(
            order_id=stored_order_id,
            payment_id=request.razorpay_payment_id,
            event_type="CHECKOUT_CALLBACK",
            source="FRONTEND",
            status="RECEIVED",
            message="Checkout success callback received.",
        )

        try:
            razorpay_client.utility.verify_payment_signature({
                "razorpay_order_id": stored_order_id,
                "razorpay_payment_id": request.razorpay_payment_id,
                "razorpay_signature": request.razorpay_signature,
            })
        except razorpay.errors.SignatureVerificationError:
            log_event(
                order_id=stored_order_id,
                payment_id=request.razorpay_payment_id,
                event_type="SIGNATURE_VERIFICATION",
                source="PAYTRACE",
                status="FAILED",
                message="Razorpay payment signature verification failed.",
            )
            raise HTTPException(
                status_code=400,
                detail="Invalid Razorpay payment signature",
            )

        log_event(
            order_id=stored_order_id,
            payment_id=request.razorpay_payment_id,
            event_type="SIGNATURE_VERIFICATION",
            source="PAYTRACE",
            status="VERIFIED",
            message="Razorpay payment signature verified successfully.",
        )

        payment = razorpay_client.payment.fetch(
            request.razorpay_payment_id
        )

        log_event(
            order_id=stored_order_id,
            payment_id=request.razorpay_payment_id,
            event_type="RAZORPAY_PAYMENT_STATE",
            source="RAZORPAY",
            status=payment.get("status"),
            message=f"Razorpay payment state is {payment.get('status')}.",
            metadata={
                "amount": payment.get("amount"),
                "method": payment.get("method"),
            },
        )

        razorpay_order = razorpay_client.order.fetch(
            stored_order_id
        )

        log_event(
            order_id=stored_order_id,
            payment_id=request.razorpay_payment_id,
            event_type="RAZORPAY_ORDER_STATE",
            source="RAZORPAY",
            status=razorpay_order.get("status"),
            message=f"Razorpay order state is {razorpay_order.get('status')}.",
        )

        if payment.get("order_id") != stored_order_id:
            raise HTTPException(
                status_code=400,
                detail="Payment does not belong to this order",
            )

        if payment.get("amount") != stored_order["amount"]:
            raise HTTPException(
                status_code=400,
                detail="Payment amount does not match merchant order",
            )

        provider_ready = (
            payment.get("status") == "captured"
            and razorpay_order.get("status") == "paid"
        )

        current_order = get_order(stored_order_id)
        current_merchant_state = current_order["merchant_state"]

        if current_merchant_state == "PAID":
            new_merchant_state = "PAID"
        else:
            new_merchant_state = "PAYMENT_VERIFIED"

            update_order_state(
                order_id=stored_order_id,
                merchant_state=new_merchant_state,
                payment_id=request.razorpay_payment_id,
            )

            log_event(
                order_id=stored_order_id,
                payment_id=request.razorpay_payment_id,
                event_type="MERCHANT_STATE",
                source="MERCHANT",
                status=new_merchant_state,
                message=(
                    "Checkout was verified. Merchant order is awaiting "
                    "successful webhook processing."
                ),
            )

        return {
            "success": True,
            "signature_verified": True,
            "payment": {
                "id": payment.get("id"),
                "status": payment.get("status"),
                "amount": payment.get("amount"),
                "method": payment.get("method"),
                "order_id": payment.get("order_id"),
            },
            "razorpay_order": {
                "id": razorpay_order.get("id"),
                "status": razorpay_order.get("status"),
                "amount": razorpay_order.get("amount"),
                "amount_paid": razorpay_order.get("amount_paid"),
                "amount_due": razorpay_order.get("amount_due"),
            },
            "merchant_state": new_merchant_state,
            "provider_ready": provider_ready,
            "ready_to_fulfill": (
                provider_ready and new_merchant_state == "PAID"
            ),
        }

    except HTTPException:
        raise

    except Exception as error:
        print("\n========== PAYTRACE VERIFY ERROR ==========")
        print(f"Error type: {type(error).__name__}")
        print(f"Error: {error}")
        traceback.print_exc()
        print("===========================================\n")

        raise HTTPException(
            status_code=500,
            detail=f"Payment verification failed: {str(error)}",
        )

@app.get("/api/orders")
def list_orders():
    return {"orders": get_all_orders()}

@app.get("/api/orders/{order_id}")
def order_details(order_id: str):
    order = get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

@app.get("/api/orders/{order_id}/timeline")
def order_timeline(order_id: str):
    order = get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return build_timeline(order_id)

@app.get("/api/orders/{order_id}/analysis")
def order_analysis(order_id: str):
    order = get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return analyze_order_state(order_id)


# --------------------------------------------------
# Evidence / Root Cause Investigation
# --------------------------------------------------

@app.get("/api/orders/{order_id}/evidence")
def order_evidence(order_id: str):
    order = get_order(order_id)

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Order not found",
        )

    return build_evidence(order_id)


@app.get("/api/orders/{order_id}/investigation")
def order_investigation(order_id: str):
    order = get_order(order_id)

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Order not found",
        )

    return investigate_order(order_id)


# --------------------------------------------------
# Generative AI Investigation
# --------------------------------------------------

@app.post("/api/orders/{order_id}/ai-investigation")
def ai_order_investigation(order_id: str):
    order = get_order(order_id)

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Order not found",
        )

    return generate_ai_investigation(order_id)


# --------------------------------------------------
# Incident Reproduction
# --------------------------------------------------

@app.get("/api/orders/{order_id}/reproduction/plan")
def order_reproduction_plan(order_id: str):
    order = get_order(order_id)

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Order not found",
        )

    return build_reproduction_plan(order_id)


@app.post("/api/orders/{order_id}/reproduce")
def order_reproduce(order_id: str):
    order = get_order(order_id)

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Order not found",
        )

    return reproduce_incident(order_id)


# --------------------------------------------------
# Fix Advisor + Regression Verification
# --------------------------------------------------

@app.get("/api/orders/{order_id}/fix")
def order_fix_advice(order_id: str):
    order = get_order(order_id)

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Order not found",
        )

    return advise_fix(order_id)


@app.post("/api/orders/{order_id}/verify-fix")
def order_verify_fix(order_id: str):
    order = get_order(order_id)

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Order not found",
        )

    return verify_fix(order_id)


# --------------------------------------------------
# Dashboard Aggregation
# --------------------------------------------------

@app.get("/api/dashboard/summary")
def dashboard_summary():
    return build_dashboard_summary()


@app.get("/api/orders/{order_id}/report")
def order_report(order_id: str):
    report = build_order_report(order_id)

    if not report:
        raise HTTPException(
            status_code=404,
            detail="Order not found",
        )

    return report


# --------------------------------------------------
# Complaint / Issue Intake
# --------------------------------------------------

@app.post("/api/complaints")
def create_complaint(
    request: ComplaintRequest,
):
    message = request.message.strip()

    if len(message) < 8:
        raise HTTPException(
            status_code=400,
            detail=(
                "Complaint message must contain "
                "enough detail to investigate."
            ),
        )

    return intake_complaint(
        message=message,
        order_id=request.order_id,
        payment_id=request.payment_id,
    )


@app.get("/api/complaints")
def complaints_list(
    limit: int = 50,
):
    return {
        "complaints": get_recent_complaints(
            limit=max(1, min(limit, 100))
        )
    }


@app.get("/api/complaints/{complaint_id}")
def complaint_details(
    complaint_id: str,
):
    complaint = get_complaint_record(
        complaint_id
    )

    if not complaint:
        raise HTTPException(
            status_code=404,
            detail="Complaint not found",
        )

    return complaint


@app.post("/api/complaints/{complaint_id}/recheck")
def complaint_recheck(
    complaint_id: str,
):
    complaint = recheck_complaint(
        complaint_id
    )

    if not complaint:
        raise HTTPException(
            status_code=404,
            detail="Complaint not found",
        )

    return complaint


# --------------------------------------------------
# Reliability Suite + Score
# --------------------------------------------------

@app.get("/api/reliability/suite")
def reliability_suite_status():
    return {
        "latest_run": (
            get_latest_reliability_suite()
        )
    }


@app.post("/api/reliability/suite/run")
def reliability_suite_run():
    return execute_reliability_suite()


@app.get("/api/reliability/history")
def reliability_suite_history(
    limit: int = 10,
):
    return {
        "history": get_reliability_history(
            limit=max(1, min(limit, 20))
        )
    }


# --------------------------------------------------
# Professional Incident Report Export
# --------------------------------------------------

@app.get("/api/orders/{order_id}/export/pdf")
def export_order_incident_pdf(order_id: str):
    pdf_bytes = generate_incident_report_pdf(order_id)

    if not pdf_bytes:
        raise HTTPException(
            status_code=404,
            detail="Order not found",
        )

    safe_order_id = "".join(
        character
        for character in order_id
        if character.isalnum() or character in {"_", "-"}
    )

    filename = f"PayTrace_Incident_{safe_order_id}.pdf"

    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{filename}"'
            )
        },
    )
