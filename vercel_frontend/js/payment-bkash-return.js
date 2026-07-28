// Ledger & Co. — bKash return page.
// bKash redirects the customer's browser here (BKASH_CALLBACK_URL) with
// ?paymentID=...&status=success|cancel|failure. We forward that straight
// to the backend's existing webhook endpoint (GET /api/payments/webhooks/bkash/),
// which does the same confirm/execute + stock-reduction work it would do
// for a server-to-server callback - no auth needed, no session required.

async function handleBkashReturn() {
    const container = document.getElementById("bkash-return-container");
    const paymentId = qs("paymentID");
    const status = qs("status");

    if (!paymentId) {
        container.innerHTML = `<div class="state-box">No payment reference was provided by bKash.</div>`;
        return;
    }

    try {
        const payment = await Api.bkashCallback(paymentId, status);
        if (payment.status === "success") {
            container.innerHTML = `
                <h2 class="center">Payment successful</h2>
                <p class="center">Your bKash payment has been confirmed and your order is now paid.</p>
                <div class="center"><a href="order.html?id=${payment.order}" class="btn btn-jade">View your order →</a></div>`;
        } else {
            container.innerHTML = `
                <h2 class="center">Payment not completed</h2>
                <p class="center">Your bKash payment was cancelled or could not be confirmed.</p>
                <div class="center"><a href="order.html?id=${payment.order}" class="btn btn-ghost">View your order</a></div>`;
        }
    } catch (err) {
        container.innerHTML = `
            <h2 class="center">Something went wrong</h2>
            <p class="center mono">${escapeHtml(friendlyError(err))}</p>
            <div class="center"><a href="orders.html" class="btn btn-ghost">View your orders</a></div>`;
    }
}

document.addEventListener("DOMContentLoaded", handleBkashReturn);
