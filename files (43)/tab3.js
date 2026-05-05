/**
 * tab3.js — Commentary Generator  (Persona-Based Generation)
 * POST /api/tab3/run  →  executive summary + RCA + category commentary
 * Downloads: .md  .txt  .pptx
 */
(function () {
  'use strict';
  let initialised = false;

  const PERSONAS = [
    { id:"CFO", label:"CFO", icon:"bi-bar-chart-line-fill", color:"#2563eb", badge:"C-Suite", desc:"P&L focused · strategic · risk-aware", sample:"Net variance of €2.3M adverse driven by headcount ramp in Q2…" },
    { id:"VP_FINANCE", label:"VP Finance", icon:"bi-graph-up-arrow", color:"#0891b2", badge:"Leadership", desc:"Budget stewardship · cost control · FP&A", sample:"OH overspend vs plan primarily attributable to external consulting…" },
    { id:"BUSINESS_PARTNER", label:"Biz Partner", icon:"bi-people-fill", color:"#059669", badge:"Operational", desc:"Root-cause · operational context · action-oriented", sample:"Procurement delays in EMEA resulted in OPEX shift to Q3…" },
    { id:"BOARD", label:"Board/Exec", icon:"bi-award-fill", color:"#7c3aed", badge:"Executive", desc:"High-level · narrative · investor-ready", sample:"Regional performance divergence signals structural realignment opportunity…" },
    { id:"AUDITOR", label:"Audit", icon:"bi-shield-check", color:"#dc2626", badge:"Compliance", desc:"Evidence-based · factual · JSOX-ready", sample:"Variance exceeds materiality threshold; control review recommended…" },
    { id:"FP_A", label:"FP&A Analyst", icon:"bi-calculator", color:"#d97706", badge:"Analyst", desc:"Detailed · data-driven · model-backed", sample:"Driver tree shows 62% of variance in two cost categories…" },
  ];

  let selectedPersona = PERSONAS[0];

  function buildHTML() {
    return `
<div class="va-section-label"><i class="bi bi-robot"></i> AI-Powered Commentary Generator</div>
<p style="font-size:.82rem;color:var(--text-muted);margin-bottom:12px">
  Select an <strong>audience persona</strong> to tune the commentary tone, then configure hierarchy and generate.
</p>

<!-- ═══ PERSONA SELECTOR ═══════════════════════════════════════ -->
<div class="va-section-label" style="margin-bottom:8px"><i class="bi bi-person-badge"></i> Audience Persona</div>
<div class="t3-persona-grid" id="t3-persona-grid">
  ${PERSONAS.map(p => `
  <div class="t3-persona-card" data-persona="${p.id}" style="border-color:${p.id===selectedPersona.id?p.color:''}">
    <i class="bi ${p.icon} t3-persona-icon" style="color:${p.color}"></i>
    <span class="t3-persona-name">${p.label}</span>
    <span class="t3-persona-badge" style="background:${p.color}">${p.badge}</span>
    <i class="bi bi-check-circle-fill t3-persona-check" style="color:${p.color};display:${p.id===selectedPersona.id?'block':'none'}"></i>
  </div>`).join('')}
</div>

<div class="t3-persona-detail" id="t3-persona-detail">
  <i class="bi ${selectedPersona.icon}" style="color:${selectedPersona.color};font-size:1.5rem;flex-shrink:0"></i>
  <div>
    <div style="font-weight:700;font-size:.88rem">${selectedPersona.label} — ${selectedPersona.badge}</div>
    <div style="font-size:.75rem;color:var(--text-muted)">${selectedPersona.desc}</div>
    <div class="t3-persona-sample">"${selectedPersona.sample}"</div>
  </div>
</div>

<!-- ═══ METRIC CONFIG ═══════════════════════════════════════════ -->
<div class="va-card mb-3">
  <div class="row g-3">
    <div class="col-md-6">
      <label class="form-label">Variance column <small class="text-muted">(uncheck = compute from two scenarios)</small></label>
      <div class="form-check mb-2">
        <input class="form-check-input" type="checkbox" id="t3-has-var" checked>
        <label class="form-check-label" for="t3-has-var">Variance column already present</label>
      </div>
      <div id="t3-var-col-wrap">
        <input class="form-control" id="t3-var-col" placeholder="e.g. delta" value="delta"/>
      </div>
      <div id="t3-scenario-wrap" style="display:none">
        <input class="form-control mb-2" id="t3-base-sc" placeholder="Base scenario column"/>
        <input class="form-control" id="t3-compare-sc" placeholder="Compare scenario column"/>
      </div>
    </div>
    <div class="col-md-6">
      <label class="form-label">Drill-Down Hierarchy <small class="text-muted">(comma-separated, left = top level)</small></label>
      <input class="form-control" id="t3-hierarchy" placeholder="e.g. OH/LC, Division_Desc, Function_Desc" value="OH/LC,Division_Desc"/>
      <div class="t3-hier-chips mt-2">
        <span style="font-size:.7rem;color:var(--text-muted);margin-right:4px">Quick:</span>
        <button class="t3-chip" data-val="OH/LC,Division_Desc">2-level</button>
        <button class="t3-chip" data-val="OH/LC,Division_Desc,Function_Desc">3-level</button>
        <button class="t3-chip" data-val="OH/LC,CostCat description,Division_Desc,Function_Desc">4-level</button>
      </div>
    </div>
  </div>
</div>

<!-- ═══ RUN ════════════════════════════════════════════════════ -->
<div id="t3-alert" class="va-alert"></div>
<div id="t3-progress" class="mb-3"></div>
<div class="d-flex align-items-center gap-3 mb-3">
  <button class="btn-va-primary" id="t3-btn-run"><i class="bi bi-cpu"></i> Generate Commentary</button>
  <div class="t3-active-badge" id="t3-active-badge" style="border-color:${selectedPersona.color}">
    <i class="bi ${selectedPersona.icon}" style="color:${selectedPersona.color}"></i>
    Tone: <strong>${selectedPersona.label}</strong>
  </div>
</div>

<!-- ═══ RESULTS ════════════════════════════════════════════════ -->
<hr class="va-divider" id="t3-results-divider" style="display:none">
<div id="t3-results" style="display:none">
  <div class="row g-3 mb-3" id="t3-kpi-row"></div>
  <div class="t3-used-banner" id="t3-used-banner" style="margin-bottom:12px"></div>
  <div class="row g-3 mb-3">
    <div class="col-md-6">
      <div class="va-section-label"><i class="bi bi-file-text"></i> Executive Summary</div>
      <div class="va-card" id="t3-exec" style="white-space:pre-wrap;font-size:.82rem;max-height:300px;overflow-y:auto;line-height:1.65"></div>
    </div>
    <div class="col-md-6">
      <div class="va-section-label"><i class="bi bi-diagram-3"></i> Drill-Down Trace</div>
      <div class="va-card" id="t3-trace" style="max-height:300px;overflow-y:auto;font-size:.74rem;font-family:'JetBrains Mono',monospace"></div>
    </div>
  </div>
  <div id="t3-rca-section" style="display:none">
    <div class="va-section-label"><i class="bi bi-search"></i> Root Cause Analysis</div>
    <div class="va-card mb-3" id="t3-rca" style="white-space:pre-wrap;font-size:.82rem;max-height:240px;overflow-y:auto;background:#ecfdf5;border-color:#6ee7b7;line-height:1.65"></div>
  </div>
  <div id="t3-comm-section" style="display:none">
    <div class="va-section-label"><i class="bi bi-lightbulb"></i> Category Commentary</div>
    <div class="va-card mb-3" id="t3-comm" style="white-space:pre-wrap;font-size:.82rem;max-height:280px;overflow-y:auto;background:#eff6ff;border-color:#93c5fd;line-height:1.65"></div>
  </div>
  <details class="mb-3">
    <summary style="cursor:pointer;font-size:.78rem;font-weight:600;color:var(--blue);display:flex;align-items:center;gap:6px">
      <i class="bi bi-file-earmark-text"></i> Full AI Report (raw)
    </summary>
    <div class="va-card mt-2" id="t3-full" style="white-space:pre-wrap;font-size:.75rem;max-height:340px;overflow-y:auto;font-family:'JetBrains Mono',monospace"></div>
  </details>
  <div class="va-section-label"><i class="bi bi-download"></i> Export</div>
  <div class="d-flex gap-2 flex-wrap mb-3">
    <a href="/api/tab3/download/md"   class="btn-va-success text-decoration-none"><i class="bi bi-markdown"></i> .md</a>
    <a href="/api/tab3/download/txt"  class="btn-va-success text-decoration-none"><i class="bi bi-file-text"></i> .txt</a>
    <a href="/api/tab3/download/pptx" class="btn-va-success text-decoration-none"><i class="bi bi-file-ppt"></i> .pptx</a>
  </div>
  <div class="d-flex align-items-center gap-2">
    <span style="font-size:.78rem;font-weight:600;color:var(--text-muted)">Rate this output:</span>
    <button class="t3-fb" id="t3-fb-up">👍 Helpful</button>
    <button class="t3-fb" id="t3-fb-down">👎 Needs work</button>
    <span id="t3-fb-msg" style="font-size:.75rem;color:var(--green)"></span>
  </div>
</div>

<style>
.t3-persona-grid{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin-bottom:10px}
@media(max-width:1000px){.t3-persona-grid{grid-template-columns:repeat(3,1fr)}}
@media(max-width:640px){.t3-persona-grid{grid-template-columns:repeat(2,1fr)}}
.t3-persona-card{border:1.5px solid var(--border);border-radius:10px;padding:10px 8px 8px;text-align:center;cursor:pointer;background:#fff;transition:border-color .15s,box-shadow .15s,transform .12s;position:relative}
.t3-persona-card:hover{border-color:var(--blue);box-shadow:0 2px 10px rgba(37,99,235,.12);transform:translateY(-2px)}
.t3-persona-card.sel{box-shadow:0 4px 14px rgba(0,0,0,.1);transform:translateY(-2px);border-width:2px}
.t3-persona-icon{font-size:1.4rem;display:block;margin-bottom:5px}
.t3-persona-name{font-size:.74rem;font-weight:700;color:var(--text);display:block;margin-bottom:3px}
.t3-persona-badge{font-size:.57rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;padding:1px 6px;border-radius:20px;color:#fff;display:inline-block}
.t3-persona-check{position:absolute;top:5px;right:6px;font-size:.72rem}
.t3-persona-detail{display:flex;align-items:flex-start;gap:12px;padding:10px 14px;border-radius:8px;border:1px solid var(--border);background:var(--blue-pale);margin-bottom:14px}
.t3-persona-sample{font-size:.72rem;color:var(--blue);font-style:italic;border-left:2px solid var(--blue);padding-left:8px;margin-top:5px}
.t3-hier-chips{display:flex;gap:6px;flex-wrap:wrap;align-items:center}
.t3-chip{background:var(--blue-pale);border:1px solid var(--blue);color:var(--blue);border-radius:20px;font-size:.7rem;font-weight:600;padding:2px 10px;cursor:pointer;transition:background .12s}
.t3-chip:hover{background:var(--blue);color:#fff}
.t3-active-badge{display:inline-flex;align-items:center;gap:6px;padding:5px 12px;border-radius:20px;font-size:.76rem;font-weight:600;border:1.5px solid var(--border);background:#fff;color:var(--text)}
.t3-used-banner{display:flex;align-items:center;gap:10px;padding:8px 14px;border-radius:8px;border:1px solid;font-size:.8rem}
.t3-fb{border:1px solid var(--border);background:#fff;border-radius:20px;padding:3px 12px;font-size:.76rem;cursor:pointer}
.t3-fb:hover{background:var(--blue-pale);border-color:var(--blue)}
</style>`;
  }

  function init() {
    if (initialised) return;
    initialised = true;
    document.getElementById('tab3-content').innerHTML = buildHTML();
    bindEvents();
  }

  function bindEvents() {
    document.getElementById('t3-persona-grid').addEventListener('click', e => {
      const card = e.target.closest('.t3-persona-card');
      if (!card) return;
      selectedPersona = PERSONAS.find(p => p.id === card.dataset.persona);
      refreshPersonaUI();
    });
    document.getElementById('t3-has-var').addEventListener('change', function () {
      document.getElementById('t3-var-col-wrap').style.display  = this.checked ? '' : 'none';
      document.getElementById('t3-scenario-wrap').style.display = this.checked ? 'none' : '';
    });
    document.querySelectorAll('.t3-chip').forEach(b =>
      b.addEventListener('click', () => { document.getElementById('t3-hierarchy').value = b.dataset.val; })
    );
    document.getElementById('t3-btn-run').addEventListener('click', handleRun);
    document.getElementById('t3-fb-up').addEventListener('click',
      () => { document.getElementById('t3-fb-msg').textContent = '✅ Thanks — feedback recorded!'; });
    document.getElementById('t3-fb-down').addEventListener('click',
      () => { document.getElementById('t3-fb-msg').textContent = '📝 Noted — we\'ll improve the tone.'; });
  }

  function refreshPersonaUI() {
    document.querySelectorAll('.t3-persona-card').forEach(c => {
      const p  = PERSONAS.find(x => x.id === c.dataset.persona);
      const me = p.id === selectedPersona.id;
      c.classList.toggle('sel', me);
      c.style.borderColor = me ? p.color : '';
      c.querySelector('.t3-persona-check').style.display = me ? 'block' : 'none';
    });
    document.getElementById('t3-persona-detail').innerHTML = `
      <i class="bi ${selectedPersona.icon}" style="color:${selectedPersona.color};font-size:1.5rem;flex-shrink:0"></i>
      <div>
        <div style="font-weight:700;font-size:.88rem">${selectedPersona.label} — ${selectedPersona.badge}</div>
        <div style="font-size:.75rem;color:var(--text-muted)">${selectedPersona.desc}</div>
        <div class="t3-persona-sample">"${selectedPersona.sample}"</div>
      </div>`;
    const badge = document.getElementById('t3-active-badge');
    badge.style.borderColor = selectedPersona.color;
    badge.innerHTML = `<i class="bi ${selectedPersona.icon}" style="color:${selectedPersona.color}"></i> Tone: <strong>${selectedPersona.label}</strong>`;
  }

  async function handleRun() {
    vaAlertClear('t3-alert');
    document.getElementById('t3-results-divider').style.display = 'none';
    document.getElementById('t3-results').style.display         = 'none';

    const hier = (document.getElementById('t3-hierarchy').value || '')
      .split(',').map(s => s.trim()).filter(Boolean);
    if (!hier.length) { vaAlert('t3-alert','Enter at least one hierarchy column.','warning'); return; }

    const hasVar = document.getElementById('t3-has-var').checked;
    const body = {
      hierarchy_cols:   hier,
      has_variance_col: hasVar,
      variance_col:     hasVar ? document.getElementById('t3-var-col').value.trim() : '',
      base_scenario:    hasVar ? '' : document.getElementById('t3-base-sc').value.trim(),
      compare_scenario: hasVar ? '' : document.getElementById('t3-compare-sc').value.trim(),
      persona:          selectedPersona.id,
    };

    const btn = document.getElementById('t3-btn-run');
    btn.disabled = true; btn.innerHTML = vaSpinner(`Generating (${selectedPersona.label} tone)…`);
    vaProgress('t3-progress', 30, 'Running drill-down engine…');

    try {
      const data = await vaPost('/api/tab3/run', body);
      vaProgress('t3-progress', 100, 'Done ✓');
      await delay(400); vaProgressClear('t3-progress');
      renderResults(data, hier);
      vaToast(`✅ Commentary generated — ${selectedPersona.label} tone`);
    } catch (e) {
      vaProgressClear('t3-progress');
      vaAlert('t3-alert', e.message, 'error');
    } finally {
      btn.disabled = false; btn.innerHTML = '<i class="bi bi-cpu"></i> Generate Commentary';
    }
  }

  function renderResults(data, hier) {
    document.getElementById('t3-kpi-row').innerHTML =
      kpi('Total Variance', data.total_variance || 'N/A', '') +
      kpi('Hierarchy Levels', hier.length, 'levels') +
      kpi('Primary Branches', (data.tree_data||[]).length, 'categories') +
      kpi('Leaf Nodes', data.leaf_node_count || 0, 'items');

    const banner = document.getElementById('t3-used-banner');
    banner.style.cssText += `;background:${selectedPersona.color}18;border-color:${selectedPersona.color}55`;
    banner.innerHTML = `
      <i class="bi ${selectedPersona.icon}" style="color:${selectedPersona.color};font-size:1.2rem"></i>
      <div>
        <div style="font-weight:700;color:${selectedPersona.color}">${selectedPersona.label} — ${selectedPersona.badge}</div>
        <div style="font-size:.73rem;color:var(--text-muted)">${selectedPersona.desc}</div>
      </div>`;

    const summary = data.final_summary || '';
    let exec = summary, rca = '', comm = '';
    if (summary.includes('---ROOT CAUSE ANALYSIS---')) {
      const [e, rest] = summary.split('---ROOT CAUSE ANALYSIS---');
      exec = e.replace('Executive Summary:','').trim();
      if (rest.includes('---CATEGORY COMMENTARY---')) {
        const [r,c] = rest.split('---CATEGORY COMMENTARY---');
        rca = r.trim(); comm = c.trim();
      } else { rca = rest.trim(); }
    }

    document.getElementById('t3-exec').textContent  = exec;
    document.getElementById('t3-full').textContent  = summary;
    document.getElementById('t3-trace').innerHTML   = (data.path_trace||[]).map(t =>
      `<div style="padding:3px 0;border-bottom:1px solid #eff3fb;word-break:break-word">${esc(t)}</div>`
    ).join('');
    if (rca)  { document.getElementById('t3-rca').textContent  = rca;  document.getElementById('t3-rca-section').style.display  = ''; }
    if (comm) { document.getElementById('t3-comm').textContent = comm; document.getElementById('t3-comm-section').style.display = ''; }
    document.getElementById('t3-fb-msg').textContent = '';
    document.getElementById('t3-results-divider').style.display = '';
    document.getElementById('t3-results').style.display         = '';
  }

  function kpi(label, value, sub) {
    return `<div class="col-md-3 col-6"><div class="metric-card">
      <div class="metric-label">${label}</div><div class="metric-value">${value}</div><div class="metric-sub">${sub}</div>
    </div></div>`;
  }
  function esc(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
  function delay(ms) { return new Promise(r => setTimeout(r, ms)); }

  window.addEventListener('va:tabchange', e => { if (e.detail === 'tab3') init(); });
})();
