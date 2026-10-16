// Ledger & Co. — Stripe checkout page.

async function initStripeCheckout() {
    const container = document.getElementById("stripe-container");
    const paymentId = positiveId("payment_id");
    const orderId = positiveId("order_id");

    if (!paymentId || !orderId) {
        container.innerHTML = `<div class="state-box">Missing payment information.</div>`;
        return;
    }

    if (qs('redirect_status')) {
        await reconcileStripePayment(paymentId, orderId);
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

    const { client_secret, publishable_key } = JSON.parse(stored);
    const order_id = orderId;

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
    try { const order = await Api.getOrder(order_id); orderTotal = money(order.total_amount, order.currency); } catch (e) { /* non-critical */ }

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

        try {
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

        await reconcileStripePayment(paymentId, order_id);
        } catch (err) {
            msg.textContent = 'We could not verify payment. Check your order status before retrying.';
            btn.disabled = false;
            btn.textContent = `Pay ${orderTotal}`;
        }
    });
}

async function reconcileStripePayment(paymentId, orderId) {
    const payment = await Api.confirmPayment(paymentId);
    const messages = {
        success: 'Payment successful. Your order is confirmed.',
        pending: 'Payment is awaiting confirmation. Check your order for updates.',
        failed: 'Payment was not completed. Check your order for details.',
    };
    if (payment.status === 'success') sessionStorage.removeItem(`ledgerco_payment_${paymentId}`);
    document.getElementById('stripe-container').innerHTML = `<h2 class="center">${messages[payment.status] || 'Check your payment status.'}</h2>
        <div class="center"><a class="btn btn-jade" href="order.html?id=${orderId}">View your order</a></div>`;
}

document.addEventListener("DOMContentLoaded", async () => {
    await window.StoreReady;
    if (!Auth.requireAuth()) return;
    try { await initStripeCheckout(); }
    catch (error) {
        document.getElementById('stripe-container').innerHTML = `<div class="state-box">Payment could not be loaded. ${escapeHtml(friendlyError(error))}<br><a href="orders.html">View your orders</a></div>`;
    }
});
