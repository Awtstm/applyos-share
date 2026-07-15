/* ApplyOS UI — vanilla JS, fetch-based. Hash routing over three views;
   all data comes from the /api routes (thin wrappers over the pipeline). */

"use strict";

/* ── helpers ─────────────────────────────────────────────────────── */

async function api(method, url, body) {
  const options = { method, headers: {} };
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  const response = await fetch(url, options);
  // parse via text so a non-JSON error page (e.g. a plain-text 500) yields
  // a readable message instead of Safari's cryptic .json() SyntaxError
  const text = await response.text();
  let data = null;
  if (text) {
    try { data = JSON.parse(text); } catch { data = null; }
  }
  if (!response.ok) {
    const detail = data && data.detail;
    const fallback = `HTTP ${response.status}` + (data ? "" : `: ${text.slice(0, 200)}`);
    const err = new Error(
      typeof detail === "string" ? detail : (detail && detail.detail) || fallback
    );
    err.status = response.status;
    err.errors = (detail && detail.errors) || [];
    throw err;
  }
  return data;
}

/* h("div", {class: "card", onclick: fn}, child, "text") — element helper;
   user data always lands in textContent, never in markup. */
function h(tag, attrs, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else if (key === "checked") node.checked = value;
    else if (key === "value") node.value = value;
    else if (key === "disabled") node.disabled = value;
    else node.setAttribute(key, value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined) continue;
    node.append(child.nodeType ? child : document.createTextNode(child));
  }
  return node;
}

function debounce(fn, ms) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}

let META = null;
async function meta() {
  if (!META) META = await api("GET", "/api/meta");
  return META;
}

/* ── router ──────────────────────────────────────────────────────── */

const VIEWS = {
  new: renderViewNew,
  pipeline: renderViewPipeline,
  profile: renderViewProfile,
};

function route() {
  const name = (location.hash || "#new").slice(1);
  const view = VIEWS[name] ? name : "new";
  document.querySelectorAll("nav a").forEach((a) =>
    a.classList.toggle("active", a.dataset.view === view)
  );
  document.querySelectorAll("main section").forEach((section) => {
    section.hidden = section.id !== `view-${view}`;
  });
  VIEWS[view](document.getElementById(`view-${view}`));
}

window.addEventListener("hashchange", route);
window.addEventListener("DOMContentLoaded", route);

/* ── view: Neue Bewerbung ────────────────────────────────────────── */

const newState = {
  phase: "input", // input | loading | review | rendering | preview
  current: null,  // {id, application, report}
  pool: null,
  error: null,
  reviseNotes: null,
};

const LOADING_STAGES = [
  "Posting wird analysiert …",
  "Tailoring-Plan wird erstellt …",
  "Anschreiben wird formuliert …",
  "Validierung läuft …",
];

function bulletText(bullet, lang) {
  return lang === "de" ? bullet.text_de : bullet.text_en;
}

function renderViewNew(root) {
  if (newState.phase === "input" || newState.phase === "loading") {
    renderNewInput(root);
  } else {
    renderReview(root);
  }
}

function renderNewInput(root) {
  const loading = newState.phase === "loading";
  const paste = h("textarea", {
    class: "paste-hero", id: "paste",
    placeholder: "Stellenausschreibung hier einfügen … (Cmd/Ctrl+Enter startet die Analyse)",
    disabled: loading,
  });
  const url = h("input", { id: "url", placeholder: "… oder Posting-URL", disabled: loading });
  const lang = h("select", { id: "lang", disabled: loading },
    h("option", { value: "auto" }, "Sprache: auto"),
    h("option", { value: "de" }, "Deutsch"),
    h("option", { value: "en" }, "Englisch"));
  const status = h("p", { class: "loading", id: "stage" }, "");
  const button = h("button", { class: "primary", disabled: loading,
    onclick: () => startAnalysis(paste.value, url.value, lang.value, status, button) },
    loading ? "Läuft …" : "Analysieren");

  paste.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") button.click();
  });
  // paste-and-Enter: after pasting into the empty field, plain Enter submits
  // (focus moves to the button; editing the text re-enters normal typing)
  paste.addEventListener("paste", () => {
    if (!paste.value.trim()) setTimeout(() => button.focus(), 0);
  });

  root.replaceChildren(
    h("h1", {}, "Neue Bewerbung"),
    h("div", { class: "card stack" },
      paste,
      h("div", { class: "row" }, h("div", { class: "grow" }, url), lang, button),
      status,
      newState.error ? h("div", { class: "report fail" }, newState.error) : null,
    ),
  );
  if (!loading) paste.focus();
}

async function startAnalysis(text, url, lang, statusNode, button) {
  if (!text.trim() && !url.trim()) return;
  newState.phase = "loading";
  newState.error = null;
  button.disabled = true;
  let stage = 0;
  statusNode.textContent = LOADING_STAGES[0];
  const ticker = setInterval(() => {
    stage = Math.min(stage + 1, LOADING_STAGES.length - 1);
    statusNode.textContent = LOADING_STAGES[stage];
  }, 14000);
  try {
    const body = { lang: lang === "auto" ? null : lang };
    if (url.trim()) body.url = url.trim();
    else body.text = text;
    const [created, pool] = await Promise.all([
      api("POST", "/api/applications", body),
      api("GET", "/api/profile/pool"),
      meta(),
    ]);
    newState.current = created;
    newState.pool = pool;
    newState.reviseNotes = created.notes || null; // z. B. "Automatisch gekürzt …"
    newState.phase = "review";
  } catch (err) {
    newState.phase = "input";
    newState.error = err.message + (err.errors.length ? ` — ${err.errors.join("; ")}` : "");
  } finally {
    clearInterval(ticker);
    route();
  }
}

/* ── review editor ───────────────────────────────────────────────── */

const scheduleValidate = debounce(saveAndValidate, 700);

async function saveAndValidate() {
  const { id, application } = newState.current;
  try {
    const result = await api("PUT", `/api/applications/${id}/plan`, application);
    newState.current.report = result.report;
  } catch (err) {
    newState.current.report = { ok: false, errors: err.errors.length ? err.errors : [err.message] };
  }
  updateReportPanel();
}

function updateReportPanel() {
  const report = newState.current.report;
  const panel = document.getElementById("report-panel");
  const renderButton = document.getElementById("render-button");
  if (!panel) return;
  panel.className = "report " + (report.ok ? "ok" : "fail");
  panel.replaceChildren(
    report.ok ? "✓ Validierung bestanden — bereit zum Rendern."
      : h("div", {}, "✗ Validierung fehlgeschlagen:",
          h("ul", {}, report.errors.map((e) => h("li", {}, e)))),
  );
  if (renderButton) renderButton.disabled = !report.ok || newState.phase === "rendering";
  updateBudget();
  updateBodyBudget();
}

function updateBodyBudget() {
  const node = document.getElementById("body-budget");
  if (!node) return;
  const slots = newState.current.application.slots;
  const total = ["hook", "fit_1", "fit_2", "fit_3", "closing_variant"]
    .reduce((sum, key) => sum + (slots[key] || "").length, 0);
  node.textContent = `Body gesamt: ${total}/${META.letter_body_max}`;
  node.classList.toggle("over", total > META.letter_body_max);
}

function totalBullets(plan) {
  return plan.stations.reduce((sum, s) => sum + s.bullets.length, 0);
}

function updateBudget() {
  const node = document.getElementById("budget");
  if (!node) return;
  const total = totalBullets(newState.current.application.plan);
  node.textContent = `${total}/${META.max_total_bullets} Bullets`;
  node.classList.toggle("over", total > META.max_total_bullets);
}

function stationCard(poolStation, app) {
  const lang = app.analysis.language;
  const plan = app.plan;
  const planEntry = () => plan.stations.find((s) => s.station_id === poolStation.id);

  const bulletRow = (bullet) => {
    const entry = planEntry();
    const choice = entry && entry.bullets.find((b) => b.bullet_id === bullet.id);
    const original = bulletText(bullet, lang);
    const text = h("div", {
      class: "text" + (choice && choice.rephrased_text ? " edited" : ""),
      tabindex: "0",
      title: "Klicken zum Umformulieren",
    }, (choice && choice.rephrased_text) || original);

    const startEdit = () => {
      const current = planEntry() && planEntry().bullets.find((b) => b.bullet_id === bullet.id);
      if (!current) return; // only selected bullets are editable
      const editor = h("textarea", { rows: "3", value: current.rephrased_text || original });
      const finish = () => {
        const value = editor.value.trim();
        current.rephrased_text = value && value !== original ? value : null;
        text.textContent = current.rephrased_text || original;
        text.classList.toggle("edited", !!current.rephrased_text);
        editor.replaceWith(text);
        scheduleValidate();
      };
      editor.addEventListener("blur", finish);
      editor.addEventListener("keydown", (event) => {
        if (event.key === "Escape" || ((event.metaKey || event.ctrlKey) && event.key === "Enter")) {
          event.preventDefault();
          editor.blur();
        }
      });
      text.replaceWith(editor);
      editor.focus();
    };
    text.addEventListener("click", startEdit);
    text.addEventListener("keydown", (e) => { if (e.key === "Enter") startEdit(); });

    const checkbox = h("input", {
      type: "checkbox", checked: !!choice,
      onchange: () => {
        let entryNow = planEntry();
        if (checkbox.checked) {
          if (!entryNow) {
            entryNow = { station_id: poolStation.id, bullets: [] };
            plan.stations.push(entryNow);
          }
          // keep pool order when inserting
          const selected = new Set(entryNow.bullets.map((b) => b.bullet_id));
          selected.add(bullet.id);
          const kept = new Map(entryNow.bullets.map((b) => [b.bullet_id, b]));
          entryNow.bullets = poolStation.bullets
            .filter((b) => selected.has(b.id))
            .map((b) => kept.get(b.id) || { bullet_id: b.id, rephrased_text: null });
        } else if (entryNow) {
          entryNow.bullets = entryNow.bullets.filter((b) => b.bullet_id !== bullet.id);
          // keep the empty entry: the validator reports the gapless-CV rule
          // ("every station needs at least one bullet") instead of a silent drop
        }
        updateBudget();
        scheduleValidate();
      },
    });
    return h("div", { class: "bullet" }, checkbox, text);
  };

  return h("div", { class: "card" },
    h("div", { class: "row" },
      h("strong", {}, lang === "de" ? poolStation.role_de : poolStation.role_en),
      h("span", { class: "muted small" }, `${poolStation.employer} · ${poolStation.period}`)),
    poolStation.bullets.map(bulletRow));
}

function slotEditor(app, name, label, maxChars) {
  const value = app.slots[name] || "";
  const counter = h("div", { class: "counter" + (value.length > maxChars ? " over" : "") },
    `${value.length}/${maxChars}`);
  const area = h("textarea", { rows: "4", value,
    oninput: () => {
      const text = area.value;
      app.slots[name] = name === "fit_3" && !text.trim() ? null : text;
      counter.textContent = `${text.length}/${maxChars}`;
      counter.classList.toggle("over", text.length > maxChars);
      updateBodyBudget();
      scheduleValidate();
    } });
  return h("div", { class: "stack" }, h("strong", { class: "small" }, label), area, counter);
}

function matchCard(app) {
  const match = app.match;
  // replaceChildren stringifies non-Node arguments — never return null here
  if (!match) return document.createDocumentFragment();
  return h("div", { class: "card" },
    h("div", { class: "row" },
      h("span", { class: "match-score" }, String(match.score)),
      h("div", { class: "grow" },
        h("strong", {}, "Profil-Match"),
        h("div", { class: "muted small" }, "Entscheidungshilfe: passt diese Rolle?"))),
    h("div", { class: "row", style: "align-items: flex-start" },
      h("div", { class: "grow" },
        h("strong", { class: "small" }, "Stärken für diese Rolle"),
        h("ul", { class: "small" }, match.strengths.map((s) => h("li", {}, s)))),
      h("div", { class: "grow" },
        h("strong", { class: "small" }, "Schwächen / Lücken"),
        h("ul", { class: "small" }, match.gaps.map((g) => h("li", {}, g))))));
}

function renderReview(root) {
  const { application: app, id } = newState.current;
  const pool = newState.pool;
  const lang = app.analysis.language;
  const analysis = app.analysis;

  const summary = h("div", { class: "card" },
    h("h2", {}, `${analysis.company} — ${analysis.role_title}`),
    h("p", { class: "muted small" },
      `Sprache ${analysis.language} · ${analysis.seniority}` +
      (analysis.contact_person ? ` · Kontakt: ${analysis.contact_person}` : "")),
    h("p", {}, "Anforderungen: " + analysis.top_requirements.join(", ")),
    analysis.notes ? h("p", { class: "muted small" }, analysis.notes) : null);

  const checkList = (entries, selectedIds, onToggle) =>
    entries.map((entry) => {
      const box = h("input", { type: "checkbox", checked: selectedIds.includes(entry.id),
        onchange: () => onToggle(entry.id, box.checked) });
      return h("label", { class: "bullet" }, box,
        h("span", { class: "text" }, entry.label_de
          ? (lang === "de" ? entry.label_de : entry.label_en)
          : bulletText(entry, lang)));
    });

  const extras = checkList(pool.extracurricular, app.plan.extracurricular_ids, (eid, on) => {
    const ids = new Set(app.plan.extracurricular_ids);
    if (on) ids.add(eid); else ids.delete(eid);
    app.plan.extracurricular_ids = pool.extracurricular
      .map((e) => e.id).filter((x) => ids.has(x));
    scheduleValidate();
  });

  const skills = checkList(pool.skills, app.plan.skills_order, (sid, on) => {
    if (on) app.plan.skills_order.push(sid);
    else app.plan.skills_order = app.plan.skills_order.filter((x) => x !== sid);
    scheduleValidate();
  });

  const locationNote = h("label", { class: "row" },
    h("input", { type: "checkbox", checked: app.plan.flags.mention_location_note,
      onchange: (e) => { app.plan.flags.mention_location_note = e.target.checked; scheduleValidate(); } }),
    "Standort-Baustein im Anschreiben erwähnen");

  const slotMax = META.max_slot_chars;
  const renderButton = h("button", { class: "primary", id: "render-button",
    disabled: !newState.current.report.ok,
    onclick: () => doRender(renderButton) }, "PDFs rendern");

  const preview = h("div", { id: "preview-area" });
  if (newState.phase === "preview") mountPreview(preview, id);

  root.replaceChildren(
    h("h1", {}, "Review"),
    summary,
    matchCard(app),
    h("div", { class: "row" },
      h("h2", { class: "grow" }, "CV-Plan"),
      h("span", { class: "counter", id: "budget" }, "")),
    ...pool.stations.map((station) => stationCard(station, app)),
    h("div", { class: "card" }, h("h2", {}, "Engagement"), extras),
    h("div", { class: "card" }, h("h2", {}, "Skills (Reihenfolge = Auswahl-Reihenfolge)"), skills),
    h("div", { class: "row" },
      h("h2", { class: "grow" }, "Anschreiben"),
      h("span", { class: "counter", id: "body-budget" }, "")),
    h("div", { class: "card stack" },
      slotEditor(app, "hook", "Hook", slotMax.hook),
      slotEditor(app, "fit_1", "Fit 1", slotMax.fit),
      slotEditor(app, "fit_2", "Fit 2", slotMax.fit),
      slotEditor(app, "fit_3", "Fit 3 (optional)", slotMax.fit),
      slotEditor(app, "closing_variant", "Abschluss", slotMax.closing_variant),
      locationNote),
    reviseCard(),
    h("div", { class: "report", id: "report-panel" }),
    h("div", { class: "row" },
      renderButton,
      h("button", { onclick: () => saveAndValidate() }, "Erneut validieren"),
      h("button", { class: "linklike", onclick: resetNew }, "Neues Posting")),
    preview,
  );
  updateReportPanel();
}

function reviseCard() {
  const input = h("textarea", { rows: "2",
    placeholder: 'Überarbeitung anweisen … z. B. "Kürze Fit 1 und 2, erstelle dafür ' +
      'einen Fit 3, und erwähne meine Muttersprache Deutsch im Abschluss."' });
  const status = h("span", { class: "loading" }, "");
  const button = h("button", { onclick: () => doRevise(input, button, status) },
    "Überarbeiten");
  input.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") button.click();
  });
  return h("div", { class: "card stack" },
    h("strong", { class: "small" }, "Überarbeitung anweisen"),
    h("p", { class: "muted small", style: "margin:0" },
      "Gleiche Faktengrenzen wie immer: nur Profil-Inhalte, keine neuen Zahlen "
      + "oder Behauptungen. Nicht Umsetzbares wird vermerkt."),
    input,
    h("div", { class: "row" }, button, status),
    newState.reviseNotes
      ? h("div", { class: "report" }, "Hinweis: " + newState.reviseNotes)
      : null);
}

async function doRevise(input, button, status) {
  const instruction = input.value.trim();
  if (!instruction) return;
  button.disabled = true;
  input.disabled = true;
  status.textContent = "Überarbeitung läuft …";
  try {
    const result = await api(
      "POST", `/api/applications/${newState.current.id}/revise`, { instruction }
    );
    newState.current.application = result.application;
    newState.current.report = result.report;
    newState.reviseNotes = result.notes;
    if (newState.phase === "preview") newState.phase = "review"; // PDFs sind jetzt veraltet
    renderReview(document.getElementById("view-new"));
  } catch (err) {
    status.textContent = "";
    button.disabled = false;
    input.disabled = false;
    alert("Überarbeitung fehlgeschlagen: " + err.message);
  }
}

async function doRender(button) {
  const { id } = newState.current;
  newState.phase = "rendering";
  button.disabled = true;
  button.textContent = "Rendert …";
  try {
    await api("POST", `/api/applications/${id}/render`);
    newState.phase = "preview";
    mountPreview(document.getElementById("preview-area"), id);
  } catch (err) {
    newState.current.report = { ok: false, errors: err.errors.length ? err.errors : [err.message] };
    newState.phase = "review";
    updateReportPanel();
  } finally {
    button.textContent = "PDFs rendern";
    button.disabled = !newState.current.report.ok;
  }
}

function mountPreview(node, id) {
  const stamp = Date.now();
  const urls = {
    cv: `/api/applications/${id}/pdf/cv?t=${stamp}`,
    letter: `/api/applications/${id}/pdf/letter?t=${stamp}`,
  };
  const tile = (doc, title) => h("div", {
    class: "preview-tile", role: "button", tabindex: "0",
    title: "Klicken für große Ansicht",
    onclick: () => openPdfOverlay(urls, doc),
    onkeydown: (e) => { if (e.key === "Enter") openPdfOverlay(urls, doc); },
  },
    h("iframe", { src: urls[doc], title, tabindex: "-1" }),
    h("div", { class: "muted small", style: "text-align:center; padding: 4px 0" },
      title + " — klicken zum Vergrößern"));

  const sentButton = h("button", { class: "primary",
    onclick: async () => {
      await api("POST", `/api/applications/${id}/status`, { to: "sent" });
      sentButton.replaceWith(h("span", {}, "Als versendet markiert — ",
        h("a", { href: "#pipeline" }, "zur Pipeline")));
    } }, "Als versendet markieren");
  node.replaceChildren(
    h("h2", {}, "Vorschau"),
    h("div", { class: "preview" }, tile("cv", "CV"), tile("letter", "Anschreiben")),
    h("div", { class: "row" }, sentButton),
  );
  node.scrollIntoView({ behavior: "smooth", block: "start" });
}

/* near-fullscreen PDF overlay: native browser viewer (zoom included),
   one document at a time with a CV/Anschreiben toggle. */
function openPdfOverlay(urls, active) {
  const frame = h("iframe", { src: urls[active], title: "PDF-Ansicht" });
  const tabLink = h("a", { href: urls[active], target: "_blank" }, "In neuem Tab öffnen");
  const buttons = {};
  const switchTo = (doc) => {
    active = doc;
    frame.src = urls[doc];
    tabLink.href = urls[doc];
    for (const [key, button] of Object.entries(buttons)) {
      button.className = key === doc ? "primary" : "";
    }
  };
  for (const [doc, label] of [["cv", "CV"], ["letter", "Anschreiben"]]) {
    buttons[doc] = h("button", { class: doc === active ? "primary" : "",
      onclick: () => switchTo(doc) }, label);
  }
  const close = () => {
    document.removeEventListener("keydown", onKey);
    backdrop.remove();
  };
  const onKey = (event) => { if (event.key === "Escape") close(); };
  const panel = h("div", { class: "overlay-panel" },
    h("div", { class: "row", style: "padding: 8px 16px; border-bottom: 1px solid var(--line)" },
      buttons.cv, buttons.letter,
      h("span", { class: "grow" }),
      tabLink,
      h("button", { onclick: close }, "Schließen")),
    frame);
  const backdrop = h("div", { class: "overlay-backdrop",
    onclick: (event) => { if (event.target === backdrop) close(); } }, panel);
  document.addEventListener("keydown", onKey);
  document.body.append(backdrop);
}

function resetNew() {
  newState.phase = "input";
  newState.current = null;
  newState.error = null;
  newState.reviseNotes = null;
  route();
}

/* ── view: Pipeline ──────────────────────────────────────────────── */

const ATTENTION_STATUSES = ["draft", "interview"]; // accent badges per design doc
const pipelineState = { sortKey: "created_at", sortDir: -1, statusFilter: "" };

function statusLabel(status) {
  return { draft: "Entwurf", sent: "Versendet", interview: "Interview",
    offer: "Angebot", rejected: "Absage", withdrawn: "Zurückgezogen" }[status] || status;
}

async function renderViewPipeline(root) {
  root.replaceChildren(h("h1", {}, "Pipeline"), h("p", { class: "loading" }, "Lädt …"));
  const [rows] = await Promise.all([api("GET", "/api/applications"), meta()]);
  root.replaceChildren(h("h1", {}, "Pipeline"));
  if (!rows.length) {
    root.append(h("p", { class: "muted" }, "Noch keine Bewerbungen erfasst."));
    return;
  }

  const filter = h("select", { style: "width:auto",
    onchange: () => { pipelineState.statusFilter = filter.value; renderViewPipeline(root); } },
    h("option", { value: "" }, "Alle Status"),
    META.statuses.map((s) =>
      h("option", { value: s, ...(pipelineState.statusFilter === s ? { selected: "" } : {}) },
        statusLabel(s))));
  root.append(h("div", { class: "row", style: "margin-bottom: 8px" },
    h("span", { class: "muted small grow" }, `${rows.length} Bewerbungen`), filter));

  let visible = rows;
  if (pipelineState.statusFilter) {
    visible = rows.filter((r) => r.status === pipelineState.statusFilter);
  }
  const key = pipelineState.sortKey;
  visible = [...visible].sort((a, b) => {
    if (key === "match_score") {
      return pipelineState.sortDir * ((a[key] ?? -1) - (b[key] ?? -1));
    }
    return pipelineState.sortDir * String(a[key] || "").localeCompare(String(b[key] || ""));
  });

  const sortableHeader = (label, sortKey) => {
    const active = pipelineState.sortKey === sortKey;
    return h("th", {},
      h("button", { class: "linklike th-sort" + (active ? " active" : ""),
        onclick: () => {
          pipelineState.sortDir = active ? -pipelineState.sortDir : 1;
          pipelineState.sortKey = sortKey;
          renderViewPipeline(root);
        } },
        label + (active ? (pipelineState.sortDir > 0 ? " ↑" : " ↓") : "")));
  };

  const table = h("table", {},
    h("tr", {},
      sortableHeader("Firma", "company"),
      h("th", {}, "Rolle"),
      sortableHeader("Status", "status"),
      sortableHeader("Match", "match_score"),
      sortableHeader("Erstellt", "created_at"),
      sortableHeader("Versendet", "sent_at"),
      h("th", {}, "Kanal")));
  for (const row of visible) table.append(pipelineRow(row, root));
  root.append(table);
}

function pipelineRow(row, root) {
  const targets = META.transitions[row.status] || [];
  const statusCell = h("td", {});
  if (targets.length) {
    const select = h("select", { style: "width:auto",
      onchange: async () => {
        if (!select.value) return;
        try {
          await api("POST", `/api/applications/${row.id}/status`, { to: select.value });
          renderViewPipeline(root);
        } catch (err) {
          alert(err.message);
          select.value = "";
        }
      } },
      h("option", { value: "" }, statusLabel(row.status) + " →"),
      targets.map((t) => h("option", { value: t }, statusLabel(t))));
    statusCell.append(select);
  } else {
    statusCell.append(h("span", { class: "badge" +
      (ATTENTION_STATUSES.includes(row.status) ? " attention" : "") }, statusLabel(row.status)));
  }

  const detailRow = h("tr", { hidden: "" }, h("td", { colspan: "7" }));
  const mainRow = h("tr", {},
    h("td", {}, h("button", { class: "linklike",
      onclick: () => toggleDetail(row, detailRow) }, row.company)),
    h("td", {}, row.role),
    statusCell,
    h("td", { class: "muted" }, row.match_score == null ? "—" : String(row.match_score)),
    h("td", { class: "muted" }, row.created_at.slice(0, 10)),
    h("td", { class: "muted" }, row.sent_at ? row.sent_at.slice(0, 10) : "—"),
    h("td", { class: "muted" }, row.channel || "—"));

  const fragment = document.createDocumentFragment();
  fragment.append(mainRow, detailRow);
  return fragment;
}

async function toggleDetail(row, detailRow) {
  if (!detailRow.hidden) {
    detailRow.hidden = true;
    return;
  }
  const detail = await api("GET", `/api/applications/${row.id}`);
  const cell = detailRow.firstChild;
  const noteInput = h("textarea", { rows: "2", placeholder: "Notiz … (Esc verwirft)" });
  noteInput.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { noteInput.value = ""; noteInput.blur(); }
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") saveNote.click();
  });
  const saveNote = h("button", { onclick: async () => {
    if (!noteInput.value.trim()) return;
    const updated = await api("POST", `/api/applications/${row.id}/note`,
      { text: noteInput.value.trim() });
    noteInput.value = "";
    notesNode.replaceChildren(...notesLines(updated.notes));
  } }, "Notiz speichern");
  const notesNode = h("div", { class: "small stack" }, notesLines(detail.notes));

  cell.replaceChildren(h("div", { class: "stack", style: "padding: 8px 0" },
    h("div", { class: "small muted" },
      detail.events.map((e) => `${e.created_at.slice(0, 16).replace("T", " ")} ${e.from_status || "·"} → ${e.to_status}`).join("  |  ")),
    detail.cv_path ? h("div", { class: "small" },
      h("a", { href: `/api/applications/${row.id}/pdf/cv`, target: "_blank" }, "CV"), " · ",
      h("a", { href: `/api/applications/${row.id}/pdf/letter`, target: "_blank" }, "Anschreiben"), " · ",
      h("span", { class: "muted" }, detail.app_path)) : h("div", { class: "small muted" }, "Noch nicht gerendert."),
    notesNode,
    h("div", { class: "row" }, h("div", { class: "grow" }, noteInput), saveNote),
    h("div", { class: "row" },
      h("span", { class: "grow" }),
      h("button", { class: "linklike small muted-action", onclick: async () => {
        const confirmed = confirm(
          `Bewerbung #${row.id} (${row.company} — ${row.role}) inklusive ` +
          "Status-Historie und Notizen endgültig aus dem CRM entfernen?\n\n" +
          "Die gerenderten PDFs und die application.json im output-Ordner " +
          "bleiben erhalten.");
        if (!confirmed) return;
        await api("DELETE", `/api/applications/${row.id}`);
        renderViewPipeline(document.getElementById("view-pipeline"));
      } }, "Eintrag löschen"))));
  detailRow.hidden = false;
}

function notesLines(notes) {
  return notes ? notes.split("\n").map((line) => h("div", {}, line)) : [h("span", { class: "muted" }, "Keine Notizen.")];
}

/* ── view: Profil ────────────────────────────────────────────────── */

async function renderViewProfile(root) {
  root.replaceChildren(h("h1", {}, "Profil"), h("p", { class: "loading" }, "Lädt …"));
  const { text } = await api("GET", "/api/profile/yaml");

  const editor = h("textarea", { class: "yaml-editor", spellcheck: "false", value: text });
  const feedback = h("div", { class: "report", hidden: "" });
  const save = h("button", { class: "primary", onclick: async () => {
    save.disabled = true;
    save.textContent = "Validiert …";
    try {
      await api("PUT", "/api/profile/yaml", { text: editor.value });
      feedback.hidden = false;
      feedback.className = "report ok";
      feedback.replaceChildren("✓ Profil validiert und gespeichert.");
    } catch (err) {
      feedback.hidden = false;
      feedback.className = "report fail";
      feedback.replaceChildren(
        h("div", {}, "✗ Nicht gespeichert — Schema-Fehler:",
          h("ul", {}, (err.errors.length ? err.errors : [err.message]).map((e) => h("li", {}, e)))));
    } finally {
      save.disabled = false;
      save.textContent = "Validieren & Speichern";
    }
  } }, "Validieren & Speichern");

  editor.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") save.click();
  });

  root.replaceChildren(
    h("h1", {}, "Profil"),
    h("p", { class: "muted small" },
      "profile/profile.yaml — Quelle aller CV-/Anschreiben-Inhalte. ",
      "Gespeichert wird nur, was das Schema besteht (Cmd/Ctrl+Enter speichert)."),
    h("div", { class: "card stack" }, editor, feedback, h("div", { class: "row" }, save)),
  );
}
