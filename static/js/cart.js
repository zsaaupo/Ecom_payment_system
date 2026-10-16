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
        try {
            const data = JSON.parse(localStorage.getItem(CART_KEY));
            if (!data || typeof data !== 'object' || Array.isArray(data)) return {};
            return Object.fromEntries(Object.entries(data).filter(([id, line]) =>
                /^[1-9]\d*$/.test(id) && line && line.product &&
                String(line.product.id) === id && Number.isInteger(line.quantity) && line.quantity > 0 &&
                Number.isInteger(line.product.stock) && line.product.stock >= line.quantity &&
                Number.isFinite(Number(line.product.price)) && Number(line.product.price) >= 0
            ));
        } catch { return {}; }
    },
    _write(data) {
        localStorage.setItem(CART_KEY, JSON.stringify(data));
        window.dispatchEvent(new CustomEvent("cart:updated"));
    },
    add(product, quantity = 1) {
        quantity = Number(quantity);
        if (!Number.isInteger(quantity) || quantity < 1 || !Number.isInteger(product.stock) || product.stock < 1) return 0;
        const data = this._read();
        const key = String(product.id);
        const existingQty = data[key] ? data[key].quantity : 0;
        const newQty = Math.min(product.stock, existingQty + quantity);
        data[key] = { product, quantity: newQty };
        this._write(data);
        return Math.max(0, newQty - existingQty);
    },
    setQuantity(productId, quantity) {
        quantity = Number(quantity);
        if (!Number.isInteger(quantity)) return;
        const data = this._read();
        const key = String(productId);
        if (quantity <= 0) { delete data[key]; }
        else if (data[key]) { data[key].quantity = Math.min(data[key].product.stock, quantity); }
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
        return this.lines().reduce((sum, l) => sum + Math.round(l.subtotal * 100), 0) / 100;
    },
    isEmpty() { return Object.keys(this._read()).length === 0; },
    /** Payload shape the backend's POST /api/orders/ expects. */
    toOrderItems() {
        return Object.values(this._read()).map((l) => ({ product_id: l.product.id, quantity: l.quantity }));
    },
};
