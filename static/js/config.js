// Ledger & Co. — API base URL configuration.
//
// Configured for same-origin Django hosting (PythonAnywhere / local runserver).
// Automatically uses the current origin so all /api/ calls route to the same Django server.
(function () {
    const DEFAULT_API_BASE_URL = (window.location && window.location.origin && window.location.origin !== "null")
        ? window.location.origin
        : "http://localhost:8000";
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
