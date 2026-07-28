// Ledger & Co. — home / product listing page.

async function loadProducts(query = {}) {
    const container = document.getElementById("product-grid-container");
    try {
        const data = await Api.listProducts(query);
        renderProducts(data);
    } catch (err) {
        container.innerHTML = `<div class="state-box">Could not load products.<br><span class="mono">${escapeHtml(friendlyError(err))}</span></div>`;
    }
}

function renderProducts(data) {
    const container = document.getElementById("product-grid-container");
    const results = data.results ?? data; // tolerate both paginated and plain-list shapes
    const count = data.count ?? results.length;

    document.getElementById("listing-count").textContent = `${count} item${count === 1 ? "" : "s"}`;

    const search = qs("q");
    const categoryId = qs("category");
    const title = document.getElementById("listing-title");
    if (search) title.textContent = `Results for "${search}"`;
    else if (categoryId) title.textContent = "Filtered by category";
    else title.textContent = "All products";

    if (!results.length) {
        container.innerHTML = `<div class="state-box"><h3>No products here yet</h3><p>Run <code class="mono">python manage.py seed_data</code> on the backend, or adjust your filters.</p></div>`;
        renderPagination(null);
        return;
    }

    container.innerHTML = `<div class="product-grid">${results.map(productCard).join("")}</div>`;

    container.querySelectorAll("[data-quick-add]").forEach((btn) => {
        btn.addEventListener("click", (e) => {
            e.preventDefault();
            const product = JSON.parse(btn.getAttribute("data-product"));
            Cart.add(product, 1);
            toast(`Added ${product.name} to your cart.`, "success");
        });
    });

    renderPagination(data);
}

function productCard(p) {
    const available = p.is_available;
    const productSnapshot = JSON.stringify({ id: p.id, name: p.name, sku: p.sku, price: p.price, stock: p.stock }).replace(/'/g, "&apos;");
    return `
    <div class="product-card">
        <a href="product.html?id=${p.id}" style="color:inherit;">
            <div class="product-thumb">${escapeHtml((p.name || "?")[0])}</div>
            <div class="product-body">
                ${p.category_name ? `<span class="product-cat">${escapeHtml(p.category_name)}</span>` : ""}
                <span class="product-name">${escapeHtml(p.name)}</span>
            </div>
        </a>
        <div class="product-body" style="padding-top:0;">
            <div class="product-card-foot">
                <span class="product-price">${money(p.price)}</span>
                ${available
                    ? `<span class="stock-pill in">${p.stock} in stock</span>`
                    : `<span class="stock-pill out">Out of stock</span>`}
            </div>
            <div class="product-card-foot">
                <span></span>
                <button class="quick-add-btn" data-quick-add data-product='${productSnapshot}' ${available ? "" : "disabled"}>
                    + Add to cart
                </button>
            </div>
        </div>
    </div>`;
}

function getPageNum(urlStr) {
    if (!urlStr) return null;
    try {
        const u = new URL(urlStr, window.location.href);
        return u.searchParams.get("page");
    } catch {
        return null;
    }
}

function renderPagination(data) {
    const el = document.getElementById("pagination");
    if (!data || (!data.next && !data.previous)) { el.innerHTML = ""; return; }
    el.innerHTML = `
        ${data.previous ? `<a href="#" id="prev-page">← Prev</a>` : ""}
        ${data.next ? `<a href="#" id="next-page">Next →</a>` : ""}`;
    const prevBtn = document.getElementById("prev-page");
    const nextBtn = document.getElementById("next-page");
    if (prevBtn) prevBtn.addEventListener("click", (e) => {
        e.preventDefault();
        loadProducts({ q: qs("q"), category: qs("category"), page: getPageNum(data.previous) });
        window.scrollTo({ top: 0, behavior: "smooth" });
    });
    if (nextBtn) nextBtn.addEventListener("click", (e) => {
        e.preventDefault();
        loadProducts({ q: qs("q"), category: qs("category"), page: getPageNum(data.next) });
        window.scrollTo({ top: 0, behavior: "smooth" });
    });
}

document.addEventListener("DOMContentLoaded", () => {
    const searchInput = document.querySelector(".nav-search input");
    if (searchInput && qs("q")) searchInput.value = qs("q");

    loadProducts({ q: qs("q"), category: qs("category") });
});
