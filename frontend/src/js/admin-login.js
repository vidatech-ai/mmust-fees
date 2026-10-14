(function () {
  // Already signed in? Skip the form.
  if (sessionStorage.getItem("admin_token")) {
    location.href = "dashboard.html";
    return;
  }

  const form = document.getElementById("adminForm");
  const user = document.getElementById("user");
  const pw = document.getElementById("pw");
  const msg = document.getElementById("msg");
  const btn = document.getElementById("submitBtn");

  function show(text) {
    msg.textContent = text;
    msg.className = "msg error";
    msg.hidden = false;
  }

  document.getElementById("togglePw").addEventListener("click", () => {
    pw.type = pw.type === "password" ? "text" : "password";
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    msg.hidden = true;
    if (!user.value.trim() || !pw.value) {
      show("Enter your username and password.");
      return;
    }
    btn.disabled = true;
    btn.textContent = "Signing in...";
    try {
      const res = await fetch(API_BASE + "/auth/admin/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: user.value.trim(), password: pw.value }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        show(typeof data.detail === "string" ? data.detail : "Could not sign in.");
        return;
      }
      sessionStorage.setItem("admin_token", data.token);
      location.href = "dashboard.html";
    } catch (err) {
      show("Cannot reach the server. Check your connection and try again.");
    } finally {
      btn.disabled = false;
      btn.textContent = "Sign in";
    }
  });
})();
