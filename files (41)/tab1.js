/**
 * tab1.js — Tagetik Mapping tab
 *
 * Flow:
 *  1. Render HTML into #tab1-content on first activation
 *  2. User drags/selects an Excel file → upload zone updates
 *  3. "Generate Mapping" → POST /api/tab1/upload (multipart)
 *     → progress bar animates → preview table rendered
 *  4. Download CSV / Excel buttons hit GET endpoints
 */

(function () {
  'use strict';

  let initialised = false;

  /* ── HTML TEMPLATE ──────────────────────────────────────────────────── */
  function buildHTML() {
    return `
      <!-- Section label -->
      <div class="va-section-label"><i class="bi bi-folder2-open"></i> Upload Monthly Excel</div>

      <!-- Upload zone -->
      <div class="upload-zone" id="t1-dropzone">
        <input type="file" id="t1-file-input" accept=".xlsx,.xls" />
        <i class="bi bi-cloud-upload"></i>
        <p><strong>Drag & drop</strong> your monthly Excel file here</p>
        <p>or <strong id="t1-browse-link" style="color:var(--blue);cursor:pointer;">browse to upload</strong></p>
        <p class="mt-2" style="font-size:.72rem;" id="t1-file-name"></p>
      </div>

      <!-- Alert -->
      <div id="t1-alert" class="va-alert mt-3"></div>

      <!-- Progress -->
      <div id="t1-progress" class="mt-3"></div>

      <!-- Action button -->
      <div class="mt-3 d-flex gap-2">
        <button class="btn-va-primary" id="t1-btn-generate">
          <i class="bi bi-gear"></i> Generate Mapping
        </button>
      </div>

      <hr class="va-divider" id="t1-results-divider" style="display:none">

      <!-- Results section -->
      <div id="t1-results" style="display:none">

        <!-- Stats row -->
        <div class="row g-3 mb-3" id="t1-stats-row"></div>

        <!-- Warnings -->
        <div id="t1-warnings"></div>

        <!-- Preview label -->
        <div class="va-section-label mt-3"><i class="bi bi-table"></i> Preview — top 100 rows</div>

        <!-- Preview table -->
        <div class="va-table-wrap mb-3">
          <div class="va-table-scroll" id="t1-table-wrap"></div>
        </div>

        <!-- Downloads -->
        <div class="va-section-label"><i class="bi bi-download"></i> Download</div>
        <div class="d-flex gap-2">
          <a id="t1-dl-csv"  href="/api/tab1/download/csv"
             class="btn-va-success text-decoration-none" style="display:none">
            <i class="bi bi-filetype-csv"></i> Download CSV
          </a>
          <a id="t1-dl-xlsx" href="/api/tab1/download/xlsx"
             class="btn-va-success text-decoration-none" style="display:none">
            <i class="bi bi-file-earmark-excel"></i> Download Excel
          </a>
        </div>
      </div>
    `;
  }

  /* ── INIT ───────────────────────────────────────────────────────────── */
  function init() {
    if (initialised) return;
    initialised = true;

    document.getElementById('tab1-content').innerHTML = buildHTML();
    bindEvents();
  }

  /* ── EVENT BINDING ──────────────────────────────────────────────────── */
  function bindEvents() {
    const dropzone   = document.getElementById('t1-dropzone');
    const fileInput  = document.getElementById('t1-file-input');
    const browseLink = document.getElementById('t1-browse-link');
    const btnGenerate= document.getElementById('t1-btn-generate');

    // Browse
    browseLink.addEventListener('click', () => fileInput.click());
    dropzone.addEventListener('click', () => fileInput.click());

    // File selected
    fileInput.addEventListener('change', () => {
      if (fileInput.files[0]) setFileName(fileInput.files[0].name);
    });

    // Drag & drop
    dropzone.addEventListener('dragover', e => { e.preventDefault(); dropzone.classList.add('drag-over'); });
    dropzone.addEventListener('dragleave', () => dropzone.classList.remove('drag-over'));
    dropzone.addEventListener('drop', e => {
      e.preventDefault();
      dropzone.classList.remove('drag-over');
      const f = e.dataTransfer.files[0];
      if (f) { fileInput.files = e.dataTransfer.files; setFileName(f.name); }
    });

    // Generate button
    btnGenerate.addEventListener('click', handleGenerate);
  }

  function setFileName(name) {
    document.getElementById('t1-file-name').textContent = `📄 ${name}`;
  }

  /* ── GENERATE HANDLER ───────────────────────────────────────────────── */
  async function handleGenerate() {
    const fileInput = document.getElementById('t1-file-input');
    if (!fileInput.files || !fileInput.files[0]) {
      vaAlert('t1-alert', 'Please select a file first.', 'warning');
      return;
    }

    vaAlertClear('t1-alert');
    hideResults();

    const btn = document.getElementById('t1-btn-generate');
    btn.disabled = true;
    btn.innerHTML = vaSpinner('Generating…');

    // Animate progress
    vaProgress('t1-progress', 10, 'Reading Excel file…');

    try {
      const formData = new FormData();
      formData.append('file', fileInput.files[0]);

      await delay(300);
      vaProgress('t1-progress', 30, 'Normalising headers…');
      await delay(200);
      vaProgress('t1-progress', 55, 'Computing MTD / YTD…');
      await delay(200);
      vaProgress('t1-progress', 75, 'Merging mapping file…');

      const data = await vaPostForm('/api/tab1/upload', formData);

      vaProgress('t1-progress', 100, 'Done ✓');
      await delay(500);
      vaProgressClear('t1-progress');

      renderResults(data);
      vaToast('✅ Mapping generated successfully!', 'success');

    } catch (err) {
      vaProgressClear('t1-progress');
      vaAlert('t1-alert', `Error: ${err.message}`, 'error');
    } finally {
      btn.disabled = false;
      btn.innerHTML = '<i class="bi bi-gear"></i> Generate Mapping';
    }
  }

  /* ── RENDER RESULTS ─────────────────────────────────────────────────── */
  function renderResults(data) {
    // Stats row
    const statsRow = document.getElementById('t1-stats-row');
    statsRow.innerHTML = `
      ${metricCard('Total Rows',    data.rows.toLocaleString(),  'Mapped records')}
      ${metricCard('Total Columns', data.columns.length,         'Output columns')}
      ${metricCard('Status',        '✅ Ready',                  'Mapping complete')}
    `;

    // Warnings
    const warnDiv = document.getElementById('t1-warnings');
    warnDiv.innerHTML = (data.warnings || [])
      .map(w => `<div class="va-alert va-alert-warning show mb-2"><i class="bi bi-exclamation-triangle-fill"></i><span>${w}</span></div>`)
      .join('');

    // Preview table
    const wrap  = document.getElementById('t1-table-wrap');
    wrap.innerHTML = '';
    if (data.preview && data.preview.length) {
      const table = vaBuildTable(data.columns, data.preview);
      wrap.appendChild(table);
    }

    // Show download buttons
    document.getElementById('t1-dl-csv').style.display  = '';
    document.getElementById('t1-dl-xlsx').style.display = '';

    // Show results section
    document.getElementById('t1-results-divider').style.display = '';
    document.getElementById('t1-results').style.display = '';
  }

  function hideResults() {
    document.getElementById('t1-results-divider').style.display = 'none';
    document.getElementById('t1-results').style.display         = 'none';
    document.getElementById('t1-dl-csv').style.display          = 'none';
    document.getElementById('t1-dl-xlsx').style.display         = 'none';
  }

  function metricCard(label, value, sub) {
    return `
      <div class="col-md-3 col-6">
        <div class="metric-card">
          <div class="metric-label">${label}</div>
          <div class="metric-value">${value}</div>
          <div class="metric-sub">${sub}</div>
        </div>
      </div>`;
  }

  /* ── UTIL ───────────────────────────────────────────────────────────── */
  function delay(ms) { return new Promise(r => setTimeout(r, ms)); }

  /* ── ACTIVATE on tab switch ─────────────────────────────────────────── */
  window.addEventListener('va:tabchange', e => {
    if (e.detail === 'tab1') init();
  });

  // Also init immediately in case tab1 is the default active tab
  window.addEventListener('DOMContentLoaded', init);

})();
