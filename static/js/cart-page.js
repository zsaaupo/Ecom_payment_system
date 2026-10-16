// Ledger & Co. — cart page rendering (data logic lives in cart.js).

function renderCartPage() {
    const container = document.getElementById("cart-container");
    const lines = Cart.lines();

    if (!lines.length) {
        container.innerHTML = `
            <div class="empty-state">
                <h2>Your cart is empty</h2>
                <p>Browse the catalog and add something you like.</p>
                <a href="index.html" class="btn btn-primary">Continue shopping</a>
            </div>`;
        return;
    }

    container.innerHTML = `
        <div class="ledger">
            <div class="ledger-row head"><span>Item</span><span>Qty</span><span>Unit price</span><span>Subtotal</span></div>
            ${lines.map((l) => `
                <div class="ledger-row" data-line="${l.product.id}">
                    <div>
                        <div class="ledger-item-name">${escapeHtml(l.product.name)}</div>
                        <div class="ledger-item-meta">SKU ${escapeHtml(l.product.sku)} · <a href="#" class="remove-link" data-remove="${l.product.id}">remove</a></div>
                    </div>
                    <div class="qty-inline">
                        <button type="button" data-step="-1" data-target="${l.product.id}">−</button>
                        <input class="qty-input mono" type="number" min="1" max="${l.product.stock}" value="${l.quantity}" data-qty="${l.product.id}" style="width:48px;">
                        <button type="button" data-step="1" data-target="${l.product.id}">+</button>
                    </div>
                    <span class="ledger-figure">${money(l.product.price)}</span>
                    <span class="ledger-figure">${money(l.subtotal)}</span>
                </div>`).join("")}
            <div class="ledger-total-row"><span>Total</span><span class="mono">${money(Cart.total())}</span></div>
        </div>
        <div class="center" style="margin-top: 28px;">
            <a href="checkout.html" class="btn btn-jade">Proceed to checkout →</a>
        </div>`;

    container.querySelectorAll("[data-remove]").forEach((el) => {
        el.addEventListener("click", (e) => {
            e.preventDefault();
            Cart.remove(el.getAttribute("data-remove"));
            renderCartPage();
        });
    });
    container.querySelectorAll("[data-step]").forEach((btn) => {
        btn.addEventListener("click", () => {
            const id = btn.getAttribute("data-target");
            const input = container.querySelector(`[data-qty="${id}"]`);
            const step = parseInt(btn.getAttribute("data-step"), 10);
            const next = Math.max(1, (parseInt(input.value, 10) || 1) + step);
            Cart.setQuantity(id, next);
            renderCartPage();
        });
    });
    container.querySelectorAll("[data-qty]").forEach((input) => {
        input.addEventListener("change", () => {
            Cart.setQuantity(input.getAttribute("data-qty"), Math.max(1, parseInt(input.value, 10) || 1));
            renderCartPage();
        });
    });
}

document.addEventListener("DOMContentLoaded", async () => { await window.StoreReady; renderCartPage(); });
