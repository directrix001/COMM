/**
 * tab5.js — Run History
 * GET /api/tab5/runs         → list all runs
 * GET /api/tab5/runs/{id}    → run detail
 * POST /api/tab5/runs/{id}/feedback
 * GET /api/tab5/summary      → feedback counts
 */
(function () {
  'use strict';
  let initialised = false;

  function buildHTML() {
    return `
      <div class="va-section-label"><i class="bi bi-database"></i> Historical Analysis Runs</div>

      <div id="t5-alert" class="va-alert mb-3"></div>

      <!-- Feedback summary KPIs -->
      <div class="row g-3 mb-3" id="t5-summary-row">
        <div class="col-md-4"><div class="metric-card" id="t5-kpi-pos">
          <div class="metric-label">👍 Positive</div><div class="metric-value">–</div>
        </div></div>
        <div class="col-md-4"><div class="metric-card" id="t5-kpi-neg">
          <div class="metric-label">👎 Negative</div><div class="metric-value">–</div>
        </div></div>
        <div class="col-md-4"><div class="metric-card" id="t5-kpi-none">
          <div class="metric-label">➖ No Rating</div><div class="metric-value">–</div>
        </div></div>
      </div>

      <!-- Runs table -->
      <div class="va-table-wrap mb-3">
        <div class="va-table-scroll" id="t5-table-wrap">
          <p style="padding:16px;color:var(--text-muted);font-size:.82rem">Loading…</p>
        </div>
      </div>

      <!-- Detail panel -->
      <div id="t5-detail" style="display:none">
        <hr class="va-divider">
        <div class="va-section-label"><i class="bi bi-file-text"></i> Run Details</div>
        <div class="row g-3 mb-3" id="t5-detail-kpis"></div>
        <p id="t5-detail-meta" style="font-size:.78rem;color:var(--text-muted)"></p>
        <div class="va-card" id="t5-detail-summary"
          style="white-space:pre-wrap;font-size:.8rem;max-height:400px;overflow-y:auto"></div>
      </div>
    `;
  }

  function init() {
    if (initialised) return;
    initialised = true;
    document.getElementById('tab5-content').innerHTML = buildHTML();
    loadData();
  }

  async function loadData() {
    try {
      const [runs, summary] = await Promise.all([
        vaGet('/api/tab5/runs'),
        vaGet('/api/tab5/summary'),
      ]);
      renderSummary(summary);
      renderTable(runs);
    } catch (e) {
      vaAlert('t5-alert', `Error loading history: ${e.message}`, 'error');
    }
  }

  function renderSummary(s) {
    document.querySelector('#t5-kpi-pos  .metric-value').textContent = s.positive;
    document.querySelector('#t5-kpi-neg  .metric-value').textContent = s.negative;
    document.querySelector('#t5-kpi-none .metric-value').textContent = s.none;
  }

  function renderTable(runs) {
    const wrap = document.getElementById('t5-table-wrap');
    if (!runs.length) {
      wrap.innerHTML = '<p style="padding:16px;color:var(--text-muted)">No runs yet. Use the Commentary Generator tab to log analyses.</p>';
      return;
    }
    const cols = ['id','timestamp','filename','total_variance','feedback_label'];
    const table = vaBuildTable(cols, runs, { rightAlign: ['id'] });
    table.querySelectorAll('tbody tr').forEach((tr, i) => {
      tr.style.cursor = 'pointer';
      tr.addEventListener('click', () => loadDetail(runs[i].id));
    });
    wrap.innerHTML = '';
    wrap.appendChild(table);
  }

  async function loadDetail(id) {
    try {
      const run = await vaGet(`/api/tab5/runs/${id}`);
      const det = document.getElementById('t5-detail');
      document.getElementById('t5-detail-kpis').innerHTML = `
        ${kpi('Run ID',   run.id, '')}
        ${kpi('Variance', run.total_variance, '')}
        ${kpi('Feedback', run.feedback_label || '➖', '')}
      `;
      document.getElementById('t5-detail-meta').textContent =
        `File: ${run.filename}  |  Ran at: ${run.timestamp}  |  Hierarchy: ${(run.hierarchy_list||[]).join(' → ')}`;
      document.getElementById('t5-detail-summary').textContent = run.summary || '(no summary)';
      det.style.display = '';
      det.scrollIntoView({ behavior: 'smooth' });
    } catch(e) {
      vaAlert('t5-alert', e.message, 'error');
    }
  }

  function kpi(label, value, sub) {
    return `<div class="col-md-4"><div class="metric-card">
      <div class="metric-label">${label}</div>
      <div class="metric-value">${value}</div>
      <div class="metric-sub">${sub}</div>
    </div></div>`;
  }

  window.addEventListener('va:tabchange', e => {
    if (e.detail === 'tab5') { init(); if (initialised) loadData(); }
  });
})();
