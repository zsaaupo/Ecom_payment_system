# Ledger & Co. — E-Commerce Ordering & Multi-Provider Payment System

A production-ready Django REST Framework backend with an integrated HTML5/CSS3/Vanilla JavaScript storefront served directly via Django's template engine and static asset pipeline. The system implements a robust ordering pipeline, concurrency-safe inventory reservation, hierarchical product categorization (DFS + Caching), and a multi-provider payment architecture using the **Strategy Pattern** supporting **Stripe** and **bKash Tokenized Checkout**.

---

## Table of Contents
1. [System Architecture & Design Patterns](#system-architecture--design-patterns)
2. [Key Features](#key-features)
3. [Sandbox Payment Test Credentials](#sandbox-payment-test-credentials)
   - [bKash Sandbox Test Wallets](#bkash-sandbox-test-wallets)
   - [Stripe Sandbox Test Cards](#stripe-sandbox-test-cards)
4. [Environment Configuration (.env)](#environment-configuration-env)
5. [Local Development Setup](#local-development-setup)
6. [Docker Deployment](#docker-deployment)
7. [PythonAnywhere Production Deployment](#pythonanywhere-production-deployment)
8. [REST API Reference](#rest-api-reference)
9. [Testing, QA & Concurrency Verification](#testing-qa--concurrency-verification)
10. [Scheduled Jobs & Payment Reconciliation](#scheduled-jobs--payment-reconciliation)

---

## System Architecture & Design Patterns

The project follows clean architectural principles and industry-standard design patterns:

- **Payment Strategy Pattern (`payments/strategies.py`)**:
  - `PaymentStrategy` (Abstract Interface): Defines `initiate()`, `confirm()`, `query()`, and `verify_webhook()`.
  - `StripePaymentStrategy` (Concrete Strategy): Handles Stripe PaymentIntents (test and live mode) with client secret handoff.
  - `BkashPaymentStrategy` (Concrete Strategy): Implements bKash Tokenized Checkout v1.2.0 (token grant, create payment, execute, status query).
  - `PaymentContext`: Decouples business logic from specific payment providers. Adding new gateways requires implementing a new strategy without modifying order workflows.
- **Concurrency & Inventory Protection (`orders/services.py`)**:
  - Pessimistic locking using Django's `select_for_update()` inside atomic database transactions (`transaction.atomic()`).
  - Strict inventory validation prevents race conditions and overselling during simultaneous checkouts.
  - Idempotency guards prevent duplicate order placement and double payments.
- **Hierarchical Category Tree (DFS + Caching) (`products/services.py`)**:
  - Self-referencing recursive parent-child category tree.
  - Rebuilt via Depth-First Search (DFS) algorithm with linear runtime.
  - Caching layer supports zero-dependency in-memory cache (`LocMemCache`) for local development, seamlessly upgradeable to Redis via `REDIS_URL`.

---

## Key Features

- **Authentication & User Management**: Custom user model, token-based authentication (`TokenAuthentication`), user registration, login, profile management, and order history.
- **Catalog & Inventory**: Products, categories, image handling, stock tracking, price management, search, and category tree endpoints.
- **Cart & Order Processing**: Session/localStorage client cart, atomic stock reservation upon order creation, order state machine (`pending` -> `paid` / `canceled`).
- **Payment Gateways**:
  - **Stripe**: Credit/debit card processing with 3D Secure / SCA support.
  - **bKash**: Tokenized checkout (grant token, execute, query, and callback verification).
- **Responsive Storefront**: Clean, modern interface written in Vanilla JS and CSS without external bulky UI frameworks.

---

## Sandbox Payment Test Credentials

### bKash Sandbox Test Wallets

To test bKash payments, ensure `STORE_CURRENCY=BDT` is set in your `.env` file (bKash strictly requires BDT).

| Field | Sandbox Test Value |
| --- | --- |
| **Sandbox Portal / Base URL** | `https://tokenized.sandbox.bka.sh/v1.2.0-beta` |
| **Merchant App Key** | Set in `.env` (`BKASH_APP_KEY`) |
| **Merchant App Secret** | Set in `.env` (`BKASH_APP_SECRET`) |
| **Merchant Username** | Set in `.env` (`BKASH_USERNAME`) |
| **Merchant Password** | Set in `.env` (`BKASH_PASSWORD`) |
| **Verification Code (OTP)** | **`123456`** |
| **PIN** | **`12121`** |

#### Approved Sandbox Test Wallet Numbers
Use any of the following 11-digit numbers during checkout on the bKash payment screen:

| # | Test Wallet Number | Network / Operator | Purpose |
| :---: | :---: | :---: | :---: |
| **1** | **`01770618575`** | Grameenphone | Sandbox Customer Checkout |
| **2** | **`01929918378`** | Banglalink | Sandbox Customer Checkout |
| **3** | **`01770618576`** | Grameenphone | Sandbox Customer Checkout |
| **4** | **`01877722345`** | Robi | Sandbox Customer Checkout |
| **5** | **`01619777282`** | Airtel | Sandbox Customer Checkout |
| **6** | **`01619777283`** | Airtel | Sandbox Customer Checkout |

#### bKash Checkout Flow:
1. Select **bKash** on the `/checkout.html` page and click **Place order & continue to payment**.
2. On the bKash hosted screen, input any wallet number from the table above (e.g. `01770618575`) and click **Confirm**.
3. Enter OTP: **`123456`** and click **Confirm**.
4. Enter PIN: **`12121`** and click **Confirm**.
5. bKash redirects to your callback URL, executes the payment, marks the order as **Paid**, and redirects back to the confirmation page.

---

### Stripe Sandbox Test Cards

Stripe is active when `STRIPE_SECRET_KEY` and `STRIPE_PUBLISHABLE_KEY` are provided. Supports orders in both `USD` and `BDT`.

| Field | Test Value | Notes |
| --- | --- | --- |
| **Card Number** | **`4242 4242 4242 4242`** | Standard successful test Visa card |
| **Expiration Date** | Any valid future date (e.g., `12/30`) | Must not be in the past |
| **CVC / CVV** | Any 3 digits (e.g., `123`) | Any 3 digits accepted |
| **Billing ZIP / Postal Code** | Any 5 digits (e.g., `12345`) | Any 5 digits accepted |

#### Additional Stripe Test Cards for Error Testing:
- `4000 0000 0000 0002`: Card declined (generic decline).
- `4000 0000 0000 0069`: Card declined (insufficient funds).
- `4000 0000 0000 0341`: 3D Secure / SCA authentication required.

---

## Environment Configuration (.env)

Create a `.env` file in the project root by copying `.env.example`:

```sh
cp .env.example .env
```

### Environment Variables Reference

| Variable | Description | Example / Recommended Value |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | Cryptographic signing secret | Generate with `python -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `DJANGO_DEBUG` | Django debug mode | `True` for dev, `False` for production |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated allowed hostnames | `localhost,127.0.0.1,0.0.0.0,.pythonanywhere.com` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Trusted origins for HTTPS forms/POSTs | `https://your-domain.com,https://your-id.ngrok-free.app` |
| `DJANGO_DB_DIR` | SQLite directory path | Leave blank for root (dev); `/app/data` for Docker |
| `CORS_ALLOW_ALL_ORIGINS` | CORS convenience toggle | `False` (or `True` if using a standalone dev server) |
| `FRONTEND_URL` | Frontend origin for payment redirects | Leave blank for same-origin server hosting |
| `STORE_CURRENCY` | Store currency (`USD` or `BDT`) | **`BDT`** (enables bKash + Stripe) or **`USD`** (Stripe only) |
| `REDIS_URL` | Redis connection URL | Leave blank for built-in `locmem` cache; or `redis://127.0.0.1:6379/1` |
| `CATEGORY_TREE_CACHE_TTL` | Category tree cache TTL in seconds | `3600` |
| `STRIPE_SECRET_KEY` | Stripe secret key | `sk_test_...` |
| `STRIPE_PUBLISHABLE_KEY` | Stripe publishable key | `pk_test_...` |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret | `whsec_...` (from Stripe CLI or dashboard) |
| `BKASH_BASE_URL` | bKash API base URL | `https://tokenized.sandbox.bka.sh/v1.2.0-beta` |
| `BKASH_APP_KEY` | bKash merchant sandbox app key | Provider credentials |
| `BKASH_APP_SECRET` | bKash merchant sandbox app secret | Provider credentials |
| `BKASH_USERNAME` | bKash merchant sandbox username | Provider credentials |
| `BKASH_PASSWORD` | bKash merchant sandbox password | Provider credentials |
| `BKASH_CALLBACK_URL` | Public callback URL for bKash redirect | `http://localhost:8000/api/payments/webhooks/bkash/` |

---

## Local Development Setup

### Prerequisites
- Python 3.12+
- Git

### Installation Steps

1. **Clone the repository and create virtual environment**:
   ```bash
   git clone <repo-url>
   cd Ecom_payment_system

   # Create virtual environment
   python -m venv venv

   # Activate virtual environment
   # Windows PowerShell:
   .\venv\Scripts\Activate.ps1
   # macOS / Linux:
   source venv/bin/activate
   ```

2. **Install dependencies**:
   ```bash
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables**:
   Copy `.env.example` to `.env` and configure your credentials.

4. **Initialize Database and Seed Catalog**:
   ```bash
   python manage.py migrate
   python manage.py seed_data
   ```

5. **Create an Administrator Account**:
   ```bash
   python manage.py createsuperuser
   ```

6. **Start the Development Server**:
   ```bash
   python manage.py runserver 127.0.0.1:8000
   ```

7. **Access the Application**:
   - **Storefront**: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
   - **REST API**: [http://127.0.0.1:8000/api/](http://127.0.0.1:8000/api/)
   - **Django Admin**: [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)

---

## Docker Deployment

The application includes container definitions for both the backend application and Redis caching.

1. **Build and start services**:
   ```bash
   docker compose up -d --build
   ```

2. **Run migrations and seed database in the container**:
   ```bash
   docker compose exec backend python manage.py migrate
   docker compose exec backend python manage.py seed_data
   ```

3. **View logs**:
   ```bash
   docker compose logs -f backend
   ```

4. **Stop services**:
   ```bash
   docker compose down
   ```

---

## PythonAnywhere Production Deployment

Both the Django backend and static frontend storefront run unified under the same domain.

1. **Clone repo on PythonAnywhere**:
   ```bash
   git clone <repo-url> /home/<username>/Ecom_payment_system
   ```

2. **Setup virtual environment**:
   ```bash
   mkvirtualenv ecom-venv --python=/usr/bin/python3.12
   cd /home/<username>/Ecom_payment_system
   pip install -r requirements.txt
   python manage.py migrate
   python manage.py seed_data
   python manage.py collectstatic --noinput
   ```

3. **Create `.env`** at `/home/<username>/Ecom_payment_system/.env`:
   - Set `DJANGO_DEBUG=False`
   - Set `DJANGO_ALLOWED_HOSTS=<username>.pythonanywhere.com`
   - Set `DJANGO_CSRF_TRUSTED_ORIGINS=https://<username>.pythonanywhere.com`
   - Set `BKASH_CALLBACK_URL=https://<username>.pythonanywhere.com/api/payments/webhooks/bkash/`
   - Leave `FRONTEND_URL=` blank (same origin)

4. **Web Tab Configuration**:
   - **Source directory**: `/home/<username>/Ecom_payment_system`
   - **Virtualenv**: `/home/<username>/.virtualenvs/ecom-venv`
   - **Static files**:
     - URL: `/static/` -> Directory: `/home/<username>/Ecom_payment_system/staticfiles`
     - URL: `/media/` -> Directory: `/home/<username>/Ecom_payment_system/media`
   - **WSGI file**: Configure `sys.path` and load `ecommerce.settings`.

5. Click **Reload**.

---

## REST API Reference

All API routes return JSON and require `Authorization: Token <token>` unless marked public.

### Authentication (`/api/auth/`)
| Endpoint | Method | Auth | Description |
| --- | :---: | :---: | --- |
| `/api/auth/register/` | POST | Public | Register customer account (`username`, `email`, `password`) |
| `/api/auth/login/` | POST | Public | Authenticate user and receive auth token |
| `/api/auth/logout/` | POST | Token | Invalidate current session/token |
| `/api/auth/profile/` | GET, PUT | Token | View or update customer profile |

### Products & Categories (`/api/products/`)
| Endpoint | Method | Auth | Description |
| --- | :---: | :---: | --- |
| `/api/products/` | GET | Public | Paginated product list with search and category filtering |
| `/api/products/{id}/` | GET | Public | Retrieve single product details |
| `/api/products/categories/` | GET | Public | List all product categories |
| `/api/products/categories/tree/` | GET | Public | Cached recursive DFS category tree structure |

### Orders (`/api/orders/`)
| Endpoint | Method | Auth | Description |
| --- | :---: | :---: | --- |
| `/api/orders/` | GET | Token | List authenticated user's order history |
| `/api/orders/` | POST | Token | Place new order with items; locks inventory atomically |
| `/api/orders/{id}/` | GET | Token | Retrieve order status and item summary |

### Payments (`/api/payments/`)
| Endpoint | Method | Auth | Description |
| --- | :---: | :---: | --- |
| `/api/payments/config/` | GET | Public | Provider availability (`stripe`, `bkash`) and store currency |
| `/api/payments/initiate/` | POST | Token | Initiate transaction for an order with chosen provider |
| `/api/payments/{id}/` | GET | Token | Check payment record status |
| `/api/payments/{id}/confirm/` | POST | Token | Confirm payment completion |
| `/api/payments/{id}/query/` | GET | Token | Query live provider gateway status |
| `/api/payments/webhooks/stripe/` | POST | Stripe Sig | Webhook endpoint for asynchronous Stripe events |
| `/api/payments/webhooks/bkash/` | GET, POST | Public | Callback/Webhook endpoint for bKash redirect verification |

---

## Testing, QA & Concurrency Verification

Run the test suite to verify unit tests, regression tests, and race-condition prevention:

```bash
# Run Django internal test suite
python manage.py test --noinput

# Verify system migrations and check integrity
python manage.py check
python manage.py makemigrations --check --dry-run

# Run Concurrency & Race Condition Verification
python qa/concurrency_check.py

# Run Frontend integration test suite
node --test qa/frontend.test.cjs

# Verify Python dependency tree
python -m pip check
```

---

## Scheduled Jobs & Payment Reconciliation

In case of network drops between customer browser redirects and gateway confirmations, run the payment reconciliation job:

```bash
# Reconciles pending payments against upstream Stripe and bKash APIs
python manage.py reconcile_payments
```

This command queries pending payment statuses directly from provider APIs, updates stale records, and releases expired inventory reservations. Can be scheduled via cron or Celery.
