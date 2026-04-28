/**
 * tab3.js — Commentary Generator tab
 * POST /api/tab3/run  →  show executive summary, RCA, category commentary
 * Downloads: .md  .txt  .pptx
 */
(function () {
  'use strict';
  let initialised = false;

  function buildHTML() {
    return `
      <div class="va-section-label"><i class="bi bi-robot"></i> AI-Powered Commentary Generator</div>
      <p style="font-size:.82rem;color:var(--text-muted);margin-bottom:16px">
        Generates executive-level variance commentary using recursive drill-down via Azure OpenAI.
        Uses Tab 2 pivot data from session by default.
      </p>

      <!-- Config -->
      <div class="va-card mb-3">
        <div class="row g-3">
          <div class="col-md-6">
            <label class="form-label">Variance column <small class="text-muted">(or uncheck to compute)</small></label>
            <div class="form-check mb-2">
              <input class="form-check-input" type="checkbox" id="t3-has-var" checked>
              <label class="form-check-label" for="t3-has-var">Variance column already present</label>
            </div>
            <div id="t3-var-col-wrap">
              <input class="form-control" id="t3-var-col" placeholder="Column name e.g. delta" value="delta" />
            </div>
            <div id="t3-scenario-wrap" style="display:none">
              <input class="form-control mb-2" id="t3-base-sc"    placeholder="Base scenario column" />
              <input class="form-control"       id="t3-compare-sc" placeholder="Compare scenario column" />
            </div>
          </div>
          <div class="col-md-6">
            <label class="form-label">Hierarchy (comma-separated column names)</label>
            <input class="form-control" id="t3-hierarchy"
              placeholder="e.g. OH/LC, Division_Desc, Function_Desc" value="OH/LC,Division_Desc" />
            <small class="text-muted">Left = top level → right = leaf reason</small>
          </div>
        </div>
      </div>

      <div id="t3-alert" class="va-alert"></div>
      <div id="t3-progress" class="mb-3"></div>

      <button class="btn-va-primary" id="t3-btn-run">
        <i class="bi bi-cpu"></i> Generate Commentary
      </button>

      <hr class="va-divider" id="t3-results-divider" style="display:none">

      <div id="t3-results" style="display:none">
        <!-- KPIs -->
        <div class="row g-3 mb-3" id="t3-kpi-row"></div>

        <!-- Summary + Tree side by side -->
        <div class="row g-3 mb-3">
          <div class="col-md-6">
            <div class="va-section-label"><i class="bi bi-file-text"></i> Executive Summary</div>
            <div class="va-card" id="t3-exec-summary" style="white-space:pre-wrap;font-size:.82rem;max-height:340px;overflow-y:auto"></div>
          </div>
          <div class="col-md-6">
            <div class="va-section-label"><i class="bi bi-diagram-3"></i> Drill-Down Trace</div>
            <div class="va-card" id="t3-trace" style="max-height:340px;overflow-y:auto;font-size:.78rem;font-family:'JetBrains Mono',monospace"></div>
          </div>
        </div>

        <!-- RCA -->
        <div id="t3-rca-section" style="display:none">
          <div class="va-section-label"><i class="bi bi-search"></i> Root Cause Analysis</div>
          <div class="va-card mb-3" id="t3-rca" style="white-space:pre-wrap;font-size:.82rem;max-height:260px;overflow-y:auto;background:#ecfdf5;border-color:#6ee7b7"></div>
        </div>

        <!-- Category commentary -->
        <div id="t3-comm-section" style="display:none">
          <div class="va-section-label"><i class="bi bi-lightbulb"></i> Category Commentary</div>
          <div class="va-card mb-3" id="t3-comm" style="white-space:pre-wrap;font-size:.82rem;max-height:300px;overflow-y:auto;background:#eff6ff;border-color:#93c5fd"></div>
        </div>

        <!-- Full report -->
        <details class="mb-3">
          <summary style="cursor:pointer;font-size:.78rem;font-weight:600;color:var(--blue)">📄 Full AI Report</summary>
          <div class="va-card mt-2" id="t3-full-report" style="white-space:pre-wrap;font-size:.78rem;max-height:400px;overflow-y:auto"></div>
        </details>

        <!-- Downloads -->
        <div class="va-section-label"><i class="bi bi-download"></i> Export</div>
        <div class="d-flex gap-2 flex-wrap">
          <a href="/api/tab3/download/md"   class="btn-va-success text-decoration-none"><i class="bi bi-markdown"></i> Download .md</a>
          <a href="/api/tab3/download/txt"  class="btn-va-success text-decoration-none"><i class="bi bi-file-text"></i> Download .txt</a>
          <a href="/api/tab3/download/pptx" class="btn-va-success text-decoration-none"><i class="bi bi-file-ppt"></i> Download .pptx</a>
        </div>

        <!-- Feedback -->
        <div class="mt-3" id="t3-feedback-wrap">
          <small style="font-size:.78rem;font-weight:600">Rate this analysis:</small>
          <button class="btn-va-outline ms-2" id="t3-fb-up"   style="padding:4px 12px">👍</button>
          <button class="btn-va-outline ms-1" id="t3-fb-down" style="padding:4px 12px">👎</button>
          <span id="t3-fb-msg" style="font-size:.75rem;color:var(--green);margin-left:8px"></span>
        </div>
      </div>
    `;
  }

  function init() {
    if (initialised) return;
    initialised = true;
    document.getElementById('tab3-content').innerHTML = buildHTML();
    bindEvents();
  }

  function bindEvents() {
    document.getElementById('t3-has-var').addEventListener('change', function () {
      document.getElementById('t3-var-col-wrap').style.display   = this.checked ? '' : 'none';
      document.getElementById('t3-scenario-wrap').style.display  = this.checked ? 'none' : '';
    });

    document.getElementById('t3-btn-run').addEventListener('click', handleRun);
    document.getElementById('t3-fb-up').addEventListener('click',   () => sendFeedback(1));
    document.getElementById('t3-fb-down').addEventListener('click', () => sendFeedback(-1));
  }

  async function handleRun() {
    vaAlertClear('t3-alert');
    document.getElementById('t3-results-divider').style.display = 'none';
    document.getElementById('t3-results').style.display         = 'none';

    const hierRaw = document.getElementById('t3-hierarchy').value;
    const hierarchy = hierRaw.split(',').map(s => s.trim()).filter(Boolean);
    if (!hierarchy.length) { vaAlert('t3-alert','Enter at least one hierarchy column.','warning'); return; }

    const hasVar = document.getElementById('t3-has-var').checked;
    const body = {
      hierarchy_cols:   hierarchy,
      has_variance_col: hasVar,
      variance_col:     hasVar ? document.getElementById('t3-var-col').value.trim() : '',
      base_scenario:    hasVar ? '' : document.getElementById('t3-base-sc').value.trim(),
      compare_scenario: hasVar ? '' : document.getElementById('t3-compare-sc').value.trim(),
    };

    const btn = document.getElementById('t3-btn-run');
    btn.disabled = true; btn.innerHTML = vaSpinner('Generating…');
    vaProgress('t3-progress', 30, 'Running drill-down engine…');

    try {
      const data = await vaPost('/api/tab3/run', body);
      vaProgress('t3-progress', 100, 'Done ✓');
      await delay(400); vaProgressClear('t3-progress');
      renderResults(data);
      vaToast('✅ Commentary generated!');
    } catch (e) {
      vaProgressClear('t3-progress');
      vaAlert('t3-alert', e.message, 'error');
    } finally {
      btn.disabled = false; btn.innerHTML = '<i class="bi bi-cpu"></i> Generate Commentary';
    }
  }

  function renderResults(data) {
    // KPIs
    document.getElementById('t3-kpi-row').innerHTML = `
      ${kpi('Total Variance',   data.total_variance  || 'N/A', '')}
      ${kpi('Hierarchy Levels', (data.tree_data||[]).length > 0 ? 'Multi-level' : '–', '')}
      ${kpi('Primary Branches', (data.tree_data||[]).length, 'top-level categories')}
      ${kpi('Leaf Nodes',       data.leaf_node_count || 0,  'final drill-down items')}
    `;

    const summary = data.final_summary || '';
    let exec = summary, rca = '', comm = '';
    if (summary.includes('---ROOT CAUSE ANALYSIS---')) {
      const p  = summary.split('---ROOT CAUSE ANALYSIS---');
      exec     = p[0].replace('Executive Summary:','').trim();
      const r2 = p[1];
      if (r2.includes('---CATEGORY COMMENTARY---')) {
        const p2 = r2.split('---CATEGORY COMMENTARY---');
        rca = p2[0].trim(); comm = p2[1].trim();
      } else { rca = r2.trim(); }
    }

    document.getElementById('t3-exec-summary').textContent = exec;
    document.getElementById('t3-full-report').textContent  = summary;

    // Trace
    const traceEl = document.getElementById('t3-trace');
    traceEl.innerHTML = (data.path_trace || []).map(t =>
      `<div style="padding:3px 0;border-bottom:1px solid #eff3fb">${escHtml(t)}</div>`
    ).join('');

    // RCA
    if (rca) {
      document.getElementById('t3-rca').textContent = rca;
      document.getElementById('t3-rca-section').style.display = '';
    }
    if (comm) {
      document.getElementById('t3-comm').textContent = comm;
      document.getElementById('t3-comm-section').style.display = '';
    }

    document.getElementById('t3-results-divider').style.display = '';
    document.getElementById('t3-results').style.display         = '';
  }

  async function sendFeedback(score) {
    const runId = window._t3_run_id;
    if (!runId) return;
    try {
      await vaPost(`/api/tab5/runs/${runId}/feedback`, { score });
      document.getElementById('t3-fb-msg').textContent = score > 0 ? '✅ Thanks for the positive feedback!' : '✅ Feedback recorded.';
    } catch(e) { /* ignore */ }
  }

  function kpi(label, value, sub) {
    return `<div class="col-md-3 col-6"><div class="metric-card">
      <div class="metric-label">${label}</div>
      <div class="metric-value">${value}</div>
      <div class="metric-sub">${sub}</div>
    </div></div>`;
  }

  function escHtml(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
  function delay(ms) { return new Promise(r => setTimeout(r, ms)); }

  window.addEventListener('va:tabchange', e => { if (e.detail === 'tab3') init(); });
})();
