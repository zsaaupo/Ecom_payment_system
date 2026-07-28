// Ledger & Co. — account page.

async function loadAccount() {
    const container = document.getElementById("account-container");
    try {
        const [user, ordersData] = await Promise.all([Api.getProfile(), Api.listOrders()]);
        Auth.setSession(Auth.getToken(), user); // keep cached user info fresh
        const orders = (ordersData.results ?? ordersData).slice(0, 10);

        container.innerHTML = `
            <div class="ledger" style="margin-bottom: 32px;">
                <div class="ledger-row" style="grid-template-columns: 1fr 1fr;">
                    <div><div class="ledger-item-meta">Username</div><div class="ledger-item-name">${escapeHtml(user.username)}</div></div>
                    <div><div class="ledger-item-meta">Email</div><div class="ledger-item-name">${escapeHtml(user.email)}</div></div>
                </div>
                <div class="ledger-row" style="grid-template-columns: 1fr 1fr;">
                    <div><div class="ledger-item-meta">Name</div><div class="ledger-item-name">${escapeHtml(user.first_name)} ${escapeHtml(user.last_name)}</div></div>
                    <div><div class="ledger-item-meta">Phone</div><div class="ledger-item-name">${escapeHtml(user.phone_number) || "—"}</div></div>
                </div>
            </div>
            <div class="section-head"><h2>Recent orders</h2><a href="orders.html" class="muted">View all →</a></div>
            ${orders.length ? `
            <div class="ledger">
                <div class="ledger-row head"><span>Order</span><span>Placed</span><span>Status</span><span>Total</span></div>
                ${orders.map((o) => `
                    <a href="order.html?id=${o.id}" class="ledger-row" style="color:inherit;">
                        <div class="ledger-item-name mono">#${o.id}</div>
                        <span class="mono">${new Date(o.created_at).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })}</span>
                        <span class="stamp ${o.status}">${o.status}</span>
                        <span class="ledger-figure">${money(o.total_amount)}</span>
                    </a>`).join("")}
            </div>` : `<p class="muted">No orders yet.</p>`}`;
    } catch (err) {
        container.innerHTML = `<div class="state-box">Could not load your account.<br><span class="mono">${escapeHtml(friendlyError(err))}</span></div>`;
    }
}

document.addEventListener("DOMContentLoaded", () => {
    if (!Auth.requireAuth()) return;
    loadAccount();
});
