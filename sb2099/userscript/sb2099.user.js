// ==UserScript==
// @name         sb2099 - 斗鱼 2099 烂梗发送器
// @namespace    https://github.com/LEorEu/sb2099
// @version      0.5.0
// @description  在斗鱼 2099 房间页面内嵌入烂梗库面板：搜索 / 单条复制 / 一键发送，收藏夹可从主站导入
// @author       sb2099.cn
// @match        https://www.douyu.com/*
// @match        https://www.douyu.com
// @match        https://www.douyu.com/room/*
// @include      https://*.douyu.com/*
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
  const API_BASE = 'https://www.sb2099.cn';
  const SCRIPT_VERSION = '0.5.0';
  const STORAGE_KEY_FAVS = 'sb2099_favorites_v1'; // 与主站收藏夹同一 key/结构，可互通

  // ---- 工具：API 调用 -----------------------------------------------------
  function apiGet(path) {
    return new Promise((resolve, reject) => {
      if (typeof GM_xmlhttpRequest === 'function') {
        GM_xmlhttpRequest({
          method: 'GET',
          url: API_BASE + path,
          timeout: 8000,
          onload: (r) => {
            try { resolve(JSON.parse(r.responseText)); }
            catch (e) { reject(new Error('bad json: ' + e)); }
          },
          onerror: () => reject(new Error('network error')),
          ontimeout: () => reject(new Error('timeout')),
        });
      } else {
        fetch(API_BASE + path).then((r) => r.json()).then(resolve, reject);
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
    } catch (_) { return fallback; }
  }

  function saveJSON(key, value) {
    const s = JSON.stringify(value);
    if (typeof GM_setValue === 'function') GM_setValue(key, s);
    else localStorage.setItem(key, s);
  }

  // 收藏结构：{ groups: { name: [ids...] }, order: [name1, ...] }（与主站一致）
  function loadFavorites() {
    return loadJSON(STORAGE_KEY_FAVS, { groups: { '默认': [] }, order: ['默认'] });
  }
  function saveFavorites(f) { saveJSON(STORAGE_KEY_FAVS, f); }

  // ---- 复制 ---------------------------------------------------------------
  async function copyToClipboard(text) {
    if (typeof GM_setClipboard === 'function') { GM_setClipboard(text, 'text'); return true; }
    if (navigator.clipboard && window.isSecureContext) {
      try { await navigator.clipboard.writeText(text); return true; } catch (_) {}
    }
    const ta = document.createElement('textarea');
    ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.select();
    let ok = false;
    try { ok = document.execCommand('copy'); } catch (_) {}
    document.body.removeChild(ta);
    return ok;
  }

  // ---- 发送到斗鱼弹幕框 ---------------------------------------------------
  // 关键：斗鱼弹幕框是 .ChatSend-txt（contenteditable div，不是 textarea），且可能在 shadow DOM 里。
  // 必须穿透 shadow DOM 查找，并用 innerText 赋值——这正是之前“未找到弹幕框”的原因。
  function querySelectorDeep(selector, root) {
    root = root || document;
    const found = root.querySelector(selector);
    if (found) return found;
    const all = root.querySelectorAll('*');
    for (const el of all) {
      if (el.shadowRoot) {
        const f = querySelectorDeep(selector, el.shadowRoot);
        if (f) return f;
      }
    }
    return null;
  }

  function fillDouyuInput(text) {
    const input =
      querySelectorDeep('.ChatSend-txt') ||
      querySelectorDeep('textarea[placeholder*="弹幕"]') ||
      querySelectorDeep('textarea[placeholder*="聊天"]');
    if (!input) return null;
    input.focus();
    const tag = input.tagName;
    if (tag === 'TEXTAREA' || tag === 'INPUT') {
      const proto = tag === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
      const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
      setter.call(input, text);
    } else {
      input.innerText = text; // contenteditable div
    }
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
    return input;
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
    q: '',
    page: 1,
    size: 20,
    activeTab: 'lib', // lib | fav
    activeFavGroup: '默认',
    libResult: { list: [], total: 0, last_page: true },
    favorites: loadFavorites(),
  };

  // ---- 样式 ---------------------------------------------------------------
  const STYLE = `
  /* 悬浮启动按钮：贴右侧、偏下，竖排——避开 sb6657（聊天工具栏按钮 + 右上浮窗） */
  .sb2099-fab {
    position: fixed; right: 0; top: 64%; transform: translateY(-50%);
    padding: 9px 8px; border-radius: 10px 0 0 10px;
    background: #ff5d5d; color: #fff; font-weight: 800; font-size: 12px;
    letter-spacing: .5px; writing-mode: vertical-rl; text-orientation: mixed;
    cursor: pointer; z-index: 2147483000;
    box-shadow: -2px 2px 10px rgba(0,0,0,.3);
    border: none; line-height: 1; opacity: .9;
  }
  .sb2099-fab:hover { background: #ff3d3d; opacity: 1; padding-right: 11px; }

  /* 浮动可拖拽小窗：默认在右下角弹出，不挡聊天主区 */
  .sb2099-panel {
    position: fixed; right: 14px; bottom: 64px;
    width: 340px; max-width: 92vw; max-height: 70vh;
    background: #fff; color: #1a1a1a;
    border: 1px solid #e5e5e5; border-radius: 12px;
    box-shadow: 0 10px 30px rgba(0,0,0,.22);
    z-index: 2147483001;
    display: none; flex-direction: column; overflow: hidden;
    font: 13px/1.5 -apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
  }
  .sb2099-panel * { box-sizing: border-box; }

  .sb2099-head {
    display: flex; align-items: center; gap: 8px;
    padding: 9px 12px; border-bottom: 1px solid #eee;
    cursor: move; user-select: none; background: #fafafa;
    border-radius: 12px 12px 0 0;
  }
  .sb2099-head .title { font-weight: 600; font-size: 14px; flex: 1; }
  .sb2099-head .ver { color: #999; font-size: 11px; }
  .sb2099-head .close { background: transparent; border: none; cursor: pointer; font-size: 18px; color: #666; }

  .sb2099-tabs { display: flex; border-bottom: 1px solid #eee; }
  .sb2099-tabs button {
    flex: 1; background: transparent; border: none; padding: 10px;
    font-size: 13px; color: #666; cursor: pointer; border-bottom: 2px solid transparent;
  }
  .sb2099-tabs button.active { color: #ff5252; border-bottom-color: #ff5252; font-weight: 500; }

  .sb2099-body { flex: 1; overflow-y: auto; padding: 10px 14px; }

  .sb2099-filters .row { display: flex; gap: 6px; margin-bottom: 8px; }
  .sb2099-filters input.q { flex: 1; padding: 6px 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 13px; min-width: 0; }
  .sb2099-filters .sbtn { background: #4caf50; color: #fff; border: none; border-radius: 4px; font-size: 13px; padding: 4px 12px; cursor: pointer; white-space: nowrap; }
  .sb2099-filters .clear { background: transparent; border: 1px solid #ddd; border-radius: 4px; font-size: 12px; padding: 4px 8px; color: #666; cursor: pointer; white-space: nowrap; }

  .sb2099-fav-tools { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; flex-wrap: wrap; }
  .sb2099-fav-tools button { background: #ff5252; color: #fff; border: none; border-radius: 4px; padding: 4px 10px; font-size: 12px; cursor: pointer; }
  .sb2099-fav-tools .note { color: #999; font-size: 11px; }
  .sb2099-fav-groups { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 10px; }
  .sb2099-fav-groups .gchip { padding: 3px 8px; background: #f3f4f6; border-radius: 4px; font-size: 12px; cursor: pointer; user-select: none; border: 1px solid transparent; }
  .sb2099-fav-groups .gchip.active { background: #ff5252; color: #fff; border-color: #ff5252; }

  .sb2099-list { list-style: none; padding: 0; margin: 0; }
  .sb2099-list li { display: flex; align-items: flex-start; gap: 8px; padding: 7px 0; border-bottom: 1px solid #f0f0f0; }
  .sb2099-list .content { flex: 1; white-space: pre-wrap; word-break: break-word; font-size: 13px; cursor: pointer; }
  .sb2099-list li:hover .content { color: #ff5252; }
  .sb2099-list .send { flex-shrink: 0; background: #ff5722; color: #fff; border: none; padding: 3px 12px; border-radius: 5px; font-size: 12px; cursor: pointer; }
  .sb2099-list .send:hover { background: #f4511e; }

  .sb2099-pager { display: flex; justify-content: center; align-items: center; gap: 12px; padding: 12px 0; color: #999; font-size: 12px; }
  .sb2099-pager button { background: transparent; border: 1px solid #ddd; border-radius: 4px; padding: 3px 12px; cursor: pointer; color: #666; font-size: 12px; }
  .sb2099-pager button:disabled { opacity: .4; cursor: not-allowed; }

  .sb2099-empty, .sb2099-loading { color: #999; padding: 20px 0; text-align: center; font-size: 12px; }

  .sb2099-toast {
    position: fixed; left: 50%; bottom: 80px;
    transform: translateX(-50%) translateY(20px);
    padding: 6px 14px; border-radius: 4px; font-size: 13px;
    color: #fff; background: #333; opacity: 0;
    transition: opacity .2s, transform .2s; pointer-events: none; z-index: 2147483002;
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
        else if (k === 'on') { for (const ev in attrs[k]) e.addEventListener(ev, attrs[k][ev]); }
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
    const fab = el('button', { class: 'sb2099-fab', title: 'sb2099 烂梗库（点击开/关）' }, ['🐹 sb2099']);
    fab.addEventListener('click', togglePanel);
    document.body.appendChild(fab);

    $panel = el('div', { class: 'sb2099-panel' });
    document.body.appendChild($panel);
    refreshPanel();
    enableDrag($panel);
    setPanelOpen(false); // 进页面默认关闭，点悬浮按钮再显示
  }

  function setPanelOpen(open) { $panel.style.display = open ? 'flex' : 'none'; }
  function togglePanel() { setPanelOpen(getComputedStyle($panel).display === 'none'); }

  // 拖拽：按住标题栏移动整个面板
  function enableDrag(panel) {
    let dragging = false, ox = 0, oy = 0;
    panel.addEventListener('pointerdown', (e) => {
      const head = e.target.closest && e.target.closest('.sb2099-head');
      if (!head || !panel.contains(head)) return;
      if (e.target.closest('button')) return;
      dragging = true;
      const r = panel.getBoundingClientRect();
      ox = e.clientX - r.left; oy = e.clientY - r.top;
      panel.style.left = r.left + 'px'; panel.style.top = r.top + 'px';
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
    if (state.activeTab === 'lib') renderLibBody();
    else renderFavBody();
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
      }, ['烂梗库']),
      el('button', {
        class: state.activeTab === 'fav' ? 'active' : '',
        on: { click: () => { state.activeTab = 'fav'; refreshPanel(); } },
      }, ['收藏 (' + totalFavorites() + ')']),
    ]);
  }

  function totalFavorites() {
    return Object.values(state.favorites.groups).reduce((acc, arr) => acc + arr.length, 0);
  }

  // 单条：正文（点击复制）+ 发送
  function renderItem(it) {
    const li = el('li');
    li.appendChild(el('div', {
      class: 'content', title: '点击复制',
      on: { click: () => doCopy(it) },
    }, [it.content]));
    li.appendChild(el('button', {
      class: 'send',
      on: { click: (e) => { e.stopPropagation(); doSend(it); } },
    }, ['发送']));
    return li;
  }

  // ---- 烂梗库 tab ---------------------------------------------------------
  async function renderLibBody() {
    $body.innerHTML = '';
    $body.appendChild(renderFilters());

    const loader = el('div', { class: 'sb2099-loading' }, ['加载中…']);
    $body.appendChild(loader);
    try {
      const path = '/api/barrage?sort=new'
        + (state.q ? '&q=' + encodeURIComponent(state.q) : '')
        + '&page=' + state.page + '&size=' + state.size;
      const r = await apiGet(path);
      state.libResult = (r && r.data) || { list: [], total: 0, last_page: true };
    } catch (e) {
      state.libResult = { list: [], total: 0, last_page: true };
      toast('加载失败，检查 sb2099 服务地址', false);
    }
    loader.remove();

    const items = state.libResult.list || [];
    if (items.length === 0) {
      $body.appendChild(el('div', { class: 'sb2099-empty' }, ['空结果。']));
    } else {
      const ul = el('ul', { class: 'sb2099-list' });
      items.forEach((it) => ul.appendChild(renderItem(it)));
      $body.appendChild(ul);
    }
    $body.appendChild(renderPager());
  }

  function renderFilters() {
    const wrap = el('div', { class: 'sb2099-filters' });
    const row = el('div', { class: 'row' });
    const input = el('input', { class: 'q', type: 'text', placeholder: '搜索烂梗…', value: state.q });
    const search = () => { state.q = input.value.trim(); state.page = 1; renderLibBody(); };
    input.addEventListener('keydown', (e) => { if (e.key === 'Enter') search(); });
    row.appendChild(input);
    row.appendChild(el('button', { class: 'sbtn', on: { click: search } }, ['搜索']));
    row.appendChild(el('button', { class: 'clear', on: { click: () => {
      state.q = ''; state.page = 1; renderLibBody();
    } } }, ['清空筛选']));
    wrap.appendChild(row);
    return wrap;
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

  // ---- 收藏 tab（只读：导入 + 分组 + 列表，增删导出都回主站）---------------
  function renderFavBody() {
    $body.innerHTML = '';
    $body.appendChild(renderFavTools());
    $body.appendChild(renderFavGroups());

    const ids = state.favorites.groups[state.activeFavGroup] || [];
    if (ids.length === 0) {
      $body.appendChild(el('div', { class: 'sb2099-empty' }, ['本分组还没有收藏，去主站收藏后「导出」再来这里「导入」。']));
      return;
    }

    const loader = el('div', { class: 'sb2099-loading' }, ['加载中…']);
    $body.appendChild(loader);
    fetchFavoriteEntries(ids).then((items) => {
      loader.remove();
      if (items.length === 0) {
        $body.appendChild(el('div', { class: 'sb2099-empty' }, ['没取到内容（可能已下架）']));
        return;
      }
      const ul = el('ul', { class: 'sb2099-list' });
      items.forEach((it) => ul.appendChild(renderItem(it)));
      $body.appendChild(ul);
    }).catch(() => {
      loader.remove();
      $body.appendChild(el('div', { class: 'sb2099-empty' }, ['加载失败']));
    });
  }

  function renderFavTools() {
    const wrap = el('div', { class: 'sb2099-fav-tools' });
    wrap.appendChild(el('button', { on: { click: () => {
      const text = prompt('粘贴主站收藏夹「导出」的 JSON：');
      if (!text) return;
      try {
        const data = JSON.parse(text);
        if (!data.groups || !data.order) throw new Error('bad structure');
        state.favorites = data;
        saveFavorites(data);
        state.activeFavGroup = data.order[0] || '默认';
        refreshPanel();
        toast('导入完成', true);
      } catch (e) {
        toast('JSON 解析失败', false);
      }
    } } }, ['⬇ 从主站导入']));
    wrap.appendChild(el('span', { class: 'note' }, ['新建/移动/导出请到主站收藏夹']));
    return wrap;
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

  async function fetchFavoriteEntries(ids) {
    if (!ids.length) return [];
    try {
      const r = await apiGet('/api/barrage/by-ids?ids=' + ids.join(','));
      const list = (r && r.data) || [];
      const map = new Map(list.map((it) => [it.id, it]));
      return ids.map((id) => map.get(id)).filter(Boolean);
    } catch (_) {
      return [];
    }
  }

  // ---- 动作 ---------------------------------------------------------------
  async function doCopy(it) {
    const ok = await copyToClipboard(it.content);
    toast(ok ? '已复制' : '复制失败', ok);
    if (ok) apiPost('/api/copy', { source: 'barrage', id: it.id }).catch(() => {});
  }

  let _sendCd = false;
  async function doSend(it) {
    if (_sendCd) { toast('发送冷却中，稍等几秒', false); return; }
    const input = fillDouyuInput(it.content);
    if (!input) {
      const ok = await copyToClipboard(it.content);
      toast(ok ? '未找到弹幕框，已复制到剪贴板' : '未找到弹幕框', false);
      return;
    }
    const sendBtn = querySelectorDeep('.ChatSend-button');
    if (sendBtn) {
      _sendCd = true;
      setTimeout(() => {
        sendBtn.click();
        toast('已发送', true);
        setTimeout(() => { _sendCd = false; }, 5000); // 防刷屏冷却
      }, 60);
    } else {
      toast('已填入弹幕框，按回车发送', true);
    }
    apiPost('/api/copy', { source: 'barrage', id: it.id }).catch(() => {});
  }

  // ---- 启动 ---------------------------------------------------------------
  function start() {
    if (document.getElementById('sb2099-toast') || document.querySelector('.sb2099-fab')) return; // 防重复
    injectStyle();
    renderRoot();
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
