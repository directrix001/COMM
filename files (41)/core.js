/**
 * core.js — shared utilities
 * Tab switching · Toast · Multiselect · API helpers
 */

/* ── TAB SWITCHING ──────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  const tabs    = document.querySelectorAll('.va-tab');
  const panels  = document.querySelectorAll('.va-panel');

  function activateTab(id) {
    tabs.forEach(t => t.classList.toggle('active', t.dataset.tab === id));
    panels.forEach(p => p.classList.toggle('active', p.id === id));
    // Notify each tab module
    window.dispatchEvent(new CustomEvent('va:tabchange', { detail: id }));
  }

  tabs.forEach(t => t.addEventListener('click', () => activateTab(t.dataset.tab)));

  // Initialise tab 1 on first load
  activateTab('tab1');
});


/* ── TOAST ──────────────────────────────────────────────────────────────── */
function vaToast(msg, type = 'success') {
  const el   = document.getElementById('va-toast');
  const body = document.getElementById('va-toast-body');
  body.textContent = msg;
  el.className = `toast align-items-center border-0 text-bg-${type}`;
  const bsToast = bootstrap.Toast.getOrCreateInstance(el, { delay: 3500 });
  bsToast.show();
}


/* ── ALERT HELPER ───────────────────────────────────────────────────────── */
function vaAlert(containerId, msg, type = 'info') {
  const el = document.getElementById(containerId);
  if (!el) return;
  el.className = `va-alert va-alert-${type} show`;
  el.innerHTML = `<i class="bi bi-info-circle-fill"></i><span>${msg}</span>`;
}
function vaAlertClear(containerId) {
  const el = document.getElementById(containerId);
  if (el) el.className = 'va-alert';
}


/* ── PROGRESS ───────────────────────────────────────────────────────────── */
function vaProgress(containerId, pct, label = '') {
  let wrap = document.getElementById(containerId);
  if (!wrap) return;
  wrap.innerHTML = `
    <div class="d-flex justify-content-between mb-1">
      <small class="text-muted">${label}</small>
      <small class="text-muted">${pct}%</small>
    </div>
    <div class="va-progress">
      <div class="va-progress-bar" style="width:${pct}%"></div>
    </div>`;
}
function vaProgressClear(containerId) {
  const el = document.getElementById(containerId);
  if (el) el.innerHTML = '';
}


/* ── SPINNER HTML ───────────────────────────────────────────────────────── */
function vaSpinner(label = 'Processing…') {
  return `<span class="va-spinner"></span>${label}`;
}


/* ── MULTISELECT ────────────────────────────────────────────────────────── */
class VaMultiselect {
  /**
   * @param {HTMLElement} container  – .va-multiselect wrapper
   * @param {string[]}    options
   * @param {string}      placeholder
   */
  constructor(container, options = [], placeholder = 'Select…') {
    this.container   = container;
    this.options     = [];
    this.placeholder = placeholder;

    this.btn = document.createElement('button');
    this.btn.type = 'button';
    this.btn.className = 'va-multiselect-btn';
    this.btn.textContent = placeholder;

    this.dropdown = document.createElement('div');
    this.dropdown.className = 'va-multiselect-dropdown';

    container.appendChild(this.btn);
    container.appendChild(this.dropdown);

    this.btn.addEventListener('click', e => {
      e.stopPropagation();
      this.dropdown.classList.toggle('open');
    });
    document.addEventListener('click', () => this.dropdown.classList.remove('open'));

    if (options.length) this.setOptions(options);
  }

  setOptions(opts, keepChecked = []) {
    this.options = opts;
    this.dropdown.innerHTML = '';
    opts.forEach(opt => {
      const row   = document.createElement('label');
      row.className = 'va-ms-item';
      const cb    = document.createElement('input');
      cb.type     = 'checkbox';
      cb.value    = opt;
      cb.checked  = keepChecked.includes(opt);
      cb.addEventListener('change', () => this._updateBtn());
      row.appendChild(cb);
      row.appendChild(document.createTextNode(opt));
      this.dropdown.appendChild(row);
    });
    this._updateBtn();
  }

  checked() {
    return [...this.dropdown.querySelectorAll('input:checked')].map(i => i.value);
  }

  clearAll() {
    this.dropdown.querySelectorAll('input').forEach(i => i.checked = false);
    this._updateBtn();
  }

  _updateBtn() {
    const sel = this.checked();
    this.btn.textContent = sel.length ? sel.join(', ') : this.placeholder;
  }
}


/* ── API FETCH HELPERS ──────────────────────────────────────────────────── */
async function vaPost(url, body, opts = {}) {
  const res  = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    ...opts,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

async function vaPostForm(url, formData) {
  const res = await fetch(url, { method: 'POST', body: formData });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

async function vaGet(url) {
  const res = await fetch(url);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}


/* ── TABLE BUILDER ──────────────────────────────────────────────────────── */
/**
 * Build a <table class="va-table"> from records.
 * @param {string[]} columns
 * @param {object[]} records
 * @param {object}   opts  { rightAlign: string[], favCols: string[], favLower: bool }
 */
function vaBuildTable(columns, records, opts = {}) {
  const { rightAlign = [], favCols = [], favLower = true } = opts;

  const table = document.createElement('table');
  table.className = 'va-table';

  // thead
  const thead = document.createElement('thead');
  const tr    = document.createElement('tr');
  columns.forEach(c => {
    const th = document.createElement('th');
    th.textContent = c;
    if (!rightAlign.includes(c)) th.classList.add('left');
    tr.appendChild(th);
  });
  thead.appendChild(tr);
  table.appendChild(thead);

  // tbody
  const tbody = document.createElement('tbody');
  records.forEach(row => {
    const tr2 = document.createElement('tr');
    columns.forEach(c => {
      const td  = document.createElement('td');
      const val = row[c];
      td.textContent = val == null ? '–' : val;
      if (!rightAlign.includes(c)) td.classList.add('left');
      if (favCols.includes(c) && val != null) {
        const n = parseFloat(val);
        if (!isNaN(n)) {
          td.classList.add(
            favLower ? (n < 0 ? 'fav' : n > 0 ? 'adv' : 'neut')
                     : (n > 0 ? 'fav' : n < 0 ? 'adv' : 'neut')
          );
        }
      }
      tr2.appendChild(td);
    });
    tbody.appendChild(tr2);
  });
  table.appendChild(tbody);
  return table;
}

/* expose globally */
window.VaMultiselect = VaMultiselect;
window.vaToast       = vaToast;
window.vaAlert       = vaAlert;
window.vaAlertClear  = vaAlertClear;
window.vaProgress    = vaProgress;
window.vaProgressClear = vaProgressClear;
window.vaSpinner     = vaSpinner;
window.vaPost        = vaPost;
window.vaPostForm    = vaPostForm;
window.vaGet         = vaGet;
window.vaBuildTable  = vaBuildTable;
