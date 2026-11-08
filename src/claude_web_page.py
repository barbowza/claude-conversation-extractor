"""Single-page UI served by claude_web.py (kept as a module so it ships with py_modules)."""

PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Claude Sessions</title>
<style>
:root {
  --bg: #f7f6f3; --panel: #ffffff; --text: #1d1c1a; --muted: #6b6862; --border: #e3e0d9;
  --accent: #c2410c; --accent-soft: #fdeee6; --sel: #f1ede4;
  --user: #eef3fb; --user-edge: #3b6fc4; --asst: #ffffff; --asst-edge: #c2410c;
  --tool: #f3f1ec; --tool-edge: #8a857a; --code: #f1efe9; --mark: #fde68a;
  --mono: ui-monospace, "Cascadia Code", Consolas, Menlo, monospace;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #161514; --panel: #1f1e1c; --text: #ecebe8; --muted: #9b978f; --border: #34322e;
    --accent: #f08a4b; --accent-soft: #3a2619; --sel: #2b2926;
    --user: #1c2533; --user-edge: #6c9be6; --asst: #1f1e1c; --asst-edge: #f08a4b;
    --tool: #252320; --tool-edge: #8a857a; --code: #2a2825; --mark: #6b5310;
  }
}
* { box-sizing: border-box; }
html, body { height: 100%; margin: 0; }
body { background: var(--bg); color: var(--text); font: 14px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
.app { display: grid; grid-template-columns: 380px 1fr; height: 100vh; }
aside { border-right: 1px solid var(--border); background: var(--panel); display: flex; flex-direction: column; min-height: 0; }
.side-head { padding: 14px 14px 10px; border-bottom: 1px solid var(--border); }
.side-head h1 { font-size: 15px; margin: 0 0 8px; display: flex; justify-content: space-between; align-items: baseline; }
.side-head h1 small { color: var(--muted); font-weight: 400; font-size: 12px; }
input[type=search] { width: 100%; padding: 7px 10px; border: 1px solid var(--border); border-radius: 6px; background: var(--bg); color: var(--text); font: inherit; }
.filters { display: flex; flex-wrap: wrap; gap: 4px 12px; margin-top: 8px; font-size: 12px; color: var(--muted); }
.filters label { display: inline-flex; gap: 4px; align-items: center; cursor: pointer; }
select { font: inherit; font-size: 12px; background: var(--bg); color: var(--text); border: 1px solid var(--border); border-radius: 4px; }
#list { overflow-y: auto; flex: 1; }
.item { display: block; width: 100%; text-align: left; border: 0; border-bottom: 1px solid var(--border); background: none; color: inherit; font: inherit; padding: 10px 14px; cursor: pointer; }
.item:hover { background: var(--sel); }
.item.active { background: var(--accent-soft); box-shadow: inset 3px 0 0 var(--accent); }
.item .t { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.item .p { color: var(--muted); font-size: 12.5px; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; margin-top: 2px; }
.item .m { color: var(--muted); font-size: 11.5px; margin-top: 4px; display: flex; gap: 8px; flex-wrap: wrap; }
.tag { font-size: 10.5px; padding: 0 5px; border-radius: 3px; border: 1px solid var(--border); color: var(--muted); }
main { display: flex; flex-direction: column; min-width: 0; min-height: 0; }
.main-head { padding: 14px 24px; border-bottom: 1px solid var(--border); background: var(--panel); }
.main-head h2 { margin: 0; font-size: 18px; word-break: break-word; }
.meta { color: var(--muted); font-size: 12.5px; margin-top: 4px; display: flex; flex-wrap: wrap; gap: 4px 14px; }
.meta code { font-family: var(--mono); font-size: 12px; }
.toolbar { display: flex; flex-wrap: wrap; gap: 8px 14px; align-items: center; margin-top: 10px; font-size: 13px; }
.toolbar label { display: inline-flex; gap: 5px; align-items: center; cursor: pointer; }
.btn { font: inherit; font-size: 12.5px; padding: 4px 10px; border: 1px solid var(--border); border-radius: 5px; background: var(--bg); color: var(--text); text-decoration: none; cursor: pointer; }
.btn:hover { border-color: var(--accent); color: var(--accent); }
#back { display: none; }
#conv { overflow-y: auto; flex: 1; padding: 20px 24px 60px; }
.empty { color: var(--muted); padding: 40px; text-align: center; }
.msg { max-width: 980px; margin: 0 auto 14px; border: 1px solid var(--border); border-left: 3px solid var(--asst-edge); background: var(--asst); border-radius: 6px; padding: 10px 14px; }
.msg.user { background: var(--user); border-left-color: var(--user-edge); }
.msg.tool_use, .msg.tool_result, .msg.system { background: var(--tool); border-left-color: var(--tool-edge); font-size: 13px; }
.msg-h { display: flex; justify-content: space-between; gap: 10px; font-size: 12px; color: var(--muted); margin-bottom: 6px; }
.msg-h b { color: var(--text); }
.body { white-space: pre-wrap; word-wrap: break-word; overflow-wrap: anywhere; }
.body code { font-family: var(--mono); font-size: 12.5px; background: var(--code); padding: 1px 4px; border-radius: 3px; }
.body pre { font-family: var(--mono); font-size: 12.5px; background: var(--code); padding: 10px 12px; border-radius: 5px; overflow-x: auto; white-space: pre; margin: 6px 0; }
.body .h { font-weight: 700; }
.body a { color: var(--accent); }
.collapsed .body { max-height: 320px; overflow: hidden; -webkit-mask-image: linear-gradient(#000 70%, transparent); mask-image: linear-gradient(#000 70%, transparent); }
.more { margin-top: 6px; }
mark { background: var(--mark); color: inherit; border-radius: 2px; }
.err { color: #c0392b; }
@media (max-width: 800px) {
  .app { grid-template-columns: 1fr; }
  .app.viewing aside { display: none; }
  .app:not(.viewing) main { display: none; }
  #back { display: inline-block; }
  .main-head, #conv { padding-left: 16px; padding-right: 16px; }
}
</style>
</head>
<body>
<div class="app" id="app">
  <aside>
    <div class="side-head">
      <h1>Claude sessions <small id="count"></small></h1>
      <input type="search" id="q" placeholder="Filter by title, prompt, folder or id" autocomplete="off">
      <div class="filters">
        <label><input type="checkbox" id="subagents"> Subagents</label>
        <label><input type="checkbox" id="archived" checked> Archived</label>
        <label>Sort <select id="sort">
          <option value="modified">Last modified</option>
          <option value="size">Size</option>
          <option value="messages">Messages</option>
        </select></label>
        <button class="btn" id="refresh" type="button" title="Rescan sessions">Refresh</button>
      </div>
    </div>
    <div id="list"><div class="empty">Loading…</div></div>
  </aside>
  <main>
    <div class="main-head" id="head" hidden>
      <button class="btn" id="back" type="button">← Sessions</button>
      <h2 id="title"></h2>
      <div class="meta" id="meta"></div>
      <div class="toolbar">
        <label><input type="checkbox" id="detailed"> Show tool calls</label>
        <label><input type="checkbox" id="promptsOnly"> Your prompts only</label>
        <input type="search" id="find" placeholder="Highlight in conversation" style="width:200px">
        <span style="flex:1"></span>
        <a class="btn" id="exMd">Export .md</a>
        <a class="btn" id="exHtml">Export .html</a>
        <a class="btn" id="exJson">Export .json</a>
      </div>
    </div>
    <div id="conv"><div class="empty">Pick a session on the left.</div></div>
  </main>
</div>
<script>
"use strict";
const $ = (id) => document.getElementById(id);
let sessions = [];
let current = null;      // session info object
let messages = [];

function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}
function fmtDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return isNaN(d) ? iso : d.toLocaleString(undefined, {year:"numeric", month:"short", day:"numeric", hour:"2-digit", minute:"2-digit"});
}
function fmtSize(n) {
  return n > 1048576 ? (n / 1048576).toFixed(1) + " MB" : Math.max(1, Math.round(n / 1024)) + " KB";
}
function folderName(s) {
  if (s.cwd) return s.cwd;
  return s.project;
}
function sessionTitle(s) {
  return s.title || s.preview || s.id;
}

// Minimal, escape-first markdown: fenced code, inline code, bold, headings, links.
function inline(text) {
  let h = esc(text);
  h = h.replace(/`([^`\n]+)`/g, "<code>$1</code>");
  h = h.replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>");
  h = h.replace(/^(#{1,6}) (.+)$/gm, '<span class="h">$2</span>');
  h = h.replace(/\bhttps?:\/\/[^\s<>"')\]]+/g, (u) => `<a href="${u}" target="_blank" rel="noopener noreferrer">${u}</a>`);
  return h;
}
function render(text) {
  const parts = String(text).split(/```[^\n`]*\n?([\s\S]*?)```/g);
  let out = "";
  for (let i = 0; i < parts.length; i++) {
    out += i % 2 ? `<pre>${esc(parts[i].replace(/\n$/, ""))}</pre>` : inline(parts[i]);
  }
  return out;
}
function highlight(root, term) {
  if (!term) return 0;
  const lower = term.toLowerCase();
  let hits = 0;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  for (const node of nodes) {
    const t = node.nodeValue, tl = t.toLowerCase();
    let idx = tl.indexOf(lower);
    if (idx < 0) continue;
    const frag = document.createDocumentFragment();
    let pos = 0;
    while (idx >= 0) {
      frag.appendChild(document.createTextNode(t.slice(pos, idx)));
      const m = document.createElement("mark");
      m.textContent = t.slice(idx, idx + term.length);
      frag.appendChild(m);
      hits++;
      pos = idx + term.length;
      idx = tl.indexOf(lower, pos);
    }
    frag.appendChild(document.createTextNode(t.slice(pos)));
    node.parentNode.replaceChild(frag, node);
  }
  return hits;
}

async function getJSON(url) {
  const r = await fetch(url);
  const data = await r.json();
  if (!r.ok) throw new Error(data.error || r.statusText);
  return data;
}

async function loadSessions() {
  $("list").innerHTML = '<div class="empty">Scanning sessions…</div>';
  try {
    const data = await getJSON("/api/sessions");
    sessions = data.sessions;
    renderList();
    openFromHash();
  } catch (e) {
    $("list").innerHTML = `<div class="empty err">Could not load sessions: ${esc(e.message)}</div>`;
  }
}

function renderList() {
  const q = $("q").value.trim().toLowerCase();
  const showSub = $("subagents").checked, showArch = $("archived").checked;
  const sort = $("sort").value;
  let rows = sessions.filter((s) => (showSub || !s.subagent) && (showArch || !s.archived));
  if (q) rows = rows.filter((s) => [s.title, s.preview, s.cwd, s.project, s.id, s.branch].join(" ").toLowerCase().includes(q));
  const key = {modified: (s) => s.modified, size: (s) => s.size, messages: (s) => s.userCount + s.assistantCount}[sort];
  rows.sort((a, b) => (key(a) < key(b) ? 1 : key(a) > key(b) ? -1 : 0));
  $("count").textContent = `${rows.length} of ${sessions.length}`;
  if (!rows.length) { $("list").innerHTML = '<div class="empty">No sessions match.</div>'; return; }
  $("list").innerHTML = rows.map((s) => `
    <button class="item${current && current.path === s.path ? " active" : ""}" data-path="${esc(s.path)}" type="button">
      <div class="t">${esc(sessionTitle(s))}</div>
      ${s.title && s.preview ? `<div class="p">${esc(s.preview)}</div>` : ""}
      <div class="m">
        <span>${esc(fmtDate(s.modified))}</span>
        <span>${s.userCount} prompts · ${s.assistantCount} replies</span>
        <span>${fmtSize(s.size)}</span>
        ${s.subagent ? '<span class="tag">subagent</span>' : ""}
        ${s.archived ? '<span class="tag">archived</span>' : ""}
      </div>
      <div class="m" title="${esc(folderName(s))}">${esc(folderName(s))}</div>
    </button>`).join("");
}

function exportUrl(fmt) {
  return `/api/export?path=${encodeURIComponent(current.path)}&format=${fmt}${$("detailed").checked ? "&detailed=1" : ""}`;
}

async function openSession(path, push = true) {
  const s = sessions.find((x) => x.path === path);
  if (!s) return;
  current = s;
  if (push && decodeURIComponent(location.hash.slice(1)) !== path) history.pushState(null, "", "#" + encodeURIComponent(path));
  $("app").classList.add("viewing");
  document.querySelectorAll(".item").forEach((el) => el.classList.toggle("active", el.dataset.path === path));
  $("head").hidden = false;
  $("title").textContent = sessionTitle(s);
  $("meta").innerHTML = [
    `<span>${esc(fmtDate(s.first))} → ${esc(fmtDate(s.last || s.modified))}</span>`,
    s.cwd ? `<span>Folder <code>${esc(s.cwd)}</code></span>` : "",
    s.branch ? `<span>Branch <code>${esc(s.branch)}</code></span>` : "",
    `<span>Session <code>${esc(s.id)}</code></span>`,
    `<span>File <code>${esc(s.path)}</code> (${fmtSize(s.size)})</span>`,
  ].join("");
  $("exMd").href = exportUrl("markdown");
  $("exHtml").href = exportUrl("html");
  $("exJson").href = exportUrl("json");
  await loadMessages();
}

async function loadMessages() {
  const path = current.path;
  $("conv").innerHTML = '<div class="empty">Loading conversation…</div>';
  try {
    const data = await getJSON(`/api/session?path=${encodeURIComponent(path)}${$("detailed").checked ? "&detailed=1" : ""}`);
    if (!current || current.path !== path) return;   // user moved on
    messages = data.messages;
    renderMessages();
    $("conv").scrollTop = 0;
  } catch (e) {
    $("conv").innerHTML = `<div class="empty err">Could not load: ${esc(e.message)}</div>`;
  }
}

const ROLE = {user: "You", assistant: "Claude", tool_use: "Tool call", tool_result: "Tool result", system: "System"};
function renderMessages() {
  const only = $("promptsOnly").checked;
  const rows = only ? messages.filter((m) => m.role === "user") : messages;
  if (!rows.length) { $("conv").innerHTML = '<div class="empty">No readable messages in this session.</div>'; return; }
  $("conv").innerHTML = rows.map((m, i) => {
    const long = m.content.length > 2500 || m.content.split("\n").length > 40;
    return `<div class="msg ${esc(m.role)}${long ? " collapsed" : ""}">
      <div class="msg-h"><b>${ROLE[m.role] || esc(m.role)}</b><span>${esc(fmtDate(m.timestamp))}</span></div>
      <div class="body">${render(m.content)}</div>
      ${long ? '<button class="btn more" type="button">Show all</button>' : ""}
    </div>`;
  }).join("");
  const term = $("find").value.trim();
  if (term) {
    document.querySelectorAll(".msg.collapsed").forEach((el) => {
      if (el.textContent.toLowerCase().includes(term.toLowerCase())) expand(el);
    });
    const n = highlight($("conv"), term);
    const first = $("conv").querySelector("mark");
    if (first) first.scrollIntoView({block: "center"});
    $("find").title = `${n} matches`;
  }
}
function expand(msgEl) {
  msgEl.classList.remove("collapsed");
  const b = msgEl.querySelector(".more");
  if (b) b.remove();
}

function openFromHash() {
  const path = decodeURIComponent(location.hash.slice(1));
  if (path && sessions.some((s) => s.path === path)) openSession(path, false);
  else { current = null; $("app").classList.remove("viewing"); }
}

$("list").addEventListener("click", (e) => {
  const item = e.target.closest(".item");
  if (item) openSession(item.dataset.path);
});
$("conv").addEventListener("click", (e) => {
  if (e.target.classList.contains("more")) expand(e.target.closest(".msg"));
});
$("q").addEventListener("input", renderList);
["subagents", "archived", "sort"].forEach((id) => $(id).addEventListener("change", renderList));
$("refresh").addEventListener("click", loadSessions);
$("detailed").addEventListener("change", () => { if (current) { openSession(current.path, false); } });
$("promptsOnly").addEventListener("change", renderMessages);
let findTimer;
$("find").addEventListener("input", () => { clearTimeout(findTimer); findTimer = setTimeout(renderMessages, 250); });
$("back").addEventListener("click", () => { history.pushState(null, "", location.pathname); openFromHash(); });
window.addEventListener("popstate", openFromHash);
loadSessions();
</script>
</body>
</html>
"""
