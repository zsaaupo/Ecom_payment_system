// Ledger & Co. — API base URL configuration.
//
// IMPORTANT: change the default below to your deployed/ngrok Django backend
// URL before (or after) deploying to Vercel. No trailing slash.
//
// For quick local testing you can also override it on the fly, without
// editing this file or redeploying, by visiting any page with ?api=...,
// e.g.  https://your-frontend.vercel.app/?api=https://xxxx.ngrok-free.app
// The override is remembered in this browser via localStorage.
(function () {
    const DEFAULT_API_BASE_URL = "https://legible-unfrozen-elves.ngrok-free.dev";

    const params = new URLSearchParams(window.location.search);
    const overrideApi = params.get("api");
    if (overrideApi) {
        localStorage.setItem("ledgerco_api_base", overrideApi.replace(/\/$/, ""));
    }

    window.API_BASE_URL = localStorage.getItem("ledgerco_api_base") || DEFAULT_API_BASE_URL;
})();
