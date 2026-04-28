/**
 * tab6.js — Comment Search
 * GET  /api/tab6/filters  → populate filter dropdowns
 * POST /api/tab6/search   → render results table
 * GET  /api/tab6/download/csv|xlsx
 */
(function () {
  'use strict';
  let initialised = false;
  let msWidgets   = {};   // { Category, Scenarios, Functions, ... }
  let filterCols  = [];

  function buildHTML() {
    return `
      <div class="va-section-label"><i class="bi bi-search"></i> Commentary Search Engine</div>
      <p style="font-size:.82rem;color:var(--text-muted);margin-bottom:16px">
        Search the master commentary database using column filters and free-text keyword search.
      </p>

      <!-- Search bar + Reset -->
      <div class="d-flex gap-2 mb-3">
        <input class="form-control" id="t6-search-text"
          placeholder="Search inside Comments…" style="max-width:480px" />
        <button class="btn-va-outline" id="t6-btn-reset">
          <i class="bi bi-arrow-counterclockwise"></i> Reset
        </button>
      </div>

      <!-- Filter grid — populated dynamically -->
      <div id="t6-alert" class="va-alert mb-2"></div>
      <div id="t6-filter-loading" style="font-size:.8rem;color:var(--text-muted)">
        <span class="va-spinner"></span> Loading filters…
      </div>

      <div class="row g-2 mb-3" id="t6-filter-row" style="display:none"></div>

      <!-- Search button -->
      <div class="d-flex gap-2 mb-3" id="t6-search-btn-wrap" style="display:none !important">
        <button class="btn-va-primary" id="t6-btn-search">
          <i class="bi bi-search"></i> Search
        </button>
      </div>

      <div id="t6-progress" class="mb-2"></div>

      <!-- Results -->
      <div id="t6-results" style="display:none">
        <div class="va-section-label">
          <i class="bi bi-table"></i>
          Results — <span id="t6-count">0</span> row(s)
        </div>

        <div class="va-table-wrap mb-3">
          <div class="va-table-scroll" id="t6-table-wrap" style="max-height:480px"></div>
        </div>

        <!-- Downloads -->
        <div class="va-section-label"><i class="bi bi-download"></i> Download</div>
        <div class="d-flex gap-2">
          <a href="/api/tab6/download/csv"
             class="btn-va-success text-decoration-none" id="t6-dl-csv">
            <i class="bi bi-filetype-csv"></i> Download CSV
          </a>
          <a href="/api/tab6/download/xlsx"
             class="btn-va-success text-decoration-none" id="t6-dl-xlsx">
            <i class="bi bi-file-earmark-excel"></i> Download Excel
          </a>
        </div>
      </div>
    `;
  }

  function init() {
    if (initialised) return;
    initialised = true;
    document.getElementById('tab6-content').innerHTML = buildHTML();
    loadFilters();
    bindEvents();
  }

  /* ── Load filter options from API ───────────────────────────────────── */
  async function loadFilters() {
    try {
      const data = await vaGet('/api/tab6/filters');
      filterCols  = data.filter_cols || [];
      renderFilterGrid(data.options || {});
      document.getElementById('t6-filter-loading').style.display = 'none';
      document.getElementById('t6-filter-row').style.display      = '';
      document.getElementById('t6-search-btn-wrap').style.cssText = '';
    } catch (e) {
      document.getElementById('t6-filter-loading').style.display = 'none';
      vaAlert('t6-alert',
        `Could not load master database: ${e.message}. Use the PPT Upload tab to create it first.`,
        'warning');
    }
  }

  function renderFilterGrid(options) {
    const row = document.getElementById('t6-filter-row');
    row.innerHTML = '';
    msWidgets = {};

    filterCols.forEach(col => {
      const vals = options[col] || [];
      const colDiv = document.createElement('div');
      colDiv.className = 'col-md-3 col-6';
      colDiv.innerHTML = `
        <label class="form-label">${col}</label>
        <div class="va-multiselect" id="ms6-${col.replace(/\W/g,'_')}"></div>
      `;
      row.appendChild(colDiv);

      const container = colDiv.querySelector('.va-multiselect');
      const ms = new VaMultiselect(container, vals, `All ${col}`);
      // Auto-search on every change
      ms.dropdown.addEventListener('change', debounce(handleSearch, 400));
      msWidgets[col] = ms;
    });
  }

  /* ── Events ─────────────────────────────────────────────────────────── */
  function bindEvents() {
    document.getElementById('t6-btn-search').addEventListener('click', handleSearch);
    document.getElementById('t6-search-text').addEventListener(
      'input', debounce(handleSearch, 500)
    );
    document.getElementById('t6-btn-reset').addEventListener('click', handleReset);
  }

  async function handleSearch() {
    vaAlertClear('t6-alert');
    vaProgress('t6-progress', 40, 'Searching…');

    const filters = {};
    filterCols.forEach(col => {
      if (msWidgets[col]) {
        const checked = msWidgets[col].checked();
        if (checked.length) filters[col] = checked;
      }
    });

    const body = {
      search_text: document.getElementById('t6-search-text').value.trim(),
      filters,
    };

    try {
      const data = await vaPost('/api/tab6/search', body);
      vaProgress('t6-progress', 100, 'Done');
      setTimeout(() => vaProgressClear('t6-progress'), 400);
      renderResults(data);
    } catch (e) {
      vaProgressClear('t6-progress');
      vaAlert('t6-alert', e.message, 'error');
    }
  }

  function handleReset() {
    Object.values(msWidgets).forEach(ms => ms.clearAll());
    document.getElementById('t6-search-text').value = '';
    document.getElementById('t6-results').style.display = 'none';
    vaAlertClear('t6-alert');
  }

  /* ── Render results ─────────────────────────────────────────────────── */
  function renderResults(data) {
    document.getElementById('t6-count').textContent = (data.count || 0).toLocaleString();

    const wrap = document.getElementById('t6-table-wrap');
    wrap.innerHTML = '';

    if (!data.records || !data.records.length) {
      wrap.innerHTML = '<p style="padding:16px;color:var(--text-muted)">No matching records.</p>';
    } else {
      // Limit display to first 500 rows for performance
      const shown = data.records.slice(0, 500);
      const table = vaBuildTable(data.columns || [], shown);
      wrap.appendChild(table);
      if (data.count > 500) {
        const note = document.createElement('p');
        note.style.cssText = 'font-size:.72rem;color:var(--text-muted);padding:8px 14px';
        note.textContent = `Showing first 500 of ${data.count.toLocaleString()} rows. Download for full data.`;
        wrap.appendChild(note);
      }
    }

    document.getElementById('t6-results').style.display = '';
  }

  /* ── Util ───────────────────────────────────────────────────────────── */
  function debounce(fn, ms) {
    let t;
    return function (...args) { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
  }

  window.addEventListener('va:tabchange', e => { if (e.detail === 'tab6') init(); });
})();
