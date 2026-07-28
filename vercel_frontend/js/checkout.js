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
            option.querySelector("input").checked = true;
            container.querySelectorAll(".provider-option").forEach((o) => o.classList.toggle("selected", o === option));
        });
    });

    document.getElementById("checkout-form").addEventListener("submit", handleCheckoutSubmit);
}

async function handleCheckoutSubmit(e) {
    e.preventDefault();
    const provider = e.target.querySelector('input[name="provider"]:checked')?.value;
    if (!provider) { toast("Please choose a payment method.", "error"); return; }

    const btn = document.getElementById("place-order-btn");
    btn.disabled = true;
    btn.textContent = "Placing order…";

    try {
        const order = await Api.createOrder(Cart.toOrderItems());
        const payment = await Api.initiatePayment(order.id, provider);
        Cart.clear();

        if (provider === "stripe") {
            sessionStorage.setItem(`ledgerco_payment_${payment.id}`, JSON.stringify({
                client_secret: payment.client_secret,
                publishable_key: payment.publishable_key,
                order_id: order.id,
            }));
            window.location.href = `payment-stripe.html?payment_id=${payment.id}&order_id=${order.id}`;
        } else {
            if (!payment.bkash_url) {
                toast("bKash did not return a checkout URL.", "error");
                btn.disabled = false;
                btn.textContent = "Place order & continue to payment →";
                return;
            }
            sessionStorage.setItem(`ledgerco_bkash_${order.id}`, payment.bkash_url);
            window.location.href = `payment-bkash.html?order_id=${order.id}`;
        }
    } catch (err) {
        toast(friendlyError(err), "error");
        btn.disabled = false;
        btn.textContent = "Place order & continue to payment →";
    }
}

document.addEventListener("DOMContentLoaded", () => {
    if (!Auth.requireAuth()) return;
    renderCheckout();
});
