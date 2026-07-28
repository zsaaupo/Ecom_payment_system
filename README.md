# Ledger & Co. — Environment Configuration & Deployment Guide

This document provides the official environment configuration and deployment reference for the **Ledger & Co. E-Commerce Ordering & Payment System API**.

---

## 1. Environment Variables Reference (`.env`)

Create `.env` in the root of `ecommerce_project_api` by copying `.env.example`:

```bash
cp .env.example .env
```

### Complete Variable Reference Table

| Category | Key | Description / Recommended Value |
| :--- | :--- | :--- |
| **Django Core** | `DJANGO_SECRET_KEY` | Secret signing key (e.g. `django-insecure-xxxx...`) |
| | `DJANGO_DEBUG` | `True` for development/testing, `False` for live production |
| | `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,0.0.0.0,.ngrok-free.app,.ngrok-free.dev` |
| | `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://*.ngrok-free.app,https://*.ngrok-free.dev` |
| | `CORS_ALLOW_ALL_ORIGINS` | `True` (Allows Vercel frontend to query backend API) |
| | `FRONTEND_URL` | Base URL of your deployed frontend<br>`https://vercelfrontend-delta.vercel.app` |
| **Database & Cache** | `DJANGO_DB_DIR` | Leave blank for local dev (Docker sets to `/app/data`) |
| | `REDIS_URL` | Redis URL<br>Local: `redis://127.0.0.1:6379/1`<br>Docker: `redis://redis:6379/1` |
| | `CATEGORY_TREE_CACHE_TTL` | Category tree cache duration in seconds (default `3600`) |
| **Stripe Payment** | `STRIPE_SECRET_KEY` | Secret key starting with `sk_test_...` (Test) or `sk_live_...` (Live) |
| | `STRIPE_PUBLISHABLE_KEY` | Public key starting with `pk_test_...` (Test) or `pk_live_...` (Live) |
| | `STRIPE_WEBHOOK_SECRET` | Signing secret starting with `whsec_...` |
| **bKash Payment** | `BKASH_BASE_URL` | **Sandbox:** `https://tokenized.sandbox.bka.sh/v1.2.0-beta`<br>**Live:** `https://tokenized.pay.bka.sh/v1.2.0-beta` |
| | `BKASH_APP_KEY` | Merchant App Key from bKash portal |
| | `BKASH_APP_SECRET` | Merchant App Secret |
| | `BKASH_USERNAME` | Merchant API Username |
| | `BKASH_PASSWORD` | Merchant API Password |
| | `BKASH_CALLBACK_URL` | `https://<your-ngrok-domain>/api/payments/webhooks/bkash/` |

---

## 2. Payment Integrations Setup

### 2.1 Stripe Integration (Test + Live Mode)

1. **Credentials:** Get keys from [Stripe Dashboard](https://dashboard.stripe.com/apikeys). Toggle between **Test mode** and **Live mode**:
   - Test mode secret: `STRIPE_SECRET_KEY=sk_test_...`
   - Test mode public: `STRIPE_PUBLISHABLE_KEY=pk_test_...`
2. **Webhook Endpoint:**
   - **Local Testing (Stripe CLI):**
     ```bash
     stripe listen --forward-to localhost:8000/api/payments/webhooks/stripe/
     ```
     Copy the signing secret output (`whsec_...`) into `STRIPE_WEBHOOK_SECRET`.
   - **Production Webhook Endpoint:**
     Add endpoint in Stripe Dashboard: `https://<your-ngrok-domain>/api/payments/webhooks/stripe/`.
     Listen for events: `payment_intent.succeeded` and `payment_intent.payment_failed`.

### 2.2 bKash Integration (Sandbox + Live Mode)

1. **Sandbox Setup:** Obtain sandbox credentials from [bKash Developer Portal](https://developer.bka.sh/docs/sandbox-checkout).
2. **Live Production Setup:** Update `.env` with live credentials:
   ```env
   BKASH_BASE_URL=https://tokenized.pay.bka.sh/v1.2.0-beta
   BKASH_APP_KEY=your_live_app_key
   BKASH_APP_SECRET=your_live_app_secret
   BKASH_USERNAME=your_live_username
   BKASH_PASSWORD=your_live_password
   BKASH_CALLBACK_URL=https://<your-ngrok-domain>/api/payments/webhooks/bkash/
   ```
3. **Browser Redirect & Webhook Handling:**
   - Webhook endpoint: `/api/payments/webhooks/bkash/` (alias `/payments/bkash/callback/`).
   - Atomically updates order to `PAID` and reduces stock using `select_for_update()`.
   - Automatically redirects browser to `FRONTEND_URL` + `/order.html?id={orderID}`.

---

## 3. Local Tunneling via ngrok

Expose your local Django server or Docker container to the public internet:

```powershell
ngrok http 8000 --host-header=localhost:8000
```

> **Note:** Ensure `DJANGO_ALLOWED_HOSTS` includes `.ngrok-free.dev` and `CORS_ALLOW_ALL_ORIGINS=True` in `.env`.

---

## 4. Docker Deployment (Backend + Database + Redis)

1. **Start Stack:**
   ```powershell
   docker compose up --build -d
   ```
2. **Seed Initial Catalog & Admin User:**
   ```powershell
   docker compose exec backend python manage.py seed_data
   ```
3. **Container Architecture:**
   - **`ledgerco_backend`:** Gunicorn WSGI server serving Django API on port `8000`.
   - **`ledgerco_redis`:** Redis 7 container serving category tree cache on port `6379`.
   - **Persistent Volume Storage:** SQLite database file (`sqlite_data`), media uploads (`media_data`), and logs (`logs_data`).
