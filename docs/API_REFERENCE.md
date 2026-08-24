# PayTrace AI — API Reference

Base local URL:

```text
http://127.0.0.1:8000
```

---

## Health

### `GET /health`
Backend health and current controlled fault state.

---

## Fault injection

### `GET /api/faults`
Returns current fault configuration.

### `POST /api/faults/webhook/enable`
Enables controlled failure for successful Razorpay webhook processing.

### `POST /api/faults/webhook/disable`
Disables controlled webhook failure.

---

## Razorpay payment workflow

### `POST /api/orders`

Creates a Razorpay Test Mode order.

Example:

```json
{
  "amount": 49900
}
```

Amounts use paise.

### `POST /api/payments/verify`

Verifies Razorpay checkout signature and fetches authoritative payment/order state.

```json
{
  "razorpay_payment_id": "pay_...",
  "razorpay_order_id": "order_...",
  "razorpay_signature": "..."
}
```

### `POST /api/webhooks/razorpay`

Receives and validates Razorpay webhooks.

Recommended Test Mode events:

```text
payment.captured
order.paid
```

---

## Orders

### `GET /api/orders`
Lists PayTrace orders.

### `GET /api/orders/{order_id}`
Returns one merchant-tracked order.

---

## Investigation

### `GET /api/orders/{order_id}/timeline`
Chronological evidence trail.

### `GET /api/orders/{order_id}/analysis`
Deterministic state-divergence analysis.

### `GET /api/orders/{order_id}/evidence`
Normalized evidence used during investigation.

### `GET /api/orders/{order_id}/investigation`
Deterministic root-cause hypotheses.

### `POST /api/orders/{order_id}/ai-investigation`
Optional generative explanation layer. External AI failure should degrade gracefully.

---

## Reproduction

### `GET /api/orders/{order_id}/reproduction/plan`
Returns the reproduction plan.

### `POST /api/orders/{order_id}/reproduce`
Replays the isolated incident signature and compares it with the original evidence.

---

## Fix and regression

### `GET /api/orders/{order_id}/fix`
Returns fix recommendations.

### `POST /api/orders/{order_id}/verify-fix`
Runs regression verification.

Supported successful verdict:

```text
FIX_VERIFIED
```

---

## Dashboard

### `GET /api/dashboard/summary`
Aggregates:

```text
total orders
healthy
active incidents
recovered
pending
reproduced
verified fixes
current convergence rate
reliability score
```

### `GET /api/orders/{order_id}/report`
Aggregated incident object including:

```text
order
timeline
analysis
investigation
fix
latest reproduction
latest regression
```

---

## PDF export

### `GET /api/orders/{order_id}/export/pdf`
Generates and downloads a professional incident PDF.

---

## Complaints

### `POST /api/complaints`

```json
{
  "message": "Customer says ₹499 was deducted but the merchant still shows pending.",
  "order_id": "order_...",
  "payment_id": null
}
```

### `GET /api/complaints`
Lists recent complaints.

### `GET /api/complaints/{complaint_id}`
Returns one complaint.

### `POST /api/complaints/{complaint_id}/recheck`
Re-runs complaint correlation against current evidence.

---

## Reliability suite

### `GET /api/reliability/suite`
Returns latest reliability-suite run.

### `POST /api/reliability/suite/run`
Executes the controlled reliability suite.

### `GET /api/reliability/history`
Returns recent suite history.

Current scenarios:

```text
NORMAL_PAYMENT
WEBHOOK_HANDLER_RETRY
DUPLICATE_WEBHOOK
OUT_OF_ORDER_EVENTS
DELAYED_WEBHOOK_RECOVERY
```
