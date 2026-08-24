# PayTrace AI — Buildathon Demo Guide

## Goal

Demonstrate:

```text
Detect → Diagnose → Reproduce → Fix → Verify
```

without using Swagger during the main presentation.

---

## Before judging

### 1. Start backend

```powershell
uvicorn app.main:app --reload
```

Expected:

```text
Uvicorn running on http://127.0.0.1:8000
Application startup complete.
```

Check:

```text
http://127.0.0.1:8000/health
```

### 2. Start frontend

```powershell
npm run dev
```

Open:

```text
http://localhost:5173
```

### 3. Start zrok

```powershell
zrok2 share public localhost:8000 --headless
```

Keep this terminal open.

Verify:

```text
https://<CURRENT-ZROK-DOMAIN>/health
```

Expected:

```json
{
  "status": "healthy",
  "fault_mode": {
    "webhook_processing_failure": false
  }
}
```

### 4. Configure Razorpay Test Mode webhook

Use:

```text
https://<CURRENT-ZROK-DOMAIN>/api/webhooks/razorpay
```

Enable:

```text
payment.captured
order.paid
```

Webhook secret must match:

```env
RAZORPAY_WEBHOOK_SECRET=
```

---

## Main live demo

### Step 1 — Open Reliability Lab

Show:

```text
Reliability Score: 100 / 100
5 / 5 executable scenarios passed
```

Say:

> This is not a production uptime claim. It means all five current controlled reliability scenarios pass.

### Step 2 — Run guided incident

Click:

```text
Run PayTrace Demo
```

Complete the ₹499 Razorpay Test Mode checkout.

### Step 3 — Let PayTrace continue

Expected:

```text
Inject webhook fault        PASS
Complete test payment       PASS
Detect divergence           PASS
Diagnose root cause         PASS
Reproduce failure           PASS
Verify fix                  PASS
```

Expected diagnosis:

```text
WEBHOOK_HANDLER_FAILURE
98% confidence
```

Expected verdict:

```text
FIX_VERIFIED
```

### Step 4 — Open Incident Workspace

Show:

```text
Provider Truth:
CAPTURED

Merchant Truth:
PAYMENT_VERIFIED / PAID

Root Cause:
WEBHOOK_HANDLER_FAILURE

Failure Boundary:
MERCHANT_WEBHOOK_PROCESSING

Confidence:
98%
```

Then show:

```text
Failure reproduced       VERIFIED
Hypothesis confirmed     VERIFIED
Regression passed        VERIFIED
Fix verified             VERIFIED
```

### Step 5 — Export incident report

Click:

```text
Export Incident PDF
```

Explain that the report contains payment states, evidence timeline, root cause, reproduction proof, fix direction, regression result, and reliability context.

---

## Optional complaint demo

Complaint:

> Customer says ₹499 was deducted but the merchant dashboard still shows the payment as pending.

Expected for a recovered incident:

```text
CORRELATED_RECOVERED
EXACT_ORDER_ID
100%

Provider paid:
YES

Merchant state:
PAID

State divergence:
NOT ACTIVE

Historical root cause:
WEBHOOK_HANDLER_FAILURE
```

---

## Backup plan

If diagnosis stalls:

1. Open `https://<CURRENT-ZROK-DOMAIN>/health`.
2. Confirm Razorpay uses the same current zrok domain.
3. Watch backend logs for:

```text
[WEBHOOK] payment.captured ...
[FAULT] Injected webhook failure ...
```

If no `[WEBHOOK]` appears, the webhook did not reach PayTrace.

---

## Suggested demo language

Opening:

> A payment provider can process a transaction correctly while the merchant still fails afterward. PayTrace investigates that reliability gap.

Before the demo:

> I'll intentionally create a merchant-side webhook failure in Razorpay Test Mode and let PayTrace investigate it.

During diagnosis:

> PayTrace does not use an LLM to decide payment truth. It uses verified provider and merchant evidence.

During reproduction:

> Instead of merely suggesting a cause, PayTrace replays the failure signature in an isolated lab.

During verification:

> The fix is not marked successful until the same scenario passes regression.

Closing:

> PayTrace turns a payment complaint into verified engineering evidence: detect, diagnose, reproduce, and prove the fix.
