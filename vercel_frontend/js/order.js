// Ledger & Co. — order detail page.

async function loadOrder() {
    const container = document.getElementById("order-container");
    const id = qs("id");
    if (!id) {
        container.innerHTML = `<div class="state-box">No order specified.</div>`;
        return;
    }

    try {
        const order = await Api.getOrder(id);
        renderOrder(order);
    } catch (err) {
        container.innerHTML = `<div class="state-box">Could not load this order.<br><span class="mono">${escapeHtml(friendlyError(err))}</span></div>`;
    }
}

function renderOrder(order) {
    const container = document.getElementById("order-container");
    const payment = order.payments && order.payments.length ? order.payments[order.payments.length - 1] : null;
    const placedAt = new Date(order.created_at);

    container.innerHTML = `
    <div class="receipt">
        <div class="receipt-body">
            <div class="receipt-head">
                <div class="mono muted">ORDER №${order.id}</div>
                <h2 style="margin: 8px 0 0;">Ledger &amp; Co.</h2>
                <div class="muted" style="font-size:0.85rem;">${placedAt.toLocaleString(undefined, { dateStyle: "long", timeStyle: "short" })}</div>
                <div class="stamp ${order.status}">${order.status}</div>
            </div>
            ${order.items.map((item) => `
                <div class="ledger-row" style="grid-template-columns: 1fr auto auto; padding: 10px 0; border-bottom: 1px dashed var(--rule);">
                    <div>
                        <div class="ledger-item-name">${escapeHtml(item.product.name)}</div>
                        <div class="ledger-item-meta">${item.quantity} × ${money(item.price)}</div>
                    </div>
                    <span></span>
                    <span class="ledger-figure">${money(item.subtotal)}</span>
                </div>`).join("")}
            <div class="ledger-total-row" style="margin: 16px -28px -32px; border-radius: 0 0 var(--radius-lg) var(--radius-lg);">
                <span>Total</span>
                <span class="mono">${money(order.total_amount)}</span>
            </div>
        </div>
    </div>

    ${payment ? `
    <div class="wrap" style="max-width: 480px; margin-top: 24px; padding: 0;">
        <div class="ledger">
            <div class="ledger-row head"><span>Payment</span><span></span></div>
            <div class="ledger-row" style="grid-template-columns: 1fr auto;">
                <div><div class="ledger-item-meta">Provider</div><span class="badge-provider">${payment.provider}</span></div>
                <span class="stamp ${payment.status}">${payment.status}</span>
            </div>
            <div class="ledger-row" style="grid-template-columns: 1fr;">
                <div>
                    <div class="ledger-item-meta">Transaction ID</div>
                    <div class="mono" style="font-size:0.82rem; word-break:break-all;">${escapeHtml(payment.transaction_id)}</div>
                </div>
            </div>
        </div>
    </div>` : order.status === "pending" ? `
    <div class="center" style="margin-top:24px;">
        <p class="muted">This order hasn't been paid yet.</p>
        <a href="index.html" class="btn btn-ghost">Back to catalog</a>
    </div>` : ""}`;
}

document.addEventListener("DOMContentLoaded", () => {
    if (!Auth.requireAuth()) return;
    loadOrder();
});
