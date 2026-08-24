# PayTrace AI — Security Checklist

Before publishing or submitting the repository:

- [ ] `backend/.env` is ignored by Git.
- [ ] `frontend/.env` is ignored by Git.
- [ ] No Razorpay secret key is present in frontend code.
- [ ] No webhook secret is present in frontend code.
- [ ] No Gemini/OpenAI API key is committed.
- [ ] `.venv/` is not committed.
- [ ] `node_modules/` is not committed.
- [ ] Local SQLite/database files are not committed.
- [ ] Runtime complaint/reliability JSON is not committed unless intentionally sanitized.
- [ ] Razorpay webhook signature verification remains enabled.
- [ ] Checkout payment signature verification remains enabled.
- [ ] Test Mode is clearly identified in the UI and documentation.
- [ ] `CORS_ORIGINS` is restricted to known frontend origins when hosted.
- [ ] Public screenshots do not expose secret values.
- [ ] Exported incident PDFs contain test identifiers only.
- [ ] Production mutation/refund/charge actions remain disabled.

## Secret ownership

### Backend only

```text
RAZORPAY_KEY_SECRET
RAZORPAY_WEBHOOK_SECRET
GEMINI_API_KEY
```

### Safe to expose

```text
Razorpay Test Mode key ID
VITE_API_URL
public zrok URL
```

Even safe-to-expose values should still be clearly associated with Test Mode.
