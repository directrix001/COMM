/**
 * tab4.js — Chat with Data
 * POST /api/tab4/ask  →  conversational Q&A
 * DELETE /api/tab4/clear  →  clear history
 */
(function () {
  'use strict';
  let initialised = false;

  function buildHTML() {
    return `
      <div class="va-section-label"><i class="bi bi-chat-dots"></i> Chat with Your Data</div>
      <p style="font-size:.82rem;color:var(--text-muted);margin-bottom:16px">
        Ask natural language questions about your loaded dataset (Tab 1 or Tab 2 data in session).
      </p>

      <!-- Chat window -->
      <div id="t4-chat-window" style="
        background:#fff; border:1px solid var(--border); border-radius:10px;
        height:420px; overflow-y:auto; padding:16px 20px; margin-bottom:12px;
        display:flex; flex-direction:column; gap:12px;
      ">
        <div class="t4-msg t4-assistant">
          <div class="t4-bubble">👋 Hi! Ask me anything about your loaded data — totals, top drivers, comparisons, etc.</div>
        </div>
      </div>

      <div id="t4-alert" class="va-alert mb-2"></div>

      <!-- Input row -->
      <div class="d-flex gap-2">
        <input class="form-control" id="t4-input" placeholder="Ask your dataset a question…" />
        <button class="btn-va-primary" id="t4-btn-send" style="white-space:nowrap">
          <i class="bi bi-send-fill"></i> Send
        </button>
        <button class="btn-va-outline" id="t4-btn-clear" style="white-space:nowrap">
          <i class="bi bi-trash3"></i> Clear
        </button>
      </div>
    `;
  }

  const CSS = `
    .t4-msg { display:flex; gap:8px; align-items:flex-start; }
    .t4-user      { flex-direction:row-reverse; }
    .t4-bubble {
      max-width:75%; padding:10px 14px; border-radius:12px;
      font-size:.82rem; line-height:1.55; white-space:pre-wrap;
    }
    .t4-user .t4-bubble      { background:var(--blue); color:#fff; border-bottom-right-radius:3px; }
    .t4-assistant .t4-bubble { background:#f1f5fb; color:var(--text); border-bottom-left-radius:3px; }
    .t4-typing { opacity:.5; font-style:italic; }
  `;

  function init() {
    if (initialised) return;
    initialised = true;
    if (!document.getElementById('t4-style')) {
      const s = document.createElement('style'); s.id = 't4-style'; s.textContent = CSS;
      document.head.appendChild(s);
    }
    document.getElementById('tab4-content').innerHTML = buildHTML();
    bindEvents();
  }

  function bindEvents() {
    document.getElementById('t4-btn-send').addEventListener('click', handleSend);
    document.getElementById('t4-input').addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
    });
    document.getElementById('t4-btn-clear').addEventListener('click', handleClear);
  }

  async function handleSend() {
    const input = document.getElementById('t4-input');
    const q = input.value.trim();
    if (!q) return;

    vaAlertClear('t4-alert');
    appendMsg('user', q);
    input.value = '';

    const typingId = appendMsg('assistant', '⏳ Thinking…', true);
    setLoading(true);

    try {
      const data = await vaPost('/api/tab4/ask', { question: q });
      removeMsg(typingId);
      appendMsg('assistant', data.answer || '(No answer returned)');
    } catch (e) {
      removeMsg(typingId);
      appendMsg('assistant', `❌ Error: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }

  async function handleClear() {
    try { await fetch('/api/tab4/clear', { method:'DELETE' }); } catch(_) {}
    const win = document.getElementById('t4-chat-window');
    win.innerHTML = `<div class="t4-msg t4-assistant">
      <div class="t4-bubble">Chat cleared. Ask me anything about your data!</div>
    </div>`;
  }

  let _msgId = 0;
  function appendMsg(role, text, isTyping = false) {
    const id  = `t4-msg-${_msgId++}`;
    const win = document.getElementById('t4-chat-window');
    const div = document.createElement('div');
    div.id        = id;
    div.className = `t4-msg t4-${role}`;
    div.innerHTML = `<div class="t4-bubble${isTyping ? ' t4-typing' : ''}">${escHtml(text)}</div>`;
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

  function escHtml(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

  window.addEventListener('va:tabchange', e => { if (e.detail === 'tab4') init(); });
})();
