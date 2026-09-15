// Ledger & Co. — bKash "continue to checkout" intermediate page.

async function initBkashPage() {
    const container = document.getElementById("bkash-container");
    const orderId = positiveId("order_id");

    if (!orderId) {
        container.innerHTML = `<div class="state-box">Missing order information.</div>`;
        return;
    }

    const bkashUrl = sessionStorage.getItem(`ledgerco_bkash_${orderId}`);
    if (!bkashUrl) {
        container.innerHTML = `
            <h2 class="center">Session expired</h2>
            <p class="center">This checkout session isn't available anymore.</p>
            <div class="center"><a href="order.html?id=${orderId}" class="btn btn-ghost">View your order</a></div>`;
        return;
    }
    const checkoutUrl = new URL(bkashUrl);
    if (checkoutUrl.protocol !== 'https:') throw new Error('Invalid payment address.');

    let orderTotal = "";
    try { const order = await Api.getOrder(orderId); orderTotal = money(order.total_amount, order.currency); } catch (e) { /* non-critical */ }

    container.innerHTML = `
        <h2 class="center">Pay with bKash</h2>
        <p class="center mono">Order #${orderId} ${orderTotal ? "· " + orderTotal : ""}</p>
        <p class="center">You'll be redirected to bKash's secure checkout page to complete your payment.</p>
        <a href="${escapeHtml(checkoutUrl.href)}" class="btn btn-jade btn-block">Continue to bKash →</a>
        <div class="form-foot"><a href="order.html?id=${orderId}">Cancel and return to order</a></div>`;
}

document.addEventListener("DOMContentLoaded", async () => {
    await window.StoreReady;
    if (!Auth.requireAuth()) return;
    try { await initBkashPage(); }
    catch (error) { document.getElementById('bkash-container').textContent = friendlyError(error); }
});
