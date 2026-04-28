/**
 * tab2.js — Variance Analysis tab
 *
 * Flow:
 *  1. Render HTML skeleton into #tab2-content on first activation
 *  2. Data source selection:
 *       (a) "Use Tab 1 output"  → POST /api/tab2/use-tab1 (stub — calls /upload with session)
 *       (b) "Upload Master DB"  → POST /api/tab2/upload
 *       (c) "Upload Two Files"  → POST /api/tab2/upload-two
 *  3. After load → GET /api/tab2/filters → populate all multiselects + scenario selects
 *  4. "Run Variance" → POST /api/tab2/run → render metrics, pivot table, hotspot cards
 *  5. Download Excel → GET /api/tab2/download/xlsx
 */

(function () {
  'use strict';

  let initialised = false;
  let msWidgets   = {};   // { markets, regions, divisions, entities, lc_oh }
  let filterData  = null; // last /filters response
  let lastResult  = null; // last /run response

  /* ── HTML TEMPLATE ──────────────────────────────────────────────────── */
  function buildHTML() {
    return `
      <!-- ── Data Source ─────────────────────────────────────────────── -->
      <div class="va-section-label"><i class="bi bi-database"></i> Data Source</div>

      <div class="mb-3">
        <label class="form-label">Select data source mode</label>
        <select class="form-select" id="t2-src-mode" style="max-width:420px">
          <option value="tab1">Use Generated Output (from Tagetik Mapping)</option>
          <option value="master">Upload Master DB (single file with both scenarios)</option>
          <option value="two">Upload Two Files (A &amp; B — assign scenario labels)</option>
        </select>
      </div>

      <!-- sub-panels -->
      <div id="t2-src-tab1"   class="t2-src-panel">
        <div class="va-alert va-alert-info show" style="display:flex">
          <i class="bi bi-info-circle-fill"></i>
          <span>Will use data from Tab 1 session. Make sure you have run Tagetik Mapping first.</span>
        </div>
        <button class="btn-va-outline" id="t2-btn-load-tab1">
          <i class="bi bi-link-45deg"></i> Load Tab 1 Data
        </button>
      </div>

      <div id="t2-src-master" class="t2-src-panel" style="display:none">
        <div class="upload-zone" id="t2-dropzone-master">
          <input type="file" id="t2-file-master" accept=".xlsx,.xls" />
          <i class="bi bi-cloud-upload"></i>
          <p><strong>Upload Master DB</strong> (.xlsx with Scenario column)</p>
          <p id="t2-master-fname" style="font-size:.72rem;color:var(--blue-light)"></p>
        </div>
        <button class="btn-va-primary mt-2" id="t2-btn-load-master">
          <i class="bi bi-upload"></i> Upload & Load
        </button>
      </div>

      <div id="t2-src-two" class="t2-src-panel" style="display:none">
        <div class="row g-3">
          <div class="col-md-6">
            <label class="form-label">Scenario A file</label>
            <div class="upload-zone" id="t2-dropzone-a">
              <input type="file" id="t2-file-a" accept=".xlsx,.xls" />
              <i class="bi bi-cloud-upload"></i>
              <p>File for <strong>Scenario A</strong></p>
              <p id="t2-a-fname" style="font-size:.72rem;color:var(--blue-light)"></p>
            </div>
            <input class="form-control mt-2" id="t2-label-a" placeholder="Scenario A label" value="Scenario_A" />
          </div>
          <div class="col-md-6">
            <label class="form-label">Scenario B file</label>
            <div class="upload-zone" id="t2-dropzone-b">
              <input type="file" id="t2-file-b" accept=".xlsx,.xls" />
              <i class="bi bi-cloud-upload"></i>
              <p>File for <strong>Scenario B</strong></p>
              <p id="t2-b-fname" style="font-size:.72rem;color:var(--blue-light)"></p>
            </div>
            <input class="form-control mt-2" id="t2-label-b" placeholder="Scenario B label" value="Scenario_B" />
          </div>
        </div>
        <button class="btn-va-primary mt-3" id="t2-btn-load-two">
          <i class="bi bi-upload"></i> Upload & Combine
        </button>
      </div>

      <div id="t2-src-alert" class="va-alert mt-2"></div>

      <hr class="va-divider" id="t2-config-divider" style="display:none">

      <!-- ── Filters & Configuration ────────────────────────────────── -->
      <div id="t2-config-section" style="display:none">

        <div class="va-section-label"><i class="bi bi-sliders"></i> Filters &amp; Configuration</div>

        <!-- Period + Scenarios -->
        <div class="row g-3 mb-3">
          <div class="col-md-4">
            <label class="form-label">📅 Analysis Period</label>
            <div class="d-flex gap-3">
              <div class="form-check">
                <input class="form-check-input" type="radio" name="t2-period-mode" id="t2-ytd" value="ytd" checked>
                <label class="form-check-label" for="t2-ytd">YTD</label>
              </div>
              <div class="form-check">
                <input class="form-check-input" type="radio" name="t2-period-mode" id="t2-mtd" value="mtd">
                <label class="form-check-label" for="t2-mtd">MTD — Specific Month</label>
              </div>
            </div>
            <select class="form-select mt-2" id="t2-month-select" style="display:none"></select>
          </div>
          <div class="col-md-4">
            <label class="form-label">📌 Scenario A (Base)</label>
            <select class="form-select" id="t2-sc-a"></select>
          </div>
          <div class="col-md-4">
            <label class="form-label">📌 Scenario B (Compare)</label>
            <select class="form-select" id="t2-sc-b"></select>
          </div>
        </div>

        <!-- Multi-select filters -->
        <div class="row g-3 mb-3">
          <div class="col-md-2 col-6">
            <label class="form-label">🌍 Market</label>
            <div class="va-multiselect" id="ms-markets"></div>
          </div>
          <div class="col-md-2 col-6">
            <label class="form-label">🗺️ Region</label>
            <div class="va-multiselect" id="ms-regions"></div>
          </div>
          <div class="col-md-3 col-6">
            <label class="form-label">🏢 Division</label>
            <div class="va-multiselect" id="ms-divisions"></div>
          </div>
          <div class="col-md-3 col-6">
            <label class="form-label">🏛️ Entity</label>
            <div class="va-multiselect" id="ms-entities"></div>
          </div>
          <div class="col-md-2 col-6">
            <label class="form-label">🏷️ OH/LC</label>
            <div class="va-multiselect" id="ms-lc-oh"></div>
          </div>
        </div>

        <!-- Pivot fields + Favorable -->
        <div class="row g-3 mb-3">
          <div class="col-md-8">
            <label class="form-label">🔀 Pivot Row Fields (hierarchy)</label>
            <div class="va-multiselect" id="ms-groups"></div>
          </div>
          <div class="col-md-4">
            <label class="form-label">✅ Favorable variance when</label>
            <select class="form-select" id="t2-fav-mode">
              <option value="lower">A &lt; B  (cost — lower is better)</option>
              <option value="higher">A &gt; B  (revenue — higher is better)</option>
            </select>
          </div>
        </div>

        <div id="t2-run-alert" class="va-alert"></div>
        <div id="t2-run-progress" class="mb-3"></div>

        <div class="d-flex gap-2">
          <button class="btn-va-primary" id="t2-btn-run">
            <i class="bi bi-play-fill"></i> Run Variance Analysis
          </button>
        </div>

      </div><!-- /t2-config-section -->

      <hr class="va-divider" id="t2-results-divider" style="display:none">

      <!-- ── Results ─────────────────────────────────────────────────── -->
      <div id="t2-results" style="display:none">

        <!-- KPI cards -->
        <div class="row g-3 mb-3" id="t2-kpi-row"></div>

        <hr class="va-divider">

        <!-- Pivot table -->
        <div class="va-section-label"><i class="bi bi-table"></i> Pivot Variance</div>
        <div class="va-table-wrap mb-3">
          <div class="va-table-scroll" id="t2-pivot-wrap"></div>
        </div>

        <hr class="va-divider">

        <!-- Hotspot -->
        <div class="va-section-label"><i class="bi bi-fire"></i> Variance Hotspot — Top 4 Adverse</div>
        <div class="hs-row" id="t2-hotspot-row"></div>

        <hr class="va-divider">

        <!-- Top/Bottom 5 -->
        <div class="va-section-label"><i class="bi bi-bar-chart-steps"></i> Top &amp; Bottom 5 Movers</div>
        <div class="row g-3">
          <div class="col-md-6">
            <p class="mb-1" style="font-size:.78rem;font-weight:600" id="t2-top5-label">Top 5 Favourable</p>
            <div class="va-table-wrap"><div class="va-table-scroll" id="t2-top5-wrap"></div></div>
          </div>
          <div class="col-md-6">
            <p class="mb-1" style="font-size:.78rem;font-weight:600" id="t2-bot5-label">Top 5 Adverse</p>
            <div class="va-table-wrap"><div class="va-table-scroll" id="t2-bot5-wrap"></div></div>
          </div>
        </div>

        <hr class="va-divider">

        <!-- Download -->
        <div class="va-section-label"><i class="bi bi-download"></i> Export</div>
        <a id="t2-dl-xlsx" href="/api/tab2/download/xlsx"
           class="btn-va-success text-decoration-none">
          <i class="bi bi-file-earmark-excel"></i> Download Variance Report (Excel)
        </a>
        <p class="mt-1" style="font-size:.68rem;color:var(--text-muted)">
          Includes: README · Variance (Flat) · PivotSource
        </p>

      </div><!-- /t2-results -->
    `;
  }

  /* ── INIT ───────────────────────────────────────────────────────────── */
  function init() {
    if (initialised) return;
    initialised = true;
    document.getElementById('tab2-content').innerHTML = buildHTML();
    bindSrcMode();
    bindFileZones();
    bindRunButton();
    bindPeriodRadio();
  }

  /* ── SRC MODE ───────────────────────────────────────────────────────── */
  function bindSrcMode() {
    const sel = document.getElementById('t2-src-mode');
    sel.addEventListener('change', () => {
      document.querySelectorAll('.t2-src-panel').forEach(p => p.style.display = 'none');
      document.getElementById(`t2-src-${sel.value}`).style.display = '';
    });

    // Load Tab1 button
    document.getElementById('t2-btn-load-tab1').addEventListener('click', async () => {
      try {
        const data = await vaGet('/api/tab2/filters');
        onFiltersLoaded(data);
        vaToast('Tab 1 data loaded!');
      } catch (e) {
        vaAlert('t2-src-alert', `Could not load Tab 1 data: ${e.message}`, 'error');
      }
    });

    // Master upload button
    document.getElementById('t2-btn-load-master').addEventListener('click', async () => {
      const fi = document.getElementById('t2-file-master');
      if (!fi.files[0]) { vaAlert('t2-src-alert', 'Select a file first.', 'warning'); return; }
      await doUpload('/api/tab2/upload', (() => {
        const fd = new FormData(); fd.append('file', fi.files[0]); return fd;
      })());
    });

    // Two files button
    document.getElementById('t2-btn-load-two').addEventListener('click', async () => {
      const fa = document.getElementById('t2-file-a');
      const fb = document.getElementById('t2-file-b');
      if (!fa.files[0] || !fb.files[0]) {
        vaAlert('t2-src-alert', 'Select both files.', 'warning'); return;
      }
      const fd = new FormData();
      fd.append('file_a', fa.files[0]);
      fd.append('file_b', fb.files[0]);
      fd.append('label_a', document.getElementById('t2-label-a').value || 'Scenario_A');
      fd.append('label_b', document.getElementById('t2-label-b').value || 'Scenario_B');
      await doUpload('/api/tab2/upload-two', fd);
    });
  }

  async function doUpload(url, fd) {
    vaAlertClear('t2-src-alert');
    try {
      const data = await vaPostForm(url, fd);
      onFiltersLoaded(data);
      vaToast(`✅ Loaded ${data.rows.toLocaleString()} rows!`);
    } catch (e) {
      vaAlert('t2-src-alert', e.message, 'error');
    }
  }

  /* ── BIND FILE DROP ZONES ────────────────────────────────────────────── */
  function bindFileZones() {
    bindZone('t2-dropzone-master', 't2-file-master', 't2-master-fname');
    bindZone('t2-dropzone-a',      't2-file-a',      't2-a-fname');
    bindZone('t2-dropzone-b',      't2-file-b',      't2-b-fname');
  }

  function bindZone(zoneId, inputId, labelId) {
    const zone  = document.getElementById(zoneId);
    const input = document.getElementById(inputId);
    const label = document.getElementById(labelId);
    zone.addEventListener('click', () => input.click());
    input.addEventListener('change', () => { if (input.files[0]) label.textContent = `📄 ${input.files[0].name}`; });
    zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag-over'); });
    zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
    zone.addEventListener('drop', e => {
      e.preventDefault(); zone.classList.remove('drag-over');
      if (e.dataTransfer.files[0]) {
        input.files = e.dataTransfer.files;
        label.textContent = `📄 ${e.dataTransfer.files[0].name}`;
      }
    });
  }

  /* ── PERIOD RADIO ───────────────────────────────────────────────────── */
  function bindPeriodRadio() {
    document.querySelectorAll('input[name="t2-period-mode"]').forEach(r => {
      r.addEventListener('change', () => {
        const mtd = document.getElementById('t2-month-select');
        mtd.style.display = r.value === 'mtd' ? '' : 'none';
      });
    });
  }

  /* ── POPULATE FILTERS ───────────────────────────────────────────────── */
  function onFiltersLoaded(data) {
    filterData = data;

    // Show config section
    document.getElementById('t2-config-divider').style.display = '';
    document.getElementById('t2-config-section').style.display = '';

    // Scenario dropdowns
    populateSelect('t2-sc-a', data.scenarios || []);
    populateSelect('t2-sc-b', data.scenarios || [], 1);

    // Month select
    const ms = document.getElementById('t2-month-select');
    ms.innerHTML = (data.month_cols || []).map(c => `<option value="${c}">${c}</option>`).join('');

    // Multiselect widgets
    const defs = [
      ['ms-markets',   data.markets   || [], 'All Markets'],
      ['ms-regions',   data.regions   || [], 'All Regions'],
      ['ms-divisions', data.divisions || [], 'All Divisions'],
      ['ms-entities',  data.entities  || [], 'All Entities'],
      ['ms-lc-oh',     data.lc_oh     || [], 'All OH/LC'],
      ['ms-groups',    data.avail_group || [], 'Select pivot fields'],
    ];
    defs.forEach(([id, opts, ph]) => {
      const el = document.getElementById(id);
      el.innerHTML = '';
      msWidgets[id] = new VaMultiselect(el, opts, ph);
    });
    // Default group selection
    if (data.avail_group && msWidgets['ms-groups']) {
      const defaults = (data.avail_group).slice(0, 3);
      msWidgets['ms-groups'].setOptions(data.avail_group, defaults);
    }
  }

  function populateSelect(id, opts, defaultIdx = 0) {
    const sel = document.getElementById(id);
    sel.innerHTML = opts.map((o, i) => `<option value="${o}" ${i === defaultIdx ? 'selected' : ''}>${o}</option>`).join('');
  }

  /* ── RUN BUTTON ─────────────────────────────────────────────────────── */
  function bindRunButton() {
    document.getElementById('t2-btn-run').addEventListener('click', handleRun);
  }

  async function handleRun() {
    vaAlertClear('t2-run-alert');
    hideResults();

    const groups = msWidgets['ms-groups'] ? msWidgets['ms-groups'].checked() : [];
    if (!groups.length) {
      vaAlert('t2-run-alert', 'Select at least one Pivot Row Field.', 'warning');
      return;
    }

    const periodMode = document.querySelector('input[name="t2-period-mode"]:checked').value;
    let sel_period;
    if (periodMode === 'ytd') {
      const fd = filterData;
      sel_period = fd && fd.month_cols && fd.month_cols.length ? '__YTD_CALC__' : 'YTD';
    } else {
      sel_period = document.getElementById('t2-month-select').value;
    }

    const body = {
      scenario_a:        document.getElementById('t2-sc-a').value,
      scenario_b:        document.getElementById('t2-sc-b').value,
      sel_period,
      group_fields:      groups,
      favorable_is_lower: document.getElementById('t2-fav-mode').value === 'lower',
      sel_markets:   msWidgets['ms-markets']   ? msWidgets['ms-markets'].checked()   : [],
      sel_regions:   msWidgets['ms-regions']   ? msWidgets['ms-regions'].checked()   : [],
      sel_divisions: msWidgets['ms-divisions'] ? msWidgets['ms-divisions'].checked() : [],
      sel_entities:  msWidgets['ms-entities']  ? msWidgets['ms-entities'].checked()  : [],
      sel_lc_oh:     msWidgets['ms-lc-oh']     ? msWidgets['ms-lc-oh'].checked()     : [],
    };

    const btn = document.getElementById('t2-btn-run');
    btn.disabled = true;
    btn.innerHTML = vaSpinner('Running…');
    vaProgress('t2-run-progress', 40, 'Aggregating & pivoting…');

    try {
      const data = await vaPost('/api/tab2/run', body);
      vaProgress('t2-run-progress', 100, 'Done ✓');
      await delay(400);
      vaProgressClear('t2-run-progress');
      lastResult = data;
      renderResults(data, body.favorable_is_lower);
      vaToast('✅ Variance analysis complete!');
    } catch (e) {
      vaProgressClear('t2-run-progress');
      vaAlert('t2-run-alert', e.message, 'error');
    } finally {
      btn.disabled = false;
      btn.innerHTML = '<i class="bi bi-play-fill"></i> Run Variance Analysis';
    }
  }

  /* ── RENDER RESULTS ─────────────────────────────────────────────────── */
  function renderResults(data, favLower) {
    // KPI row
    const kpiRow = document.getElementById('t2-kpi-row');
    const varColor = (favLower && data.total_variance.startsWith('-')) ||
                     (!favLower && !data.total_variance.startsWith('-')) ? 'var(--green)' : 'var(--red)';
    kpiRow.innerHTML = `
      ${kpi('Total A', data.total_a, 'Scenario A')}
      ${kpi('Total B', data.total_b, 'Scenario B')}
      ${kpi('Net Variance (A−B)', `<span style="color:${varColor}">${data.total_variance}</span>`, data.pct_variance + ' vs B')}
      ${kpi('Max Single |Δ|', data.max_variance, `${data.rows} leaf rows`)}
    `;

    // Pivot table
    const pivWrap = document.getElementById('t2-pivot-wrap');
    pivWrap.innerHTML = '';
    if (data.records && data.records.length) {
      const numCols = ['A','B','delta','delta_pct'];
      const table = vaBuildTable(
        data.columns,
        data.records,
        { rightAlign: numCols, favCols: ['delta','delta_pct'], favLower: favLower }
      );
      pivWrap.appendChild(table);
    }

    // Hotspot
    renderHotspot(data.hotspot || [], data.group_fields || []);

    // Top/Bottom 5
    const top5Cols = (data.columns || []).slice(0, 6);
    renderMini('t2-top5-wrap', top5Cols, data.top5 || []);
    renderMini('t2-bot5-wrap', top5Cols, data.bot5 || []);
    document.getElementById('t2-top5-label').textContent = favLower ? 'Top 5 Favourable' : 'Top 5 Positive';
    document.getElementById('t2-bot5-label').textContent = favLower ? 'Top 5 Adverse'    : 'Top 5 Negative';

    document.getElementById('t2-results-divider').style.display = '';
    document.getElementById('t2-results').style.display = '';
  }

  function renderHotspot(hotspot, groupFields) {
    const row     = document.getElementById('t2-hotspot-row');
    const ranks   = ['r1','r2','r3','r4'];
    const labels  = ['#1 Worst','#2','#3','#4'];
    const lastDim = groupFields[groupFields.length - 1] || 'Item';
    row.innerHTML = hotspot.slice(0,4).map((h, i) => {
      const delta = h.delta != null ? Number(h.delta).toLocaleString(undefined,{maximumFractionDigits:0}) : '–';
      const arrow = h.delta > 0 ? '▲' : '▼';
      const pct   = h.pct   != null ? `${Number(h.pct).toFixed(1)}%` : '–';
      return `
        <div class="hs-card ${ranks[i] || 'r4'}">
          <div class="hs-rank">${labels[i] || `#${i+1}`}</div>
          <div class="hs-dim">${lastDim}</div>
          <div class="hs-name" title="${h[lastDim] || ''}">${h[lastDim] || '–'}</div>
          <div class="hs-delta">${arrow} ${delta}</div>
          <div class="hs-meta">A: ${fmtN(h.A)} | B: ${fmtN(h.B)}</div>
          <div class="hs-meta">Δ% vs B: ${pct}</div>
        </div>`;
    }).join('');
  }

  function renderMini(wrapperId, cols, records) {
    const wrap = document.getElementById(wrapperId);
    wrap.innerHTML = '';
    if (!records.length) { wrap.textContent = 'No data'; return; }
    wrap.appendChild(vaBuildTable(cols, records, { rightAlign: ['A','B','delta','delta_pct'] }));
  }

  function hideResults() {
    document.getElementById('t2-results-divider').style.display = 'none';
    document.getElementById('t2-results').style.display         = 'none';
  }

  function kpi(label, value, sub) {
    return `
      <div class="col-md-3 col-6">
        <div class="metric-card">
          <div class="metric-label">${label}</div>
          <div class="metric-value">${value}</div>
          <div class="metric-sub">${sub}</div>
        </div>
      </div>`;
  }

  function fmtN(v) {
    if (v == null) return '–';
    const n = parseFloat(v);
    if (isNaN(n)) return '–';
    if (Math.abs(n) >= 1e6) return (n/1e6).toFixed(2) + 'M';
    if (Math.abs(n) >= 1e3) return (n/1e3).toFixed(1) + 'K';
    return n.toFixed(0);
  }

  function delay(ms) { return new Promise(r => setTimeout(r, ms)); }

  /* ── ACTIVATE ───────────────────────────────────────────────────────── */
  window.addEventListener('va:tabchange', e => { if (e.detail === 'tab2') init(); });

})();
