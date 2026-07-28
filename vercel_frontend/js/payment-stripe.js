// Ledger & Co. — Stripe checkout page.

async function initStripeCheckout() {
    const container = document.getElementById("stripe-container");
    const paymentId = qs("payment_id");
    const orderId = qs("order_id");

    if (!paymentId || !orderId) {
        container.innerHTML = `<div class="state-box">Missing payment information.</div>`;
        return;
    }

    const stored = sessionStorage.getItem(`ledgerco_payment_${paymentId}`);
    if (!stored) {
        container.innerHTML = `
            <h2 class="center">Session expired</h2>
            <p class="center">This payment session isn't available anymore (maybe this page was reloaded, or opened in a new tab).</p>
            <div class="center"><a href="order.html?id=${orderId}" class="btn btn-ghost">View your order</a></div>`;
        return;
    }

    const { client_secret, publishable_key, order_id } = JSON.parse(stored);

    if (!publishable_key || !client_secret) {
        container.innerHTML = `
            <div class="flash flash-error">
                Stripe isn't configured on the backend yet. Set <code class="mono">STRIPE_SECRET_KEY</code> and
                <code class="mono">STRIPE_PUBLISHABLE_KEY</code> in the backend's <code class="mono">.env</code>, then retry checkout.
            </div>
            <div class="center" style="margin-top:16px;"><a href="order.html?id=${order_id}" class="btn btn-ghost">Back to order</a></div>`;
        return;
    }

    let orderTotal = "";
    try { orderTotal = money((await Api.getOrder(order_id)).total_amount); } catch (e) { /* non-critical */ }

    container.innerHTML = `
        <h2 class="center">Pay with Stripe</h2>
        <p class="center mono">Order #${order_id} ${orderTotal ? "· " + orderTotal : ""}</p>
        <div id="payment-element"></div>
        <button id="submit-btn" class="btn btn-jade btn-block" style="margin-top: 20px;">Pay ${orderTotal}</button>
        <div id="payment-message" class="field-error" style="margin-top:12px;"></div>`;

    const stripe = Stripe(publishable_key);
    const elements = stripe.elements({ clientSecret: client_secret });
    elements.create("payment").mount("#payment-element");

    document.getElementById("submit-btn").addEventListener("click", async function () {
        const btn = this;
        btn.disabled = true;
        btn.textContent = "Processing…";
        const msg = document.getElementById("payment-message");
        msg.textContent = "";

        const { error } = await stripe.confirmPayment({
            elements,
            confirmParams: { return_url: window.location.href },
            redirect: "if_required",
        });

        if (error) {
            msg.textContent = error.message;
            btn.disabled = false;
            btn.textContent = `Pay ${orderTotal}`;
            return;
        }

        try {
            await Api.confirmPayment(paymentId);
            sessionStorage.removeItem(`ledgerco_payment_${paymentId}`);
            toast("Payment successful! Your order is confirmed.", "success");
        } catch (err) {
            toast("Payment went through, but we couldn't reconcile it automatically. Check your order status.", "error");
        }
        window.location.href = `order.html?id=${order_id}`;
    });
}

document.addEventListener("DOMContentLoaded", () => {
    if (!Auth.requireAuth()) return;
    initStripeCheckout();
});
