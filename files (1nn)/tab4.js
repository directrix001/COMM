/**
 * tab4.js — Chat with Data  (UPDATED)
 * ─────────────────────────────────────────────────────────────────────
 * WHAT CHANGED vs previous version:
 *
 * 1. TWO RADIO BUTTONS at top — "Tagetik Mapping (Tab 1)" and
 *    "Variance Analysis (Tab 2)". Selection is sent to backend as
 *    body.data_source = "tab1" | "tab2".
 *
 * 2. Status check on tab activate — GET /api/tab4/status tells us
 *    which DataFrames are loaded. Unavailable option gets a ⚠️ warning
 *    and is disabled so user can't select missing data.
 *
 * 3. Switching data source clears the chat window and shows a banner
 *    explaining which DataFrame is now active:
 *      tab1 → "Tagetik Mapping: enriched dataset with all months,
 *               Entity, Region, OH/LC, CostCat…"
 *      tab2 → "Variance Analysis: pivot with Variance (M€),
 *               Variance %, scenario columns…"
 *
 * 4. Persona-aware suggested prompts unchanged — still driven by
 *    window.__va_persona from Tab 3.
 *
 * 5. body sent to POST /api/tab4/ask now includes data_source field.
 *
 * 6. Comments mark every insertion point clearly.
 *
 * POST /api/tab4/ask      { question, data_source }
 * GET  /api/tab4/status   → { tab1_available, tab2_available }
 * DELETE /api/tab4/clear  → clears both history keys
 */
(function () {
  'use strict';
  let initialised  = false;
  let currentSource = 'tab2'; // default: variance data

  // ── DATA SOURCE DEFINITIONS ──────────────────────────────────────────
  // Describes what each DataFrame contains so the UI can inform the user
  const DATA_SOURCES = {
    tab1: {
      label:    'Tagetik Mapping (Tab 1)',
      icon:     'bi-folder2-open',
      color:    '#2563eb',
      desc:     'Full enriched dataset: Entity, Region, Market, OH/LC, CostCat, MTD, YTD, all month columns.',
      warning:  'No Tagetik Mapping data found. Go to Tab 1, upload your Excel file and click Generate Mapping first.',
      /* DataFrame: final_db_bytes
         Columns include: Entity_desc, Region, Market, OH/LC,
         CostCat description, Division_Desc, Function_Desc,
         Scenario, MTD, YTD, 1-Apr … 12-Mar */
    },
    tab2: {
      label:    'Variance Analysis (Tab 2)',
      icon:     'bi-graph-up-arrow',
      color:    '#059669',
      desc:     'Aggregated pivot: Variance (M€), Variance %, scenario columns, group fields.',
      warning:  'No Variance Analysis data found. Go to Tab 2, load data and click Run Variance Analysis first.',
      /* DataFrame: leaf_df_bytes (preferred) or master_db_bytes (fallback)
         Columns include: OH/LC, Division_Desc, Function_Desc (group_fields),
         <Scenario A name>, <Scenario B name>,
         Variance (M€), Variance % */
    },
  };

  // ── PERSONA PROMPT LIBRARY (unchanged from previous version) ─────────
  const PERSONA_PROMPTS = {
    CFO: {
      label: "CFO", color: "#2563eb",
      groups: [
        { label:"P&L Impact",     icon:"bi-bar-chart-line-fill", color:"#2563eb",
          prompts:["What is the total net variance and its P&L impact?",
                   "Which cost category is driving the most adverse variance?",
                   "How does this variance compare as a % of total budget?",
                   "What is the bottom-line impact if we do nothing?"] },
        { label:"Risk & Exposure",icon:"bi-shield-exclamation",  color:"#dc2626",
          prompts:["What are the top 3 financial risks in this data?",
                   "Which regions or divisions are most exposed?",
                   "Are there any variance spikes that signal structural issues?",
                   "What is our worst-case scenario based on current trends?"] },
        { label:"Strategic Actions",icon:"bi-arrow-up-right-circle",color:"#059669",
          prompts:["What immediate corrective actions should I prioritise?",
                   "Which areas offer the fastest cost recovery opportunity?",
                   "Summarise the key messages for a board presentation",
                   "What does this variance tell us about our strategic direction?"] },
        { label:"Executive Summary",icon:"bi-file-earmark-text",color:"#7c3aed",
          prompts:["Give me a 3-bullet executive summary of this variance",
                   "What is the single biggest story in this data?",
                   "Compare performance across the top 3 divisions in one sentence each",
                   "What should I highlight to the Board this quarter?"] },
      ],
    },
    VP_FINANCE: {
      label:"VP Finance", color:"#0891b2",
      groups:[
        { label:"Budget vs Actual",icon:"bi-graph-up-arrow",color:"#0891b2",
          prompts:["Show budget vs actual variance by cost category",
                   "Which departments are over budget and by how much?",
                   "What is the YTD spend vs plan across all divisions?",
                   "Identify the top 5 budget overruns with their drivers"] },
        { label:"Cost Control",icon:"bi-scissors",color:"#dc2626",
          prompts:["Where are the biggest cost-control opportunities?",
                   "Which OH costs are running above benchmark?",
                   "Break down procured services variance by region",
                   "What travel & meals spend is above threshold?"] },
        { label:"FP&A Insights",icon:"bi-calculator",color:"#059669",
          prompts:["What is the variance trend across all available months?",
                   "Forecast full-year variance based on current run-rate",
                   "Which line items need reforecast this quarter?",
                   "Show me the waterfall of variances from plan to actual"] },
        { label:"Reporting",icon:"bi-clipboard-data",color:"#7c3aed",
          prompts:["Summarise in 4 bullets for the monthly finance pack",
                   "What commentary should I include in the CFO dashboard?",
                   "Which variances need management explanation this period?",
                   "List variances that exceed the materiality threshold of 5%"] },
      ],
    },
    BUSINESS_PARTNER: {
      label:"Biz Partner", color:"#059669",
      groups:[
        { label:"Root Cause",icon:"bi-diagram-3",color:"#059669",
          prompts:["What is the primary root cause of the largest variance?",
                   "Which operational activities are driving cost overruns?",
                   "Break down the variance by function and explain each",
                   "What changed this period compared to last period?"] },
        { label:"Team Actions",icon:"bi-people-fill",color:"#0891b2",
          prompts:["Which teams need to take corrective action and why?",
                   "What specific actions can reduce the adverse variance?",
                   "Which cost categories can be deferred to next quarter?",
                   "Who owns the largest overspend and what should they do?"] },
        { label:"Operational Detail",icon:"bi-gear",color:"#d97706",
          prompts:["Show variance breakdown by department within each division",
                   "Which procurement categories are over plan?",
                   "Break down headcount-related costs vs non-headcount",
                   "Compare this region's performance to others"] },
        { label:"Narrative",icon:"bi-chat-quote",color:"#7c3aed",
          prompts:["Write a 2-paragraph business narrative for this variance",
                   "What context should I give the VP when presenting this?",
                   "Summarise what happened and what we are doing about it",
                   "Draft talking points for the next business review"] },
      ],
    },
    BOARD: {
      label:"Board/Exec", color:"#7c3aed",
      groups:[
        { label:"Key Messages",icon:"bi-award-fill",color:"#7c3aed",
          prompts:["What are the 3 key messages for the Board this quarter?",
                   "Summarise overall performance in 2 sentences",
                   "What is the strategic implication of this variance?",
                   "How does this compare to our investor commitments?"] },
        { label:"Performance",icon:"bi-speedometer2",color:"#0891b2",
          prompts:["How is overall performance tracking against annual plan?",
                   "Which markets are outperforming and which are lagging?",
                   "What percentage of the portfolio is on track?",
                   "Show the high-level variance split: favourable vs adverse"] },
        { label:"Risk & Opportunity",icon:"bi-lightning-charge",color:"#dc2626",
          prompts:["What are the top strategic risks in this data?",
                   "Where are the growth or savings opportunities?",
                   "What needs Board-level decision or escalation?",
                   "Which trends should concern the Board most?"] },
        { label:"Governance",icon:"bi-shield-check",color:"#059669",
          prompts:["Are there any control or compliance concerns in this data?",
                   "Which variances require Board approval to address?",
                   "What governance actions should be logged this period?",
                   "Summarise the key accountability owners for each risk"] },
      ],
    },
    AUDITOR: {
      label:"Audit", color:"#dc2626",
      groups:[
        { label:"Materiality",icon:"bi-shield-check",color:"#dc2626",
          prompts:["Which variances exceed the materiality threshold of €500K?",
                   "List all line items with variance > 10% of plan",
                   "Are there any zero-balance items that should have activity?",
                   "Which cost categories have unexplained variances?"] },
        { label:"Control Checks",icon:"bi-search",color:"#d97706",
          prompts:["Identify any duplicate or anomalous entries in the data",
                   "Which departments show unusual spending patterns?",
                   "Are there any transactions outside the normal range?",
                   "Show me all rows where actual exceeds budget by more than 20%"] },
        { label:"Evidence Trail",icon:"bi-file-earmark-ruled",color:"#0891b2",
          prompts:["List all variances that need documented justification",
                   "Which line items have missing or incomplete data?",
                   "Show row count and completeness across all key columns",
                   "What data quality issues exist that could affect the audit?"] },
        { label:"JSOX / Compliance",icon:"bi-clipboard2-check",color:"#7c3aed",
          prompts:["Which variances require JSOX control documentation?",
                   "Are there any intercompany recharges that seem unusual?",
                   "List all provisions and accruals in this dataset",
                   "What follow-up procedures should I recommend?"] },
      ],
    },
    FP_A: {
      label:"FP&A Analyst", color:"#d97706",
      groups:[
        { label:"Driver Analysis",icon:"bi-calculator",color:"#d97706",
          prompts:["Show me the full driver tree for the top variance",
                   "What percentage of total variance comes from the top 3 drivers?",
                   "Break down volume vs price vs mix effects in the variance",
                   "Which drivers are one-time vs recurring?"] },
        { label:"Trend & Forecast",icon:"bi-graph-up",color:"#0891b2",
          prompts:["What is the month-on-month variance trend?",
                   "Project the full-year variance based on current run-rate",
                   "Which cost lines are accelerating vs decelerating?",
                   "Show cumulative YTD variance vs plan for each month"] },
        { label:"Data Deep-Dive",icon:"bi-table",color:"#059669",
          prompts:["Show summary statistics for all numeric columns",
                   "Which rows have the highest absolute delta values?",
                   "How many unique entities, divisions and functions are in the data?",
                   "Show the distribution of variance across cost categories"] },
        { label:"Model Support",icon:"bi-diagram-2",color:"#7c3aed",
          prompts:["What assumptions are implied by the current variance pattern?",
                   "Which line items should I include in a sensitivity analysis?",
                   "Identify cost categories suitable for zero-based budgeting",
                   "What correlations exist between the highest-variance categories?"] },
      ],
    },
  };

  let activeGroup = 0;

  function getCurrentPersona() {
    const pid = window.__va_persona || 'CFO';
    return PERSONA_PROMPTS[pid] || PERSONA_PROMPTS.CFO;
  }

  // ── BUILD HTML ────────────────────────────────────────────────────────
  function buildHTML() {
    return `
<div class="va-section-label"><i class="bi bi-chat-dots"></i> Chat with Your Data</div>
<p style="font-size:.82rem;color:var(--text-muted);margin-bottom:10px">
  Ask natural language questions. Select the dataset to chat with using the
  buttons below, then type or click a suggested prompt.
</p>

<!-- ═══ DATA SOURCE RADIO BUTTONS (NEW) ═══════════════════════════════
     Two radio buttons controlling which DataFrame the agent queries.
     Selection sent as body.data_source = "tab1" | "tab2" on every ask.
     Status is checked on tab activate — unavailable option shows warning.
══════════════════════════════════════════════════════════════════════ -->
<div class="t4-source-radio-wrap" id="t4-source-radio-wrap">

  <div class="t4-radio-btn ${currentSource==='tab2'?'selected':''}"
       id="t4-radio-tab2" data-source="tab2">
    <i class="bi bi-graph-up-arrow" style="color:#059669"></i>
    <div>
      <div class="t4-radio-label">Variance Analysis <span class="t4-radio-tab">(Tab 2)</span></div>
      <div class="t4-radio-desc">Pivot: Variance (M€), Variance %, scenario columns</div>
    </div>
    <span class="t4-radio-status" id="t4-status-tab2">
      <span class="va-spinner" style="width:12px;height:12px;border-width:1.5px"></span>
    </span>
  </div>

  <div class="t4-radio-btn ${currentSource==='tab1'?'selected':''}"
       id="t4-radio-tab1" data-source="tab1">
    <i class="bi bi-folder2-open" style="color:#2563eb"></i>
    <div>
      <div class="t4-radio-label">Tagetik Mapping <span class="t4-radio-tab">(Tab 1)</span></div>
      <div class="t4-radio-desc">Full dataset: Entity, Region, OH/LC, CostCat, all months</div>
    </div>
    <span class="t4-radio-status" id="t4-status-tab1">
      <span class="va-spinner" style="width:12px;height:12px;border-width:1.5px"></span>
    </span>
  </div>

</div>

<!-- Active dataset banner -->
<div class="t4-active-banner" id="t4-active-banner"></div>

<!-- ═══ PERSONA CONTEXT BANNER ════════════════════════════════════════ -->
<div class="t4-persona-banner" id="t4-persona-banner">
  <i class="bi bi-person-badge" id="t4-banner-icon"></i>
  <div>
    <span style="font-weight:700;font-size:.8rem" id="t4-banner-name">CFO</span>
    <span style="font-size:.73rem;color:var(--text-muted);margin-left:6px" id="t4-banner-hint"></span>
  </div>
  <a href="#" id="t4-banner-change"
     style="font-size:.72rem;color:var(--blue);margin-left:auto;text-decoration:none">
    Change in Tab 3 →
  </a>
</div>

<!-- ═══ CHAT WINDOW ═══════════════════════════════════════════════════ -->
<div id="t4-chat-window" class="t4-chat-window">
  <div class="t4-msg t4-assistant">
    <div class="t4-avatar"><i class="bi bi-robot"></i></div>
    <div class="t4-bubble" id="t4-welcome-msg">
      👋 Hi! Select a dataset above, then ask me anything about your data.<br>
      Pick a <strong>suggested prompt</strong> or type your own question.
    </div>
  </div>
</div>

<div id="t4-alert" class="va-alert mb-2"></div>

<!-- ═══ SUGGESTED PROMPTS ══════════════════════════════════════════════ -->
<div class="t4-suggestions" id="t4-suggestions">
  <div class="t4-group-tabs" id="t4-group-tabs"></div>
  <div class="t4-prompt-chips" id="t4-prompt-chips"></div>
</div>

<!-- ═══ INPUT ROW ════════════════════════════════════════════════════ -->
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
/* ── Data source radio buttons ───────────────────────────────────── */
.t4-source-radio-wrap{
  display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px;
}
.t4-radio-btn{
  display:flex;align-items:center;gap:10px;
  padding:10px 14px;border-radius:10px;
  border:1.5px solid var(--border);background:#fff;
  cursor:pointer;transition:border-color .15s,background .15s,box-shadow .15s;
  user-select:none;
}
.t4-radio-btn:hover{ border-color:var(--blue); background:var(--blue-pale); }
.t4-radio-btn.selected{
  border-width:2px;box-shadow:0 2px 10px rgba(0,0,0,.08);
}
.t4-radio-btn.disabled{ opacity:.55; cursor:not-allowed; pointer-events:none; }
.t4-radio-btn .bi{ font-size:1.3rem; flex-shrink:0; }
.t4-radio-label{ font-size:.82rem; font-weight:700; color:var(--text); }
.t4-radio-tab  { font-size:.72rem; font-weight:400; color:var(--text-muted); }
.t4-radio-desc { font-size:.7rem; color:var(--text-muted); margin-top:2px; }
.t4-radio-status{ margin-left:auto; flex-shrink:0; font-size:.72rem; }
.t4-status-ok   { color:var(--green); }
.t4-status-warn { color:#d97706; }

/* ── Active dataset banner ───────────────────────────────────────── */
.t4-active-banner{
  padding:8px 14px;border-radius:8px;
  font-size:.78rem;margin-bottom:8px;
  display:none;align-items:center;gap:8px;
  border:1px solid; transition:all .2s;
}
.t4-active-banner.show{ display:flex; }
.t4-active-banner.tab1{ background:var(--blue-pale); border-color:#93c5fd; color:#1d4ed8; }
.t4-active-banner.tab2{ background:#ecfdf5;           border-color:#6ee7b7; color:#065f46; }

/* ── Persona banner ──────────────────────────────────────────────── */
.t4-persona-banner{
  display:flex;align-items:center;gap:10px;
  padding:7px 14px;border-radius:8px;
  border:1.5px solid var(--border);background:#fff;
  margin-bottom:8px;font-size:.82rem;
  transition:border-color .2s,background .2s;
}
/* ── Chat window ─────────────────────────────────────────────────── */
.t4-chat-window{
  background:#fff;border:1px solid var(--border);border-radius:10px;
  height:300px;overflow-y:auto;padding:14px 16px;margin-bottom:10px;
  display:flex;flex-direction:column;gap:10px;scroll-behavior:smooth;
}
.t4-msg{ display:flex;gap:8px;align-items:flex-start; }
.t4-user{ flex-direction:row-reverse; }
.t4-avatar{
  width:28px;height:28px;border-radius:50%;flex-shrink:0;
  display:flex;align-items:center;justify-content:center;
  background:var(--navy2);color:#fff;font-size:.78rem;
}
.t4-user .t4-avatar{ background:var(--blue); }
.t4-bubble{
  max-width:72%;padding:9px 13px;border-radius:12px;
  font-size:.8rem;line-height:1.55;white-space:pre-wrap;word-break:break-word;
}
.t4-assistant .t4-bubble{ background:#f1f5fb;color:var(--text);border-bottom-left-radius:3px; }
.t4-user .t4-bubble{ background:var(--blue);color:#fff;border-bottom-right-radius:3px; }
.t4-typing .t4-bubble{ opacity:.55;font-style:italic; }
/* ── Suggestions ─────────────────────────────────────────────────── */
.t4-suggestions{
  background:#fff;border:1px solid var(--border);border-radius:10px;
  padding:10px 12px;margin-bottom:10px;
}
.t4-group-tabs{
  display:flex;gap:6px;flex-wrap:wrap;
  margin-bottom:8px;padding-bottom:8px;border-bottom:1px solid var(--border);
}
.t4-group-tab{
  background:transparent;border:1px solid var(--border);border-radius:6px;
  padding:4px 10px;font-size:.72rem;font-weight:600;color:var(--text-muted);
  cursor:pointer;display:flex;align-items:center;gap:4px;
  transition:border-color .12s,color .12s,background .12s;
}
.t4-group-tab:hover{ border-color:var(--blue);color:var(--blue);background:var(--blue-pale); }
.t4-group-tab.active{ background:var(--blue-pale);font-weight:700; }
.t4-prompt-chips{ display:flex;gap:6px;flex-wrap:wrap; }
.t4-prompt-chip{
  background:#f8faff;border:1px solid var(--border);
  border-radius:20px;padding:4px 12px;font-size:.72rem;color:var(--text);
  cursor:pointer;transition:background .12s,border-color .12s,color .12s;white-space:nowrap;
}
.t4-prompt-chip:hover{ background:var(--blue);border-color:var(--blue);color:#fff; }
/* ── Input row ─────────────────────────────────────────────────────── */
.t4-input-row{ display:flex;gap:8px;align-items:center; }
.t4-input-wrap{ flex:1; }
.t4-input{
  width:100%;border:1px solid #93c5fd;border-radius:8px;
  padding:9px 14px;font-size:.82rem;font-family:'Sora',sans-serif;color:var(--text);
  outline:none;transition:border-color .15s,box-shadow .15s;
}
.t4-input:focus{ border-color:var(--blue);box-shadow:0 0 0 3px rgba(37,99,235,.1); }
.t4-send-btn{ padding:8px 16px !important;border-radius:8px !important; }
.t4-clear-btn{ padding:7px 12px !important;border-radius:8px !important; }
.t4-dot{
  display:inline-block;width:5px;height:5px;border-radius:50%;
  background:var(--blue);animation:t4bounce .8s infinite;margin-right:2px;
}
.t4-dot:nth-child(2){ animation-delay:.15s; }
.t4-dot:nth-child(3){ animation-delay:.3s; }
@keyframes t4bounce{0%,80%,100%{transform:translateY(0)}40%{transform:translateY(-5px)}}
</style>`;
  }

  // ── INIT ────────────────────────────────────────────────────────────────
  function init() {
    if (initialised) return;
    initialised = true;
    document.getElementById('tab4-content').innerHTML = buildHTML();
    bindEvents();
    renderPersonaBanner();
    renderPromptGroups();
    checkStatus(); // NEW: check which data sources are loaded
  }

  // ── RE-RENDER when tab activated ─────────────────────────────────────
  function refresh() {
    if (!initialised) { init(); return; }
    renderPersonaBanner();
    renderPromptGroups();
    checkStatus();
  }

  // ── STATUS CHECK (NEW) ───────────────────────────────────────────────
  // GET /api/tab4/status → { tab1_available, tab2_available }
  // Disables radio button and shows warning if data not loaded
  async function checkStatus() {
    try {
      const data = await vaGet('/api/tab4/status');
      updateRadioStatus('tab1', data.tab1_available);
      updateRadioStatus('tab2', data.tab2_available);
      renderActiveBanner();
    } catch (_) {
      // Silently ignore — status is non-critical
    }
  }

  function updateRadioStatus(source, available) {
    const btn      = document.getElementById(`t4-radio-${source}`);
    const statusEl = document.getElementById(`t4-status-${source}`);
    if (!btn || !statusEl) return;

    if (available) {
      statusEl.innerHTML = '<span class="t4-status-ok"><i class="bi bi-check-circle-fill"></i> Ready</span>';
      btn.classList.remove('disabled');
      btn.title = '';
    } else {
      statusEl.innerHTML = '<span class="t4-status-warn"><i class="bi bi-exclamation-triangle-fill"></i> Not loaded</span>';
      // Don't disable entirely — allow click to show a warning message instead
      btn.title = DATA_SOURCES[source].warning;
    }
  }

  // ── ACTIVE DATASET BANNER (NEW) ───────────────────────────────────────
  function renderActiveBanner() {
    const banner = document.getElementById('t4-active-banner');
    if (!banner) return;
    const src = DATA_SOURCES[currentSource];
    banner.className = `t4-active-banner show ${currentSource}`;
    banner.innerHTML = `
      <i class="bi ${src.icon}"></i>
      <div>
        <strong>${src.label}</strong>
        <span style="font-size:.72rem;margin-left:6px">${src.desc}</span>
      </div>`;
  }

  // ── RADIO BUTTON EVENTS (NEW) ─────────────────────────────────────────
  function bindRadioButtons() {
    document.querySelectorAll('.t4-radio-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const newSource = btn.dataset.source;
        if (newSource === currentSource) return;

        // Check if this source is available (has warning title)
        if (btn.title && btn.title.includes('not loaded') || btn.title.includes('Go to')) {
          // Show inline warning in chat instead of blocking
          appendMsg('assistant',
            `⚠️ ${DATA_SOURCES[newSource].warning}`
          );
          return;
        }

        currentSource = newSource;

        // Update radio button styles
        document.querySelectorAll('.t4-radio-btn').forEach(b => {
          b.classList.toggle('selected', b.dataset.source === newSource);
        });

        // Update colour accent on selected button
        const src = DATA_SOURCES[currentSource];
        document.getElementById(`t4-radio-${currentSource}`).style.borderColor = src.color;
        const other = currentSource === 'tab1' ? 'tab2' : 'tab1';
        document.getElementById(`t4-radio-${other}`).style.borderColor = '';

        // Clear chat and show context switch message
        clearChatWindow();
        appendMsg('assistant',
          `✅ Switched to <strong>${src.label}</strong>.\n${src.desc}\n\nAsk me anything about this dataset!`
        );
        renderActiveBanner();
      });
    });
  }

  function clearChatWindow() {
    const win = document.getElementById('t4-chat-window');
    if (win) win.innerHTML = '';
  }

  // ── PERSONA BANNER ───────────────────────────────────────────────────
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
      CFO:'— strategic P&L questions', VP_FINANCE:'— budget & cost control',
      BUSINESS_PARTNER:'— operational root-cause', BOARD:'— board narrative',
      AUDITOR:'— materiality & JSOX', FP_A:'— driver analysis',
    };
    const pid = window.__va_persona || 'CFO';
    document.getElementById('t4-banner-hint').textContent = hints[pid] || '';
  }

  // ── PROMPT GROUPS ────────────────────────────────────────────────────
  function renderPromptGroups() {
    const persona = getCurrentPersona();
    const groups  = persona.groups;
    activeGroup   = 0;

    const tabsEl = document.getElementById('t4-group-tabs');
    if (!tabsEl) return;
    tabsEl.innerHTML = groups.map((g, i) => `
      <button class="t4-group-tab ${i===0?'active':''}" data-gi="${i}"
        style="${i===0?`border-color:${g.color};color:${g.color};background:${g.color}18`:''}">
        <i class="bi ${g.icon}"></i> ${g.label}
      </button>`).join('');

    renderChips(groups[0]);

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

  // ── BIND ALL EVENTS ──────────────────────────────────────────────────
  function bindEvents() {
    // NEW: radio button switching
    bindRadioButtons();

    document.getElementById('t4-input').addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
    });
    document.getElementById('t4-btn-send').addEventListener('click', handleSend);
    document.getElementById('t4-btn-clear').addEventListener('click', handleClear);
    document.getElementById('t4-banner-change').addEventListener('click', e => {
      e.preventDefault();
      document.querySelector('.va-tab[data-tab="tab3"]')?.click();
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
      // NEW: include data_source in request body
      const data = await vaPost('/api/tab4/ask', {
        question:    q,
        data_source: currentSource,   // "tab1" or "tab2"
      });
      removeMsg(typingId);
      appendMsg('assistant', data.answer || '(No answer returned)');
    } catch (e) {
      removeMsg(typingId);
      appendMsg('assistant',
        e.message.includes('404')
          ? `⚠️ ${DATA_SOURCES[currentSource]?.warning || 'No data in session.'}`
          : `❌ Error: ${e.message}`
      );
    } finally {
      setLoading(false);
    }
  }

  // ── CLEAR ─────────────────────────────────────────────────────────────
  async function handleClear() {
    try { await fetch('/api/tab4/clear', { method:'DELETE' }); } catch(_) {}
    clearChatWindow();
    appendMsg('assistant', 'Chat cleared. Ask me anything about your loaded data!');
  }

  // ── MESSAGE HELPERS ───────────────────────────────────────────────────
  let _mid = 0;

  function appendMsg(role, text) {
    const id  = `t4m${_mid++}`;
    const win = document.getElementById('t4-chat-window');
    if (!win) return id;
    const icon = role === 'user' ? 'bi-person-fill' : 'bi-robot';
    const div  = document.createElement('div');
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
    if (!win) return id;
    const div = document.createElement('div');
    div.id = id; div.className = 't4-msg t4-assistant t4-typing';
    div.innerHTML = `<div class="t4-avatar"><i class="bi bi-robot"></i></div>
      <div class="t4-bubble">
        <span class="t4-dot"></span><span class="t4-dot"></span><span class="t4-dot"></span>
      </div>`;
    win.appendChild(div);
    win.scrollTop = win.scrollHeight;
    return id;
  }

  function removeMsg(id) { const el = document.getElementById(id); if (el) el.remove(); }

  function setLoading(on) {
    const btn = document.getElementById('t4-btn-send');
    const inp = document.getElementById('t4-input');
    if (btn) btn.disabled = on;
    if (inp) inp.disabled = on;
  }

  function esc(s) {
    return String(s)
      .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
      .replace(/\n/g,'<br>');
  }

  window.addEventListener('va:tabchange', e => {
    if (e.detail === 'tab4') refresh();
  });

})();
