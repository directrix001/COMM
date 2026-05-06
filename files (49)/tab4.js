/**
 * tab4.js — Chat with Data
 * UPDATED: Persona-aware suggested prompts driven by Tab 3 selection.
 * Reads window.__va_persona (set by tab3.js on every persona change).
 * POST /api/tab4/ask      → Q&A answer
 * DELETE /api/tab4/clear  → clear history
 */
(function () {
  'use strict';
  let initialised = false;

  // ── PERSONA-AWARE PROMPT LIBRARY ──────────────────────────────────────
  // Each persona gets 4 tailored groups with prompts matching their frame.
  const PERSONA_PROMPTS = {

    CFO: {
      label: "CFO",
      color: "#2563eb",
      groups: [
        {
          label: "P&L Impact",
          icon: "bi-bar-chart-line-fill",
          color: "#2563eb",
          prompts: [
            "What is the total net variance and its P&L impact?",
            "Which cost category is driving the most adverse variance?",
            "How does this variance compare as a % of total budget?",
            "What is the bottom-line impact if we do nothing?",
          ],
        },
        {
          label: "Risk & Exposure",
          icon: "bi-shield-exclamation",
          color: "#dc2626",
          prompts: [
            "What are the top 3 financial risks in this data?",
            "Which regions or divisions are most exposed?",
            "Are there any variance spikes that signal structural issues?",
            "What is our worst-case scenario based on current trends?",
          ],
        },
        {
          label: "Strategic Actions",
          icon: "bi-arrow-up-right-circle",
          color: "#059669",
          prompts: [
            "What immediate corrective actions should I prioritise?",
            "Which areas offer the fastest cost recovery opportunity?",
            "Summarise the key messages for a board presentation",
            "What does this variance tell us about our strategic direction?",
          ],
        },
        {
          label: "Executive Summary",
          icon: "bi-file-earmark-text",
          color: "#7c3aed",
          prompts: [
            "Give me a 3-bullet executive summary of this variance",
            "What is the single biggest story in this data?",
            "Compare performance across the top 3 divisions in one sentence each",
            "What should I highlight to the Board this quarter?",
          ],
        },
      ],
    },

    VP_FINANCE: {
      label: "VP Finance",
      color: "#0891b2",
      groups: [
        {
          label: "Budget vs Actual",
          icon: "bi-graph-up-arrow",
          color: "#0891b2",
          prompts: [
            "Show budget vs actual variance by cost category",
            "Which departments are over budget and by how much?",
            "What is the YTD spend vs plan across all divisions?",
            "Identify the top 5 budget overruns with their drivers",
          ],
        },
        {
          label: "Cost Control",
          icon: "bi-scissors",
          color: "#dc2626",
          prompts: [
            "Where are the biggest cost-control opportunities?",
            "Which OH costs are running above benchmark?",
            "Break down procured services variance by region",
            "What travel & meals spend is above threshold?",
          ],
        },
        {
          label: "FP&A Insights",
          icon: "bi-calculator",
          color: "#059669",
          prompts: [
            "What is the variance trend across all available months?",
            "Forecast full-year variance based on current run-rate",
            "Which line items need reforecast this quarter?",
            "Show me the waterfall of variances from plan to actual",
          ],
        },
        {
          label: "Reporting",
          icon: "bi-clipboard-data",
          color: "#7c3aed",
          prompts: [
            "Summarise in 4 bullets for the monthly finance pack",
            "What commentary should I include in the CFO dashboard?",
            "Which variances need management explanation this period?",
            "List variances that exceed the materiality threshold of 5%",
          ],
        },
      ],
    },

    BUSINESS_PARTNER: {
      label: "Biz Partner",
      color: "#059669",
      groups: [
        {
          label: "Root Cause",
          icon: "bi-diagram-3",
          color: "#059669",
          prompts: [
            "What is the primary root cause of the largest variance?",
            "Which operational activities are driving cost overruns?",
            "Break down the variance by function and explain each",
            "What changed this period compared to last period?",
          ],
        },
        {
          label: "Team Actions",
          icon: "bi-people-fill",
          color: "#0891b2",
          prompts: [
            "Which teams need to take corrective action and why?",
            "What specific actions can reduce the adverse variance?",
            "Which cost categories can be deferred to next quarter?",
            "Who owns the largest overspend and what should they do?",
          ],
        },
        {
          label: "Operational Detail",
          icon: "bi-gear",
          color: "#d97706",
          prompts: [
            "Show variance breakdown by department within each division",
            "Which procurement categories are over plan?",
            "Break down headcount-related costs vs non-headcount",
            "Compare this region's performance to others",
          ],
        },
        {
          label: "Narrative",
          icon: "bi-chat-quote",
          color: "#7c3aed",
          prompts: [
            "Write a 2-paragraph business narrative for this variance",
            "What context should I give the VP when presenting this?",
            "Summarise what happened and what we are doing about it",
            "Draft talking points for the next business review",
          ],
        },
      ],
    },

    BOARD: {
      label: "Board/Exec",
      color: "#7c3aed",
      groups: [
        {
          label: "Key Messages",
          icon: "bi-award-fill",
          color: "#7c3aed",
          prompts: [
            "What are the 3 key messages for the Board this quarter?",
            "Summarise overall performance in 2 sentences",
            "What is the strategic implication of this variance?",
            "How does this compare to our investor commitments?",
          ],
        },
        {
          label: "Performance",
          icon: "bi-speedometer2",
          color: "#0891b2",
          prompts: [
            "How is overall performance tracking against annual plan?",
            "Which markets are outperforming and which are lagging?",
            "What percentage of the portfolio is on track?",
            "Show the high-level variance split: favourable vs adverse",
          ],
        },
        {
          label: "Risk & Opportunity",
          icon: "bi-lightning-charge",
          color: "#dc2626",
          prompts: [
            "What are the top strategic risks in this data?",
            "Where are the growth or savings opportunities?",
            "What needs Board-level decision or escalation?",
            "Which trends should concern the Board most?",
          ],
        },
        {
          label: "Governance",
          icon: "bi-shield-check",
          color: "#059669",
          prompts: [
            "Are there any control or compliance concerns in this data?",
            "Which variances require Board approval to address?",
            "What governance actions should be logged this period?",
            "Summarise the key accountability owners for each risk",
          ],
        },
      ],
    },

    AUDITOR: {
      label: "Audit",
      color: "#dc2626",
      groups: [
        {
          label: "Materiality",
          icon: "bi-shield-check",
          color: "#dc2626",
          prompts: [
            "Which variances exceed the materiality threshold of €500K?",
            "List all line items with variance > 10% of plan",
            "Are there any zero-balance items that should have activity?",
            "Which cost categories have unexplained variances?",
          ],
        },
        {
          label: "Control Checks",
          icon: "bi-search",
          color: "#d97706",
          prompts: [
            "Identify any duplicate or anomalous entries in the data",
            "Which departments show unusual spending patterns?",
            "Are there any transactions outside the normal range?",
            "Show me all rows where actual exceeds budget by more than 20%",
          ],
        },
        {
          label: "Evidence Trail",
          icon: "bi-file-earmark-ruled",
          color: "#0891b2",
          prompts: [
            "List all variances that need documented justification",
            "Which line items have missing or incomplete data?",
            "Show row count and completeness across all key columns",
            "What data quality issues exist that could affect the audit?",
          ],
        },
        {
          label: "JSOX / Compliance",
          icon: "bi-clipboard2-check",
          color: "#7c3aed",
          prompts: [
            "Which variances require JSOX control documentation?",
            "Are there any intercompany recharges that seem unusual?",
            "List all provisions and accruals in this dataset",
            "What follow-up procedures should I recommend?",
          ],
        },
      ],
    },

    FP_A: {
      label: "FP&A Analyst",
      color: "#d97706",
      groups: [
        {
          label: "Driver Analysis",
          icon: "bi-calculator",
          color: "#d97706",
          prompts: [
            "Show me the full driver tree for the top variance",
            "What percentage of total variance comes from the top 3 drivers?",
            "Break down volume vs price vs mix effects in the variance",
            "Which drivers are one-time vs recurring?",
          ],
        },
        {
          label: "Trend & Forecast",
          icon: "bi-graph-up",
          color: "#0891b2",
          prompts: [
            "What is the month-on-month variance trend?",
            "Project the full-year variance based on current run-rate",
            "Which cost lines are accelerating vs decelerating?",
            "Show cumulative YTD variance vs plan for each month",
          ],
        },
        {
          label: "Data Deep-Dive",
          icon: "bi-table",
          color: "#059669",
          prompts: [
            "Show summary statistics for all numeric columns",
            "Which rows have the highest absolute delta values?",
            "How many unique entities, divisions and functions are in the data?",
            "Show the distribution of variance across cost categories",
          ],
        },
        {
          label: "Model Support",
          icon: "bi-diagram-2",
          color: "#7c3aed",
          prompts: [
            "What assumptions are implied by the current variance pattern?",
            "Which line items should I include in a sensitivity analysis?",
            "Identify cost categories suitable for zero-based budgeting",
            "What correlations exist between the highest-variance categories?",
          ],
        },
      ],
    },

  };

  // Default fallback when no persona selected yet
  const DEFAULT_GROUPS = PERSONA_PROMPTS.CFO.groups;

  let activeGroup = 0;

  // ── GET CURRENT PERSONA FROM TAB 3 ───────────────────────────────────
  function getCurrentPersona() {
    // tab3.js writes window.__va_persona whenever user selects a card
    const pid = window.__va_persona || 'CFO';
    return PERSONA_PROMPTS[pid] || PERSONA_PROMPTS.CFO;
  }

  // ── BUILD HTML ────────────────────────────────────────────────────────
  function buildHTML() {
    return `
<div class="va-section-label"><i class="bi bi-chat-dots"></i> Chat with Your Data</div>
<p style="font-size:.82rem;color:var(--text-muted);margin-bottom:10px">
  Ask natural language questions about your loaded dataset. 
  Suggested prompts are tuned to the <strong>audience persona</strong> selected in Tab 3.
</p>

<!-- ═══ PERSONA CONTEXT BANNER ════════════════════════════════════ -->
<div class="t4-persona-banner" id="t4-persona-banner">
  <i class="bi bi-person-badge" id="t4-banner-icon"></i>
  <div>
    <span style="font-weight:700;font-size:.8rem" id="t4-banner-name">CFO</span>
    <span style="font-size:.73rem;color:var(--text-muted);margin-left:6px" id="t4-banner-hint">
      — prompts tuned to strategic, high-level questions
    </span>
  </div>
  <a href="#" id="t4-banner-change" style="font-size:.72rem;color:var(--blue);margin-left:auto;text-decoration:none">
    Change in Tab 3 →
  </a>
</div>

<!-- ═══ DATA SOURCE STATUS ════════════════════════════════════════ -->
<div class="t4-source-status" id="t4-source-status">
  <i class="bi bi-info-circle"></i>
  <span>No data loaded yet. Run Tab 1 mapping or Tab 2 variance analysis first.</span>
</div>

<!-- ═══ CHAT WINDOW ═══════════════════════════════════════════════ -->
<div id="t4-chat-window" class="t4-chat-window">
  <div class="t4-msg t4-assistant">
    <div class="t4-avatar"><i class="bi bi-robot"></i></div>
    <div class="t4-bubble" id="t4-welcome-msg">
      👋 Hi! I'm ready to answer questions about your data.<br>
      Pick a <strong>suggested prompt</strong> below or type your own.
    </div>
  </div>
</div>

<div id="t4-alert" class="va-alert mb-2"></div>

<!-- ═══ SUGGESTED PROMPTS ══════════════════════════════════════════ -->
<div class="t4-suggestions" id="t4-suggestions">
  <div class="t4-group-tabs" id="t4-group-tabs"></div>
  <div class="t4-prompt-chips" id="t4-prompt-chips"></div>
</div>

<!-- ═══ INPUT ROW ════════════════════════════════════════════════ -->
<div class="t4-input-row">
  <div class="t4-input-wrap">
    <input class="t4-input" id="t4-input"
      placeholder="Ask your dataset a question… (Enter to send)" />
  </div>
  <button class="btn-va-primary t4-send-btn" id="t4-btn-send">
    <i class="bi bi-send-fill"></i>
  </button>
  <button class="btn-va-outline t4-clear-btn" id="t4-btn-clear" title="Clear chat">
    <i class="bi bi-trash3"></i>
  </button>
</div>

<style>
/* ── Persona banner ──────────────────────────────────────────── */
.t4-persona-banner{
  display:flex;align-items:center;gap:10px;
  padding:8px 14px;border-radius:8px;
  border:1.5px solid var(--border);background:#fff;
  margin-bottom:8px;font-size:.82rem;
  transition:border-color .2s,background .2s;
}
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
  height:320px;overflow-y:auto;padding:14px 16px;margin-bottom:10px;
  display:flex;flex-direction:column;gap:10px;scroll-behavior:smooth;
}
/* ── Messages ─────────────────────────────────────────────────── */
.t4-msg{display:flex;gap:8px;align-items:flex-start}
.t4-user{flex-direction:row-reverse}
.t4-avatar{
  width:28px;height:28px;border-radius:50%;flex-shrink:0;
  display:flex;align-items:center;justify-content:center;
  background:var(--navy2);color:#fff;font-size:.78rem;
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
  background:#f8faff;border:1px solid var(--border);
  border-radius:20px;padding:4px 12px;font-size:.72rem;color:var(--text);
  cursor:pointer;transition:background .12s,border-color .12s,color .12s;white-space:nowrap;
}
.t4-prompt-chip:hover{background:var(--blue);border-color:var(--blue);color:#fff}
/* ── Input row ─────────────────────────────────────────────────── */
.t4-input-row{display:flex;gap:8px;align-items:center}
.t4-input-wrap{flex:1}
.t4-input{
  width:100%;border:1px solid #93c5fd;border-radius:8px;
  padding:9px 14px;font-size:.82rem;font-family:'Sora',sans-serif;color:var(--text);
  outline:none;transition:border-color .15s,box-shadow .15s;
}
.t4-input:focus{border-color:var(--blue);box-shadow:0 0 0 3px rgba(37,99,235,.1)}
.t4-send-btn{padding:8px 16px !important;border-radius:8px !important}
.t4-clear-btn{padding:7px 12px !important;border-radius:8px !important}
/* ── Typing dots ─────────────────────────────────────────────── */
.t4-dot{
  display:inline-block;width:5px;height:5px;border-radius:50%;
  background:var(--blue);animation:t4bounce .8s infinite;margin-right:2px;
}
.t4-dot:nth-child(2){animation-delay:.15s}
.t4-dot:nth-child(3){animation-delay:.3s}
@keyframes t4bounce{0%,80%,100%{transform:translateY(0)}40%{transform:translateY(-5px)}}
</style>`;
  }

  // ── RENDER PERSONA BANNER ─────────────────────────────────────────────
  function renderPersonaBanner() {
    const persona = getCurrentPersona();
    const banner  = document.getElementById('t4-persona-banner');
    if (!banner) return;

    banner.style.borderColor = persona.color;
    banner.style.background  = persona.color + '10';

    document.getElementById('t4-banner-icon').style.color = persona.color;
    document.getElementById('t4-banner-name').textContent = persona.label;
    document.getElementById('t4-banner-name').style.color = persona.color;

    const hints = {
      CFO:              "— prompts tuned to strategic, high-level P&L questions",
      VP_FINANCE:       "— prompts tuned to budget stewardship and cost control",
      BUSINESS_PARTNER: "— prompts tuned to operational root-cause and team actions",
      BOARD:            "— prompts tuned to board-level narrative and governance",
      AUDITOR:          "— prompts tuned to materiality, controls and JSOX compliance",
      FP_A:             "— prompts tuned to detailed driver analysis and modelling",
    };
    const pid = window.__va_persona || 'CFO';
    document.getElementById('t4-banner-hint').textContent = hints[pid] || "";
  }

  // ── RENDER PROMPT GROUPS ──────────────────────────────────────────────
  function renderPromptGroups() {
    const persona = getCurrentPersona();
    const groups  = persona.groups;
    activeGroup   = 0;

    // Group tabs
    const tabsEl = document.getElementById('t4-group-tabs');
    if (!tabsEl) return;
    tabsEl.innerHTML = groups.map((g, i) => `
      <button class="t4-group-tab ${i===0?'active':''}" data-gi="${i}"
        style="${i===0 ? `border-color:${g.color};color:${g.color};background:${g.color}18` : ''}">
        <i class="bi ${g.icon}"></i> ${g.label}
      </button>`).join('');

    renderChips(groups[0]);

    // Group tab click
    tabsEl.addEventListener('click', e => {
      const btn = e.target.closest('.t4-group-tab');
      if (!btn) return;
      activeGroup = parseInt(btn.dataset.gi, 10);
      const g = groups[activeGroup];
      tabsEl.querySelectorAll('.t4-group-tab').forEach((b, i) => {
        const isMe = i === activeGroup;
        b.classList.toggle('active', isMe);
        b.style.borderColor = isMe ? g.color : '';
        b.style.color       = isMe ? g.color : '';
        b.style.background  = isMe ? g.color + '18' : '';
      });
      renderChips(g);
    });
  }

  function renderChips(group) {
    const el = document.getElementById('t4-prompt-chips');
    if (!el) return;
    el.innerHTML = group.prompts.map(p =>
      `<button class="t4-prompt-chip" data-prompt="${p.replace(/"/g,'&quot;')}">${p}</button>`
    ).join('');
    el.querySelectorAll('.t4-prompt-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        document.getElementById('t4-input').value = chip.dataset.prompt;
        document.getElementById('t4-input').focus();
        handleSend();
      });
    });
  }

  // ── INIT ────────────────────────────────────────────────────────────────
  function init() {
    if (initialised) return;
    initialised = true;
    document.getElementById('tab4-content').innerHTML = buildHTML();
    bindEvents();
    renderPersonaBanner();
    renderPromptGroups();
    checkDataStatus();
  }

  // ── RE-RENDER when tab activated (persona may have changed in Tab 3) ───
  function refresh() {
    if (!initialised) { init(); return; }
    renderPersonaBanner();
    renderPromptGroups();
    checkDataStatus();
  }

  // ── DATA STATUS ──────────────────────────────────────────────────────
  async function checkDataStatus() {
    try {
      await vaGet('/api/tab2/filters');
      const el = document.getElementById('t4-source-status');
      if (el) { el.className = 't4-source-status ok'; el.innerHTML = '<i class="bi bi-check-circle-fill"></i><span>Data loaded from session — ready to chat!</span>'; }
    } catch (_) {}
  }

  // ── EVENTS ───────────────────────────────────────────────────────────
  function bindEvents() {
    document.getElementById('t4-input').addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
    });
    document.getElementById('t4-btn-send').addEventListener('click', handleSend);
    document.getElementById('t4-btn-clear').addEventListener('click', handleClear);
    document.getElementById('t4-banner-change').addEventListener('click', e => {
      e.preventDefault();
      // Switch to Tab 3
      const tab3btn = document.querySelector('.va-tab[data-tab="tab3"]');
      if (tab3btn) tab3btn.click();
    });
  }

  // ── SEND ─────────────────────────────────────────────────────────────
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
      appendMsg('assistant',
        e.message.includes('404')
          ? '⚠️ No data in session. Run Tab 1 Mapping or Tab 2 Variance Analysis first, then return here.'
          : `❌ Error: ${e.message}`
      );
    } finally {
      setLoading(false);
    }
  }

  // ── CLEAR ────────────────────────────────────────────────────────────
  async function handleClear() {
    try { await fetch('/api/tab4/clear', { method: 'DELETE' }); } catch(_) {}
    const win = document.getElementById('t4-chat-window');
    win.innerHTML = `
      <div class="t4-msg t4-assistant">
        <div class="t4-avatar"><i class="bi bi-robot"></i></div>
        <div class="t4-bubble">Chat cleared. Ask me anything about your loaded data!</div>
      </div>`;
  }

  // ── MESSAGE HELPERS ──────────────────────────────────────────────────
  let _mid = 0;

  function appendMsg(role, text) {
    const id  = `t4m${_mid++}`;
    const win = document.getElementById('t4-chat-window');
    const icon = role === 'user' ? 'bi-person-fill' : 'bi-robot';
    const div = document.createElement('div');
    div.id = id; div.className = `t4-msg t4-${role}`;
    div.innerHTML = `<div class="t4-avatar"><i class="bi ${icon}"></i></div>
      <div class="t4-bubble">${esc(text)}</div>`;
    win.appendChild(div);
    win.scrollTop = win.scrollHeight;
    return id;
  }

  function appendTyping() {
    const id  = `t4m${_mid++}`;
    const win = document.getElementById('t4-chat-window');
    const div = document.createElement('div');
    div.id = id; div.className = 't4-msg t4-assistant t4-typing';
    div.innerHTML = `<div class="t4-avatar"><i class="bi bi-robot"></i></div>
      <div class="t4-bubble"><span class="t4-dot"></span><span class="t4-dot"></span><span class="t4-dot"></span></div>`;
    win.appendChild(div);
    win.scrollTop = win.scrollHeight;
    return id;
  }

  function removeMsg(id) { const el = document.getElementById(id); if (el) el.remove(); }

  function setLoading(on) {
    document.getElementById('t4-btn-send').disabled = on;
    document.getElementById('t4-input').disabled    = on;
  }

  function esc(s) {
    return String(s)
      .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
      .replace(/\n/g,'<br>');
  }

  // ── TAB CHANGE LISTENER ───────────────────────────────────────────────
  window.addEventListener('va:tabchange', e => {
    if (e.detail === 'tab4') refresh();   // refresh picks up latest persona
  });

})();
