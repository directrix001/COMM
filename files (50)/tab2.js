/**
 * tab2.js — Variance Analysis  v3
 * Changes:
 *  1. Table headers use actual scenario names (not A/B)
 *  2. delta → "Variance (M€)", delta_pct → "Variance %" (from backend)
 *  3. Hotspot cards REMOVED
 *  4. Expandable pivot table — click group row to expand/collapse detail rows
 *     Shows totals-first, detail on expand
 */
(function () {
  'use strict';
  let initialised = false;
  let msWidgets   = {};
  let filterData  = null;
  let lastResult  = null;

  // ── HTML TEMPLATE ─────────────────────────────────────────────────────
  function buildHTML() {
    return `
      <div class="va-section-label"><i class="bi bi-database"></i> Data Source</div>

      <div class="mb-3">
        <label class="form-label">Select data source mode</label>
        <select class="form-select" id="t2-src-mode" style="max-width:420px">
          <option value="tab1">Use Generated Output (from Tagetik Mapping)</option>
          <option value="master">Upload Master DB (single file with both scenarios)</option>
          <option value="two">Upload Two Files (A &amp; B — assign scenario labels)</option>
        </select>
      </div>

      <div id="t2-src-tab1" class="t2-src-panel">
        <div class="va-alert va-alert-info show" style="display:flex">
          <i class="bi bi-info-circle-fill"></i>
          <span>Uses mapping output from Tab 1. Run Tagetik Mapping first.</span>
        </div>
        <button class="btn-va-outline" id="t2-btn-load-tab1">
          <i class="bi bi-link-45deg"></i> Load Tab 1 Data
        </button>
      </div>

      <div id="t2-src-master" class="t2-src-panel" style="display:none">
        <div class="upload-zone-compact" id="t2-dropzone-master">
          <input type="file" id="t2-file-master" accept=".xlsx,.xls" />
          <i class="bi bi-cloud-upload" style="font-size:1rem"></i>
          <span><strong>Master DB</strong> (.xlsx with Scenario column)</span>
          <span id="t2-master-fname" style="color:var(--blue-light);font-size:.72rem"></span>
        </div>
        <button class="btn-va-primary mt-2" id="t2-btn-load-master">
          <i class="bi bi-upload"></i> Upload &amp; Load
        </button>
      </div>

      <div id="t2-src-two" class="t2-src-panel" style="display:none">
        <div class="row g-3">
          <div class="col-md-6">
            <label class="form-label">Scenario A file</label>
            <div class="upload-zone-compact" id="t2-dropzone-a">
              <input type="file" id="t2-file-a" accept=".xlsx,.xls" />
              <i class="bi bi-cloud-upload" style="font-size:1rem"></i>
              <span>File for <strong>Scenario A</strong></span>
              <span id="t2-a-fname" style="color:var(--blue-light);font-size:.72rem"></span>
            </div>
            <input class="form-control mt-2" id="t2-label-a" placeholder="Scenario A label" value="Scenario_A"/>
          </div>
          <div class="col-md-6">
            <label class="form-label">Scenario B file</label>
            <div class="upload-zone-compact" id="t2-dropzone-b">
              <input type="file" id="t2-file-b" accept=".xlsx,.xls" />
              <i class="bi bi-cloud-upload" style="font-size:1rem"></i>
              <span>File for <strong>Scenario B</strong></span>
              <span id="t2-b-fname" style="color:var(--blue-light);font-size:.72rem"></span>
            </div>
            <input class="form-control mt-2" id="t2-label-b" placeholder="Scenario B label" value="Scenario_B"/>
          </div>
        </div>
        <button class="btn-va-primary mt-3" id="t2-btn-load-two">
          <i class="bi bi-upload"></i> Upload &amp; Combine
        </button>
      </div>

      <div id="t2-src-alert" class="va-alert mt-2"></div>

      <hr class="va-divider" id="t2-config-divider" style="display:none">

      <!-- ── Filters ──────────────────────────────────────────────────── -->
      <div id="t2-config-section" style="display:none">
        <div class="va-section-label"><i class="bi bi-sliders"></i> Filters &amp; Configuration</div>

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

        <div class="row g-2 mb-3">
          <div class="col-md-2 col-6"><label class="form-label">🌍 Market</label><div class="va-multiselect" id="ms-markets"></div></div>
          <div class="col-md-2 col-6"><label class="form-label">🗺️ Region</label><div class="va-multiselect" id="ms-regions"></div></div>
          <div class="col-md-3 col-6"><label class="form-label">🏢 Division</label><div class="va-multiselect" id="ms-divisions"></div></div>
          <div class="col-md-3 col-6"><label class="form-label">🏛️ Entity</label><div class="va-multiselect" id="ms-entities"></div></div>
          <div class="col-md-2 col-6"><label class="form-label">🏷️ OH/LC</label><div class="va-multiselect" id="ms-lc-oh"></div></div>
        </div>

        <div class="row g-3 mb-3">
          <div class="col-md-8">
            <label class="form-label">🔀 Pivot Row Fields (hierarchy — top level first)</label>
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

        <button class="btn-va-primary" id="t2-btn-run">
          <i class="bi bi-play-fill"></i> Run Variance Analysis
        </button>
      </div>

      <hr class="va-divider" id="t2-results-divider" style="display:none">

      <!-- ── Results ──────────────────────────────────────────────────── -->
      <div id="t2-results" style="display:none">

        <!-- KPI cards -->
        <div class="row g-3 mb-3" id="t2-kpi-row"></div>

        <hr class="va-divider">

        <!-- Expandable Pivot Table -->
        <div class="va-section-label">
          <i class="bi bi-table"></i> Pivot Variance
          <span style="font-size:.65rem;font-weight:400;color:var(--text-muted);margin-left:8px">
            Click any group row to expand / collapse detail
          </span>
        </div>
        <div class="va-table-wrap mb-3">
          <div class="va-table-scroll" id="t2-pivot-wrap" style="max-height:520px"></div>
        </div>

        <hr class="va-divider">

        <!-- Top / Bottom 5 movers -->
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
      </div>

      <!-- Inline pivot expand/collapse styles -->
      <style>
        .piv-group-row { cursor:pointer; user-select:none; }
        .piv-group-row:hover td { background:#dde8f8 !important; }
        .piv-group-row td { background:#dde8f8; font-weight:700; }
        .piv-grand-row td { background:#1e3a5f !important; color:#e8edf8 !important; font-weight:700; }
        .piv-detail-row td { background:#fff; }
        .piv-detail-row:hover td { background:#f5f9ff; }
        .piv-expand-icon { margin-right:6px; font-size:.7rem; transition:transform .15s; }
        .piv-group-row.open .piv-expand-icon { transform: rotate(90deg); }
        .piv-subtotal-row td { background:#f0f5fd; font-style:italic; font-weight:600; }
      </style>
    `;
  }

  // ── INIT ──────────────────────────────────────────────────────────────
  function init() {
    if (initialised) return;
    initialised = true;
    document.getElementById('tab2-content').innerHTML = buildHTML();
    bindSrcMode();
    bindFileZones();
    bindPeriodRadio();
    document.getElementById('t2-btn-run').addEventListener('click', handleRun);
  }

  // ── SRC MODE ──────────────────────────────────────────────────────────
  function bindSrcMode() {
    const sel = document.getElementById('t2-src-mode');
    sel.addEventListener('change', () => {
      document.querySelectorAll('.t2-src-panel').forEach(p => p.style.display = 'none');
      document.getElementById(`t2-src-${sel.value}`).style.display = '';
    });

    // Load Tab 1
    document.getElementById('t2-btn-load-tab1').addEventListener('click', async () => {
      const btn = document.getElementById('t2-btn-load-tab1');
      btn.disabled = true;
      btn.innerHTML = vaSpinner('Loading…');
      try {
        const data = await vaPost('/api/tab2/load-tab1', {});
        onFiltersLoaded(data);
        vaToast('✅ Tab 1 data loaded — ' + data.rows.toLocaleString() + ' rows');
        vaAlertClear('t2-src-alert');
      } catch (e) {
        vaAlert('t2-src-alert',
          e.message.includes('404')
            ? '⚠️ No Tab 1 data found. Go to <strong>Tagetik Mapping</strong> tab first.'
            : 'Error: ' + e.message,
          'error');
      } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-link-45deg"></i> Load Tab 1 Data';
      }
    });

    // Master upload
    document.getElementById('t2-btn-load-master').addEventListener('click', async () => {
      const fi = document.getElementById('t2-file-master');
      if (!fi.files[0]) { vaAlert('t2-src-alert', 'Select a file first.', 'warning'); return; }
      const fd = new FormData(); fd.append('file', fi.files[0]);
      await doUpload('/api/tab2/upload', fd);
    });

    // Two files
    document.getElementById('t2-btn-load-two').addEventListener('click', async () => {
      const fa = document.getElementById('t2-file-a');
      const fb = document.getElementById('t2-file-b');
      if (!fa.files[0] || !fb.files[0]) { vaAlert('t2-src-alert','Select both files.','warning'); return; }
      const fd = new FormData();
      fd.append('file_a',  fa.files[0]);
      fd.append('file_b',  fb.files[0]);
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
      vaToast('✅ Loaded ' + data.rows.toLocaleString() + ' rows!');
    } catch (e) { vaAlert('t2-src-alert', e.message, 'error'); }
  }

  function bindFileZones() {
    [['t2-dropzone-master','t2-file-master','t2-master-fname'],
     ['t2-dropzone-a',     't2-file-a',     't2-a-fname'],
     ['t2-dropzone-b',     't2-file-b',     't2-b-fname']
    ].forEach(([zId, iId, lId]) => {
      const zone = document.getElementById(zId);
      const inp  = document.getElementById(iId);
      const lbl  = document.getElementById(lId);
      zone.addEventListener('click', () => inp.click());
      inp.addEventListener('change', () => { if (inp.files[0]) lbl.textContent = '📄 ' + inp.files[0].name; });
      zone.addEventListener('dragover',  e => { e.preventDefault(); zone.classList.add('drag-over'); });
      zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
      zone.addEventListener('drop', e => {
        e.preventDefault(); zone.classList.remove('drag-over');
        if (e.dataTransfer.files[0]) { inp.files = e.dataTransfer.files; lbl.textContent = '📄 ' + e.dataTransfer.files[0].name; }
      });
    });
  }

  function bindPeriodRadio() {
    document.querySelectorAll('input[name="t2-period-mode"]').forEach(r => {
      r.addEventListener('change', () => {
        document.getElementById('t2-month-select').style.display = r.value === 'mtd' ? '' : 'none';
      });
    });
  }

  // ── FILTER POPULATION ─────────────────────────────────────────────────
  function onFiltersLoaded(data) {
    filterData = data;
    document.getElementById('t2-config-divider').style.display  = '';
    document.getElementById('t2-config-section').style.display  = '';

    populateSelect('t2-sc-a', data.scenarios || [], 0);
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
      msWidgets['ms-groups'].setOptions(data.avail_group, (data.avail_group).slice(0, 3));
    }
  }

  function populateSelect(id, opts, defaultIdx = 0) {
    const sel = document.getElementById(id);
    sel.innerHTML = opts.map((o, i) =>
      `<option value="${o}" ${i === defaultIdx ? 'selected' : ''}>${o}</option>`
    ).join('');
  }

  // ── RUN ───────────────────────────────────────────────────────────────
  async function handleRun() {
    vaAlertClear('t2-run-alert');
    hideResults();

    const groups = msWidgets['ms-groups'] ? msWidgets['ms-groups'].checked() : [];
    if (!groups.length) { vaAlert('t2-run-alert','Select at least one Pivot Row Field.','warning'); return; }

    const periodMode = document.querySelector('input[name="t2-period-mode"]:checked').value;
    let sel_period;
    if (periodMode === 'ytd') {
      sel_period = (filterData && filterData.month_cols && filterData.month_cols.length)
        ? '__YTD_CALC__' : 'YTD';
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
      await delay(400); vaProgressClear('t2-run-progress');
      lastResult = data;
      renderResults(data);
      vaToast('✅ Variance analysis complete!');
    } catch (e) {
      vaProgressClear('t2-run-progress');
      vaAlert('t2-run-alert', e.message, 'error');
    } finally {
      btn.disabled = false;
      btn.innerHTML = '<i class="bi bi-play-fill"></i> Run Variance Analysis';
    }
  }

  // ── RENDER RESULTS ────────────────────────────────────────────────────
  function renderResults(data) {
    const scA    = data.scenario_a || 'Scenario A';
    const scB    = data.scenario_b || 'Scenario B';
    const favLow = data.favorable_is_lower;
    const varCol = data.col_variance_m   || 'Variance (M€)';
    const pctCol = data.col_variance_pct || 'Variance %';

    // KPI cards
    const varColor = (favLow && data.total_variance && data.total_variance.startsWith('-'))
                  || (!favLow && data.total_variance && !data.total_variance.startsWith('-'))
                   ? 'var(--green)' : 'var(--red)';

    document.getElementById('t2-kpi-row').innerHTML = `
      ${kpi(scA,                  data.total_a,        'M€')}
      ${kpi(scB,                  data.total_b,        'M€')}
      ${kpi('Net Variance (M€)',  `<span style="color:${varColor}">${data.total_variance}</span>`, data.pct_variance + ' vs B')}
      ${kpi('Max |Δ| (M€)',       data.max_variance,   data.rows + ' leaf rows')}
    `;

    // Expandable pivot table
    renderPivotTable(data, varCol, pctCol, scA, scB, favLow);

    // Top / Bottom 5
    const top5Cols = (data.group_fields || []).slice(0, 3).concat([scA, scB, varCol, pctCol]);
    renderMini('t2-top5-wrap', top5Cols, data.top5 || [], varCol, pctCol, favLow);
    renderMini('t2-bot5-wrap', top5Cols, data.bot5 || [], varCol, pctCol, favLow);
    document.getElementById('t2-top5-label').textContent = favLow ? 'Top 5 Favourable' : 'Top 5 Positive';
    document.getElementById('t2-bot5-label').textContent = favLow ? 'Top 5 Adverse'    : 'Top 5 Negative';

    document.getElementById('t2-results-divider').style.display = '';
    document.getElementById('t2-results').style.display         = '';
  }

  // ── EXPANDABLE PIVOT TABLE ────────────────────────────────────────────
  function renderPivotTable(data, varCol, pctCol, scA, scB, favLow) {
    const wrap       = document.getElementById('t2-pivot-wrap');
    const records    = data.records || [];
    const groups     = data.group_fields || [];

    if (!records.length) { wrap.innerHTML = '<p style="padding:16px;color:var(--text-muted)">No data.</p>'; return; }

    const numCols   = [scA, scB, varCol, pctCol];
    const dimCols   = groups;
    const allCols   = dimCols.concat(numCols);

    // ── Build aggregated groups ──────────────────────────────────────────
    // We show ONE level of grouping (first dim col) with totals
    // then expand to show each detail row under that group

    const firstDim   = dimCols[0] || '';
    const groupTotals = {}; // firstDim value → {scA, scB, varM, varPct}

    records.forEach(r => {
      const key = r[firstDim] ?? '(blank)';
      if (!groupTotals[key]) groupTotals[key] = { scA: 0, scB: 0, rows: [] };
      groupTotals[key].scA += (r[scA]  || 0);
      groupTotals[key].scB += (r[scB]  || 0);
      groupTotals[key].rows.push(r);
    });

    // Grand total
    const grandA   = records.reduce((s, r) => s + (r[scA] || 0), 0);
    const grandB   = records.reduce((s, r) => s + (r[scB] || 0), 0);
    const grandVar = grandA - grandB;
    const grandPct = grandB !== 0 ? ((grandVar / grandB) * 100).toFixed(2) : null;

    // ── Build HTML ──────────────────────────────────────────────────────
    const tbl = document.createElement('table');
    tbl.className = 'va-table';
    tbl.style.tableLayout = 'auto';

    // thead
    const thead = tbl.createTHead();
    const hrow  = thead.insertRow();
    allCols.forEach(c => {
      const th = document.createElement('th');
      th.textContent = c;
      th.className   = numCols.includes(c) ? '' : 'left';
      hrow.appendChild(th);
    });

    // tbody
    const tbody = tbl.createTBody();

    // Grand total row
    const gtr = tbody.insertRow();
    gtr.className = 'piv-grand-row';
    allCols.forEach((c, ci) => {
      const td = gtr.insertCell();
      if (c === firstDim) {
        td.textContent = 'GRAND TOTAL';
        td.colSpan = dimCols.length;
        td.className = 'left';
        // skip remaining dim cols
        return;
      }
      if (dimCols.indexOf(c) > 0 && dimCols.indexOf(c) < dimCols.length) {
        td.style.display = 'none'; return;
      }
      if (c === scA)     td.textContent = grandA.toFixed(2);
      else if (c === scB)    td.textContent = grandB.toFixed(2);
      else if (c === varCol) td.textContent = grandVar.toFixed(2);
      else if (c === pctCol) td.textContent = grandPct !== null ? grandPct : '–';
      td.style.textAlign = 'right';
      td.style.fontFamily = "'JetBrains Mono', monospace";
      if (c === varCol || c === pctCol) {
        const v = parseFloat(td.textContent);
        if (!isNaN(v)) td.className = favLow ? (v < 0 ? 'fav' : v > 0 ? 'adv' : '') : (v > 0 ? 'fav' : v < 0 ? 'adv' : '');
      }
    });

    // Group rows + detail rows
    Object.entries(groupTotals).forEach(([groupKey, gt]) => {
      const gVar   = gt.scA - gt.scB;
      const gPct   = gt.scB !== 0 ? ((gVar / gt.scB) * 100).toFixed(2) : null;
      const groupId = 'grp_' + groupKey.replace(/\W/g, '_');

      // Group header row (shows totals)
      const grpRow = tbody.insertRow();
      grpRow.className  = 'piv-group-row';
      grpRow.dataset.group = groupId;

      allCols.forEach((c, ci) => {
        if (dimCols.indexOf(c) > 0) return; // skip extra dim cols (colspan below)
        const td = grpRow.insertCell();
        if (c === firstDim) {
          td.colSpan   = dimCols.length;
          td.className = 'left';
          td.innerHTML = `<i class="bi bi-chevron-right piv-expand-icon"></i><strong>${esc(groupKey)}</strong>`;
        } else if (c === scA) {
          td.textContent = gt.scA.toFixed(2);
        } else if (c === scB) {
          td.textContent = gt.scB.toFixed(2);
        } else if (c === varCol) {
          td.textContent = gVar.toFixed(2);
        } else if (c === pctCol) {
          td.textContent = gPct !== null ? gPct : '–';
        }
        if (numCols.includes(c)) {
          td.style.textAlign  = 'right';
          td.style.fontFamily = "'JetBrains Mono', monospace";
        }
        if ((c === varCol || c === pctCol)) {
          const v = parseFloat(td.textContent);
          if (!isNaN(v)) td.className = favLow ? (v < 0 ? 'fav' : v > 0 ? 'adv' : '') : (v > 0 ? 'fav' : v < 0 ? 'adv' : '');
        }
      });

      // Detail rows (hidden by default)
      gt.rows.forEach(r => {
        const dr = tbody.insertRow();
        dr.className        = 'piv-detail-row';
        dr.dataset.parent   = groupId;
        dr.style.display    = 'none'; // collapsed by default

        allCols.forEach(c => {
          const td = dr.insertCell();
          const v  = r[c];
          if (dimCols.includes(c)) {
            td.textContent = v != null ? v : '–';
            td.className   = 'left';
            td.style.paddingLeft = c === firstDim ? '28px' : '';
          } else {
            td.textContent      = v != null ? v : '–';
            td.style.textAlign  = 'right';
            td.style.fontFamily = "'JetBrains Mono', monospace";
            if (c === varCol || c === pctCol) {
              const n = parseFloat(v);
              if (!isNaN(n)) td.className = favLow ? (n < 0 ? 'fav' : n > 0 ? 'adv' : 'neut') : (n > 0 ? 'fav' : n < 0 ? 'adv' : 'neut');
            }
          }
        });
      });

      // Expand / collapse click
      grpRow.addEventListener('click', () => {
        const isOpen = grpRow.classList.toggle('open');
        tbody.querySelectorAll(`tr[data-parent="${groupId}"]`).forEach(dr => {
          dr.style.display = isOpen ? '' : 'none';
        });
      });
    });

    wrap.innerHTML = '';
    wrap.appendChild(tbl);
  }

  // ── MINI TABLE (top/bottom 5) ─────────────────────────────────────────
  function renderMini(wrapperId, cols, records, varCol, pctCol, favLow) {
    const wrap = document.getElementById(wrapperId);
    wrap.innerHTML = '';
    if (!records.length) { wrap.textContent = 'No data'; return; }
    const safe = cols.filter(c => records[0] && c in records[0]);
    const tbl  = vaBuildTable(safe, records, {
      rightAlign: safe.filter(c => [varCol, pctCol].some(k => c === k) || safe.indexOf(c) >= safe.length - 4),
      favCols:    [varCol, pctCol],
      favLower:   favLow,
    });
    wrap.appendChild(tbl);
  }

  function hideResults() {
    document.getElementById('t2-results-divider').style.display = 'none';
    document.getElementById('t2-results').style.display         = 'none';
  }

  // ── HELPERS ───────────────────────────────────────────────────────────
  function kpi(label, value, sub) {
    return `<div class="col-md-3 col-6"><div class="metric-card">
      <div class="metric-label">${label}</div>
      <div class="metric-value">${value}</div>
      <div class="metric-sub">${sub}</div>
    </div></div>`;
  }

  function esc(s) {
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  function delay(ms) { return new Promise(r => setTimeout(r, ms)); }

  window.addEventListener('va:tabchange', e => { if (e.detail === 'tab2') init(); });
})();
