(function () {
  const form = document.getElementById("loginForm");
  const reg = document.getElementById("reg");
  const pw = document.getElementById("pw");
  const msg = document.getElementById("msg");
  const btn = document.getElementById("submitBtn");
  const remember = document.getElementById("remember");

  function show(text, type) {
    msg.textContent = text;
    msg.className = "msg " + type;
    msg.hidden = false;
  }

  document.getElementById("togglePw").addEventListener("click", () => {
    pw.type = pw.type === "password" ? "text" : "password";
  });

  document.getElementById("forgot").addEventListener("click", (e) => {
    e.preventDefault();
    show("Please visit ABA 210 to have your password reset.", "info");
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    msg.hidden = true;
    const regNo = reg.value.trim();
    if (!regNo || !pw.value) {
      show("Enter your registration number and password.", "error");
      return;
    }
    btn.disabled = true;
    btn.textContent = "Signing in...";
    try {
      const res = await fetch(API_BASE + "/auth/student/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reg_number: regNo, password: pw.value }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        show(typeof data.detail === "string" ? data.detail : "Could not sign in. Check your details.", "error");
        return;
      }
      const store = remember.checked ? localStorage : sessionStorage;
      store.setItem("portal_token", data.token);
      store.setItem("portal_student", JSON.stringify(data.student));
      window.location.href = "student/dashboard.html";
    } catch (err) {
      show("Cannot reach the server. Check your connection and try again.", "error");
    } finally {
      btn.disabled = false;
      btn.textContent = "Sign in";
    }
  });
})();
