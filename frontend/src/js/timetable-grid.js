// Shared by the admin and student timetable pages: weekly grid, day-by-day list, key dates
(function () {
  const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
  const SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const TYPE_LABEL = { lecture: "Lecture", practical: "Practical", tutorial: "Tutorial", clinical: "Clinical", cat: "CAT", exam: "Exam" };
  const KIND_LABEL = { semester: "Semester", cat: "CAT", exam: "Exam", holiday: "Holiday", event: "Event" };
  const PX = 1.2; // pixels per minute (72px per hour; keep in step with timetable.css)

  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined && text !== null) e.textContent = text;
    return e;
  }
  const mins = (t) => { const p = String(t).split(":"); return parseInt(p[0], 10) * 60 + parseInt(p[1], 10); };
  const hhmm = (n) => String(Math.floor(n / 60)).padStart(2, "0") + ":" + String(n % 60).padStart(2, "0");
  const pretty = (t) => hhmm(mins(t));
  const fmtDate = (s) => { const p = String(s).slice(0, 10).split("-"); return p[2] + "/" + p[1] + "/" + p[0]; };
  function todayDow() { const d = new Date().getDay(); return d === 0 ? 7 : d; }
  function todayStr() {
    const d = new Date(), z = (n) => String(n).padStart(2, "0");
    return d.getFullYear() + "-" + z(d.getMonth() + 1) + "-" + z(d.getDate());
  }
  const byTime = (a, b) => mins(a.start_time) - mins(b.start_time);

  // side-by-side lanes for classes that overlap in time on one day
  function layout(list) {
    const out = [];
    let cluster = [], clusterEnd = -1;
    const flush = () => {
      const lanesEnd = [];
      cluster.forEach((item) => {
        let lane = lanesEnd.findIndex((e) => e <= item.s);
        if (lane === -1) { lane = lanesEnd.length; lanesEnd.push(0); }
        lanesEnd[lane] = item.e;
        item.lane = lane;
      });
      cluster.forEach((item) => { item.lanes = lanesEnd.length; out.push(item); });
      cluster = [];
    };
    list.forEach((c) => {
      const item = { c: c, s: mins(c.start_time), e: mins(c.end_time) };
      if (cluster.length && item.s >= clusterEnd) { flush(); clusterEnd = -1; }
      cluster.push(item);
      clusterEnd = Math.max(clusterEnd, item.e);
    });
    if (cluster.length) flush();
    return out;
  }

  function fillBlock(b, c) {
    b.appendChild(el("b", "", c.unit_code || c.unit_name));
    if (c.unit_code) b.appendChild(el("span", "tt-name", c.unit_name));
    const meta = [c.venue, c.lecturer].filter(Boolean).join(" \u00b7 ");
    if (meta) b.appendChild(el("span", "tt-meta", meta));
    b.appendChild(el("span", "tt-time-text", pretty(c.start_time) + " - " + pretty(c.end_time)));
  }

  function renderGrid(box, classes, opts) {
    opts = opts || {};
    box.textContent = "";
    if (!classes.length) { box.appendChild(el("p", "tt-empty", opts.emptyText || "No classes yet.")); return; }
    const days = classes.some((c) => c.day_of_week === 7) ? 7 : 6;
    let start = Math.min.apply(null, classes.map((c) => mins(c.start_time)));
    let end = Math.max.apply(null, classes.map((c) => mins(c.end_time)));
    start = Math.floor(Math.min(start, 8 * 60) / 60) * 60;
    end = Math.ceil(Math.max(end, 17 * 60) / 60) * 60;
    const height = (end - start) * PX;

    const grid = el("div", "tt-grid");
    grid.style.setProperty("--days", days);
    const head = el("div", "tt-head");
    head.appendChild(el("div", "tt-corner"));
    for (let d = 1; d <= days; d++) head.appendChild(el("div", "tt-dayhead" + (d === opts.today ? " today" : ""), SHORT[d - 1]));
    grid.appendChild(head);

    const body = el("div", "tt-body");
    const times = el("div", "tt-times");
    times.style.height = height + "px";
    for (let m = start; m < end; m += 60) {
      const t = el("div", "tt-time", hhmm(m));
      t.style.top = (m - start) * PX + "px";
      times.appendChild(t);
    }
    body.appendChild(times);

    for (let d = 1; d <= days; d++) {
      const col = el("div", "tt-col" + (d === opts.today ? " today" : ""));
      col.style.height = height + "px";
      layout(classes.filter((c) => c.day_of_week === d).sort(byTime)).forEach((it) => {
        const c = it.c;
        const b = el("div", "tt-block tt-" + c.class_type);
        b.style.top = (it.s - start) * PX + "px";
        b.style.height = Math.max((it.e - it.s) * PX - 2, 24) + "px";
        b.style.left = (it.lane * 100 / it.lanes) + "%";
        b.style.width = (100 / it.lanes) + "%";
        b.title = c.unit_name + (c.venue ? " - " + c.venue : "");
        fillBlock(b, c);
        if (opts.onSelect) { b.classList.add("click"); b.addEventListener("click", () => opts.onSelect(c)); }
        col.appendChild(b);
      });
      body.appendChild(col);
    }
    grid.appendChild(body);
    box.appendChild(grid);
  }

  function renderDays(box, classes, opts) {
    opts = opts || {};
    box.textContent = "";
    for (let d = 1; d <= 7; d++) {
      const list = classes.filter((c) => c.day_of_week === d).sort(byTime);
      if (!list.length) continue;
      const sec = el("section", "tt-day" + (d === opts.today ? " today" : ""));
      sec.appendChild(el("h4", "", DAYS[d - 1] + (d === opts.today ? " (today)" : "")));
      list.forEach((c) => {
        const card = el("div", "tt-card tt-" + c.class_type);
        card.appendChild(el("span", "tt-ctime", pretty(c.start_time) + " - " + pretty(c.end_time)));
        const info = el("div", "tt-cinfo");
        info.appendChild(el("b", "", (c.unit_code ? c.unit_code + " " : "") + c.unit_name));
        info.appendChild(el("span", "", [TYPE_LABEL[c.class_type], c.venue, c.lecturer].filter(Boolean).join(" \u00b7 ")));
        card.appendChild(info);
        if (opts.onSelect) { card.classList.add("click"); card.addEventListener("click", () => opts.onSelect(c)); }
        sec.appendChild(card);
      });
      box.appendChild(sec);
    }
  }

  function renderEvents(box, events, opts) {
    opts = opts || {};
    box.textContent = "";
    if (!events.length) { box.appendChild(el("p", "tt-empty", opts.emptyText || "Nothing posted yet.")); return; }
    const today = todayStr();
    events.forEach((e) => {
      const last = e.end_date || e.event_date;
      const row = el("div", "tt-ev" + (last < today ? " past" : ""));
      row.appendChild(el("span", "tt-badge tt-k-" + e.kind, KIND_LABEL[e.kind] || "Event"));
      const info = el("div", "tt-evinfo");
      info.appendChild(el("b", "", e.title));
      const when = fmtDate(e.event_date) + (e.end_date && e.end_date !== e.event_date ? " - " + fmtDate(e.end_date) : "");
      info.appendChild(el("span", "", when + (e.year_of_study ? " \u00b7 Year " + e.year_of_study : "")));
      if (e.details) info.appendChild(el("span", "tt-meta", e.details));
      row.appendChild(info);
      if (opts.actions) row.appendChild(opts.actions(e));
      box.appendChild(row);
    });
  }

  function nextClass(classes, now) {
    const dow = now.getDay() === 0 ? 7 : now.getDay();
    const nowMin = now.getHours() * 60 + now.getMinutes();
    let best = null, bestDelta = Infinity;
    classes.forEach((c) => {
      let delta = (c.day_of_week - dow) * 1440 + mins(c.start_time) - nowMin;
      if (delta < 0) delta += 7 * 1440;
      if (delta < bestDelta) { best = c; bestDelta = delta; }
    });
    return best ? { c: best, inMin: bestDelta } : null;
  }

  function describeNext(n, now) {
    if (!n) return "";
    const c = n.c;
    const dow = now.getDay() === 0 ? 7 : now.getDay();
    let when;
    if (n.inMin < 60) when = "in " + n.inMin + " min";
    else if (c.day_of_week === dow && n.inMin < 1440) when = "today at " + pretty(c.start_time);
    else when = DAYS[c.day_of_week - 1] + " at " + pretty(c.start_time);
    return "Next class: " + (c.unit_code ? c.unit_code + " " : "") + c.unit_name + (c.venue ? " (" + c.venue + ")" : "") + " - " + when;
  }

  window.tt = { el: el, DAYS: DAYS, TYPE_LABEL: TYPE_LABEL, KIND_LABEL: KIND_LABEL, todayDow: todayDow,
                renderGrid: renderGrid, renderDays: renderDays, renderEvents: renderEvents,
                nextClass: nextClass, describeNext: describeNext };
})();
