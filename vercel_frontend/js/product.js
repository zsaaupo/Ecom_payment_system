// Ledger & Co. — product detail page.

async function loadProduct() {
    const container = document.getElementById("product-container");
    const id = qs("id");
    if (!id) {
        container.innerHTML = `<div class="state-box">No product specified.</div>`;
        return;
    }

    try {
        const product = await Api.getProduct(id);
        document.title = `${product.name} — Ledger & Co.`;
        renderProduct(product);

        try {
            const related = await Api.getRelatedProducts(id);
            renderRelated(related);
        } catch (e) { /* related products are a nice-to-have; fail quietly */ }
    } catch (err) {
        container.innerHTML = `<div class="state-box">Could not load this product.<br><span class="mono">${escapeHtml(friendlyError(err))}</span></div>`;
    }
}

function renderProduct(p) {
    const container = document.getElementById("product-container");
    container.innerHTML = `
    <div class="detail-grid">
        <div class="detail-thumb">${escapeHtml((p.name || "?")[0])}</div>
        <div>
            ${p.category_name ? `<span class="product-cat">${escapeHtml(p.category_name)}</span>` : ""}
            <h1>${escapeHtml(p.name)}</h1>
            <div class="detail-sku">SKU ${escapeHtml(p.sku)}</div>
            <div class="detail-price">${money(p.price)}</div>
            <p>${escapeHtml(p.description) || "No description provided."}</p>
            ${p.is_available ? `
                <span class="stock-pill in">${p.stock} in stock</span>
                <div class="qty-form">
                    <button type="button" id="qty-minus" class="btn btn-ghost">−</button>
                    <input type="number" id="qty-input" value="1" min="1" max="${p.stock}">
                    <button type="button" id="qty-plus" class="btn btn-ghost">+</button>
                    <button type="button" id="add-to-cart-btn" class="btn btn-jade">Add to cart</button>
                </div>
            ` : `
                <span class="stock-pill out">Out of stock</span>
                <p class="muted" style="margin-top:16px;">Check back soon — this item is currently unavailable.</p>
            `}
        </div>
    </div>
    <div id="related-container"></div>`;

    if (p.is_available) {
        const qtyInput = document.getElementById("qty-input");
        document.getElementById("qty-minus").addEventListener("click", () => { qtyInput.value = Math.max(1, parseInt(qtyInput.value || "1", 10) - 1); });
        document.getElementById("qty-plus").addEventListener("click", () => { qtyInput.value = Math.min(p.stock, parseInt(qtyInput.value || "1", 10) + 1); });
        document.getElementById("add-to-cart-btn").addEventListener("click", () => {
            const qty = Math.max(1, parseInt(qtyInput.value || "1", 10));
            Cart.add({ id: p.id, name: p.name, sku: p.sku, price: p.price, stock: p.stock }, qty);
            toast(`Added ${qty} × ${p.name} to your cart.`, "success");
        });
    }
}

function renderRelated(related) {
    if (!related.length) return;
    const el = document.getElementById("related-container");
    el.innerHTML = `
        <div class="section-head" style="margin-top:56px;">
            <h2>You might also like</h2>
            <span class="muted mono">via category traversal</span>
        </div>
        <div class="product-grid">
            ${related.map((rp) => `
                <a href="product.html?id=${rp.id}" class="product-card">
                    <div class="product-thumb">${escapeHtml((rp.name || "?")[0])}</div>
                    <div class="product-body">
                        <span class="product-cat">${escapeHtml(rp.category_name || "")}</span>
                        <span class="product-name">${escapeHtml(rp.name)}</span>
                        <div class="product-row"><span class="product-price">${money(rp.price)}</span></div>
                    </div>
                </a>`).join("")}
        </div>`;
}

document.addEventListener("DOMContentLoaded", loadProduct);
