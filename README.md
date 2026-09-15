# Ledger & Co. — E-commerce ordering and payments

Django REST API with a separate HTML/CSS/JavaScript storefront. Supports customer accounts,
catalog/category management, orders, Stripe, and bKash. SQLite is the default database;
Redis is optional for shared category caching.

## Run locally

Use Python 3.12 or newer. From the project root:

```sh
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux instead: source .venv/bin/activate
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py seed_data
python manage.py runserver 127.0.0.1:8000
```

The default configuration runs without a `.env` or external services. The seeder creates
sample products and categories; it no longer creates an administrator with a public password.
Create your administrator with `python manage.py createsuperuser`.

In a second terminal, serve the storefront:

```sh
python -m http.server 8080 --bind 127.0.0.1 --directory vercel_frontend
```

Open **http://localhost:8080**. The API runs at **http://localhost:8000/api/** and the
administration site at **http://localhost:8000/admin/**. Payment buttons remain unavailable
until provider credentials are configured. Product browsing, registration, login, and carts
work without payment credentials.

## Configuration

Copy `.env.example` to `.env` in the repository root and supply your settings. Restart the
backend after changing environment variables.

| Variable | Purpose |
| --- | --- |
| `DJANGO_SECRET_KEY` | Set a unique, long random value for any hosted deployment. |
| `DJANGO_DEBUG` | `True` locally; `False` when hosted. |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated backend hostnames, without schemes. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | HTTPS origins allowed to submit admin/session forms. |
| `DJANGO_DB_DIR` | Directory containing `db.sqlite3`; defaults to repository root. |
| `CORS_ALLOW_ALL_ORIGINS` | Development convenience. Set `False` when hosted. |
| `CORS_ALLOWED_ORIGINS` | Comma-separated trusted frontend origins for hosted use. |
| `FRONTEND_URL` | Storefront origin used by bKash browser redirects; default `http://localhost:8080`. |
| `STORE_CURRENCY` | `USD` by default, or `BDT`. See the currency rules below. |
| `REDIS_URL` | Blank for local memory cache; set for shared multi-worker caching. |
| `CATEGORY_TREE_CACHE_TTL` | Category cache lifetime in seconds, default 3600. |
| `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY` | Matching Stripe test or live keys. |
| `STRIPE_WEBHOOK_SECRET` | Signing secret for the configured Stripe webhook. |
| `BKASH_BASE_URL` | Provider API origin/path; sandbox default is in `.env.example`. |
| `BKASH_APP_KEY`, `BKASH_APP_SECRET`, `BKASH_USERNAME`, `BKASH_PASSWORD` | bKash merchant credentials. |
| `BKASH_CALLBACK_URL` | Public callback URL, either backend callback or frontend return page. |

The browser obtains the configured currency and available providers from
`GET /api/payments/config/`. No private credentials are returned there.

### Currency rules

Catalog prices use one store currency. Stripe charges the order's stored currency.
bKash accepts BDT orders only. The default sample catalog was priced/displayed in USD,
so bKash is unavailable until you deliberately configure a BDT catalog.

**Changing `STORE_CURRENCY` does not convert prices.** Reprice the catalog before changing
currencies. Existing orders retain their stored currency. Migration `orders.0003` labels
historical order amounts USD because that was the original storefront currency; existing
bKash transactions from before this fix need manual review because the original app charged
BDT while displaying USD. The migration cannot infer a correct exchange rate or refund history.

### Stripe setup

Set matching test keys and configure a webhook at `/api/payments/webhooks/stripe/` for:

- `payment_intent.succeeded`
- `payment_intent.payment_failed`
- `payment_intent.canceled`

For local webhook testing:

```sh
stripe listen --forward-to localhost:8000/api/payments/webhooks/stripe/
```

Use its signing secret as `STRIPE_WEBHOOK_SECRET`. A declined card attempt stays retryable
on the same PaymentIntent; a verified cancellation closes it. Initiation reuses the existing
payment and includes a Stripe idempotency key. Browser returns, queries, and webhooks share
the same order/stock transition logic.

### bKash setup

Use the provider's sandbox credentials and a public callback address. Choose either:

- `https://YOUR_BACKEND/api/payments/webhooks/bkash/` — backend redirects to `FRONTEND_URL`.
- `https://YOUR_FRONTEND/payment-bkash-return.html` — frontend calls the backend callback.

Browser parameters are untrusted. A cancellation/failure callback is checked with bKash;
success executes the payment. An uncertain execute response triggers a status query.
Provider outages leave payments retryable instead of recording an unverified failure.

## Stock and payment operations

- Order creation validates the entire basket and saves all lines or none.
- Payment initiation reserves available units, preventing competing orders from selling them.
- A successful payment consumes its reservation once. Repeated confirmations are harmless.
- A verified final failure/cancellation restores reserved units once.
- Old orders without reservations deduct all lines atomically at success. If stock is missing,
  the payment remains recorded as received and the order is flagged `needs_review`.
- Order/payment fields in the administrator cannot be edited to bypass these transitions.

Run `python manage.py reconcile_payments` to query pending payments and apply verified results.
Schedule this command in your deployment if webhook delivery is unreliable. **Pending or unknown
payments keep their stock reserved.** For abandoned Stripe sessions, cancel the PaymentIntent
in Stripe and reconcile (or receive its cancellation webhook). For bKash, reconcile after the
provider reports a final cancellation/expiry. Do not release stock based only on elapsed time:
the provider might already have accepted payment. Automatic refunding and provider-side session
cancellation are not implemented here.

The SQLite configuration uses IMMEDIATE transactions because SQLite ignores row-level
`select_for_update` locks. Provider initiation currently runs inside that transaction, so slow
provider calls serialize writes. This is appropriate for the existing small SQLite project;
high-throughput production use needs a separate reservation/job workflow and load testing.

## Tests

```sh
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test --noinput
python qa/concurrency_check.py
node --test qa/frontend.test.cjs
python -m pip check
```

The concurrency check creates and removes an isolated SQLite database outside the project
directory. Backend tests use Django's test database. Payment provider requests are mocked.
Frontend tests use Node's built-in runner; no npm installation is needed.

Optional known-vulnerability scan:

```sh
python -m pip install pip-audit
python -m pip_audit --cache-dir ../work/audit-cache
```

A GitHub Actions workflow runs backend, frontend, migration, and concurrency checks on pushes
and pull requests. It has been added locally; its hosted run remains to be verified after pushing.

## Hosting

### Backend with Docker

Create `.env` first, then run `docker compose up --build -d`. SQLite, media, and logs use
persistent volumes. Redis provides shared category caching. The image excludes `.env` and
local virtual environments. Static administrator assets are collected on startup and served
by WhiteNoise with debug disabled. Uploaded media needs a separate web server or object-storage
configuration in production; WhiteNoise serves application static files, not user uploads.

Use HTTPS, a real secret key, explicit allowed hosts/origins, debug disabled, and your provider
credentials. Check deployment-specific settings with `python manage.py check --deploy`.
The Docker image and real deployment have not been executed as part of this local QA run.

### Frontend with Vercel

Set `DEFAULT_API_BASE_URL` in `vercel_frontend/js/config.js` to the trusted HTTPS backend origin.
Deploy `vercel_frontend` as the Vercel project root, with framework preset **Other** and no build.
The old `?api=...` override was removed because a crafted link could redirect login credentials
and tokens to another server. Configure the backend URL in source before deploying.

Enable the frontend origin in backend CORS settings and set `FRONTEND_URL` accordingly.
Do not put provider secret keys in frontend files.
