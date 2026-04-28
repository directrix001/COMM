/**
 * tab7.js — PPT Upload & Master Database Push
 * POST /api/tab7/upload   → extract PPT → preview editable table
 * POST /api/tab7/push     → push to master DB
 * GET  /api/tab7/download → download edited Excel
 * GET  /api/tab7/master   → preview master DB
 */
(function () {
  'use strict';
  let initialised  = false;
  let extractedCols    = [];
  let extractedRecords = [];

  function buildHTML() {
    return `
      <div class="va-section-label"><i class="bi bi-upload"></i> PPT Upload &amp; Master Database Push</div>
      <p style="font-size:.82rem;color:var(--text-muted);margin-bottom:16px">
        Upload the current month SVP PowerPoint deck. Comments are extracted, enriched with
        metadata (category, region, criteria…) and ready to push to the master database.
      </p>

      <!-- Upload zone -->
      <div class="upload-zone" id="t7-dropzone">
        <input type="file" id="t7-file-input" accept=".pptx,.ppt" />
        <i class="bi bi-file-earmark-ppt"></i>
        <p><strong>Drag &amp; drop</strong> your PowerPoint file here</p>
        <p>or <strong id="t7-browse-link" style="color:var(--blue);cursor:pointer">browse to upload</strong></p>
        <p class="mt-2" style="font-size:.72rem;color:var(--blue-light)" id="t7-file-name"></p>
      </div>

      <div id="t7-alert" class="va-alert mt-3"></div>
      <div id="t7-progress" class="mt-3"></div>

      <div class="mt-3">
        <button class="btn-va-primary" id="t7-btn-extract">
          <i class="bi bi-magic"></i> Extract from PPT
        </button>
      </div>

      <!-- Extracted preview + actions -->
      <div id="t7-extracted-section" style="display:none">
        <hr class="va-divider">
        <div class="va-section-label"><i class="bi bi-pencil-square"></i> Review &amp; Edit Extracted Data</div>

        <div class="mb-2" style="font-size:.78rem;color:var(--text-muted)" id="t7-extracted-meta"></div>

        <!-- Editable table -->
        <div class="va-table-wrap mb-3">
          <div class="va-table-scroll" id="t7-table-wrap" style="max-height:440px"></div>
        </div>

        <!-- Action buttons -->
        <div class="d-flex gap-2 flex-wrap">
          <button class="btn-va-primary" id="t7-btn-push">
            <i class="bi bi-cloud-upload"></i> Push to Master Database
          </button>
          <a href="/api/tab7/download" class="btn-va-success text-decoration-none" id="t7-dl-btn">
            <i class="bi bi-file-earmark-excel"></i> Download Edited File (.xlsx)
          </a>
        </div>

        <div id="t7-push-alert" class="va-alert mt-3"></div>
      </div>

      <!-- Master DB preview -->
      <div id="t7-master-section" style="display:none">
        <hr class="va-divider">
        <div class="va-section-label"><i class="bi bi-database-check"></i> Current Master Database</div>
        <div class="mb-2" style="font-size:.78rem;color:var(--text-muted)" id="t7-master-meta"></div>
        <div class="va-table-wrap">
          <div class="va-table-scroll" id="t7-master-wrap" style="max-height:320px"></div>
        </div>
      </div>
    `;
  }

  function init() {
    if (initialised) return;
    initialised = true;
    document.getElementById('tab7-content').innerHTML = buildHTML();
    bindEvents();
    loadMasterPreview();
  }

  /* ── Events ─────────────────────────────────────────────────────────── */
  function bindEvents() {
    const dropzone  = document.getElementById('t7-dropzone');
    const fileInput = document.getElementById('t7-file-input');
    const browse    = document.getElementById('t7-browse-link');

    browse.addEventListener('click',  () => fileInput.click());
    dropzone.addEventListener('click',() => fileInput.click());

    fileInput.addEventListener('change', () => {
      if (fileInput.files[0]) setFileName(fileInput.files[0].name);
    });

    dropzone.addEventListener('dragover', e => { e.preventDefault(); dropzone.classList.add('drag-over'); });
    dropzone.addEventListener('dragleave',() => dropzone.classList.remove('drag-over'));
    dropzone.addEventListener('drop', e => {
      e.preventDefault(); dropzone.classList.remove('drag-over');
      if (e.dataTransfer.files[0]) {
        fileInput.files = e.dataTransfer.files;
        setFileName(e.dataTransfer.files[0].name);
      }
    });

    document.getElementById('t7-btn-extract').addEventListener('click', handleExtract);
    document.getElementById('t7-btn-push').addEventListener('click',    handlePush);
  }

  function setFileName(name) {
    document.getElementById('t7-file-name').textContent = `📄 ${name}`;
  }

  /* ── Extract PPT ────────────────────────────────────────────────────── */
  async function handleExtract() {
    const fileInput = document.getElementById('t7-file-input');
    if (!fileInput.files || !fileInput.files[0]) {
      vaAlert('t7-alert', 'Please select a PowerPoint file first.', 'warning');
      return;
    }

    vaAlertClear('t7-alert');
    document.getElementById('t7-extracted-section').style.display = 'none';

    const btn = document.getElementById('t7-btn-extract');
    btn.disabled = true;
    btn.innerHTML = vaSpinner('Extracting…');
    vaProgress('t7-progress', 20, 'Reading slides…');

    try {
      const fd = new FormData();
      fd.append('file', fileInput.files[0]);

      await delay(300);
      vaProgress('t7-progress', 55, 'Enriching metadata…');

      const data = await vaPostForm('/api/tab7/upload', fd);

      vaProgress('t7-progress', 100, 'Done ✓');
      await delay(400);
      vaProgressClear('t7-progress');

      extractedCols    = data.columns  || [];
      extractedRecords = data.records  || [];

      renderExtracted(data);
      vaToast(`✅ Extracted ${data.rows} rows from ${fileInput.files[0].name}`);

    } catch (e) {
      vaProgressClear('t7-progress');
      vaAlert('t7-alert', `Extraction failed: ${e.message}`, 'error');
    } finally {
      btn.disabled = false;
      btn.innerHTML = '<i class="bi bi-magic"></i> Extract from PPT';
    }
  }

  function renderExtracted(data) {
    document.getElementById('t7-extracted-meta').textContent =
      `${data.rows} rows extracted — review and edit below before pushing.`;

    const wrap = document.getElementById('t7-table-wrap');
    wrap.innerHTML = '';

    if (data.records && data.records.length) {
      const table = buildEditableTable(data.columns, data.records);
      wrap.appendChild(table);
    }

    document.getElementById('t7-extracted-section').style.display = '';
  }

  /* ── Build editable HTML table ──────────────────────────────────────── */
  function buildEditableTable(columns, records) {
    const table = document.createElement('table');
    table.className = 'va-table';
    table.id = 't7-edit-table';

    // thead
    const thead = document.createElement('thead');
    const hrow  = document.createElement('tr');
    columns.forEach(c => {
      const th = document.createElement('th');
      th.textContent = c;
      th.className   = 'left';
      hrow.appendChild(th);
    });
    thead.appendChild(hrow);
    table.appendChild(thead);

    // tbody — contenteditable cells
    const tbody = document.createElement('tbody');
    records.forEach((row, ri) => {
      const tr = document.createElement('tr');
      tr.dataset.rowIndex = ri;
      columns.forEach(col => {
        const td = document.createElement('td');
        td.className     = 'left';
        td.contentEditable = 'true';
        td.style.minWidth  = '100px';
        td.style.outline   = 'none';
        td.textContent   = row[col] == null ? '' : row[col];
        td.addEventListener('focus', () => td.style.background = '#eff5ff');
        td.addEventListener('blur',  () => {
          td.style.background = '';
          // Sync back to extractedRecords
          extractedRecords[ri][col] = td.textContent;
        });
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    return table;
  }

  /* ── Push to master ─────────────────────────────────────────────────── */
  async function handlePush() {
    vaAlertClear('t7-push-alert');
    const btn = document.getElementById('t7-btn-push');
    btn.disabled = true;
    btn.innerHTML = vaSpinner('Pushing…');

    try {
      const data = await vaPost('/api/tab7/push', {});
      vaAlert('t7-push-alert',
        `✅ Pushed ${data.pushed_rows} rows. Master database now has ${data.master_rows} rows.`,
        'success');
      vaToast('Master database updated!');
      loadMasterPreview();
    } catch (e) {
      vaAlert('t7-push-alert', `Push failed: ${e.message}`, 'error');
    } finally {
      btn.disabled = false;
      btn.innerHTML = '<i class="bi bi-cloud-upload"></i> Push to Master Database';
    }
  }

  /* ── Master DB preview ──────────────────────────────────────────────── */
  async function loadMasterPreview() {
    try {
      const data = await vaGet('/api/tab7/master');
      if (!data.total) return;

      document.getElementById('t7-master-meta').textContent =
        `${data.total.toLocaleString()} total rows in master database (showing first 100)`;

      const wrap = document.getElementById('t7-master-wrap');
      wrap.innerHTML = '';
      if (data.records && data.records.length) {
        wrap.appendChild(vaBuildTable(data.columns, data.records));
      }
      document.getElementById('t7-master-section').style.display = '';
    } catch (_) {
      // Master DB doesn't exist yet — silently skip
    }
  }

  /* ── Util ───────────────────────────────────────────────────────────── */
  function delay(ms) { return new Promise(r => setTimeout(r, ms)); }

  window.addEventListener('va:tabchange', e => { if (e.detail === 'tab7') init(); });
})();
