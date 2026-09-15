// Ledger & Co. — API base URL configuration.
//
// IMPORTANT: change the default below to your deployed/ngrok Django backend
// URL before (or after) deploying to Vercel. No trailing slash.
//
// Edit the trusted default for deployment. Query-string overrides are disabled.
(function () {
    // Configure this trusted origin when deploying. URL query parameters must never
    // choose where the browser sends passwords and authentication tokens.
    const DEFAULT_API_BASE_URL = "http://localhost:8000";
    window.API_BASE_URL = DEFAULT_API_BASE_URL;
    localStorage.removeItem('ledgerco_api_base');
    window.STORE_CURRENCY = 'USD';
    window.PAYMENT_PROVIDERS = {};
    window.StoreReady = fetch(`${window.API_BASE_URL}/api/payments/config/`, {
        headers: { 'ngrok-skip-browser-warning': 'true' },
    }).then(response => {
        if (!response.ok) throw new Error('Checkout configuration unavailable.');
        return response.json();
    }).then(config => {
        window.STORE_CURRENCY = config.currency;
        window.PAYMENT_PROVIDERS = config.providers;
    }).catch(() => { window.STORE_CONFIG_ERROR = true; });
})();
