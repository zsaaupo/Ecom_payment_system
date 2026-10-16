# Ledger & Co. — E-Commerce Ordering & Multi-Provider Payment System

> 🚀 **Live URL:** [https://paymentsystem.pythonanywhere.com/](https://paymentsystem.pythonanywhere.com/)

A production-ready Django REST Framework backend with an integrated HTML5/CSS3/Vanilla JavaScript storefront served directly via Django's template engine and static asset pipeline. The system implements a robust ordering pipeline, concurrency-safe inventory reservation, hierarchical product categorization (DFS + Caching), and a multi-provider payment architecture using the **Strategy Pattern** supporting **Stripe** and **bKash Tokenized Checkout**.

---

## Table of Contents
1. [Live Demo & Quick Testing Guide](#-live-demo--quick-testing-guide)
2. [Sandbox Payment Test Credentials](#sandbox-payment-test-credentials)
   - [bKash Sandbox Test Wallets](#bkash-sandbox-test-wallets)
   - [Stripe Sandbox Test Cards](#stripe-sandbox-test-cards)
3. [System Architecture & Design Patterns](#system-architecture--design-patterns)
4. [Key Features](#key-features)
5. [Environment Configuration (.env)](#environment-configuration-env)
6. [Local Development Setup](#local-development-setup)
7. [Docker Deployment](#docker-deployment)
8. [PythonAnywhere Production Deployment](#pythonanywhere-production-deployment)
9. [REST API Reference](#rest-api-reference)
10. [Testing, QA & Concurrency Verification](#testing-qa--concurrency-verification)
11. [Scheduled Jobs & Payment Reconciliation](#scheduled-jobs--payment-reconciliation)

---

## 🌐 Live Demo & Quick Testing Guide

You can test the complete end-to-end purchasing and payment flow directly on the live server:

1. **Visit the Live Storefront**: Open [https://paymentsystem.pythonanywhere.com/](https://paymentsystem.pythonanywhere.com/)
2. **Account Sign In / Register**:
   - Register a new customer account at [Register](https://paymentsystem.pythonanywhere.com/register.html) or sign in at [Login](https://paymentsystem.pythonanywhere.com/login.html).
3. **Add Items to Cart**:
   - Browse catalog products, view details, and click **Add to Cart**.
4. **Proceed to Checkout**:
   - Open [Cart](https://paymentsystem.pythonanywhere.com/cart.html) or go directly to [Checkout](https://paymentsystem.pythonanywhere.com/checkout.html).
5. **Select Payment Gateway**:
   - Choose either **bKash** or **Stripe** and use the bound test credentials below.

---

## Sandbox Payment Test Credentials

### bKash Sandbox Test Wallets

The live deployment at [paymentsystem.pythonanywhere.com](https://paymentsystem.pythonanywhere.com/) is configured with `STORE_CURRENCY=BDT` and connects to the official bKash Tokenized Checkout sandbox.

| Field | Sandbox Test Value |
| --- | --- |
| **Active Live Demo** | [https://paymentsystem.pythonanywhere.com/](https://paymentsystem.pythonanywhere.com/) |
| **Sandbox Gateway URL** | `https://tokenized.sandbox.bka.sh/v1.2.0-beta` |
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

#### Live bKash Checkout Flow:
1. Select **bKash** on [https://paymentsystem.pythonanywhere.com/checkout.html](https://paymentsystem.pythonanywhere.com/checkout.html) and click **Place order & continue to payment**.
2. On the bKash hosted sandbox screen, enter any test wallet number from above (e.g. `01770618575`) and click **Confirm**.
3. When prompted for OTP, enter: **`123456`** and click **Confirm**.
4. When prompted for PIN, enter: **`12121`** and click **Confirm**.
5. bKash automatically executes the transaction, redirects back to the live site callback, marks the order status as **Paid**, and presents the confirmed order invoice.

---

### Stripe Sandbox Test Cards

Stripe card payments are fully operational on the live site at [paymentsystem.pythonanywhere.com](https://paymentsystem.pythonanywhere.com/) via Stripe.js Elements.

| Field | Test Value | Notes |
| --- | --- | --- |
| **Card Number** | **`4242 4242 4242 4242`** | Standard successful test Visa card |
| **Expiration Date** | Any valid future date (e.g., `12/30`) | Any future month/year |
| **CVC / CVV** | Any 3 digits (e.g., `123`) | Any 3 digits accepted |
| **Billing ZIP / Postal Code** | Any 5 digits (e.g., `12345`) | Any 5 digits accepted |

#### Additional Stripe Test Cards for Scenario Testing:
- `4000 0000 0000 0002`: Card declined (generic decline testing).
- `4000 0000 0000 0069`: Card declined (insufficient funds testing).
- `4000 0000 0000 0341`: 3D Secure / SCA modal authentication required.

#### Live Stripe Checkout Flow:
1. Select **Stripe** on [https://paymentsystem.pythonanywhere.com/checkout.html](https://paymentsystem.pythonanywhere.com/checkout.html) and click **Place order & continue to payment**.
2. You will be routed to the secure Stripe card payment screen.
3. Enter Card Number **`4242 4242 4242 4242`**, any future expiration, and any 3-digit CVC.
4. Click **Pay**. Stripe verifies the PaymentIntent, transitions the order status to **Paid**, and redirects to the confirmation page.

---

## System Architecture & Design Patterns

The project follows clean architectural principles and industry-standard design patterns:

- **Payment Strategy Pattern (`payments/strategies.py`)**:
  - `PaymentStrategy` (Abstract Interface): Defines `initiate()`, `confirm()`, `query()`, and `verify_webhook()`.
  - `StripePaymentStrategy` (Concrete Strategy): Handles Stripe PaymentIntents (test and live mode) with client secret handoff and collision-proof idempotency hashing.
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
| `DJANGO_ALLOWED_HOSTS` | Comma-separated allowed hostnames | `paymentsystem.pythonanywhere.com,localhost,127.0.0.1` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Trusted origins for HTTPS forms/POSTs | `https://paymentsystem.pythonanywhere.com` |
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
| `BKASH_CALLBACK_URL` | Public callback URL for bKash redirect | `https://paymentsystem.pythonanywhere.com/api/payments/webhooks/bkash/` |

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

Both the Django backend and static frontend storefront run unified under `https://paymentsystem.pythonanywhere.com/`.

1. **Clone repo on PythonAnywhere**:
   ```bash
   git clone <repo-url> /home/paymentsystem/Ecom_payment_system
   ```

2. **Setup virtual environment**:
   ```bash
   mkvirtualenv ecom-venv --python=/usr/bin/python3.12
   cd /home/paymentsystem/Ecom_payment_system
   pip install -r requirements.txt
   python manage.py migrate
   python manage.py seed_data
   python manage.py collectstatic --noinput
   ```

3. **Create `.env`** at `/home/paymentsystem/Ecom_payment_system/.env`:
   ```env
   DJANGO_SECRET_KEY=your-generated-secret-key
   DJANGO_DEBUG=False
   DJANGO_ALLOWED_HOSTS=paymentsystem.pythonanywhere.com,localhost,127.0.0.1
   DJANGO_CSRF_TRUSTED_ORIGINS=https://paymentsystem.pythonanywhere.com
   BKASH_CALLBACK_URL=https://paymentsystem.pythonanywhere.com/api/payments/webhooks/bkash/
   FRONTEND_URL=
   STORE_CURRENCY=BDT
   ```

4. **Web Tab Configuration**:
   - **Source directory**: `/home/paymentsystem/Ecom_payment_system`
   - **Working directory**: `/home/paymentsystem/Ecom_payment_system`
   - **Virtualenv**: `/home/paymentsystem/.virtualenvs/ecom-venv`
   - **Static files mapping**:
     - URL: `/static/` -> Directory: `/home/paymentsystem/Ecom_payment_system/staticfiles`
     - URL: `/media/` -> Directory: `/home/paymentsystem/Ecom_payment_system/media`
   - **WSGI configuration file**:
     ```python
     import os
     import sys
     path = '/home/paymentsystem/Ecom_payment_system'
     if path not in sys.path:
         sys.path.append(path)
     os.environ['DJANGO_SETTINGS_MODULE'] = 'ecommerce.settings'
     from django.core.wsgi import get_wsgi_application
     application = get_wsgi_application()
     ```

5. Click **Reload paymentsystem.pythonanywhere.com**.

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
