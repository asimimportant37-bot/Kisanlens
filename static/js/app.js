/* KisanLens front-end. No framework; all user/server text is inserted with textContent. */
(function () {
  'use strict';

  const LANG_KEY = 'kisanlens-lang';
  const RESULT_KEY = 'kisanlens:lastResult';
  const MAX_BYTES = 8 * 1024 * 1024;
  const OK_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
  const OK_EXT = /\.(jpe?g|png|webp)$/i;

  let dict = {};
  let lang = 'en';
  try { lang = localStorage.getItem(LANG_KEY) || 'en'; } catch (e) { /* storage blocked */ }

  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));

  /* ------------------------------------------------------------ helpers */
  function h(tag, attrs, ...kids) {
    const el = document.createElement(tag);
    Object.entries(attrs || {}).forEach(([k, v]) => {
      if (k === 'class') el.className = v;
      else if (k === 'text') el.textContent = v;
      else if (v !== null && v !== undefined) el.setAttribute(k, v);
    });
    kids.flat().forEach((k) => { if (k) el.append(k); });
    return el;
  }
  const has = (key) => !!((dict[lang] && dict[lang][key]) || (dict.en && dict.en[key]));
  function t(key, vars) {
    let v = (dict[lang] && dict[lang][key]) || (dict.en && dict.en[key]) || key;
    if (vars) v = v.replace(/\{(\w+)\}/g, (m, k) => (vars[k] !== undefined ? vars[k] : m));
    return v;
  }
  const loc = (obj) => (obj && (obj[lang] || obj.en)) || '';
  const pct = (x) => (x * 100).toFixed(1) + '%';

  async function api(path, opts) {
    const options = Object.assign({ credentials: 'same-origin' }, opts || {});
    options.headers = Object.assign({ 'X-Requested-With': 'KisanLens' }, options.headers || {});
    let res;
    try { res = await fetch(path, options); } catch (e) { throw { code: 'network' }; }
    let data = null;
    try { data = await res.json(); } catch (e) { /* non-JSON */ }
    if (!res.ok || !data || !data.ok) {
      const err = (data && data.error) || {};
      throw { code: err.code || 'server_error', message: err.message, status: res.status };
    }
    return data;
  }
  function errText(err) {
    const key = 'err.' + (err && err.code);
    if (has(key)) return t(key);
    return t('err.generic');
  }

  /* --------------------------------------------------------------- i18n */
  async function loadDict() {
    try {
      const r = await fetch('/static/i18n/translations.json');
      dict = await r.json();
    } catch (e) { dict = {}; }
  }
  function applyI18n() {
    document.documentElement.lang = lang;
    $$('[data-i18n]').forEach((el) => { if (has(el.dataset.i18n)) el.textContent = t(el.dataset.i18n); });
    $$('[data-i18n-placeholder]').forEach((el) => { el.placeholder = t(el.dataset.i18nPlaceholder); });
    const sel = $('#lang-select');
    if (sel) sel.value = lang;
    document.dispatchEvent(new CustomEvent('langchange'));
  }
  function setupLang() {
    const sel = $('#lang-select');
    if (!sel) return;
    sel.addEventListener('change', () => {
      lang = sel.value === 'hi' ? 'hi' : 'en';
      try { localStorage.setItem(LANG_KEY, lang); } catch (e) { /* ignore */ }
      applyI18n();
    });
  }
  function setupMenu() {
    const btn = $('#menu-btn'), nav = $('#nav');
    if (!btn || !nav) return;
    btn.addEventListener('click', () => {
      const open = nav.classList.toggle('is-open');
      btn.setAttribute('aria-expanded', String(open));
    });
  }

  /* ----------------------------------------------- leaf illustrations */
  const LEAF = 'M60 8C95 25 105 70 60 112 15 70 25 25 60 8Z';
  const OVERLAYS = {
    healthy: '',
    target_spots: '<g fill="#6b4226"><circle cx="72" cy="55" r="9"/><circle cx="48" cy="72" r="7"/><circle cx="68" cy="88" r="5"/></g><g fill="none" stroke="#d6b85a" stroke-width="2"><circle cx="72" cy="55" r="14"/><circle cx="48" cy="72" r="11"/><circle cx="68" cy="88" r="9"/></g><g fill="none" stroke="#2c1a0e" stroke-width="1.2"><circle cx="72" cy="55" r="5"/><circle cx="48" cy="72" r="4"/></g>',
    small_spots: '<g fill="#3a2a1a"><circle cx="50" cy="45" r="3"/><circle cx="68" cy="40" r="2.6"/><circle cx="75" cy="62" r="3.2"/><circle cx="52" cy="62" r="2.8"/><circle cx="64" cy="78" r="3"/><circle cx="46" cy="82" r="2.4"/><circle cx="72" cy="90" r="2.4"/><circle cx="58" cy="54" r="2.2"/></g><g fill="none" stroke="#d8cf5a" stroke-width="1.4"><circle cx="75" cy="62" r="6"/><circle cx="64" cy="78" r="6"/><circle cx="50" cy="45" r="5.5"/></g>',
    water_blight: '<path d="M70 40c14 10 20 28 8 44-8 6-18-2-20-14s0-22 12-30z" fill="#38422a" opacity=".85"/><path d="M45 70c8-4 14 2 12 12s-12 14-16 6 0-14 4-18z" fill="#4c5a35" opacity=".8"/><path d="M62 54c4 4 6 10 2 14" stroke="#e8efe0" stroke-width="3" stroke-linecap="round" fill="none" opacity=".7"/>',
    mold: '<g fill="#d9d36a" opacity=".85"><ellipse cx="68" cy="52" rx="13" ry="9"/><ellipse cx="50" cy="74" rx="11" ry="8"/><ellipse cx="68" cy="92" rx="8" ry="6"/></g><g fill="#7a7a2e" opacity=".8"><circle cx="64" cy="50" r="1.6"/><circle cx="70" cy="54" r="1.6"/><circle cx="48" cy="72" r="1.6"/><circle cx="54" cy="76" r="1.6"/><circle cx="68" cy="92" r="1.4"/></g>',
    stippling: '<g fill="#e9eba6" opacity=".95"><circle cx="50" cy="46" r="1.4"/><circle cx="58" cy="40" r="1.4"/><circle cx="66" cy="46" r="1.4"/><circle cx="72" cy="56" r="1.4"/><circle cx="52" cy="58" r="1.4"/><circle cx="60" cy="64" r="1.4"/><circle cx="70" cy="72" r="1.4"/><circle cx="48" cy="72" r="1.4"/><circle cx="58" cy="80" r="1.4"/><circle cx="66" cy="88" r="1.4"/><circle cx="52" cy="90" r="1.4"/><circle cx="62" cy="52" r="1.4"/></g><path d="M52 66q8-6 16 0M54 76q8-5 14 0" stroke="#f4f4f0" stroke-width=".8" fill="none" opacity=".8"/>',
    curl: '<path d="M60 8C95 25 105 70 60 112 15 70 25 25 60 8Z" fill="none" stroke="#d9d05a" stroke-width="7" stroke-linejoin="round" opacity=".85"/><path d="M60 24C84 38 88 70 60 100" fill="none" stroke="#2f6a42" stroke-width="3" opacity=".6"/>',
    mosaic: '<g opacity=".85"><circle cx="52" cy="46" r="10" fill="#9bd176"/><circle cx="70" cy="64" r="12" fill="#2f6a42"/><circle cx="50" cy="78" r="9" fill="#a8d884"/><circle cx="68" cy="94" r="7" fill="#2f6a42"/><circle cx="64" cy="40" r="6" fill="#2f6a42"/></g>'
  };
  function leafSvg(visual) {
    const base = visual === 'curl' ? '#5f9d5d' : '#4F8A5B';
    return '<svg viewBox="0 0 120 120" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><path d="' + LEAF + '" fill="' + base + '" stroke="#245B3D" stroke-width="2.5"/><path d="M60 16V104" stroke="#cfe8cf" stroke-width="2.5" stroke-linecap="round"/><path d="M60 40L42 28M60 56L80 40M60 72L40 56M60 88L78 74" stroke="#cfe8cf" stroke-width="1.8" stroke-linecap="round" fill="none"/>' + (OVERLAYS[visual] || '') + '</svg>';
  }
  function illustration(visual) {
    const wrap = h('div', { class: 'art' });
    wrap.innerHTML = leafSvg(visual);   // constant, developer-authored markup only
    return wrap;
  }

  /* ------------------------------------------------------ detect page */
  function initDetect() {
    const form = $('#detect-form');
    if (!form) return;
    const fileInput = $('#file-input'), camInput = $('#camera-input');
    const dz = $('#dropzone'), preview = $('#preview'), pImg = $('#preview-img');
    const pName = $('#preview-name'), analyze = $('#analyze-btn'), errBox = $('#form-error');
    let file = null, objectUrl = null;

    function showError(msg) { errBox.textContent = msg; errBox.hidden = !msg; }
    function setFile(f) {
      showError('');
      if (!f) return;
      const typeOk = OK_TYPES.includes(f.type) || (!f.type && OK_EXT.test(f.name));
      if (!typeOk) { showError(t('err.type')); return; }
      if (f.size > MAX_BYTES) { showError(t('err.size')); return; }
      file = f;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
      objectUrl = URL.createObjectURL(f);
      pImg.src = objectUrl;
      pName.textContent = f.name + ' · ' + (f.size / 1024 / 1024).toFixed(2) + ' MB';
      preview.classList.add('is-visible');
      analyze.disabled = false;
    }
    function clearFile() {
      file = null; fileInput.value = ''; camInput.value = '';
      if (objectUrl) { URL.revokeObjectURL(objectUrl); objectUrl = null; }
      pImg.removeAttribute('src');
      preview.classList.remove('is-visible');
      analyze.disabled = true;
      showError('');
    }

    $('#choose-btn').addEventListener('click', (e) => { e.stopPropagation(); fileInput.click(); });
    $('#camera-btn').addEventListener('click', (e) => { e.stopPropagation(); camInput.click(); });
    dz.addEventListener('click', () => fileInput.click());
    dz.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fileInput.click(); } });
    fileInput.addEventListener('change', () => setFile(fileInput.files[0]));
    camInput.addEventListener('change', () => setFile(camInput.files[0]));
    $('#remove-btn').addEventListener('click', clearFile);
    ['dragenter', 'dragover'].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add('is-over'); }));
    ['dragleave', 'drop'].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove('is-over'); }));
    dz.addEventListener('drop', (e) => { if (e.dataTransfer.files.length) setFile(e.dataTransfer.files[0]); });

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (!file) { showError(t('err.nofile')); return; }
      const crop = (form.querySelector('input[name="crop"]:checked') || {}).value;
      const fd = new FormData();
      fd.append('crop', crop);
      fd.append('image', file, file.name);
      $('#loader').classList.add('is-visible');
      analyze.disabled = true;
      showError('');
      try {
        const data = await api('/api/predict', { method: 'POST', body: fd });
        sessionStorage.setItem(RESULT_KEY, JSON.stringify(data.result));
        window.location.href = '/results';
      } catch (err) {
        $('#loader').classList.remove('is-visible');
        analyze.disabled = false;
        showError(errText(err));
      }
    });

    // Honest model status banner
    api('/api/health').then((d) => {
      const banner = $('#model-banner');
      if (!d.model.available) {
        banner.hidden = false;
        banner.dataset.i18n = 'model.missing';
        banner.textContent = t('model.missing');
      }
    }).catch(() => { /* leave banner hidden; errors show on submit */ });
  }

  /* ------------------------------------------------------ results page */
  function initResults() {
    const root = $('#results-content');
    if (!root) return;
    let result = null;
    try { result = JSON.parse(sessionStorage.getItem(RESULT_KEY) || 'null'); } catch (e) { /* ignore */ }
    if (!result) { $('#results-empty').hidden = false; return; }
    root.hidden = false;

    function fillList(id, items) {
      const ul = $(id);
      ul.replaceChildren();
      (items || []).forEach((x) => ul.append(h('li', { text: x })));
    }

    function render() {
      const adv = result.advisory;
      $('#res-img').src = result.image_url;
      $('#res-crop').textContent = t('crop.' + result.crop);
      $('#res-name').textContent = loc(result.label);
      $('#res-conf').textContent = pct(result.confidence);
      const bar = $('#res-bar');
      bar.classList.toggle('warn', !result.reliable);
      bar.firstElementChild.style.width = (result.confidence * 100).toFixed(1) + '%';

      const kind = $('#res-kind');
      kind.textContent = adv ? t('results.kind.' + adv.kind) : '';
      kind.hidden = !adv;
      kind.className = 'badge' + (result.reliable ? '' : ' badge-warn');

      // top three
      const ul = $('#res-top3');
      ul.replaceChildren();
      result.top3.forEach((x) => {
        const b = h('div', { class: 'bar' }, h('i'));
        b.firstElementChild.style.width = (x.confidence * 100).toFixed(1) + '%';
        ul.append(h('li', {}, h('div', {}, h('span', { text: loc(x.label) }), h('strong', { text: pct(x.confidence) })), b));
      });

      // warnings (uncertainty is shown first and plainly)
      const wbox = $('#results-warnings');
      wbox.replaceChildren();
      const msgs = [];
      (result.warnings || []).forEach((w) => {
        msgs.push(t('warn.' + w, { crop: t('crop.' + result.predicted_crop) }));
      });
      if (adv && adv.urgent) msgs.push(t('warn.urgent'));
      if (adv && adv.kind === 'healthy') msgs.push(t('warn.healthy'));
      if (msgs.length) {
        const risky = (result.warnings || []).length > 0;
        wbox.append(h('div', { class: 'alert ' + (risky ? 'alert-warn' : 'alert-info'), role: 'status' },
          risky ? h('strong', { text: t('warn.title') }) : null,
          msgs.map((m) => h('div', { text: m }))));
      }
      $('#res-expert').classList.toggle('urgent', !result.reliable || !!(adv && adv.urgent));

      // guidance (kept separate from the prediction)
      if (adv) {
        fillList('#res-symptoms', loc(adv.symptoms));
        fillList('#res-prevention', loc(adv.prevention));
        fillList('#res-management', loc(adv.management));
      } else {
        ['#res-symptoms', '#res-prevention', '#res-management'].forEach((id) => fillList(id, [t('results.noadvice')]));
      }
    }
    render();
    document.addEventListener('langchange', render);

    const saveBtn = $('#save-btn'), msg = $('#res-action-msg');
    saveBtn.addEventListener('click', async () => {
      saveBtn.disabled = true;
      saveBtn.textContent = t('results.saving');
      msg.hidden = true;
      try {
        await api('/api/history', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ image_ref: result.image_ref }) });
        msg.className = 'alert alert-ok';
        msg.textContent = t('results.saved');
        msg.hidden = false;
        saveBtn.textContent = t('results.save');
        saveBtn.dataset.done = '1';
      } catch (err) {
        msg.className = 'alert alert-error';
        msg.textContent = errText(err);
        msg.hidden = false;
        saveBtn.disabled = false;
        saveBtn.textContent = t('results.save');
      }
    });
  }

  /* ----------------------------------------------------- library page */
  function initLibrary() {
    const grid = $('#lib-grid');
    if (!grid) return;
    let items = [], crop = '', q = '', source = null;

    function matches(d) {
      if (crop && d.crop !== crop) return false;
      if (!q) return true;
      const hay = [d.name.en, d.name.hi, d.crop, t('crop.' + d.crop)]
        .concat(d.symptoms.en, d.symptoms.hi, d.prevention.en, d.prevention.hi).join(' ').toLowerCase();
      return hay.includes(q);
    }
    function section(title, list) {
      const det = h('details', {}, h('summary', { text: title }), h('ul', { class: 'info-list' }, list.map((x) => h('li', { text: x }))));
      return det;
    }
    function render() {
      grid.replaceChildren();
      const shown = items.filter(matches);
      $('#lib-empty').hidden = shown.length > 0;
      $('#lib-count').textContent = t('diseases.count', { n: shown.length });
      shown.forEach((d, i) => {
        const card = h('article', { class: 'card hoverable disease-card' },
          illustration(d.visual),
          h('div', { class: 'body' },
            h('span', { class: 'badge', text: t('crop.' + d.crop) }),
            h('h3', { text: loc(d.name) }),
            d.urgent ? h('p', { class: 'muted', style: 'font-size:.88rem;margin-bottom:6px', text: t('diseases.urgent') }) : null,
            section(t('results.symptoms'), loc(d.symptoms)),
            section(t('results.prevention'), loc(d.prevention)),
            section(t('results.management'), loc(d.management))));
        grid.append(card);
      });
      const note = $('#lib-source');
      if (source) {
        note.hidden = false;
        note.textContent = t(source === 'model' ? 'diseases.src.model' : 'diseases.src.dataset');
      }
    }
    $('#lib-search').addEventListener('input', (e) => { q = e.target.value.trim().toLowerCase(); render(); });
    $$('.chip').forEach((c) => c.addEventListener('click', () => {
      crop = c.dataset.crop;
      $$('.chip').forEach((x) => x.setAttribute('aria-pressed', String(x === c)));
      render();
    }));
    document.addEventListener('langchange', render);

    api('/api/diseases').then((d) => {
      items = d.diseases; source = d.source;
      const refs = $('#lib-refs');
      d.references.forEach((r) => {
        const a = h('a', { href: r.url, target: '_blank', rel: 'noopener noreferrer', text: r.name });
        refs.append(h('li', {}, a));
      });
      render();
    }).catch((err) => { const n = $('#lib-source'); n.hidden = false; n.className = 'alert alert-error'; n.textContent = errText(err); });
  }

  /* ----------------------------------------------------- history page */
  function initHistory() {
    const list = $('#hist-list');
    if (!list) return;
    let scans = [], crop = '', q = '', chart = null;
    const msg = $('#hist-msg');
    const fmt = (iso) => new Date(iso).toLocaleString(lang === 'hi' ? 'hi-IN' : 'en-IN', { dateStyle: 'medium', timeStyle: 'short' });
    function flash(text, kind) { msg.className = 'alert alert-' + kind; msg.textContent = text; msg.hidden = !text; }

    function filtered() {
      return scans.filter((s) => {
        if (crop && s.crop !== crop) return false;
        if (!q) return true;
        return (loc(s.label) + ' ' + s.label.en + ' ' + s.label.hi + ' ' + s.crop + ' ' + t('crop.' + s.crop)).toLowerCase().includes(q);
      });
    }
    function drawChart(shown) {
      const card = $('#chart-card');
      if (!window.Chart || !shown.length) { card.hidden = true; return; }
      card.hidden = false;
      const counts = {};
      shown.forEach((s) => { const k = loc(s.label); counts[k] = (counts[k] || 0) + 1; });
      if (chart) chart.destroy();
      chart = new window.Chart($('#hist-chart'), {
        type: 'bar',
        data: { labels: Object.keys(counts), datasets: [{ data: Object.values(counts), backgroundColor: '#4F8A5B', borderRadius: 6 }] },
        options: { indexAxis: 'y', maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { beginAtZero: true, ticks: { precision: 0 } } } }
      });
    }
    function render() {
      const shown = filtered();
      list.replaceChildren();
      $('#clear-all').hidden = scans.length === 0;
      const none = scans.length === 0;
      $('#hist-empty').hidden = !none;
      if (!none && !shown.length) list.append(h('p', { class: 'muted', text: t('history.nomatch') }));
      shown.forEach((s) => {
        const del = h('button', { type: 'button', class: 'btn btn-danger btn-small', text: t('history.delete') });
        del.addEventListener('click', () => remove(s.id));
        list.append(h('article', { class: 'card hoverable scan-card' },
          h('img', { src: s.image_url, alt: loc(s.label), loading: 'lazy' }),
          h('div', { class: 'body' },
            h('span', { class: 'badge', text: t('crop.' + s.crop) }),
            h('h3', { text: loc(s.label) }),
            h('div', { class: 'scan-meta', text: pct(s.confidence) + ' ' + t('history.confidence') }),
            h('div', { class: 'scan-meta', text: fmt(s.created_at) }),
            del)));
      });
      drawChart(shown);
    }
    async function load() {
      try { scans = (await api('/api/history')).scans; render(); }
      catch (err) { flash(errText(err), 'error'); }
    }
    async function remove(id) {
      if (!window.confirm(t('history.confirm'))) return;
      try { await api('/api/history/' + id, { method: 'DELETE' }); flash(t('history.deleted'), 'ok'); await load(); }
      catch (err) { flash(errText(err), 'error'); }
    }
    $('#clear-all').addEventListener('click', async () => {
      if (!window.confirm(t('history.confirm.all'))) return;
      try { await api('/api/history', { method: 'DELETE' }); flash(t('history.deleted.all'), 'ok'); await load(); }
      catch (err) { flash(errText(err), 'error'); }
    });
    $('#hist-search').addEventListener('input', (e) => { q = e.target.value.trim().toLowerCase(); render(); });
    $$('.chip').forEach((c) => c.addEventListener('click', () => {
      crop = c.dataset.crop;
      $$('.chip').forEach((x) => x.setAttribute('aria-pressed', String(x === c)));
      render();
    }));
    document.addEventListener('langchange', render);
    load();
  }

  /* -------------------------------------------------------- about page */
  function initAbout() {
    const body = $('#metrics-body');
    if (!body) return;
    function render(m) {
      body.replaceChildren();
      if (!m) { body.append(h('p', { class: 'muted', text: t('about.metrics.none') })); return; }
      const n = (m.dataset && m.dataset.per_split && m.dataset.per_split.test) || '–';
      body.append(
        h('p', {}, h('strong', { text: t('about.metrics.acc') + ': ' }), document.createTextNode(pct(m.test_accuracy))),
        h('p', {}, h('strong', { text: t('about.metrics.f1') + ': ' }), document.createTextNode(m.test_macro_f1.toFixed(3))),
        h('p', {}, h('strong', { text: t('about.metrics.n') + ': ' }), document.createTextNode(String(n))),
        h('p', { class: 'disclaimer', text: t('about.metrics.note') }));
    }
    let metrics = null, loaded = false;
    api('/api/model-metrics').then((d) => { metrics = d.metrics; loaded = true; render(metrics); })
      .catch(() => { loaded = true; render(null); });
    document.addEventListener('langchange', () => { if (loaded) render(metrics); });
  }

  /* --------------------------------------------------------------- boot */
  async function boot() {
    await loadDict();
    setupLang();
    setupMenu();
    applyI18n();
    const page = document.body.dataset.page;
    if (page === 'detect') initDetect();
    if (page === 'results') initResults();
    if (page === 'diseases') initLibrary();
    if (page === 'history') initHistory();
    if (page === 'about') initAbout();
  }
  boot();
})();
