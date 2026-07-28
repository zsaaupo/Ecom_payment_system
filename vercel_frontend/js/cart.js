// Ledger & Co. — client-side cart.
// The Django backend's session cart (orders/services.py::Cart) only works
// for same-origin, server-rendered pages. This decoupled frontend runs on
// a different origin (Vercel), so the cart lives in localStorage instead
// and is sent to the backend as a plain items list only at checkout time,
// via Api.createOrder() - the exact same endpoint the Postman collection
// exercises directly.
const CART_KEY = "ledgerco_cart"; // { [productId]: { product: {...snapshot...}, quantity: n } }

const Cart = {
    _read() {
        try { return JSON.parse(localStorage.getItem(CART_KEY)) || {}; }
        catch { return {}; }
    },
    _write(data) {
        localStorage.setItem(CART_KEY, JSON.stringify(data));
        window.dispatchEvent(new CustomEvent("cart:updated"));
    },
    add(product, quantity = 1) {
        const data = this._read();
        const key = String(product.id);
        const existingQty = data[key] ? data[key].quantity : 0;
        data[key] = { product, quantity: existingQty + quantity };
        this._write(data);
    },
    setQuantity(productId, quantity) {
        const data = this._read();
        const key = String(productId);
        if (quantity <= 0) { delete data[key]; }
        else if (data[key]) { data[key].quantity = quantity; }
        this._write(data);
    },
    remove(productId) {
        const data = this._read();
        delete data[String(productId)];
        this._write(data);
    },
    clear() { this._write({}); },
    lines() {
        return Object.values(this._read()).map((line) => ({
            ...line,
            subtotal: Math.round(line.product.price * line.quantity * 100) / 100,
        }));
    },
    count() {
        return Object.values(this._read()).reduce((sum, l) => sum + l.quantity, 0);
    },
    total() {
        return this.lines().reduce((sum, l) => sum + l.subtotal, 0);
    },
    isEmpty() { return Object.keys(this._read()).length === 0; },
    /** Payload shape the backend's POST /api/orders/ expects. */
    toOrderItems() {
        return Object.values(this._read()).map((l) => ({ product_id: l.product.id, quantity: l.quantity }));
    },
};
