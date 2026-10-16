// Ledger & Co. — login page.

document.addEventListener("DOMContentLoaded", () => {
    if (Auth.isAuthenticated()) {
        window.location.href = "index.html";
        return;
    }

    document.getElementById("login-form").addEventListener("submit", async (e) => {
        e.preventDefault();
        const submitBtn = e.target.querySelector("button[type=submit]");
        submitBtn.disabled = true;
        submitBtn.textContent = "Logging in…";

        try {
            const data = await Api.login(
                document.getElementById("username").value.trim(),
                document.getElementById("password").value
            );
            Auth.setSession(data.token, data.user);
            toast(`Welcome back, ${data.user.first_name || data.user.username}.`, "success");
            const next = qs("next");
            window.location.href = safeReturnPath(next);
        } catch (err) {
            toast(friendlyError(err), "error");
            submitBtn.disabled = false;
            submitBtn.textContent = "Log in";
        }
    });
});
