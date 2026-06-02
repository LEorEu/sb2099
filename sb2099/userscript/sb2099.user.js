// ==UserScript==
// @name         sb2099 - 斗鱼 2099 烂梗发送器
// @namespace    https://github.com/LEorEu/sb2099
// @version      0.3.0
// @description  在斗鱼 2099 房间（real id 12740109）的页面内嵌入烂梗投稿库面板，支持搜索/tag 筛选/本地收藏/单条复制+发送
// @author       Eu
// @match        https://www.douyu.com/2099
// @match        https://www.douyu.com/2099?*
// @match        https://www.douyu.com/12740109
// @match        https://www.douyu.com/12740109?*
// @match        https://www.douyu.com/topic/*
// @grant        GM_xmlhttpRequest
// @grant        GM_setClipboard
// @grant        GM_getValue
// @grant        GM_setValue
// @connect      www.sb2099.cn
// @connect      sb2099.cn
// @icon         https://apic.douyucdn.cn/upload/avatar_v3/202512/a8ede184d6f04a9585e096d0d55f2776_middle.jpg
// @run-at       document-idle
// @noframes
// ==/UserScript==

(function () {
  'use strict';

  // ---- 配置 ---------------------------------------------------------------
  // 部署到公网后改这一行即可。
  const API_BASE = 'https://www.sb2099.cn';
  const SCRIPT_VERSION = '0.3.0';
  const STORAGE_KEY_FAVS = 'sb2099_favorites_v1';
  const STORAGE_KEY_BLOCKED = 'sb2099_blocked_v1';
  const STORAGE_KEY_PANEL_OPEN = 'sb2099_panel_open_v1';

  // ---- 工具：API 调用 -----------------------------------------------------
  function apiGet(path) {
    return new Promise((resolve, reject) => {
      if (typeof GM_xmlhttpRequest === 'function') {
        GM_xmlhttpRequest({
          method: 'GET',
          url: API_BASE + path,
          timeout: 8000,
          onload: (r) => {
            try {
              resolve(JSON.parse(r.responseText));
            } catch (e) {
              reject(new Error('bad json: ' + e));
            }
          },
          onerror: (e) => reject(new Error('network error')),
          ontimeout: () => reject(new Error('timeout')),
        });
      } else {
        fetch(API_BASE + path)
          .then((r) => r.json())
          .then(resolve, reject);
      }
    });
  }

  function apiPost(path, body) {
    return new Promise((resolve, reject) => {
      if (typeof GM_xmlhttpRequest === 'function') {
        GM_xmlhttpRequest({
          method: 'POST',
          url: API_BASE + path,
          data: JSON.stringify(body || {}),
          headers: { 'Content-Type': 'application/json' },
          timeout: 8000,
          onload: (r) => {
            const status = r.status;
            let data = null;
            try { data = r.responseText ? JSON.parse(r.responseText) : null; } catch (_) {}
            resolve({ ok: status >= 200 && status < 300, status, data });
          },
          onerror: () => reject(new Error('network error')),
          ontimeout: () => reject(new Error('timeout')),
        });
      } else {
        fetch(API_BASE + path, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body || {}),
        }).then(async (r) => ({ ok: r.ok, status: r.status, data: await r.json().catch(() => null) }))
          .then(resolve, reject);
      }
    });
  }

  // ---- 本地存储 -----------------------------------------------------------
  function loadJSON(key, fallback) {
    try {
      const raw = (typeof GM_getValue === 'function') ? GM_getValue(key, null) : localStorage.getItem(key);
      if (!raw) return fallback;
      return JSON.parse(raw);
    } catch (_) {
      return fallback;
    }
  }

  function saveJSON(key, value) {
    const s = JSON.stringify(value);
    if (typeof GM_setValue === 'function') GM_setValue(key, s);
    else localStorage.setItem(key, s);
  }

  // 收藏结构：{ groups: { name: [ids...] }, order: [name1, name2] }
  function loadFavorites() {
    return loadJSON(STORAGE_KEY_FAVS, { groups: { '默认': [] }, order: ['默认'] });
  }

  function saveFavorites(f) {
    saveJSON(STORAGE_KEY_FAVS, f);
  }

  function loadBlocked() {
    return new Set(loadJSON(STORAGE_KEY_BLOCKED, []));
  }

  function saveBlocked(set) {
    saveJSON(STORAGE_KEY_BLOCKED, Array.from(set));
  }

  // ---- 复制 + 发送到斗鱼输入框 -------------------------------------------
  async function copyToClipboard(text) {
    if (typeof GM_setClipboard === 'function') {
      GM_setClipboard(text, 'text');
      return true;
    }
    if (navigator.clipboard && window.isSecureContext) {
      try { await navigator.clipboard.writeText(text); return true; } catch (_) {}
    }
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    let ok = false;
    try { ok = document.execCommand('copy'); } catch (_) {}
    document.body.removeChild(ta);
    return ok;
  }

  // 尝试多个 selector 找到斗鱼直播间的弹幕输入框
  function findDouyuInput() {
    const sels = [
      'textarea.ChatSend-txt',
      'textarea[placeholder*="发个弹幕"]',
      'textarea[placeholder*="弹幕"]',
      '.Barrage-input textarea',
      '#js-barrage-input',
      '.ChatSend textarea',
    ];
    for (const s of sels) {
      const el = document.querySelector(s);
      if (el) return el;
    }
    return null;
  }

  function setReactInputValue(el, value) {
    // React 控制的 input 直接 .value= 不会触发 onChange；用原生 setter + dispatch
    const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
    setter.call(el, value);
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  }

  function sendToDouyuChat(text) {
    const el = findDouyuInput();
    if (!el) return false;
    el.focus();
    setReactInputValue(el, text);
    // 不自动按回车——避免封号风险，让主播自己 enter；只把内容塞进去
    return true;
  }

  // ---- toast --------------------------------------------------------------
  function toast(msg, ok) {
    let el = document.getElementById('sb2099-toast');
    if (!el) {
      el = document.createElement('div');
      el.id = 'sb2099-toast';
      el.className = 'sb2099-toast';
      document.body.appendChild(el);
    }
    el.textContent = msg;
    el.dataset.kind = ok ? 'ok' : 'err';
    el.classList.add('show');
    clearTimeout(el._t);
    el._t = setTimeout(() => el.classList.remove('show'), 2000);
  }

  // ---- 状态 ---------------------------------------------------------------
  const state = {
    tags: [],
    selectedTags: new Set(),
    q: '',
    sort: 'new', // new | hot
    page: 1,
    size: 20,
    activeTab: 'lib', // lib | fav
    activeFavGroup: '默认',
    libResult: { list: [], total: 0, last_page: true },
    favorites: loadFavorites(),
    blocked: loadBlocked(),
  };

  // ---- DOM 模板 -----------------------------------------------------------
  const STYLE = `
  .sb2099-fab {
    position: fixed; left: 16px; bottom: 84px;
    width: 40px; height: 40px; border-radius: 50%;
    background: #ff5d5d; color: #fff; font-weight: 700; font-size: 13px;
    display: flex; align-items: center; justify-content: center;
    cursor: pointer; z-index: 2147483000;
    box-shadow: 0 4px 12px rgba(0,0,0,.3);
    border: none; line-height: 1; opacity: .92;
  }
  .sb2099-fab:hover { background: #ff3d3d; opacity: 1; }

  /* 浮动可拖拽小窗，而非满高抽屉——不再整列挡住聊天 */
  .sb2099-panel {
    position: fixed; left: 16px; top: 84px;
    width: 340px; max-width: 92vw; max-height: 72vh;
    background: #fff; color: #1a1a1a;
    border: 1px solid #e5e5e5; border-radius: 12px;
    box-shadow: 0 10px 30px rgba(0,0,0,.22);
    z-index: 2147483001;
    display: none; flex-direction: column; overflow: hidden;
    font: 13px/1.5 -apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
  }
  .sb2099-panel.open { display: flex; }
  .sb2099-panel * { box-sizing: border-box; }

  .sb2099-head {
    display: flex; align-items: center; gap: 8px;
    padding: 9px 12px; border-bottom: 1px solid #eee;
    cursor: move; user-select: none; background: #fafafa;
    border-radius: 12px 12px 0 0;
  }
  /* 注入到斗鱼聊天工具栏的常驻开关 */
  .sb2099-tbtn {
    font-size: 13px; height: 26px; padding: 0 10px; margin-right: 14px;
    background: #ff5d23; color: #fff; border: none; border-radius: 5px;
    cursor: pointer; line-height: 26px;
  }
  .sb2099-tbtn:hover { background: #ff4500; }
  .sb2099-head .title { font-weight: 600; font-size: 14px; flex: 1; }
  .sb2099-head .ver { color: #999; font-size: 11px; }
  .sb2099-head .close {
    background: transparent; border: none; cursor: pointer;
    font-size: 18px; color: #666;
  }

  .sb2099-tabs { display: flex; border-bottom: 1px solid #eee; }
  .sb2099-tabs button {
    flex: 1; background: transparent; border: none; padding: 10px;
    font-size: 13px; color: #666; cursor: pointer; border-bottom: 2px solid transparent;
  }
  .sb2099-tabs button.active { color: #ff5252; border-bottom-color: #ff5252; font-weight: 500; }

  .sb2099-body { flex: 1; overflow-y: auto; padding: 10px 14px; }

  .sb2099-filters input.q {
    width: 100%; padding: 6px 10px; border: 1px solid #ddd; border-radius: 4px;
    font-size: 13px; margin-bottom: 8px;
  }
  .sb2099-filters .row { display: flex; gap: 6px; margin-bottom: 8px; }
  .sb2099-filters select { padding: 4px 8px; border: 1px solid #ddd; border-radius: 4px; font-size: 12px; }
  .sb2099-filters .clear { background: transparent; border: 1px solid #ddd; border-radius: 4px;
    font-size: 12px; padding: 4px 8px; color: #666; cursor: pointer; }
  .sb2099-tags { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 8px; }
  .sb2099-tags .chip {
    padding: 2px 8px; background: #f3f4f6; border-radius: 999px;
    font-size: 12px; cursor: pointer; user-select: none;
    border: 1px solid transparent;
  }
  .sb2099-tags .chip.active { background: #ff5252; color: #fff; border-color: #ff5252; }

  .sb2099-fav-groups { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 8px; }
  .sb2099-fav-groups .gchip {
    padding: 3px 8px; background: #f3f4f6; border-radius: 4px;
    font-size: 12px; cursor: pointer; user-select: none;
    border: 1px solid transparent;
  }
  .sb2099-fav-groups .gchip.active { background: #ff5252; color: #fff; border-color: #ff5252; }
  .sb2099-fav-tools {
    display: flex; gap: 4px; margin-bottom: 10px; flex-wrap: wrap;
  }
  .sb2099-fav-tools button {
    background: transparent; border: 1px solid #ddd; border-radius: 4px;
    padding: 3px 8px; font-size: 11px; cursor: pointer; color: #666;
  }

  .sb2099-list { list-style: none; padding: 0; margin: 0; }
  .sb2099-list li {
    padding: 8px 0; border-bottom: 1px solid #f0f0f0;
  }
  .sb2099-list .content {
    white-space: pre-wrap; word-break: break-word;
    font-size: 13px; margin-bottom: 4px;
  }
  .sb2099-list .meta { font-size: 11px; color: #999; margin-bottom: 4px; }
  .sb2099-list .meta > span { margin-right: 8px; }
  .sb2099-list .actions { display: flex; gap: 4px; flex-wrap: wrap; }
  .sb2099-list .actions button {
    background: transparent; border: 1px solid #ddd; color: #666;
    padding: 2px 8px; border-radius: 4px; font-size: 11px; cursor: pointer;
  }
  .sb2099-list .actions button.primary { color: #ff5252; border-color: #ff5252; }
  .sb2099-list .actions button.danger { color: #999; }

  .sb2099-pager {
    display: flex; justify-content: center; gap: 12px; padding: 12px 0;
    color: #999; font-size: 12px;
  }
  .sb2099-pager button {
    background: transparent; border: 1px solid #ddd; border-radius: 4px;
    padding: 3px 12px; cursor: pointer; color: #666; font-size: 12px;
  }
  .sb2099-pager button:disabled { opacity: .4; cursor: not-allowed; }

  .sb2099-empty { color: #999; padding: 20px 0; text-align: center; font-size: 12px; }
  .sb2099-loading { color: #999; padding: 20px 0; text-align: center; font-size: 12px; }

  .sb2099-toast {
    position: fixed; left: 50%; bottom: 80px;
    transform: translateX(-50%) translateY(20px);
    padding: 6px 14px; border-radius: 4px; font-size: 13px;
    color: #fff; background: #333; opacity: 0;
    transition: opacity .2s, transform .2s;
    pointer-events: none; z-index: 1000000;
  }
  .sb2099-toast.show { opacity: 1; transform: translateX(-50%) translateY(0); }
  .sb2099-toast[data-kind="ok"] { background: #4caf50; }
  .sb2099-toast[data-kind="err"] { background: #f44336; }
  `;

  function injectStyle() {
    const s = document.createElement('style');
    s.textContent = STYLE;
    document.head.appendChild(s);
  }

  function el(tag, attrs, children) {
    const e = document.createElement(tag);
    if (attrs) {
      for (const k in attrs) {
        if (k === 'class') e.className = attrs[k];
        else if (k === 'on') {
          for (const ev in attrs[k]) e.addEventListener(ev, attrs[k][ev]);
        }
        else if (k === 'html') e.innerHTML = attrs[k];
        else if (k === 'style') Object.assign(e.style, attrs[k]);
        else e.setAttribute(k, attrs[k]);
      }
    }
    (children || []).forEach((c) => {
      if (c == null) return;
      e.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
    });
    return e;
  }

  // ---- 渲染 ---------------------------------------------------------------
  let $panel, $body;

  function renderRoot() {
    const fab = el('button', { class: 'sb2099-fab', title: 'sb2099 烂梗库（点开/关）' }, ['梗']);
    fab.addEventListener('click', togglePanel);
    document.body.appendChild(fab);

    $panel = el('div', { class: 'sb2099-panel' });
    document.body.appendChild($panel);
    if (loadJSON(STORAGE_KEY_PANEL_OPEN, false)) {
      $panel.classList.add('open');
    }
    refreshPanel();
    enableDrag($panel);          // 头部拖拽，可把窗挪开聊天区
    startToolbarButton();        // 往斗鱼聊天工具栏注入常驻「烂梗」开关
  }

  function togglePanel() {
    const open = $panel.classList.toggle('open');
    saveJSON(STORAGE_KEY_PANEL_OPEN, open);
  }

  // 把开关按钮注入到斗鱼聊天工具栏，并定时补注入——这样刷新 / 斗鱼 SPA 重渲染后
  // 开关都还在，不会出现「关掉就再也找不到」。面板默认隐藏，点开关才显示。
  function startToolbarButton() {
    function inject() {
      const bar = document.querySelector('.ChatToolBar__right')
        || document.querySelector('.ChatToolBar-right')
        || document.querySelector('.ChatToolBar__left');
      if (bar && !bar.querySelector('#sb2099-tbtn')) {
        const btn = el('button', { id: 'sb2099-tbtn', class: 'sb2099-tbtn', title: 'sb2099 烂梗库' }, ['🐹 烂梗']);
        btn.addEventListener('click', togglePanel);
        bar.insertBefore(btn, bar.firstChild);
      }
    }
    inject();
    setInterval(inject, 2000);
  }

  // 拖拽：按住标题栏移动整个面板（按钮上不触发，避免和关闭冲突）
  function enableDrag(panel) {
    let dragging = false, ox = 0, oy = 0;
    panel.addEventListener('pointerdown', (e) => {
      const head = e.target.closest && e.target.closest('.sb2099-head');
      if (!head || !panel.contains(head)) return;
      if (e.target.closest('button')) return;
      dragging = true;
      const r = panel.getBoundingClientRect();
      ox = e.clientX - r.left; oy = e.clientY - r.top;
      panel.style.right = 'auto'; panel.style.bottom = 'auto';
      try { panel.setPointerCapture(e.pointerId); } catch (_) {}
      e.preventDefault();
    });
    panel.addEventListener('pointermove', (e) => {
      if (!dragging) return;
      const maxX = window.innerWidth - 60, maxY = window.innerHeight - 60;
      panel.style.left = Math.min(maxX, Math.max(0, e.clientX - ox)) + 'px';
      panel.style.top = Math.min(maxY, Math.max(0, e.clientY - oy)) + 'px';
    });
    const end = () => { dragging = false; };
    panel.addEventListener('pointerup', end);
    panel.addEventListener('pointercancel', end);
  }

  function refreshPanel() {
    $panel.innerHTML = '';
    $panel.appendChild(renderHead());
    $panel.appendChild(renderTabs());
    $body = el('div', { class: 'sb2099-body' });
    $panel.appendChild($body);
    if (state.activeTab === 'lib') {
      renderLibBody();
    } else {
      renderFavBody();
    }
  }

  function renderHead() {
    return el('div', { class: 'sb2099-head' }, [
      el('div', { class: 'title' }, ['sb2099 烂梗库']),
      el('div', { class: 'ver' }, ['v' + SCRIPT_VERSION]),
      el('button', { class: 'close', title: '关闭', on: { click: togglePanel } }, ['×']),
    ]);
  }

  function renderTabs() {
    return el('div', { class: 'sb2099-tabs' }, [
      el('button', {
        class: state.activeTab === 'lib' ? 'active' : '',
        on: { click: () => { state.activeTab = 'lib'; refreshPanel(); } },
      }, ['投稿库']),
      el('button', {
        class: state.activeTab === 'fav' ? 'active' : '',
        on: { click: () => { state.activeTab = 'fav'; refreshPanel(); } },
      }, ['收藏 (' + totalFavorites() + ')']),
    ]);
  }

  function totalFavorites() {
    return Object.values(state.favorites.groups).reduce((acc, arr) => acc + arr.length, 0);
  }

  // ---- 投稿库 tab ---------------------------------------------------------
  async function renderLibBody() {
    $body.innerHTML = '';
    $body.appendChild(renderFilters());
    if (state.tags.length === 0) {
      try {
        const r = await apiGet('/api/tags');
        state.tags = r.data || [];
      } catch (e) {
        state.tags = [];
      }
    }
    $body.appendChild(renderTagChips());

    const loader = el('div', { class: 'sb2099-loading' }, ['加载中…']);
    $body.appendChild(loader);

    try {
      const path = '/api/barrage?'
        + 'sort=' + state.sort
        + (state.q ? '&q=' + encodeURIComponent(state.q) : '')
        + (state.selectedTags.size ? '&tag=' + Array.from(state.selectedTags).join(',') : '')
        + '&page=' + state.page + '&size=' + state.size;
      const r = await apiGet(path);
      state.libResult = (r && r.data) || { list: [], total: 0, last_page: true };
    } catch (e) {
      state.libResult = { list: [], total: 0, last_page: true };
      toast('加载失败，检查 sb2099 服务地址', false);
    }
    loader.remove();

    const items = state.libResult.list.filter((it) => !state.blocked.has(it.id));
    if (items.length === 0) {
      $body.appendChild(el('div', { class: 'sb2099-empty' }, ['空结果。']));
    } else {
      const ul = el('ul', { class: 'sb2099-list' });
      items.forEach((it) => ul.appendChild(renderLibItem(it)));
      $body.appendChild(ul);
    }

    $body.appendChild(renderPager());
  }

  function renderFilters() {
    const wrap = el('div', { class: 'sb2099-filters' });
    const input = el('input', { class: 'q', type: 'text', placeholder: '搜索内容…（FTS5）', value: state.q });
    input.addEventListener('change', () => {
      state.q = input.value.trim();
      state.page = 1;
      renderLibBody();
    });
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') { state.q = input.value.trim(); state.page = 1; renderLibBody(); }
    });
    wrap.appendChild(input);

    const row = el('div', { class: 'row' });
    const sortSel = el('select', {}, [
      el('option', { value: 'new' }, ['最新']),
      el('option', { value: 'hot' }, ['最热']),
    ]);
    sortSel.value = state.sort;
    sortSel.addEventListener('change', () => { state.sort = sortSel.value; state.page = 1; renderLibBody(); });
    row.appendChild(sortSel);

    const clear = el('button', { class: 'clear', on: { click: () => {
      state.q = ''; state.selectedTags.clear(); state.page = 1; renderLibBody();
    } } }, ['清空筛选']);
    row.appendChild(clear);
    wrap.appendChild(row);

    return wrap;
  }

  function renderTagChips() {
    const wrap = el('div', { class: 'sb2099-tags' });
    state.tags.forEach((t) => {
      const chip = el('span', {
        class: 'chip' + (state.selectedTags.has(t.value) ? ' active' : ''),
        on: { click: () => {
          if (state.selectedTags.has(t.value)) state.selectedTags.delete(t.value);
          else state.selectedTags.add(t.value);
          state.page = 1;
          renderLibBody();
        } },
      }, [t.label]);
      wrap.appendChild(chip);
    });
    return wrap;
  }

  function renderLibItem(it) {
    const li = el('li');
    li.appendChild(el('div', { class: 'content' }, [it.content]));
    li.appendChild(el('div', { class: 'meta' }, [
      el('span', {}, ['#' + it.id]),
      el('span', {}, ['tags: ' + (it.tags || '-')]),
      el('span', {}, ['复制 ' + it.cnt]),
    ]));
    const actions = el('div', { class: 'actions' });

    const copyBtn = el('button', { class: 'primary', on: { click: () => doCopy(it) } }, ['复制']);
    const sendBtn = el('button', { on: { click: () => doSend(it) } }, ['发送']);
    const favBtn = el('button', { on: { click: () => doFavorite(it) } }, ['收藏']);
    const blockBtn = el('button', { class: 'danger', on: { click: () => doBlock(it) } }, ['屏蔽']);

    [copyBtn, sendBtn, favBtn, blockBtn].forEach((b) => actions.appendChild(b));
    li.appendChild(actions);
    return li;
  }

  function renderPager() {
    const pager = el('div', { class: 'sb2099-pager' });
    const prev = el('button', { on: { click: () => { if (state.page > 1) { state.page--; renderLibBody(); } } } }, ['上一页']);
    prev.disabled = state.page <= 1;
    pager.appendChild(prev);
    pager.appendChild(el('span', {}, ['第 ' + state.page + ' 页 · 共 ' + state.libResult.total + ' 条']));
    const next = el('button', { on: { click: () => { if (!state.libResult.last_page) { state.page++; renderLibBody(); } } } }, ['下一页']);
    next.disabled = !!state.libResult.last_page;
    pager.appendChild(next);
    return pager;
  }

  // ---- 收藏 tab -----------------------------------------------------------
  function renderFavBody() {
    $body.innerHTML = '';
    $body.appendChild(renderFavGroups());
    $body.appendChild(renderFavTools());

    const ids = state.favorites.groups[state.activeFavGroup] || [];
    if (ids.length === 0) {
      $body.appendChild(el('div', { class: 'sb2099-empty' }, ['本分组还没有收藏。']));
      return;
    }

    const loader = el('div', { class: 'sb2099-loading' }, ['加载中…']);
    $body.appendChild(loader);

    // 收藏条目走 /api/barrage 反查（按 id 拉一次再 client-side 过滤）。
    // 简化策略：限 ids 数量上限，超过时只拉前 100 个；后续可加 /api/barrage/by_ids 端点。
    fetchFavoriteEntries(ids.slice(0, 100)).then((items) => {
      loader.remove();
      const ul = el('ul', { class: 'sb2099-list' });
      items.forEach((it) => ul.appendChild(renderFavItem(it)));
      $body.appendChild(ul);
    }).catch((e) => {
      loader.remove();
      $body.appendChild(el('div', { class: 'sb2099-empty' }, ['加载失败']));
    });
  }

  async function fetchFavoriteEntries(ids) {
    if (ids.length === 0) return [];
    // 取大列表的前几页直到把所有 id 都拼齐；最坏情况翻 5 页（500 条）
    const wanted = new Set(ids);
    const found = new Map();
    let page = 1;
    while (wanted.size > 0 && page <= 5) {
      const r = await apiGet('/api/barrage?sort=new&page=' + page + '&size=100');
      const list = ((r && r.data) || {}).list || [];
      if (list.length === 0) break;
      list.forEach((it) => {
        if (wanted.has(it.id)) {
          found.set(it.id, it);
          wanted.delete(it.id);
        }
      });
      if ((r.data || {}).last_page) break;
      page++;
    }
    // 按 ids 原顺序返回
    return ids.map((id) => found.get(id)).filter(Boolean);
  }

  function renderFavGroups() {
    const wrap = el('div', { class: 'sb2099-fav-groups' });
    state.favorites.order.forEach((name) => {
      const chip = el('span', {
        class: 'gchip' + (state.activeFavGroup === name ? ' active' : ''),
        on: { click: () => { state.activeFavGroup = name; renderFavBody(); } },
      }, [name + ' (' + (state.favorites.groups[name] || []).length + ')']);
      wrap.appendChild(chip);
    });
    return wrap;
  }

  function renderFavTools() {
    const wrap = el('div', { class: 'sb2099-fav-tools' });

    wrap.appendChild(el('button', { on: { click: () => {
      const name = prompt('新分组名称：');
      if (!name) return;
      if (state.favorites.groups[name]) { toast('分组已存在', false); return; }
      state.favorites.groups[name] = [];
      state.favorites.order.push(name);
      saveFavorites(state.favorites);
      state.activeFavGroup = name;
      renderFavBody();
    } } }, ['+ 新分组']));

    wrap.appendChild(el('button', { on: { click: () => {
      const newName = prompt('重命名为：', state.activeFavGroup);
      if (!newName || newName === state.activeFavGroup) return;
      if (state.favorites.groups[newName]) { toast('分组已存在', false); return; }
      state.favorites.groups[newName] = state.favorites.groups[state.activeFavGroup];
      delete state.favorites.groups[state.activeFavGroup];
      state.favorites.order = state.favorites.order.map((x) => x === state.activeFavGroup ? newName : x);
      state.activeFavGroup = newName;
      saveFavorites(state.favorites);
      renderFavBody();
    } } }, ['重命名']));

    wrap.appendChild(el('button', { on: { click: () => {
      if (state.favorites.order.length <= 1) { toast('至少保留一个分组', false); return; }
      if (!confirm('删除分组「' + state.activeFavGroup + '」?')) return;
      delete state.favorites.groups[state.activeFavGroup];
      state.favorites.order = state.favorites.order.filter((x) => x !== state.activeFavGroup);
      state.activeFavGroup = state.favorites.order[0];
      saveFavorites(state.favorites);
      renderFavBody();
    } } }, ['删除']));

    wrap.appendChild(el('button', { on: { click: () => {
      const text = JSON.stringify(state.favorites, null, 2);
      copyToClipboard(text);
      toast('已复制到剪贴板', true);
    } } }, ['导出']));

    wrap.appendChild(el('button', { on: { click: () => {
      const text = prompt('粘贴收藏 JSON：');
      if (!text) return;
      try {
        const data = JSON.parse(text);
        if (!data.groups || !data.order) throw new Error('bad structure');
        state.favorites = data;
        saveFavorites(state.favorites);
        state.activeFavGroup = state.favorites.order[0];
        renderFavBody();
        toast('导入完成', true);
      } catch (e) {
        toast('JSON 解析失败', false);
      }
    } } }, ['导入']));

    wrap.appendChild(el('button', { on: { click: () => {
      if (state.blocked.size === 0) { toast('没有屏蔽条目', false); return; }
      if (!confirm('恢复全部 ' + state.blocked.size + ' 个屏蔽条目？')) return;
      state.blocked.clear();
      saveBlocked(state.blocked);
      toast('已恢复', true);
      refreshPanel();
    } } }, ['恢复屏蔽(' + state.blocked.size + ')']));

    return wrap;
  }

  function renderFavItem(it) {
    const li = el('li');
    li.appendChild(el('div', { class: 'content' }, [it.content]));
    li.appendChild(el('div', { class: 'meta' }, [
      el('span', {}, ['#' + it.id]),
      el('span', {}, ['tags: ' + (it.tags || '-')]),
    ]));
    const actions = el('div', { class: 'actions' });
    actions.appendChild(el('button', { class: 'primary', on: { click: () => doCopy(it) } }, ['复制']));
    actions.appendChild(el('button', { on: { click: () => doSend(it) } }, ['发送']));
    actions.appendChild(el('button', { class: 'danger', on: { click: () => {
      const group = state.favorites.groups[state.activeFavGroup];
      const idx = group.indexOf(it.id);
      if (idx >= 0) { group.splice(idx, 1); saveFavorites(state.favorites); renderFavBody(); refreshTabsCount(); }
    } } }, ['移出']));
    li.appendChild(actions);
    return li;
  }

  function refreshTabsCount() {
    // 简单做法：整个面板 refresh
    refreshPanel();
  }

  // ---- 动作 ---------------------------------------------------------------
  async function doCopy(it) {
    const ok = await copyToClipboard(it.content);
    if (!ok) { toast('复制失败', false); return; }
    toast('已复制', true);
    // fire and forget
    apiPost('/api/copy', { source: 'barrage', id: it.id }).catch(() => {});
  }

  async function doSend(it) {
    const okClip = await copyToClipboard(it.content);
    const okSet = sendToDouyuChat(it.content);
    if (okSet) {
      toast('已填入弹幕框，按回车发送', true);
    } else if (okClip) {
      toast('未找到弹幕框，已复制到剪贴板', true);
    } else {
      toast('发送失败', false);
      return;
    }
    apiPost('/api/copy', { source: 'barrage', id: it.id }).catch(() => {});
  }

  function doFavorite(it) {
    const groups = state.favorites.order;
    let target = state.activeFavGroup;
    if (groups.length > 1) {
      const choice = prompt('收藏到哪个分组？\n' + groups.map((g, i) => (i + 1) + '. ' + g).join('\n') + '\n回车默认 = "' + target + '"');
      if (choice && choice.trim()) {
        const n = parseInt(choice, 10);
        if (n >= 1 && n <= groups.length) target = groups[n - 1];
        else if (groups.includes(choice.trim())) target = choice.trim();
      }
    }
    const arr = state.favorites.groups[target];
    if (!arr.includes(it.id)) {
      arr.push(it.id);
      saveFavorites(state.favorites);
      toast('已收藏到「' + target + '」', true);
    } else {
      toast('已经在「' + target + '」', false);
    }
    refreshTabsCount();
  }

  function doBlock(it) {
    state.blocked.add(it.id);
    saveBlocked(state.blocked);
    toast('已屏蔽 #' + it.id, true);
    renderLibBody();
  }

  // ---- 启动 ---------------------------------------------------------------
  function start() {
    if (document.getElementById('sb2099-toast') || document.querySelector('.sb2099-fab')) return; // 防重复
    injectStyle();
    renderRoot();
    // 启动时检查脚本版本（提示更新）
    apiGet('/api/userscript/version').then((r) => {
      const remote = (r && r.version) || null;
      if (remote && remote !== SCRIPT_VERSION) {
        console.info('[sb2099] new userscript version available:', remote, 'current:', SCRIPT_VERSION);
      }
    }).catch(() => {});
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
