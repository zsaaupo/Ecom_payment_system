# Ledger & Co. — Decoupled Frontend (Vercel)

A plain HTML/CSS/JS build of the same storefront, but with every page
talking to the Django backend purely over its REST API (`fetch`) instead
of Django server-rendering the templates. Deploy this on Vercel; keep the
Django backend running wherever you like (locally via ngrok, or any host).

No build step, no framework, no `npm install` — it's just static files.

## 1. Point it at your backend

Edit `js/config.js`:

```js
const DEFAULT_API_BASE_URL = "http://localhost:8000";
```

Change this to your backend's public URL (e.g. an ngrok URL, or wherever
you deploy the Django app), with **no trailing slash**.

You can also override it at runtime without editing code or redeploying —
useful while testing against different backends — by visiting any page
once with `?api=...`, e.g.:

```
https://your-frontend.vercel.app/?api=https://xxxx.ngrok-free.app
```

This is saved to `localStorage` and used from then on in that browser.

## 2. Configure the Django backend to accept this frontend

On the backend (see the main project's `.env`):

- `CORS_ALLOW_ALL_ORIGINS=True` is set by default, which already allows
  this frontend to call the API from any origin. To lock this down for a
  real deployment, switch to an explicit allow-list instead (edit
  `ecommerce/settings.py`: replace `CORS_ALLOW_ALL_ORIGINS` with
  `CORS_ALLOWED_ORIGINS = ["https://your-frontend.vercel.app"]`).
- `DJANGO_ALLOWED_HOSTS` must include the host you run the backend on
  (already includes `*.ngrok-free.app` etc. via `CSRF_TRUSTED_ORIGINS` if
  using ngrok).
- **bKash only:** set `BKASH_CALLBACK_URL` to this frontend's return page
  instead of the backend's own page, e.g.:
  ```
  BKASH_CALLBACK_URL=https://your-frontend.vercel.app/payment-bkash-return.html
  ```
  bKash redirects the customer's browser here after payment; this page's
  JS (`js/payment-bkash-return.js`) then calls the backend's existing
  `/api/payments/webhooks/bkash/` endpoint to finalize the order — no
  backend code changes needed, it's the same endpoint a server-to-server
  webhook would hit.
- **Stripe** needs no equivalent change — `stripe.confirmPayment()` runs
  entirely client-side against Stripe's API, using the `return_url` of
  the current page.

## 3. Deploy to Vercel

```bash
cd vercel-frontend
vercel           # first time: follow prompts, framework preset "Other"
vercel --prod    # subsequent deploys
```

Or connect this folder as the project root in the Vercel dashboard (Git
import → set "Root Directory" to this folder → Framework Preset: Other).
No build command or output directory overrides are needed.

## 4. How auth & cart work here (different from the Django-template version)

- **Auth:** uses DRF Token Authentication. On login/register, the token
  is stored in `localStorage` and sent as `Authorization: Token <token>`
  on every subsequent request (`js/api.js`). There's no shared session
  with the backend since the two run on different origins.
- **Cart:** lives in `localStorage` (`js/cart.js`), not a Django session
  (which wouldn't survive cross-origin anyway). It's only sent to the
  backend as a plain `items` list at checkout time, via the same
  `POST /api/orders/` endpoint the Postman collection exercises.

## 5. Pages

| Page | Purpose |
|---|---|
| `index.html` | Product listing — search, category filter, quick-add to cart |
| `product.html?id=` | Product detail + DFS-based related products |
| `cart.html` | Cart (localStorage) |
| `checkout.html` | Creates the order, then hands off to a provider |
| `payment-stripe.html` | Stripe.js Payment Element + confirmation |
| `payment-bkash.html` | Redirects to bKash's hosted checkout |
| `payment-bkash-return.html` | Where bKash redirects back to (set as `BKASH_CALLBACK_URL`) |
| `login.html` / `register.html` | Auth |
| `account.html` | Profile + recent orders |
| `orders.html` / `order.html?id=` | Order history / receipt |

## 6. Local testing without Vercel

Any static file server works:

```bash
cd vercel-frontend
python3 -m http.server 5500
```

Then visit `http://127.0.0.1:5500/` with the Django backend running on
`http://localhost:8000` (the default in `config.js`).
