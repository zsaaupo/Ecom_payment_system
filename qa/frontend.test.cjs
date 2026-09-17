const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function storage() {
    const data = new Map();
    return { getItem: k => data.get(k) ?? null, setItem: (k, v) => data.set(k, String(v)), removeItem: k => data.delete(k) };
}
function context(files) {
    const elements = new Map();
    const ctx = vm.createContext({
        URL, URLSearchParams, Intl, console, setTimeout,
        localStorage: storage(), sessionStorage: storage(), CustomEvent: class {},
        window: { location: { href: 'https://shop.example/login.html', origin: 'https://shop.example', pathname: '/login.html', search: '' }, dispatchEvent() {}, PAYMENT_PROVIDERS: {stripe: true} },
        document: { addEventListener() {}, getElementById(id) { if (!elements.has(id)) elements.set(id, { innerHTML: '' }); return elements.get(id); } },
    });
    for (const file of files) vm.runInContext(fs.readFileSync(path.join(__dirname, '../vercel_frontend/js', file), 'utf8'), ctx);
    return ctx;
}
function run(ctx, source) { return vm.runInContext(source, ctx); }
const product = "{id: 1, name: 'Test', sku: 'TEST', price: '0.10', stock: 3}";

test('cart additions and direct edits respect stock', () => {
    const ctx = context(['cart.js']);
    run(ctx, `Cart.add(${product}, 2); Cart.add(${product}, 99);`);
    assert.equal(run(ctx, 'Cart.count()'), 3);
    run(ctx, 'Cart.setQuantity(1, 999)');
    assert.equal(run(ctx, 'Cart.count()'), 3);
});
test('cart ignores invalid quantities', () => {
    const ctx = context(['cart.js']);
    for (const qty of ['NaN', 'Infinity', '1.5', '-1']) run(ctx, `Cart.add(${product}, ${qty})`);
    assert.equal(run(ctx, 'Cart.count()'), 0);
});
test('cart handles malformed stored data', () => {
    const ctx = context(['cart.js']);
    for (const value of ['broken', '[]', '1', '{"1":{"quantity":1}}']) {
        ctx.localStorage.setItem('ledgerco_cart', value);
        assert.equal(run(ctx, 'Cart.count()'), 0);
    }
});
test('cart totals use rounded cents', () => {
    const ctx = context(['cart.js']);
    run(ctx, `Cart.add(${product}, 3)`);
    assert.equal(run(ctx, 'Cart.total()'), 0.3);
});
test('login return path rejects external and script destinations', () => {
    const ctx = context(['ui.js']);
    for (const url of ['https://evil.example/a.html', '//evil.example/a.html', 'javascript:alert(1)']) {
        ctx.value = url;
        assert.equal(run(ctx, 'safeReturnPath(value)'), 'index.html');
    }
    assert.equal(run(ctx, "safeReturnPath('/checkout.html?q=50%25')"), '/checkout.html?q=50%25');
});
test('HTML escaping protects text and quoted attributes', () => {
    const ctx = context(['ui.js']);
    ctx.value = '&quot;\"\'<> &';
    assert.equal(run(ctx, 'escapeHtml(value)'), '&amp;quot;&quot;&#39;&lt;&gt; &amp;');
});
test('currency formatter displays BDT explicitly', () => {
    const ctx = context(['ui.js']);
    assert.match(run(ctx, "money('12.50', 'BDT')"), /BDT/);
});
test('query IDs reject injected HTML', () => {
    const ctx = context(['ui.js']);
    ctx.window.location.search = '?order_id=%22%3E%3Cimg%3E';
    assert.equal(run(ctx, "positiveId('order_id')"), null);
});
test('corrupt account data clears the broken session', () => {
    const ctx = context(['api.js']);
    ctx.localStorage.setItem('ledgerco_user', 'broken');
    ctx.localStorage.setItem('ledgerco_token', 'test');
    assert.equal(run(ctx, 'Auth.getUser()'), null);
    assert.equal(run(ctx, 'Auth.getToken()'), null);
});
test('configuration query cannot redirect credentials', async () => {
    const ctx = context([]);
    ctx.window.location.search = '?api=https://evil.example';
    ctx.localStorage.setItem('ledgerco_api_base', 'https://evil.example');
    ctx.fetch = async () => ({ok: true, json: async () => ({currency: 'BDT', providers: {bkash: true}})});
    run(ctx, fs.readFileSync(path.join(__dirname, '../vercel_frontend/js/config.js'), 'utf8'));
    await ctx.window.StoreReady;
    assert.equal(ctx.window.API_BASE_URL, 'http://localhost:8000');
    assert.equal(ctx.window.STORE_CURRENCY, 'BDT');
});
test('pending Stripe confirmation is never shown as success', async () => {
    const ctx = context(['ui.js', 'payment-stripe.js']);
    ctx.Api = {confirmPayment: async () => ({status: 'pending'})};
    await run(ctx, "reconcileStripePayment('1', '1')");
    assert.match(ctx.document.getElementById('stripe-container').innerHTML, /awaiting confirmation/);
    assert.doesNotMatch(ctx.document.getElementById('stripe-container').innerHTML, /Payment successful/);
});
test('Stripe redirect return reconciles without a saved browser session', async () => {
    const ctx = context(['ui.js', 'payment-stripe.js']);
    ctx.window.location.search = '?payment_id=1&order_id=2&redirect_status=succeeded';
    let confirms = 0;
    ctx.Api = {confirmPayment: async () => { confirms++; return {status: 'success'}; }};
    await run(ctx, 'initStripeCheckout()');
    assert.equal(confirms, 1);
    assert.match(ctx.document.getElementById('stripe-container').innerHTML, /Payment successful/);
});
test('failed provider setup preserves cart', async () => {
    const ctx = context(['cart.js', 'api.js']);
    run(ctx, `Cart.add(${product}); Api.initiatePayment = async () => ({id: 1});`);
    await assert.rejects(run(ctx, "continueToPayment({id: 1}, 'stripe', true)"));
    assert.equal(run(ctx, 'Cart.count()'), 1);
});
test('order history requests the selected page', async () => {
    const ctx = context(['api.js']);
    let url;
    ctx.fetch = async (value) => { url = value; return {ok: true, headers: {get: () => 'application/json'}, json: async () => ({results: []})}; };
    await run(ctx, 'Api.listOrders(2)');
    assert.match(url, /page=2/);
});
test('checkout retry reuses the previously saved order', async () => {
    const ctx = context(['cart.js', 'api.js', 'checkout.js']);
    run(ctx, `Cart.add(${product}); Auth.setSession('test', {id:1});`);
    let creates = 0;
    ctx.toast = () => {};
    ctx.friendlyError = () => 'offline';
    ctx.create = async () => { creates++; return {id: 1, status: 'pending'}; };
    run(ctx, "Api.createOrder = create; Api.getOrder = async () => ({id:1,status:'pending'}); Api.initiatePayment = async () => {throw new Error('offline')};");
    ctx.event = {preventDefault() {}, target: {querySelector: () => ({value: 'stripe'})}};
    await run(ctx, 'handleCheckoutSubmit(event)');
    await run(ctx, 'handleCheckoutSubmit(event)');
    assert.equal(creates, 1);
    assert.equal(run(ctx, 'Cart.count()'), 1);
});
