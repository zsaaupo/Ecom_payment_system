// Ledger & Co. — bKash "continue to checkout" intermediate page.

async function initBkashPage() {
    const container = document.getElementById("bkash-container");
    const orderId = qs("order_id");

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

    let orderTotal = "";
    try { orderTotal = money((await Api.getOrder(orderId)).total_amount); } catch (e) { /* non-critical */ }

    container.innerHTML = `
        <h2 class="center">Pay with bKash</h2>
        <p class="center mono">Order #${orderId} ${orderTotal ? "· " + orderTotal : ""}</p>
        <p class="center">You'll be redirected to bKash's secure checkout page to complete your payment.</p>
        <a href="${bkashUrl}" class="btn btn-jade btn-block">Continue to bKash →</a>
        <div class="form-foot"><a href="order.html?id=${orderId}">Cancel and return to order</a></div>`;
}

document.addEventListener("DOMContentLoaded", () => {
    if (!Auth.requireAuth()) return;
    initBkashPage();
});
