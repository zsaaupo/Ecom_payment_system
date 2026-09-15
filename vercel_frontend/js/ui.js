// Ledger & Co. — small shared UI helpers.

function ensureToastStack() {
    let stack = document.querySelector(".toast-stack");
    if (!stack) {
        stack = document.createElement("div");
        stack.className = "toast-stack";
        document.body.appendChild(stack);
    }
    return stack;
}

function toast(message, type = "info", timeout = 4200) {
    const stack = ensureToastStack();
    const el = document.createElement("div");
    el.className = `toast toast-${type}`;
    el.textContent = message;
    stack.appendChild(el);
    setTimeout(() => el.remove(), timeout);
}

function money(amount, currency = window.STORE_CURRENCY || 'USD') {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(Number(amount));
}

function escapeHtml(str) {
    return String(str ?? '').replace(/[&<>"']/g, char => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[char]));
}

function safeReturnPath(value) {
    try {
        const url = new URL(value || 'index.html', window.location.href);
        if (url.origin === window.location.origin && /\/[^/]*\.html$/.test(url.pathname)) {
            return url.pathname + url.search + url.hash;
        }
    } catch { /* use the catalog for invalid destinations */ }
    return 'index.html';
}

function positiveId(name) {
    const value = qs(name);
    return /^[1-9]\d*$/.test(value || '') ? value : null;
}

function qs(name) {
    return new URLSearchParams(window.location.search).get(name);
}

function friendlyError(err) {
    if (err && err.data) {
        if (typeof err.data.detail === "string") return err.data.detail;
        if (err.data.detail && typeof err.data.detail === "object") {
            return Object.entries(err.data.detail).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(", ") : v}`).join(" · ");
        }
        return Object.entries(err.data).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(", ") : v}`).join(" · ");
    }
    return err.message || "Something went wrong.";
}
