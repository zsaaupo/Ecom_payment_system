// Ledger & Co. — shared nav behavior, included on every page.
// Expects this markup to exist in the page (see the header in any .html file):
//   #nav-categories-menu, #cart-badge, #auth-area

async function initNav() {
    // Dropdown open/close (categories + account menus) using event delegation
    document.addEventListener("click", (e) => {
        const btn = e.target.closest(".nav-dropdown-toggle");
        if (btn) {
            e.stopPropagation();
            const dropdown = btn.closest(".nav-dropdown");
            document.querySelectorAll(".nav-dropdown.open").forEach((open) => {
                if (open !== dropdown) open.classList.remove("open");
            });
            dropdown.classList.toggle("open");
            return;
        }
        document.querySelectorAll(".nav-dropdown.open").forEach((d) => d.classList.remove("open"));
    });

    renderCartBadge();
    window.addEventListener("cart:updated", renderCartBadge);
    renderAuthArea();
    loadCategoryMenu();

    const apiLabel = document.getElementById("api-base-label");
    if (apiLabel) apiLabel.textContent = window.API_BASE_URL;
}

function renderCartBadge() {
    const badge = document.getElementById("cart-badge");
    if (badge) badge.textContent = Cart.count();
}

function renderAuthArea() {
    const el = document.getElementById("auth-area");
    if (!el) return;

    if (Auth.isAuthenticated()) {
        const user = Auth.getUser();
        el.innerHTML = `
            <div class="nav-dropdown">
                <button class="nav-link nav-dropdown-toggle" type="button">${escapeHtml(user?.first_name || user?.username || "Account")}</button>
                <div class="nav-dropdown-menu">
                    <a href="account.html">My account</a>
                    <a href="orders.html">My orders</a>
                    <button class="link-button" id="logout-btn">Log out</button>
                </div>
            </div>`;
        document.getElementById("logout-btn").addEventListener("click", async () => {
            try { await Api.logout(); } catch (e) { /* token may already be invalid - fine either way */ }
            Auth.clearSession();
            toast("You have been logged out.", "info");
            setTimeout(() => (window.location.href = "index.html"), 500);
        });
    } else {
        el.innerHTML = `
            <a href="login.html" class="btn btn-ghost">Log in</a>
            <a href="register.html" class="btn btn-primary">Sign up</a>`;
    }
}

async function loadCategoryMenu() {
    const menu = document.getElementById("nav-categories-menu");
    const filterRow = document.getElementById("filter-row");
    if (!menu && !filterRow) return;

    try {
        const roots = await Api.getCategoryTree();
        if (menu) {
            menu.innerHTML = roots.length
                ? roots.map((c) => `<a href="index.html?category=${c.id}">${escapeHtml(c.name)}</a>`).join("")
                : `<span class="muted">No categories yet</span>`;
        }
        if (filterRow) {
            const activeId = qs("category");
            filterRow.innerHTML =
                `<a href="index.html" class="filter-chip ${!activeId ? "active" : ""}">All</a>` +
                roots.map((c) => `<a href="index.html?category=${c.id}" class="filter-chip ${String(c.id) === activeId ? "active" : ""}">${escapeHtml(c.name)}</a>`).join("");
        }
    } catch (err) {
        if (menu) menu.innerHTML = `<span class="muted">Categories unavailable</span>`;
    }
}

document.addEventListener("DOMContentLoaded", initNav);
