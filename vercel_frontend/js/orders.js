// Ledger & Co. — orders list page.

async function loadOrders() {
    const container = document.getElementById("orders-container");
    try {
        const data = await Api.listOrders();
        const orders = data.results ?? data;

        if (!orders.length) {
            container.innerHTML = `
                <div class="empty-state">
                    <h2>No orders yet</h2>
                    <p>Once you check out, your order history will show up here.</p>
                    <a href="index.html" class="btn btn-primary">Start shopping</a>
                </div>`;
            return;
        }

        container.innerHTML = `
            <div class="ledger">
                <div class="ledger-row head"><span>Order</span><span>Placed</span><span>Status</span><span>Total</span></div>
                ${orders.map((o) => `
                    <a href="order.html?id=${o.id}" class="ledger-row" style="color:inherit;">
                        <div class="ledger-item-name mono">#${o.id}</div>
                        <span class="mono">${new Date(o.created_at).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })}</span>
                        <span><span class="stamp ${o.status}">${o.status}</span></span>
                        <span class="ledger-figure">${money(o.total_amount)}</span>
                    </a>`).join("")}
            </div>`;
    } catch (err) {
        container.innerHTML = `<div class="state-box">Could not load your orders.<br><span class="mono">${escapeHtml(friendlyError(err))}</span></div>`;
    }
}

document.addEventListener("DOMContentLoaded", () => {
    if (!Auth.requireAuth()) return;
    loadOrders();
});
