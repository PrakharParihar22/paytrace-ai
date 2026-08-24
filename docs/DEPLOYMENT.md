# PayTrace AI — Deployment & GitHub Readiness

## Goal

Prepare the Buildathon repository so it is reproducible, does not expose secrets, and can move from local development to a hosted frontend/backend later.

---

## 1. Secrets

Create:

```text
backend/.env
```

from:

```text
backend/.env.example
```

Never commit the real `.env`.

Required backend values:

```env
RAZORPAY_KEY_ID=...
RAZORPAY_KEY_SECRET=...
RAZORPAY_WEBHOOK_SECRET=...
```

Optional:

```env
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.7-flash
```

PayTrace core investigation works without Gemini.

---

## 2. Frontend API URL

The frontend now reads:

```text
VITE_API_URL
```

from the Vite environment.

Local default:

```env
VITE_API_URL=http://127.0.0.1:8000
```

For a hosted backend:

```env
VITE_API_URL=https://your-api-host.example.com
```

### Security warning

Everything beginning with `VITE_` becomes visible in browser JavaScript.

Never place:

```text
RAZORPAY_KEY_SECRET
RAZORPAY_WEBHOOK_SECRET
GEMINI_API_KEY
```

in the frontend environment.

---

## 3. Backend CORS

FastAPI now reads a comma-separated environment variable:

```env
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

For a deployed frontend:

```env
CORS_ORIGINS=https://your-paytrace-frontend.example.com
```

Do not use `*` with credentialed production requests unless there is a deliberate security reason.

---

## 4. First-time Windows setup

From the project root:

```powershell
.\scripts\setup_windows.ps1
```

This:

1. creates `backend/.venv`
2. installs backend requirements
3. installs frontend packages
4. creates local `.env` files from examples if missing

This avoids relying on manual PowerShell virtual-environment activation.

---

## 5. Start locally

Backend:

```powershell
.\scripts\start_backend.ps1
```

Frontend:

```powershell
.\scripts\start_frontend.ps1
```

Then:

```text
http://localhost:5173
```

---

## 6. zrok for Razorpay webhooks

Start:

```powershell
zrok2 share public localhost:8000 --headless
```

Verify:

```text
https://<CURRENT-ZROK-DOMAIN>/health
```

Then configure Razorpay Test Mode:

```text
https://<CURRENT-ZROK-DOMAIN>/api/webhooks/razorpay
```

Enable:

```text
payment.captured
order.paid
```

---

## 7. GitHub pre-push check

Run:

```powershell
git status
```

Make sure none of these are staged:

```text
backend/.env
frontend/.env
*.db
*.sqlite
*.sqlite3
node_modules/
.venv/
```

Also search for accidentally committed secrets:

```powershell
git grep -n "RAZORPAY_KEY_SECRET"
git grep -n "RAZORPAY_WEBHOOK_SECRET"
git grep -n "GEMINI_API_KEY"
```

Seeing the variable names in `.env.example` or documentation is fine.

Seeing real values is not.

---

## 8. Recommended repository layout

```text
PAYTRACE AI/
├── .gitignore
├── README.md
├── backend/
│   ├── .env.example
│   ├── requirements.txt
│   ├── requirements-ai.txt
│   └── app/
├── frontend/
│   ├── .env.example
│   ├── package.json
│   └── src/
├── docs/
│   ├── ARCHITECTURE.md
│   ├── API_REFERENCE.md
│   ├── DEMO_GUIDE.md
│   └── DEPLOYMENT.md
└── scripts/
    ├── setup_windows.ps1
    ├── start_backend.ps1
    └── start_frontend.ps1
```

---

## 9. Production gaps to disclose

The Buildathon repository should not imply production readiness.

Current prototype limitations include:

- webhook idempotency registry is process-local
- complaint persistence uses JSON
- reliability history uses JSON
- zrok is a temporary public tunnel
- no authentication/RBAC
- no queue/dead-letter architecture
- no production reconciliation worker

These are future engineering steps, not hidden limitations.

---

## 10. Recommended hosting split later

A simple future deployment can use:

```text
Frontend:
static React/Vite host

Backend:
Python/FastAPI host

Webhook:
public HTTPS backend endpoint

Database:
managed PostgreSQL
```

For the Buildathon demo, local backend + Razorpay Test Mode + zrok is sufficient and keeps the reliability experiment controlled.
