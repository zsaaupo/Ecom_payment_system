# Storefront

Serve this directory using `python -m http.server 8080 --directory vercel_frontend` from the
repository root, then open http://localhost:8080.

Set the trusted backend origin in `js/config.js` before deploying. The default is
http://localhost:8000. Query-string backend overrides are intentionally unsupported.

The backend supplies currency and payment availability. See the [main README](../README.md)
for setup, payment configuration, testing, stock reservations, and Vercel deployment.
