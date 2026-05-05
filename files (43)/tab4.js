/**
 * tab4.js — Chat with Data  (UPDATED: Suggested Prompts + compact upload)
 * POST /api/tab4/ask      → Q&A answer
 * DELETE /api/tab4/clear  → clear history
 */
(function () {
  'use strict';
  let initialised = false;

  // ── SUGGESTED PROMPTS ──────────────────────────────────────────────────
  // Grouped by category — rendered as clickable chips above the input box
  const PROMPT_GROUPS = [
    {
      label: "Variance",
      icon: "bi-bar-chart-steps",
      color: "#2563eb",
      prompts: [
        "What is the total net variance (A minus B)?",
        "Which cost category has the highest adverse variance?",
        "Show me the top 5 rows by absolute delta value",
        "What percentage of rows are favourable vs adverse?",
      ],
    },
    {
      label: "Drill-Down",
      icon: "bi-diagram-3",
      color: "#0891b2",
      prompts: [
        "Break down variance by OH/LC classification",
        "Which Division has the largest overspend?",
        "Compare actual vs budget for each Function",
        "Show variance trend across all month columns",
      ],
    },
    {
      label: "Summary",
      icon: "bi-file-text",
      color: "#059669",
      prompts: [
        "Summarise the data in 3 bullet points",
        "What are the key risk areas based on this data?",
        "Give me an executive summary of the variance",
        "What actions would you recommend based on this data?",
      ],
    },
    {
      label: "Data Quality",
      icon: "bi-search",
      color: "#d97706",
      prompts: [
        "Are there any null or missing values in the dataset?",
        "How many unique scenarios are in this data?",
        "What columns are available in this dataset?",
        "Show me row count and column list",
      ],
    },
  ];

  let activeGroup = 0; // which prompt group tab is open

  // ── BUILD HTML ──────────────────────────────────────────────────────────
  function buildHTML() {
    return `
<div class="va-section-label"><i class="bi bi-chat-dots"></i> Chat with Your Data</div>
<p style="font-size:.82rem;color:var(--text-muted);margin-bottom:10px">
  Ask natural language questions about your loaded dataset (Tab 1 mapping or Tab 2 pivot data from session).
</p>

<!-- ═══ DATA SOURCE STATUS ════════════════════════════════════════ -->
<div class="t4-source-status" id="t4-source-status">
  <i class="bi bi-info-circle"></i>
  <span>No data loaded yet. Run Tab 1 mapping or Tab 2 variance analysis first.</span>
</div>

<!-- ═══ CHAT WINDOW ═══════════════════════════════════════════════ -->
<div id="t4-chat-window" class="t4-chat-window">
  <div class="t4-msg t4-assistant">
    <div class="t4-avatar"><i class="bi bi-robot"></i></div>
    <div class="t4-bubble">
      👋 Hi! I can answer questions about your loaded dataset.<br>
      Try a <strong>suggested prompt</strong> below or type your own question.
    </div>
  </div>
</div>

<div id="t4-alert" class="va-alert mb-2"></div>

<!-- ═══ SUGGESTED PROMPTS ══════════════════════════════════════════ -->
<div class="t4-suggestions">
  <!-- Group tabs -->
  <div class="t4-group-tabs" id="t4-group-tabs">
    ${PROMPT_GROUPS.map((g, i) => `
    <button class="t4-group-tab ${i===0?'active':''}" data-gi="${i}" style="${i===0?`border-color:${g.color};color:${g.color}`:''}">
      <i class="bi ${g.icon}"></i> ${g.label}
    </button>`).join('')}
  </div>

  <!-- Prompt chips -->
  <div class="t4-prompt-chips" id="t4-prompt-chips">
    ${promptChipsHTML(0)}
  </div>
</div>

<!-- ═══ INPUT ROW ════════════════════════════════════════════════ -->
<div class="t4-input-row">
  <div class="t4-input-wrap">
    <input class="t4-input" id="t4-input"
      placeholder="Ask your dataset a question… (Enter to send)" />
    <div class="t4-input-hint" id="t4-typing-indicator" style="display:none">
      <span class="t4-dot"></span><span class="t4-dot"></span><span class="t4-dot"></span>
    </div>
  </div>
  <button class="btn-va-primary t4-send-btn" id="t4-btn-send">
    <i class="bi bi-send-fill"></i>
  </button>
  <button class="btn-va-outline t4-clear-btn" id="t4-btn-clear" title="Clear chat">
    <i class="bi bi-trash3"></i>
  </button>
</div>

<style>
/* ── Source status ──────────────────────────────────────────── */
.t4-source-status{
  display:flex;align-items:center;gap:8px;
  padding:7px 12px;border-radius:8px;font-size:.78rem;margin-bottom:10px;
  background:#fffbeb;border:1px solid #fbbf24;color:#92400e;
}
.t4-source-status.ok{background:#ecfdf5;border-color:#6ee7b7;color:#065f46}

/* ── Chat window ─────────────────────────────────────────────── */
.t4-chat-window{
  background:#fff;border:1px solid var(--border);border-radius:10px;
  height:340px;overflow-y:auto;padding:14px 16px;margin-bottom:10px;
  display:flex;flex-direction:column;gap:10px;
  scroll-behavior:smooth;
}

/* ── Messages ─────────────────────────────────────────────────── */
.t4-msg{display:flex;gap:8px;align-items:flex-start}
.t4-user{flex-direction:row-reverse}
.t4-avatar{
  width:28px;height:28px;border-radius:50%;
  display:flex;align-items:center;justify-content:center;
  background:var(--navy2);color:#fff;font-size:.78rem;flex-shrink:0;
}
.t4-user .t4-avatar{background:var(--blue)}
.t4-bubble{
  max-width:72%;padding:9px 13px;border-radius:12px;
  font-size:.8rem;line-height:1.55;white-space:pre-wrap;word-break:break-word;
}
.t4-assistant .t4-bubble{background:#f1f5fb;color:var(--text);border-bottom-left-radius:3px}
.t4-user .t4-bubble{background:var(--blue);color:#fff;border-bottom-right-radius:3px}
.t4-typing .t4-bubble{opacity:.55;font-style:italic}

/* ── Suggestions ─────────────────────────────────────────────── */
.t4-suggestions{
  background:#fff;border:1px solid var(--border);border-radius:10px;
  padding:10px 12px;margin-bottom:10px;
}
.t4-group-tabs{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px;padding-bottom:8px;border-bottom:1px solid var(--border)}
.t4-group-tab{
  background:transparent;border:1px solid var(--border);border-radius:6px;
  padding:4px 10px;font-size:.72rem;font-weight:600;color:var(--text-muted);
  cursor:pointer;display:flex;align-items:center;gap:4px;
  transition:border-color .12s,color .12s,background .12s;
}
.t4-group-tab:hover{border-color:var(--blue);color:var(--blue);background:var(--blue-pale)}
.t4-group-tab.active{background:var(--blue-pale);font-weight:700}

.t4-prompt-chips{display:flex;gap:6px;flex-wrap:wrap}
.t4-prompt-chip{
  background:var(--off-white,#f8faff);border:1px solid var(--border);
  border-radius:20px;padding:4px 12px;font-size:.72rem;color:var(--text);
  cursor:pointer;transition:background .12s,border-color .12s,color .12s;
  white-space:nowrap;
}
.t4-prompt-chip:hover{background:var(--blue);border-color:var(--blue);color:#fff}

/* ── Input row ─────────────────────────────────────────────────── */
.t4-input-row{display:flex;gap:8px;align-items:center}
.t4-input-wrap{flex:1;position:relative}
.t4-input{
  width:100%;border:1px solid #93c5fd;border-radius:8px;
  padding:9px 14px;font-size:.82rem;font-family:'Sora',sans-serif;color:var(--text);
  outline:none;transition:border-color .15s,box-shadow .15s;
}
.t4-input:focus{border-color:var(--blue);box-shadow:0 0 0 3px rgba(37,99,235,.1)}
.t4-send-btn{padding:8px 16px !important;border-radius:8px !important}
.t4-clear-btn{padding:7px 12px !important;border-radius:8px !important}

/* ── Typing dots ─────────────────────────────────────────────── */
.t4-input-hint{position:absolute;bottom:6px;right:10px;display:flex;gap:3px;align-items:center}
.t4-dot{width:5px;height:5px;border-radius:50%;background:var(--blue);animation:t4bounce .8s infinite}
.t4-dot:nth-child(2){animation-delay:.15s}
.t4-dot:nth-child(3){animation-delay:.3s}
@keyframes t4bounce{0%,80%,100%{transform:translateY(0)}40%{transform:translateY(-5px)}}
</style>`;
  }

  function promptChipsHTML(gi) {
    const g = PROMPT_GROUPS[gi];
    return PROMPT_GROUPS[gi].prompts.map(p =>
      `<button class="t4-prompt-chip" data-prompt="${p.replace(/"/g,'&quot;')}"
         style="--chip-color:${g.color}">${p}</button>`
    ).join('');
  }

  // ── INIT ────────────────────────────────────────────────────────────────
  function init() {
    if (initialised) return;
    initialised = true;
    document.getElementById('tab4-content').innerHTML = buildHTML();
    bindEvents();
    checkDataStatus();
  }

  // ── DATA STATUS CHECK ───────────────────────────────────────────────────
  async function checkDataStatus() {
    try {
      // Quick filter call — if it succeeds there's data in session
      await vaGet('/api/tab2/filters');
      const el = document.getElementById('t4-source-status');
      el.className = 't4-source-status ok';
      el.innerHTML = '<i class="bi bi-check-circle-fill"></i><span>Data loaded from session — ready to chat!</span>';
    } catch (_) { /* keep warning state */ }
  }

  // ── EVENTS ──────────────────────────────────────────────────────────────
  function bindEvents() {
    // Group tab switching
    document.getElementById('t4-group-tabs').addEventListener('click', e => {
      const btn = e.target.closest('.t4-group-tab');
      if (!btn) return;
      activeGroup = parseInt(btn.dataset.gi, 10);
      const g = PROMPT_GROUPS[activeGroup];
      document.querySelectorAll('.t4-group-tab').forEach((b, i) => {
        b.classList.toggle('active', i === activeGroup);
        b.style.borderColor = i === activeGroup ? g.color : '';
        b.style.color       = i === activeGroup ? g.color : '';
        b.style.background  = i === activeGroup ? `${g.color}18` : '';
      });
      document.getElementById('t4-prompt-chips').innerHTML = promptChipsHTML(activeGroup);
      bindChips();
    });

    bindChips();

    // Send on Enter
    document.getElementById('t4-input').addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
    });
    document.getElementById('t4-btn-send').addEventListener('click', handleSend);
    document.getElementById('t4-btn-clear').addEventListener('click', handleClear);
  }

  function bindChips() {
    document.querySelectorAll('.t4-prompt-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        document.getElementById('t4-input').value = chip.dataset.prompt;
        document.getElementById('t4-input').focus();
        handleSend();
      });
    });
  }

  // ── SEND ────────────────────────────────────────────────────────────────
  async function handleSend() {
    const input = document.getElementById('t4-input');
    const q = input.value.trim();
    if (!q) return;

    vaAlertClear('t4-alert');
    appendMsg('user', q);
    input.value = '';

    const typingId = appendTyping();
    setLoading(true);

    try {
      const data = await vaPost('/api/tab4/ask', { question: q });
      removeMsg(typingId);
      appendMsg('assistant', data.answer || '(No answer returned)');
    } catch (e) {
      removeMsg(typingId);
      if (e.message.includes('404')) {
        appendMsg('assistant', '⚠️ No data in session. Please run Tab 1 Mapping or Tab 2 Variance Analysis first, then come back here.');
      } else {
        appendMsg('assistant', `❌ Error: ${e.message}`);
      }
    } finally {
      setLoading(false);
    }
  }

  // ── CLEAR ───────────────────────────────────────────────────────────────
  async function handleClear() {
    try { await fetch('/api/tab4/clear', { method: 'DELETE' }); } catch(_) {}
    document.getElementById('t4-chat-window').innerHTML = `
      <div class="t4-msg t4-assistant">
        <div class="t4-avatar"><i class="bi bi-robot"></i></div>
        <div class="t4-bubble">Chat cleared. Ask me anything about your loaded data!</div>
      </div>`;
    vaAlertClear('t4-alert');
  }

  // ── MESSAGE HELPERS ──────────────────────────────────────────────────────
  let _mid = 0;

  function appendMsg(role, text) {
    const id  = `t4m${_mid++}`;
    const win = document.getElementById('t4-chat-window');
    const icon = role === 'user' ? 'bi-person-fill' : 'bi-robot';
    const div = document.createElement('div');
    div.id        = id;
    div.className = `t4-msg t4-${role}`;
    div.innerHTML = `
      <div class="t4-avatar"><i class="bi ${icon}"></i></div>
      <div class="t4-bubble">${esc(text)}</div>`;
    win.appendChild(div);
    win.scrollTop = win.scrollHeight;
    return id;
  }

  function appendTyping() {
    const id  = `t4m${_mid++}`;
    const win = document.getElementById('t4-chat-window');
    const div = document.createElement('div');
    div.id        = id;
    div.className = 't4-msg t4-assistant t4-typing';
    div.innerHTML = `
      <div class="t4-avatar"><i class="bi bi-robot"></i></div>
      <div class="t4-bubble">
        <span class="t4-dot"></span><span class="t4-dot"></span><span class="t4-dot"></span>
      </div>`;
    win.appendChild(div);
    win.scrollTop = win.scrollHeight;
    return id;
  }

  function removeMsg(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
  }

  function setLoading(on) {
    document.getElementById('t4-btn-send').disabled = on;
    document.getElementById('t4-input').disabled    = on;
  }

  function esc(s) {
    return String(s)
      .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
      .replace(/\n/g,'<br>');
  }

  window.addEventListener('va:tabchange', e => {
    if (e.detail === 'tab4') { init(); if (initialised) checkDataStatus(); }
  });
})();
