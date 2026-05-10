/**
 * tab2.js — Variance Analysis tab  (UPDATED)
 *
 * Changes:
 *  1. A/B column headers shown as actual scenario names; delta → "Variance"
 *  2. Pivot table is hierarchical with expand/collapse per group level
 *     (uses tree_records from /run response instead of flat records)
 *
 * Flow:
 *  1. Render HTML skeleton into #tab2-content on first activation
 *  2. Data source selection:
 *       (a) "Use Tab 1 output"  → POST /api/tab2/load-tab1
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
          <i class="bi bi-upload"></i> Upload &amp; Load
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
          <i class="bi bi-upload"></i> Upload &amp; Combine
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
        <div class="d-flex align-items-center justify-content-between mb-2">
          <div class="va-section-label mb-0"><i class="bi bi-table"></i> Pivot Variance</div>
          <div class="d-flex gap-2">
            <button class="btn-va-outline btn-sm" id="t2-btn-expand-all" style="font-size:.72rem;padding:3px 10px">
              <i class="bi bi-chevron-down"></i> Expand All
            </button>
            <button class="btn-va-outline btn-sm" id="t2-btn-collapse-all" style="font-size:.72rem;padding:3px 10px">
              <i class="bi bi-chevron-right"></i> Collapse All
            </button>
          </div>
        </div>
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

      <!-- ── Tree Pivot Styles ──────────────────────────────────────── -->
      <style>
        /* Hierarchical pivot table */
        .va-tree-table { width:100%; border-collapse:collapse; font-size:.8rem; }
        .va-tree-table th {
          background: var(--surface-2, #1e2a3a);
          color: var(--text-muted, #8fa3b1);
          font-weight:600;
          padding: 7px 10px;
          text-align:left;
          border-bottom: 1px solid var(--border, #2a3a4a);
          white-space:nowrap;
          position:sticky;
          top:0;
          z-index:2;
        }
        .va-tree-table th.num { text-align:right; }
        .va-tree-table td {
          padding: 5px 10px;
          border-bottom: 1px solid var(--border, #2a3a4a);
          vertical-align:middle;
          white-space:nowrap;
        }
        .va-tree-table td.num { text-align:right; font-variant-numeric:tabular-nums; }

        /* Level-based indentation & styling */
        .va-tree-row[data-level="0"] td.tree-label { font-weight:700; }
        .va-tree-row[data-level="1"] td.tree-label { font-weight:600; }
        .va-tree-row[data-level="0"] { background: var(--surface-1, #162030); }
        .va-tree-row[data-level="1"] { background: var(--surface-2, #1e2a3a); }
        .va-tree-row.leaf-row { background: transparent; }
        .va-tree-row.hidden  { display:none; }

        /* Subtotal rows (non-leaf parents) */
        .va-tree-row.subtotal-row td {
          background: var(--surface-1, #162030);
          font-weight:600;
        }

        /* Grand total row */
        .va-grand-total td {
          background: var(--surface-2, #1e2a3a);
          font-weight:700;
          border-top: 2px solid var(--blue-light, #4da6ff);
          color: var(--blue-light, #4da6ff);
        }

        /* Expander toggle */
        .tree-expander {
          display:inline-flex;
          align-items:center;
          justify-content:center;
          width:18px; height:18px;
          cursor:pointer;
          border-radius:3px;
          background: var(--surface-3, #243040);
          color: var(--blue-light, #4da6ff);
          font-size:.65rem;
          margin-right:4px;
          flex-shrink:0;
          transition: background .15s;
          user-select:none;
        }
        .tree-expander:hover { background: var(--blue-light, #4da6ff); color:#fff; }
        .tree-expander.leaf-spacer {
          background:transparent;
          cursor:default;
          color:transparent;
        }

        .tree-label-inner {
          display:inline-flex;
          align-items:center;
        }

        /* Variance coloring */
        .var-fav  { color: var(--green, #22c55e); }
        .var-adv  { color: var(--red,   #ef4444); }
        .var-zero { color: var(--text-muted, #8fa3b1); }
      </style>
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
      const btn = document.getElementById('t2-btn-load-tab1');
      btn.disabled = true;
      btn.innerHTML = vaSpinner('Loading…');
      try {
        const data = await vaPost('/api/tab2/load-tab1', {});
        onFiltersLoaded(data);
        vaToast('✅ Tab 1 mapping data loaded — ' + data.rows.toLocaleString() + ' rows');
        vaAlertClear('t2-src-alert');
      } catch (e) {
        vaAlert(
          't2-src-alert',
          e.message.includes('404')
            ? '⚠️ No Tab 1 data found. Go to <strong>Tagetik Mapping</strong> tab, upload your Excel file and click Generate Mapping first.'
            : 'Could not load Tab 1 data: ' + e.message,
          'error'
        );
      } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-link-45deg"></i> Load Tab 1 Data';
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

    document.getElementById('t2-config-divider').style.display = '';
    document.getElementById('t2-config-section').style.display = '';

    populateSelect('t2-sc-a', data.scenarios || []);
    populateSelect('t2-sc-b', data.scenarios || [], 1);

    const ms = document.getElementById('t2-month-select');
    ms.innerHTML = (data.month_cols || []).map(c => `<option value="${c}">${c}</option>`).join('');

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
      scenario_a:         document.getElementById('t2-sc-a').value,
      scenario_b:         document.getElementById('t2-sc-b').value,
      sel_period,
      group_fields:       groups,
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

  /* ══════════════════════════════════════════════════════════════════════
   * HIERARCHICAL PIVOT TABLE
   * ══════════════════════════════════════════════════════════════════════ */

  /**
   * Build an expandable tree table from tree_records returned by /run.
   *
   * Each tree node:
   *   { label, field, level, is_leaf, <sc_a>, <sc_b>, Variance, "Variance %", children[] }
   *
   * Strategy:
   *  - Flatten tree into rows with unique IDs and parent IDs
   *  - Top-level nodes are expanded by default; all children hidden
   *  - Clicking expander toggles direct children visibility and
   *    recursively collapses subtree when closing
   */
  function buildTreeTable(treeRecords, colA, colB, favLower) {
    const table = document.createElement('table');
    table.className = 'va-tree-table';

    // ── Header ─────────────────────────────────────────────────────────
    const thead = table.createTHead();
    const hrow  = thead.insertRow();
    const headers = ['', colA, colB, 'Variance', 'Variance %'];
    headers.forEach((h, i) => {
      const th = document.createElement('th');
      th.textContent = h;
      if (i > 0) th.className = 'num';
      hrow.appendChild(th);
    });

    // ── Flatten tree into rows array ────────────────────────────────────
    const rows = [];   // { id, parentId, level, is_leaf, label, colA, colB, Variance, VarPct }
    let   uid  = 0;

    function flatten(nodes, parentId) {
      nodes.forEach(node => {
        const id = ++uid;
        rows.push({
          id,
          parentId,
          level:    node.level,
          is_leaf:  node.is_leaf,
          label:    node.label,
          a:        node[colA],
          b:        node[colB],
          variance: node['Variance'],
          varPct:   node['Variance %'],
          hasChildren: !node.is_leaf && node.children && node.children.length > 0,
        });
        if (!node.is_leaf && node.children && node.children.length) {
          flatten(node.children, id);
        }
      });
    }
    flatten(treeRecords, null);

    // ── Grand Total ─────────────────────────────────────────────────────
    const grandA   = rows.filter(r => r.parentId === null).reduce((s, r) => s + (r.a || 0), 0);
    const grandB   = rows.filter(r => r.parentId === null).reduce((s, r) => s + (r.b || 0), 0);
    const grandVar = grandA - grandB;
    const grandPct = grandB !== 0 ? (grandVar / grandB * 100) : null;

    // Build id→row map for child lookup
    const rowMap     = {};
    const childrenOf = {};
    rows.forEach(r => {
      rowMap[r.id] = r;
      if (!childrenOf[r.parentId]) childrenOf[r.parentId] = [];
      childrenOf[r.parentId].push(r.id);
    });

    // ── Build tbody ─────────────────────────────────────────────────────
    const tbody = table.createTBody();
    const trMap = {}; // id → <tr> element

    rows.forEach(row => {
      const tr = tbody.insertRow();
      tr.className = `va-tree-row${row.is_leaf ? ' leaf-row' : ' subtotal-row'}`;
      tr.dataset.id     = row.id;
      tr.dataset.parent = row.parentId || '';
      tr.dataset.level  = row.level;

      // Top-level rows visible; everything else hidden initially
      if (row.parentId !== null) tr.classList.add('hidden');

      // ── Label cell ───────────────────────────────────────────────────
      const tdLabel = document.createElement('td');
      tdLabel.className = 'tree-label';
      tdLabel.style.paddingLeft = `${8 + row.level * 20}px`;

      const inner = document.createElement('span');
      inner.className = 'tree-label-inner';

      if (row.hasChildren) {
        const tog = document.createElement('span');
        tog.className = 'tree-expander';
        tog.innerHTML = '&#9658;'; // ► right arrow = collapsed
        tog.dataset.expanded = 'false';
        tog.addEventListener('click', e => {
          e.stopPropagation();
          toggleNode(row.id, tog, trMap, childrenOf);
        });
        inner.appendChild(tog);
      } else {
        const spacer = document.createElement('span');
        spacer.className = 'tree-expander leaf-spacer';
        spacer.innerHTML = '&nbsp;';
        inner.appendChild(spacer);
      }

      const labelText = document.createElement('span');
      labelText.textContent = row.label || '(blank)';
      inner.appendChild(labelText);
      tdLabel.appendChild(inner);
      tr.appendChild(tdLabel);

      // ── Numeric cells ─────────────────────────────────────────────────
      [row.a, row.b, row.variance, row.varPct].forEach((val, ci) => {
        const td = document.createElement('td');
        td.className = 'num';
        if (val == null) {
          td.textContent = '–';
        } else if (ci === 3) {
          // Variance %
          const pct = parseFloat(val);
          td.textContent = isNaN(pct) ? '–' : `${pct >= 0 ? '+' : ''}${pct.toFixed(1)}%`;
          td.classList.add(varClass(pct, favLower));
        } else if (ci === 2) {
          // Variance absolute
          const v = parseFloat(val);
          td.textContent = isNaN(v) ? '–' : fmtNum(v);
          td.classList.add(varClass(v, favLower));
        } else {
          td.textContent = fmtNum(parseFloat(val));
        }
        tr.appendChild(td);
      });

      trMap[row.id] = tr;
    });

    // ── Grand Total row ─────────────────────────────────────────────────
    const gtRow = tbody.insertRow();
    gtRow.className = 'va-grand-total';
    const gtLabel = document.createElement('td');
    gtLabel.className = 'tree-label';
    gtLabel.textContent = 'Grand Total';
    gtLabel.style.paddingLeft = '8px';
    gtRow.appendChild(gtLabel);

    [grandA, grandB, grandVar, grandPct].forEach((val, ci) => {
      const td = document.createElement('td');
      td.className = 'num';
      if (val == null) {
        td.textContent = '–';
      } else if (ci === 3) {
        const pct = parseFloat(val);
        td.textContent = isNaN(pct) ? '–' : `${pct >= 0 ? '+' : ''}${pct.toFixed(1)}%`;
      } else {
        td.textContent = fmtNum(parseFloat(val));
      }
      gtRow.appendChild(td);
    });

    return table;
  }

  /**
   * Toggle expand/collapse for a node.
   * - Expand: show direct children; if a child was previously expanded, restore its children too
   * - Collapse: hide ALL descendants recursively
   */
  function toggleNode(nodeId, togEl, trMap, childrenOf) {
    const isExpanded = togEl.dataset.expanded === 'true';

    if (isExpanded) {
      // Collapse: hide all descendants
      collapseAll(nodeId, trMap, childrenOf);
      togEl.dataset.expanded = 'false';
      togEl.innerHTML = '&#9658;'; // ►
    } else {
      // Expand: show direct children only
      const kids = childrenOf[nodeId] || [];
      kids.forEach(cid => {
        const tr = trMap[cid];
        if (tr) tr.classList.remove('hidden');
      });
      togEl.dataset.expanded = 'true';
      togEl.innerHTML = '&#9660;'; // ▼
    }
  }

  function collapseAll(nodeId, trMap, childrenOf) {
    const kids = childrenOf[nodeId] || [];
    kids.forEach(cid => {
      const tr = trMap[cid];
      if (tr) {
        tr.classList.add('hidden');
        // Reset expander of child if it has one
        const childTog = tr.querySelector('.tree-expander:not(.leaf-spacer)');
        if (childTog) {
          childTog.dataset.expanded = 'false';
          childTog.innerHTML = '&#9658;';
        }
        collapseAll(cid, trMap, childrenOf);
      }
    });
  }

  /** Expand all nodes in a table */
  function expandAllNodes(wrap) {
    wrap.querySelectorAll('.tree-expander:not(.leaf-spacer)').forEach(tog => {
      if (tog.dataset.expanded === 'false') tog.click();
    });
  }

  /** Collapse all top-level nodes in a table */
  function collapseAllNodes(wrap) {
    // Click expanded top-level expanders
    wrap.querySelectorAll('.va-tree-row[data-level="0"] .tree-expander:not(.leaf-spacer)').forEach(tog => {
      if (tog.dataset.expanded === 'true') tog.click();
    });
  }

  /* ── RENDER RESULTS ─────────────────────────────────────────────────── */
  function renderResults(data, favLower) {
    const colA = data.col_a || data.scenario_a || 'Scenario A';
    const colB = data.col_b || data.scenario_b || 'Scenario B';

    // ── KPI row ─────────────────────────────────────────────────────────
    const kpiRow = document.getElementById('t2-kpi-row');
    const varIsGood = (favLower && parseFloat(data.total_variance.replace(/,/g, '')) < 0) ||
                      (!favLower && parseFloat(data.total_variance.replace(/,/g, '')) > 0);
    const varColor = varIsGood ? 'var(--green)' : 'var(--red)';
    kpiRow.innerHTML = `
      ${kpi(colA, data.total_a, 'Scenario A (Base)')}
      ${kpi(colB, data.total_b, 'Scenario B (Compare)')}
      ${kpi('Net Variance (A−B)', `<span style="color:${varColor}">${data.total_variance}</span>`, data.pct_variance + ' vs B')}
      ${kpi('Max Single |Δ|', data.max_variance, `${data.rows} leaf rows`)}
    `;

    // ── Hierarchical pivot table ────────────────────────────────────────
    const pivWrap = document.getElementById('t2-pivot-wrap');
    pivWrap.innerHTML = '';

    if (data.tree_records && data.tree_records.length) {
      const treeTable = buildTreeTable(data.tree_records, colA, colB, favLower);
      pivWrap.appendChild(treeTable);

      // Bind expand/collapse all buttons
      document.getElementById('t2-btn-expand-all').onclick   = () => expandAllNodes(pivWrap);
      document.getElementById('t2-btn-collapse-all').onclick = () => collapseAllNodes(pivWrap);
    } else if (data.records && data.records.length) {
      // Fallback: flat table if no tree data
      const numCols = [colA, colB, 'Variance', 'Variance %'];
      const table = vaBuildTable(
        data.columns, data.records,
        { rightAlign: numCols, favCols: ['Variance', 'Variance %'], favLower }
      );
      pivWrap.appendChild(table);
    }

    // ── Hotspot ─────────────────────────────────────────────────────────
    renderHotspot(data.hotspot || [], data.group_fields || [], colA, colB, favLower);

    // ── Top / Bottom 5 ──────────────────────────────────────────────────
    const top5Cols = (data.columns || []).slice(0, 6);
    renderMini('t2-top5-wrap', top5Cols, data.top5 || []);
    renderMini('t2-bot5-wrap', top5Cols, data.bot5 || []);
    document.getElementById('t2-top5-label').textContent = favLower ? 'Top 5 Favourable' : 'Top 5 Positive';
    document.getElementById('t2-bot5-label').textContent = favLower ? 'Top 5 Adverse'    : 'Top 5 Negative';

    document.getElementById('t2-results-divider').style.display = '';
    document.getElementById('t2-results').style.display = '';
  }

  function renderHotspot(hotspot, groupFields, colA, colB, favLower) {
    const row     = document.getElementById('t2-hotspot-row');
    const ranks   = ['r1','r2','r3','r4'];
    const labels  = ['#1 Worst','#2','#3','#4'];
    const lastDim = groupFields[groupFields.length - 1] || 'Item';
    row.innerHTML = hotspot.slice(0,4).map((h, i) => {
      // hotspot records now have renamed keys (colA, colB, Variance, pct)
      const varVal  = h['Variance'] != null ? h['Variance'] : h.delta;
      const aVal    = h[colA] != null ? h[colA] : h.A;
      const bVal    = h[colB] != null ? h[colB] : h.B;
      const delta   = varVal  != null ? Number(varVal).toLocaleString(undefined, {maximumFractionDigits:0}) : '–';
      const arrow   = (varVal || 0) > 0 ? '▲' : '▼';
      const pct     = h.pct  != null ? `${Number(h.pct).toFixed(1)}%` : '–';
      return `
        <div class="hs-card ${ranks[i] || 'r4'}">
          <div class="hs-rank">${labels[i] || `#${i+1}`}</div>
          <div class="hs-dim">${lastDim}</div>
          <div class="hs-name" title="${h[lastDim] || ''}">${h[lastDim] || '–'}</div>
          <div class="hs-delta">${arrow} ${delta}</div>
          <div class="hs-meta">${colA}: ${fmtN(aVal)} | ${colB}: ${fmtN(bVal)}</div>
          <div class="hs-meta">Δ% vs B: ${pct}</div>
        </div>`;
    }).join('');
  }

  function renderMini(wrapperId, cols, records) {
    const wrap = document.getElementById(wrapperId);
    wrap.innerHTML = '';
    if (!records.length) { wrap.textContent = 'No data'; return; }
    wrap.appendChild(vaBuildTable(cols, records, { rightAlign: cols.slice(-4) }));
  }

  function hideResults() {
    document.getElementById('t2-results-divider').style.display = 'none';
    document.getElementById('t2-results').style.display         = 'none';
  }

  /* ── Formatting helpers ──────────────────────────────────────────────── */

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

  function fmtNum(v) {
    if (v == null || isNaN(v)) return '–';
    return v.toLocaleString(undefined, { maximumFractionDigits: 0 });
  }

  function fmtN(v) {
    if (v == null) return '–';
    const n = parseFloat(v);
    if (isNaN(n)) return '–';
    if (Math.abs(n) >= 1e6) return (n/1e6).toFixed(2) + 'M';
    if (Math.abs(n) >= 1e3) return (n/1e3).toFixed(1) + 'K';
    return n.toFixed(0);
  }

  /**
   * Returns CSS class for variance coloring.
   * favLower=true  → negative variance = good (green), positive = bad (red)
   * favLower=false → positive variance = good (green), negative = bad (red)
   */
  function varClass(v, favLower) {
    if (v == null || isNaN(v) || v === 0) return 'var-zero';
    const good = favLower ? v < 0 : v > 0;
    return good ? 'var-fav' : 'var-adv';
  }

  function delay(ms) { return new Promise(r => setTimeout(r, ms)); }

  /* ── ACTIVATE ───────────────────────────────────────────────────────── */
  window.addEventListener('va:tabchange', e => { if (e.detail === 'tab2') init(); });

})();
