// Shared by every student page: login check, top bar, left menu
(function () {
  const store = localStorage.getItem("portal_token") ? localStorage : sessionStorage;
  const token = store.getItem("portal_token");
  if (!token) { location.href = "../index.html"; return; }

  // Top bar styles live here so every student page gets the identical bar
  const shellCss = `
    .topbar{position:fixed!important;top:0;left:0;right:0;height:76px!important;background:#fff!important;color:#0b3a7e!important;border-bottom:1px solid #dfe3ee;box-shadow:0 1px 4px rgba(20,30,60,.06);display:flex!important;align-items:center;justify-content:flex-start!important;padding:0 20px 0 0!important;z-index:30}
    .topbar button{background:none;border:0;color:inherit;cursor:pointer;font:inherit}
    .top-brand{width:220px;flex:none;height:100%;display:flex;align-items:center;justify-content:center}
    .top-brand img{height:56px!important;width:auto!important;max-width:180px!important;object-fit:contain}
    #burger{flex:none;padding:6px 8px}
    #burger svg{width:26px;height:26px}
    .top-school{flex:1;min-width:0;margin:0 16px;font-size:24px;font-weight:700;line-height:1.2;color:#1f7ad6;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;text-align:left;position:static!important;transform:none!important;height:auto!important}
    .top-right{display:flex;align-items:center;gap:18px;flex:none}
    .user-btn{border-left:1px solid #dfe3ee!important;font-size:16px}
    .sidebar{top:76px!important}
    .main{margin-top:76px!important;min-height:calc(100vh - 76px)}
    .page-grid{min-height:calc(100vh - 76px)}
    .chat-wrap{height:calc(100vh - 76px)}
    .site-note{padding:14px 20px;text-align:center;font-size:12.5px;color:#55607a;background:#fff;border-top:1px solid #dfe3ee;margin:0}
    @media (max-width:900px){.top-brand{width:auto;padding:0 6px 0 12px}.top-brand img{height:46px!important}.top-school{font-size:17px;white-space:normal;margin:0 8px}}
  `;
  const styleEl = document.createElement("style");
  styleEl.textContent = shellCss;
  document.head.appendChild(styleEl);

  const icon = (d) => `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${d}</svg>`;
  const NAV = [
    ["dashboard", "Dashboard", "dashboard.html", icon('<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/>')],
    ["messages", "Message", "messages.html", icon('<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>')],
    ["financials", "Financials", "financials.html", icon('<rect x="2" y="5" width="20" height="14" rx="2"/><line x1="2" y1="10" x2="22" y2="10"/>')],
    ["academic", "Academic", "academic.html", icon('<path d="M22 10L12 5 2 10l10 5 10-5z"/><path d="M6 12v5c3 2 9 2 12 0v-5"/>')],
    ["timetable", "Timetable", "timetable.html", icon('<rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>')],
  ];

  const page = document.body.dataset.page;
  const content = document.getElementById("content");

  const shell = document.createElement("div");
  shell.innerHTML = `
    <header class="topbar">
      <a class="top-brand" href="dashboard.html"><img src="../assets/logo.jpg" alt="Logo"></a>
      <button id="burger" aria-label="Menu">${icon('<line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/>')}</button>
      <span class="top-school" id="topSchool"></span>
      <div class="top-right">
        <a class="bell" href="messages.html" aria-label="Messages">
          ${icon('<path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.7 21a2 2 0 0 1-3.4 0"/>')}
          <span class="badge" id="badge" hidden></span>
        </a>
        <div class="user">
          <button class="user-btn" id="userBtn"><span id="avatarSlot"></span><span id="hiName">Hi</span> &#9662;</button>
          <div class="menu" id="menu" hidden><button id="changePhoto">Change photo</button><button id="removePhoto">Remove photo</button><button id="signout">Sign out</button></div>
        </div>
      </div>
    </header>
    <aside class="sidebar">
      <nav class="nav">${NAV.map(([k, label, href, ic]) => `<a href="${href}" class="${k === page ? "active" : ""}">${ic}<span>${label}</span></a>`).join("")}</nav>
      <p style="padding:14px 16px;font-size:.72rem;color:#6b7690;line-height:1.4">Copyright &copy; 2026- ABNO Softwares International</p>
    </aside>
    <main class="main" id="main"></main>`;
  document.body.prepend(...shell.children);
  document.getElementById("main").appendChild(content);
  const siteNote = document.createElement("p");
  siteNote.className = "site-note";
  siteNote.textContent = "This site is for Clinical Medicine students only.";
  document.getElementById("main").appendChild(siteNote);

  // ----- school name: shown instantly from the last visit, then refreshed -----
  const topSchool = document.getElementById("topSchool");
  try { topSchool.textContent = localStorage.getItem("school_name") || ""; } catch (e) {}
  function setSchool(name) {
    topSchool.textContent = name || "";
    try { if (name) localStorage.setItem("school_name", name); else localStorage.removeItem("school_name"); } catch (e) {}
  }
  fetch(API_BASE + "/public/school")
    .then((r) => (r.ok ? r.json() : null))
    .then((d) => { if (d) setSchool(d.school_name); })
    .catch(() => {});

  // menu toggles
  document.getElementById("burger").addEventListener("click", () => {
    if (window.innerWidth <= 900) document.body.classList.toggle("open-mobile");
    else document.body.classList.toggle("collapsed");
  });
  const menu = document.getElementById("menu");
  document.getElementById("userBtn").addEventListener("click", (e) => { e.stopPropagation(); menu.hidden = !menu.hidden; });
  document.addEventListener("click", () => (menu.hidden = true));
  document.getElementById("signout").addEventListener("click", () => {
    localStorage.removeItem("portal_token"); sessionStorage.removeItem("portal_token");
    localStorage.removeItem("portal_student"); sessionStorage.removeItem("portal_student");
    location.href = "../index.html";
  });

  // ----- profile photo -----
  function setAvatar(url) {
    const slot = document.getElementById("avatarSlot");
    slot.textContent = "";
    if (url) {
      const img = document.createElement("img");
      img.className = "avatar"; img.src = url; img.alt = "";
      slot.appendChild(img);
    } else {
      const first = document.getElementById("hiName").textContent.replace("Hi, ", "") || "S";
      const d = document.createElement("span");
      d.className = "avatar"; d.textContent = first[0].toUpperCase();
      slot.appendChild(d);
    }
  }
  async function photoRequest(method, body) {
    const res = await fetch(API_BASE + "/student/photo", { method, body, headers: { Authorization: "Bearer " + token } });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Could not update the photo");
    return data;
  }
  const picker = document.createElement("input");
  picker.type = "file"; picker.accept = "image/jpeg,image/png,image/webp"; picker.hidden = true;
  document.body.appendChild(picker);
  document.getElementById("changePhoto").addEventListener("click", () => picker.click());
  picker.addEventListener("change", async () => {
    const file = picker.files[0];
    picker.value = "";
    if (!file) return;
    if (!file.type.startsWith("image/")) { alert("Please choose a picture file."); return; }
    if (file.size > 5 * 1024 * 1024) { alert("That picture is too large. Choose one under 5 MB."); return; }
    try {
      const fd = new FormData();
      fd.append("file", file);
      const data = await photoRequest("POST", fd);
      setAvatar(data.photo_url);
    } catch (e) { alert(e.message); }
  });
  document.getElementById("removePhoto").addEventListener("click", async () => {
    try { await photoRequest("DELETE"); setAvatar(null); } catch (e) { alert(e.message); }
  });

  // helpers shared with the page scripts
  const money = (n) => "KES " + Number(n || 0).toLocaleString("en-KE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  function signOutNow() {
    localStorage.removeItem("portal_token"); sessionStorage.removeItem("portal_token");
    location.href = "../index.html";
  }
  async function api(path, opts = {}) {
    const res = await fetch(API_BASE + path, {
      ...opts,
      headers: { "Content-Type": "application/json", Authorization: "Bearer " + token, ...(opts.headers || {}) },
    });
    if (res.status === 401) { signOutNow(); throw new Error("signed out"); }
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Something went wrong");
    return data;
  }
  async function download(path, filename) {
    const res = await fetch(API_BASE + path, { headers: { Authorization: "Bearer " + token } });
    if (res.status === 401) { signOutNow(); throw new Error("signed out"); }
    if (!res.ok) throw new Error("Could not download the file");
    const url = URL.createObjectURL(await res.blob());
    const a = document.createElement("a");
    a.href = url; a.download = filename;
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
  }
  const titleCase = (s) => s.toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());

  const ready = api("/student/me").then((me) => {
    const parts = (me.name || "").trim().split(/\s+/).filter(Boolean);
    const first = titleCase(parts[1] || parts[0] || "Student");  // second name if there is one
    document.getElementById("hiName").textContent = "Hi, " + first;
    const slot = document.getElementById("avatarSlot");
    if (me.photo_url) { const img = document.createElement("img"); img.className = "avatar"; img.src = me.photo_url; img.alt = ""; slot.appendChild(img); }
    else { const d = document.createElement("span"); d.className = "avatar"; d.textContent = first[0].toUpperCase(); slot.appendChild(d); }
    const badge = document.getElementById("badge");
    if (me.unread > 0) { badge.textContent = me.unread > 9 ? "9+" : me.unread; badge.hidden = false; }
    const sn = (me.session || {}).school_name;
    if (sn && !topSchool.textContent) setSchool(sn);
    me.first = first;
    return me;
  });

  window.portal = { api, money, ready, titleCase, download };
})();
