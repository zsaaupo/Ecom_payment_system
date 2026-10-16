// Ledger & Co. — API client.
// Wraps fetch() against the Django REST API, attaching the auth token
// (DRF TokenAuthentication) when present, and normalizing errors.

const Auth = {
    getToken() { return localStorage.getItem("ledgerco_token"); },
    getUser() {
        const raw = localStorage.getItem("ledgerco_user");
        try { return raw ? JSON.parse(raw) : null; }
        catch { this.clearSession(); return null; }
    },
    setSession(token, user) {
        localStorage.setItem("ledgerco_token", token);
        localStorage.setItem("ledgerco_user", JSON.stringify(user));
    },
    clearSession() {
        localStorage.removeItem("ledgerco_token");
        localStorage.removeItem("ledgerco_user");
    },
    isAuthenticated() { return !!this.getToken(); },
    /** Redirects to login (preserving a return path) if not authenticated. Returns true if OK to proceed. */
    requireAuth() {
        if (this.isAuthenticated()) return true;
        const next = encodeURIComponent(window.location.pathname + window.location.search);
        window.location.href = `login.html?next=${next}`;
        return false;
    },
};

class ApiError extends Error {
    constructor(message, status, data) {
        super(message);
        this.status = status;
        this.data = data;
    }
}

async function apiFetch(path, { method = "GET", body, auth = true, query } = {}) {
    let url = `${window.API_BASE_URL}${path}`;
    if (query) {
        const qs = new URLSearchParams(Object.entries(query).filter(([, v]) => v !== undefined && v !== null && v !== ""));
        const qsString = qs.toString();
        if (qsString) url += (url.includes("?") ? "&" : "?") + qsString;
    }

    const headers = {
        "Content-Type": "application/json",
        "ngrok-skip-browser-warning": "true",
    };
    if (auth && Auth.getToken()) {
        headers["Authorization"] = `Token ${Auth.getToken()}`;
    }

    let response;
    try {
        response = await fetch(url, {
            method,
            headers,
            body: body !== undefined ? JSON.stringify(body) : undefined,
        });
    } catch (networkErr) {
        throw new ApiError(
            `Could not reach the backend at ${window.API_BASE_URL}. Is it running, and is the URL in js/config.js correct?`,
            0, null
        );
    }

    const contentType = response.headers.get("content-type") || "";
    const data = contentType.includes("application/json") ? await response.json().catch(() => null) : null;

    if (!response.ok) {
        const message = (data && (data.detail || JSON.stringify(data))) || `Request failed (${response.status})`;
        if (response.status === 401 && auth) {
            Auth.clearSession();
            Auth.requireAuth();
        }
        throw new ApiError(message, response.status, data);
    }
    return data;
}

const Api = {
    // --- Auth ---
    register(payload) { return apiFetch("/api/auth/register/", { method: "POST", body: payload, auth: false }); },
    login(username, password) { return apiFetch("/api/auth/login/", { method: "POST", body: { username, password }, auth: false }); },
    logout() { return apiFetch("/api/auth/logout/", { method: "POST" }); },
    getProfile() { return apiFetch("/api/auth/profile/"); },
    updateProfile(payload) { return apiFetch("/api/auth/profile/", { method: "PATCH", body: payload }); },

    // --- Products & categories ---
    listProducts({ q, category, page } = {}) {
        return apiFetch("/api/products/", { auth: false, query: { q, category, page } });
    },
    getProduct(id) { return apiFetch(`/api/products/${id}/`, { auth: false }); },
    getRelatedProducts(id) { return apiFetch(`/api/products/${id}/related/`, { auth: false }); },
    getCategoryTree() { return apiFetch("/api/products/categories/tree/", { auth: false }); },

    // --- Orders ---
    createOrder(items) { return apiFetch("/api/orders/", { method: "POST", body: { items } }); },
    listOrders(page = 1) { return apiFetch("/api/orders/", { query: { page } }); },
    getOrder(id) { return apiFetch(`/api/orders/${id}/`); },

    // --- Payments ---
    initiatePayment(orderId, provider) {
        return apiFetch("/api/payments/initiate/", { method: "POST", body: { order_id: orderId, provider } });
    },
    getPayment(id) { return apiFetch(`/api/payments/${id}/`); },
    confirmPayment(id, payload = {}) { return apiFetch(`/api/payments/${id}/confirm/`, { method: "POST", body: payload }); },
    queryPayment(id) { return apiFetch(`/api/payments/${id}/query/`); },
    /** Called from payment-bkash-return.html after bKash redirects the browser back. No auth needed - mirrors the server-to-server webhook. */
    bkashCallback(paymentId, status) {
        return apiFetch("/api/payments/webhooks/bkash/", { auth: false, query: { paymentID: paymentId, status } });
    },
};

async function continueToPayment(order, provider, clearCart = false) {
    const payment = await Api.initiatePayment(order.id, provider);
    let target;
    if (provider === 'stripe') {
        if (!payment.client_secret || !payment.publishable_key) throw new Error('Card checkout is unavailable. Your order is saved; please try again later.');
        sessionStorage.setItem(`ledgerco_payment_${payment.id}`, JSON.stringify({
            client_secret: payment.client_secret, publishable_key: payment.publishable_key, order_id: order.id,
        }));
        target = `payment-stripe.html?payment_id=${payment.id}&order_id=${order.id}`;
    } else {
        const url = new URL(payment.bkash_url);
        if (url.protocol !== 'https:') throw new Error('The payment provider returned an invalid checkout address.');
        sessionStorage.setItem(`ledgerco_bkash_${order.id}`, url.href);
        target = `payment-bkash.html?order_id=${order.id}`;
    }
    if (clearCart) Cart.clear();
    window.location.href = target;
}
