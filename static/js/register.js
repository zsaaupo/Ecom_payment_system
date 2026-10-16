// Ledger & Co. — register page.

document.addEventListener("DOMContentLoaded", () => {
    if (Auth.isAuthenticated()) {
        window.location.href = "index.html";
        return;
    }

    document.getElementById("register-form").addEventListener("submit", async (e) => {
        e.preventDefault();
        const submitBtn = e.target.querySelector("button[type=submit]");
        submitBtn.disabled = true;
        submitBtn.textContent = "Creating account…";

        const payload = {
            username: document.getElementById("username").value.trim(),
            email: document.getElementById("email").value.trim(),
            password: document.getElementById("password").value,
            first_name: document.getElementById("first_name").value.trim(),
            last_name: document.getElementById("last_name").value.trim(),
            phone_number: document.getElementById("phone_number").value.trim(),
        };

        try {
            const data = await Api.register(payload);
            Auth.setSession(data.token, data.user);
            toast(`Welcome, ${data.user.first_name || data.user.username}! Your account is ready.`, "success");
            window.location.href = "index.html";
        } catch (err) {
            toast(friendlyError(err), "error");
            submitBtn.disabled = false;
            submitBtn.textContent = "Create account";
        }
    });
});
