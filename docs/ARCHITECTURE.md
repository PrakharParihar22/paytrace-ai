# PayTrace AI — Architecture

## Architectural principle

PayTrace is built around one rule:

> **Financial truth must come from deterministic payment evidence.**

The system separates:

```text
Truth plane        → signatures, provider states, merchant states, events
Reasoning plane    → evidence correlation and root-cause hypotheses
Experiment plane   → safe reproduction and regression testing
Presentation plane → dashboard, audit trail, incident PDF
```

---

## High-level architecture

```mermaid
flowchart LR
    User["Engineer / Ops / Judge"]
    Merchant["Merchant State"]
    Razorpay["Razorpay Test Mode"]
    Tunnel["zrok Tunnel"]

    subgraph Frontend["React + Vite Dashboard"]
        Overview["Overview"]
        Incidents["Incident Workspace"]
        Complaints["Complaint Intake"]
        Lab["Reliability Lab"]
        Audit["Audit Trail"]
    end

    subgraph FastAPI["FastAPI Backend"]
        PaymentAPI["Order + Payment Verification"]
        Webhook["Webhook Handler"]
        Dashboard["Dashboard Service"]
        ComplaintAPI["Complaint API"]
        Export["PDF Export"]
    end

    subgraph Reliability["Reliability Core"]
        Timeline["Timeline Engine"]
        State["State Engine"]
        Evidence["Evidence Engine"]
        Investigator["Investigator"]
        Reproduce["Reproduction Agent"]
        Fix["Fix Advisor"]
        Regression["Regression Agent"]
        Suite["Reliability Suite"]
        Guard["Webhook Guard"]
    end

    DB[("SQLite")]
    ComplaintStore[("complaints.json")]
    SuiteStore[("reliability_suite.json")]

    User --> Frontend
    Lab --> PaymentAPI
    PaymentAPI --> Razorpay
    Razorpay --> Tunnel
    Tunnel --> Webhook
    Webhook --> Guard

    PaymentAPI --> DB
    Webhook --> DB
    Merchant --> DB

    DB --> Timeline
    Timeline --> State
    Timeline --> Evidence
    State --> Investigator
    Evidence --> Investigator

    Investigator --> Reproduce
    Investigator --> Fix
    Reproduce --> Regression
    Fix --> Regression

    Suite --> SuiteStore
    ComplaintAPI --> ComplaintStore

    Overview --> Dashboard
    Incidents --> Dashboard
    Audit --> Dashboard

    Dashboard --> Timeline
    Dashboard --> State
    Dashboard --> Investigator

    Incidents --> Export
```

---

## Payment-state model

Healthy merchant lifecycle:

```mermaid
stateDiagram-v2
    [*] --> CREATED
    CREATED --> PAYMENT_VERIFIED: Checkout signature verified
    PAYMENT_VERIFIED --> PAID: Successful webhook processed
    PAID --> [*]
```

The frontend checkout callback is **not** treated as the final merchant payment truth.

---

## Healthy payment sequence

```mermaid
sequenceDiagram
    participant U as User
    participant F as PayTrace Frontend
    participant B as FastAPI
    participant R as Razorpay
    participant W as Webhook Handler
    participant M as Merchant State

    U->>F: Run test payment
    F->>B: POST /api/orders
    B->>R: Create order
    R-->>B: order_created
    B-->>F: order + key_id

    U->>R: Complete Test Mode checkout
    R-->>F: payment_id + order_id + signature

    F->>B: POST /api/payments/verify
    B->>B: Verify payment signature
    B->>R: Fetch payment
    B->>R: Fetch order
    B->>M: PAYMENT_VERIFIED

    R->>W: payment.captured / order.paid
    W->>W: Verify webhook signature
    W->>M: PAID
    W-->>R: HTTP 2xx
```

---

## Controlled webhook failure

```mermaid
sequenceDiagram
    participant R as Razorpay
    participant W as PayTrace Webhook
    participant F as Fault Injector
    participant M as Merchant State
    participant I as Investigator

    R->>W: payment.captured
    W->>W: Signature valid
    W->>F: Controlled fault enabled?
    F-->>W: YES
    W->>W: Log WEBHOOK_PROCESSING_FAILED
    W-->>R: HTTP 500

    Note over R,M: Provider is paid, merchant is not PAID

    M-->>I: PAYMENT_VERIFIED
    W-->>I: Webhook received + processing failed
    I-->>I: WEBHOOK_HANDLER_FAILURE
```

Result:

```text
Provider:
payment_captured = true
order_paid       = true

Merchant:
PAYMENT_VERIFIED

Webhook:
received          = true
processing_failed = true

Incident:
STATE_DIVERGENCE
WEBHOOK_HANDLER_FAILURE
```

---

## Evidence model

Typical event types:

```text
ORDER_CREATED
MERCHANT_STATE
CHECKOUT_CALLBACK
SIGNATURE_VERIFICATION
RAZORPAY_PAYMENT_STATE
RAZORPAY_ORDER_STATE
payment.captured
order.paid
WEBHOOK_PROCESSING_FAILED
REPRODUCTION_RUN
REGRESSION_RUN
```

Each event may contain:

```text
sequence
timestamp
source
event type
status
payment_id
message
metadata
```

---

## Investigation architecture

```mermaid
flowchart LR
    Timeline["Event Timeline"] --> Evidence["Evidence Engine"]
    Timeline --> State["State Engine"]

    Evidence --> Investigator["Investigator"]
    State --> Investigator

    Investigator --> H1["WEBHOOK_HANDLER_FAILURE"]
    Investigator --> H2["WEBHOOK_NOT_RECEIVED"]
    Investigator --> H3["MERCHANT_STATE_WRITE_FAILURE"]
    Investigator --> H4["PENDING_ASYNC_PROCESSING"]
```

The investigator returns:

```text
primary hypothesis
confidence
failure boundary
supporting evidence
contradicting evidence
reproduction plan
incident phase
```

---

## Recovery-aware evidence

PayTrace distinguishes:

```text
ACTIVE INCIDENT
Provider paid
Merchant not PAID
Failure evidence exists
```

from:

```text
RECOVERED INCIDENT
Provider paid
Merchant PAID now
Historical failure evidence exists
```

This preserves post-incident truth even after provider retries repair the merchant state.

---

## Webhook idempotency

Important rule:

```text
event received ≠ event successfully processed
```

A failed event remains retryable:

```text
First attempt
    ↓
processing fails
    ↓
event remains retryable
    ↓
provider retries
    ↓
processing succeeds
    ↓
event marked processed
```

Current Buildathon guard is process-local; production should persist event IDs with a uniqueness constraint.

---

## Reproduction architecture

The Reproduction Agent does not initiate another real payment.

It replays the incident signature in an isolated reliability experiment.

```text
Expected:
provider_paid=true
webhook_processing_failed=true
merchant_paid=false

Replay:
provider_paid=true
webhook_processing_failed=true
merchant_paid=false

Result:
REPRODUCED
CONFIRMED
```

---

## Fix and regression

```mermaid
flowchart LR
    Incident["Confirmed Incident"] --> Advisor["Fix Advisor"]
    Advisor --> Patch["Safe Test Patch"]
    Patch --> Regression["Regression Engine"]
    Regression --> Before["Before Fix Signature"]
    Regression --> After["After Fix Signature"]
    Before --> Verdict["Compare"]
    After --> Verdict
    Verdict --> Verified["FIX_VERIFIED"]
```

---

## Complaint correlation

Correlation order:

```text
1. Exact order ID      → HIGH / 100%
2. Exact payment ID    → HIGH / 100%
3. Unique amount match → MEDIUM
4. Multiple matches    → NEEDS_CONFIRMATION
5. No reliable match   → UNRESOLVED
```

PayTrace does not silently guess when multiple orders match.

---

## Reliability score

Current scenario suite:

```text
NORMAL_PAYMENT
WEBHOOK_HANDLER_RETRY
DUPLICATE_WEBHOOK
OUT_OF_ORDER_EVENTS
DELAYED_WEBHOOK_RECOVERY
```

Each scenario executes assertions.

```text
passed scenarios / total scenarios × 100
```

This is a controlled-lab metric, not a production uptime claim.

---

## Generative AI boundary

If an external model provider fails:

```text
AI status = DEGRADED
```

but deterministic payment investigation continues.

---

## Storage

### SQLite
Core merchant/payment state and event persistence.

### complaints.json
Prototype complaint persistence.

### reliability_suite.json
Latest suite run plus limited history.

---

## Security and safety controls

- Razorpay checkout signature verification
- Razorpay webhook signature verification
- payment/order relationship validation
- amount validation
- Test Mode boundary
- controlled fault state
- no production code mutation
- no automatic refund or charge action

---

## Production evolution

A production version would likely add:

```text
PostgreSQL
Persistent webhook-event registry
Distributed locks / idempotency keys
Queue-backed webhook processing
Retry/dead-letter handling
Reconciliation workers
Authentication / RBAC
Secrets manager
Metrics and alerts
Provider adapters
```
