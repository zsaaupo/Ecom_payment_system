// Ledger & Co. — checkout page.
// Flow: require auth -> render cart summary + provider picker -> on submit,
// POST /api/orders/ (creates Order+OrderItems) -> POST /api/payments/initiate/
// -> hand off to Stripe.js (same-page) or redirect to bKash's hosted page.

function renderCheckout() {
    const container = document.getElementById("checkout-container");
    const lines = Cart.lines();

    if (!lines.length) {
        container.innerHTML = `
            <div class="empty-state">
                <h2>Your cart is empty</h2>
                <p>Add something to your cart before checking out.</p>
                <a href="index.html" class="btn btn-primary">Continue shopping</a>
            </div>`;
        return;
    }

    container.innerHTML = `
        <div class="ledger">
            <div class="ledger-row head"><span>Item</span><span>Qty</span><span>Unit price</span><span>Subtotal</span></div>
            ${lines.map((l) => `
                <div class="ledger-row">
                    <div><div class="ledger-item-name">${escapeHtml(l.product.name)}</div><div class="ledger-item-meta">SKU ${escapeHtml(l.product.sku)}</div></div>
                    <span class="mono">${l.quantity}</span>
                    <span class="ledger-figure">${money(l.product.price)}</span>
                    <span class="ledger-figure">${money(l.subtotal)}</span>
                </div>`).join("")}
            <div class="ledger-total-row"><span>Total due</span><span class="mono">${money(Cart.total())}</span></div>
        </div>

        <form id="checkout-form" style="margin-top: 32px;">
            <h3>Choose a payment method</h3>
            <div class="provider-grid">
                <label class="provider-option">
                    <input type="radio" name="provider" value="stripe" required>
                    <div class="provider-name">Stripe</div>
                    <div class="provider-desc">Card payments, test &amp; live mode</div>
                </label>
                <label class="provider-option">
                    <input type="radio" name="provider" value="bkash" required>
                    <div class="provider-name">bKash</div>
                    <div class="provider-desc">Mobile financial services (BD)</div>
                </label>
            </div>
            <button type="submit" class="btn btn-jade btn-block" id="place-order-btn">Place order &amp; continue to payment →</button>
        </form>`;

    container.querySelectorAll(".provider-option").forEach((option) => {
        option.addEventListener("click", () => {
            const input = option.querySelector('input');
            if (input.disabled) return;
            input.checked = true;
            container.querySelectorAll(".provider-option").forEach((o) => o.classList.toggle("selected", o === option));
        });
    });

    document.getElementById("checkout-form").addEventListener("submit", handleCheckoutSubmit);
    container.querySelectorAll('input[name="provider"]').forEach(input => {
        input.disabled = !window.PAYMENT_PROVIDERS[input.value];
        if (input.disabled) input.closest('.provider-option').querySelector('.provider-desc').textContent = 'Currently unavailable';
    });
    if (!Object.values(window.PAYMENT_PROVIDERS).some(Boolean)) {
        document.getElementById('place-order-btn').disabled = true;
        toast('Online payment is currently unavailable. Your cart has been saved.', 'info');
    }
}

async function handleCheckoutSubmit(e) {
    e.preventDefault();
    const provider = e.target.querySelector('input[name="provider"]:checked')?.value;
    if (!provider || !window.PAYMENT_PROVIDERS[provider]) { toast("Please choose an available payment method.", "error"); return; }

    const btn = document.getElementById("place-order-btn");
    btn.disabled = true;
    btn.textContent = "Placing order…";

    try {
        const items = Cart.toOrderItems();
        const key = `ledgerco_checkout_${Auth.getUser()?.id}_${JSON.stringify(items)}`;
        const saved = sessionStorage.getItem(key);
        let order = saved ? await Api.getOrder(saved) : null;
        if (!order || order.status !== 'pending') {
            order = await Api.createOrder(items);
            sessionStorage.setItem(key, String(order.id));
        }
        await continueToPayment(order, provider, true);
        sessionStorage.removeItem(key);
    } catch (err) {
        toast(friendlyError(err), "error");
        btn.disabled = false;
        btn.textContent = "Place order & continue to payment →";
    }
}

document.addEventListener("DOMContentLoaded", async () => {
    await window.StoreReady;
    if (!Auth.requireAuth()) return;
    renderCheckout();
});
