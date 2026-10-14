// Shared by every admin page: login check, top bar, left menu
(function () {
  const token = sessionStorage.getItem("admin_token");
  if (!token) { location.href = "index.html"; return; }

  const icon = (d) => `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${d}</svg>`;
  const NAV = [
    ["dashboard", "Dashboard", "dashboard.html", icon('<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/>')],
    ["students", "Students", "students.html", icon('<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>')],
    ["fees", "Fees", "fees.html", icon('<rect x="2" y="5" width="20" height="14" rx="2"/><line x1="2" y1="10" x2="22" y2="10"/>')],
    ["messages", "Messages", "messages.html", icon('<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>')],
    ["academic", "Academic", "academic.html", icon('<path d="M22 10L12 5 2 10l10 5 10-5z"/><path d="M6 12v5c3 2 9 2 12 0v-5"/>')],
    ["timetable", "Timetable", "timetable.html", icon('<rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>')],
    ["settings", "Settings", "settings.html", icon('<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>')],
  ];

  const page = document.body.dataset.page;
  const content = document.getElementById("content");

  const shell = document.createElement("div");
  shell.innerHTML = `
    <header class="topbar">
      <button id="burger" aria-label="Menu">${icon('<line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/>')}</button>
      <div class="top-right">
        <div class="user">
          <button class="user-btn" id="userBtn"><span id="hiName">Admin</span> &#9662;</button>
          <div class="menu" id="menu" hidden><button id="signout">Sign out</button></div>
        </div>
      </div>
    </header>
    <aside class="sidebar">
      <div class="brand"><img src="../assets/logo.jpg" alt="Logo"></div>
      <nav class="nav">${NAV.map(([k, label, href, ic]) => `<a href="${href}" class="${k === page ? "active" : ""}">${ic}<span>${label}</span></a>`).join("")}</nav>
    </aside>
    <main class="main" id="main"></main>`;
  document.body.prepend(...shell.children);
  document.getElementById("main").appendChild(content);

  document.getElementById("burger").addEventListener("click", () => {
    if (window.innerWidth <= 900) document.body.classList.toggle("open-mobile");
    else document.body.classList.toggle("collapsed");
  });
  const menu = document.getElementById("menu");
  document.getElementById("userBtn").addEventListener("click", (e) => { e.stopPropagation(); menu.hidden = !menu.hidden; });
  document.addEventListener("click", () => (menu.hidden = true));

  function signOut() {
    sessionStorage.clear();
    location.href = "index.html";
  }
  document.getElementById("signout").addEventListener("click", signOut);

  const money = (n) => "KES " + Number(n || 0).toLocaleString("en-KE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  async function api(path, opts = {}) {
    const res = await fetch(API_BASE + path, {
      ...opts,
      headers: { "Content-Type": "application/json", Authorization: "Bearer " + token, ...(opts.headers || {}) },
    });
    if (res.status === 401 || res.status === 403) { signOut(); throw new Error("signed out"); }
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      let m = "Something went wrong";
      if (typeof data.detail === "string") m = data.detail;
      else if (Array.isArray(data.detail)) m = "Please check: " + data.detail.map((d) => ((d.loc || []).slice(-1)[0] || "field") + " - " + d.msg).join("; ");
      throw new Error(m);
    }
    return data;
  }

  // Show the last saved data instantly, then refresh it from the server
  async function apiCached(path, onData) {
    const key = "cache:" + path;
    try { const old = sessionStorage.getItem(key); if (old) onData(JSON.parse(old)); } catch (e) {}
    const fresh = await api(path);
    try { sessionStorage.setItem(key, JSON.stringify(fresh)); } catch (e) {}
    onData(fresh);
    return fresh;
  }

  window.admin = { api, apiCached, money };
})();
