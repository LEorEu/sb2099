// sb2099 Modern Frontend Controller & Interactions
// Handles copying, reporting, modal popups, homepage dynamic components, and local favorites.

(function () {
  'use strict';

  const STORAGE_KEY_FAVS = 'sb2099_favorites_v1';

  // ---- Toast System ----
  function toast(msg, ok) {
    let el = document.getElementById('sb-toast');
    if (!el) {
      el = document.createElement('div');
      el.id = 'sb-toast';
      document.body.appendChild(el);
    }
    el.textContent = msg;
    el.className = 'toast ' + (ok ? 'ok' : 'err');
    el.classList.add('show');
    clearTimeout(el._t);
    el._t = setTimeout(() => el.classList.remove('show'), 2200);
  }

  // ---- Withdraw Toast (60s window with countdown + click) ----
  function withdrawToast(barrageId, windowSec) {
    const total = Math.max(5, Math.min(300, parseInt(windowSec || 60, 10)));
    let el = document.getElementById('sb-withdraw-toast');
    if (!el) {
      el = document.createElement('div');
      el.id = 'sb-withdraw-toast';
      document.body.appendChild(el);
    }
    let remaining = total;
    let intervalId = null;
    function render() {
      el.innerHTML = `
        <span class="msg">投稿已发布</span>
        <button type="button" class="withdraw-btn">撤回 (${remaining}s)</button>
      `;
      el.querySelector('.withdraw-btn').addEventListener('click', async () => {
        clearInterval(intervalId);
        el.classList.remove('show');
        const r = await fetch(`/api/submission/${barrageId}/withdraw`, { method: 'DELETE' });
        if (r.ok) {
          toast('已撤回', true);
          setTimeout(() => location.reload(), 800);
        } else if (r.status === 410) {
          toast('撤回窗口已过期', false);
        } else {
          toast('撤回失败', false);
        }
      });
    }
    render();
    el.className = 'withdraw-toast show';
    intervalId = setInterval(() => {
      remaining -= 1;
      if (remaining <= 0) {
        clearInterval(intervalId);
        el.classList.remove('show');
        return;
      }
      const btn = el.querySelector('.withdraw-btn');
      if (btn) btn.textContent = `撤回 (${remaining}s)`;
    }, 1000);
  }

  // ---- User Picker Widget ----
  // 每个带 [data-user-picker] 的容器接管：搜索 /api/users/search、选中、清除、匿名切换。
  function wireUserPicker(root) {
    if (!root || root.dataset.wired === '1') return;
    root.dataset.wired = '1';
    const hidden = root.querySelector('input[name="submitter_uid"]');
    const trigger = root.querySelector('.user-picker-trigger');
    const placeholder = root.querySelector('.user-picker-placeholder');
    const chip = root.querySelector('.user-picker-chip');
    const chipAvatar = chip.querySelector('.user-picker-avatar');
    const chipName = chip.querySelector('.user-picker-name');
    const chipClear = chip.querySelector('.user-picker-clear');
    const searchBox = root.querySelector('.user-picker-search');
    const searchInput = root.querySelector('.user-picker-input');
    const resultsEl = root.querySelector('.user-picker-results');

    function clearPick() {
      hidden.value = '';
      chip.hidden = true;
      placeholder.hidden = false;
    }
    function pickUser(uid, nickname, avatar) {
      hidden.value = uid;
      chip.hidden = false;
      placeholder.hidden = true;
      chipName.textContent = nickname || `uid ${uid}`;
      if (avatar) {
        chipAvatar.src = avatar;
        chipAvatar.hidden = false;
      } else {
        chipAvatar.hidden = true;
      }
      searchBox.hidden = true;
      resultsEl.innerHTML = '';
      searchInput.value = '';
    }

    chipClear.addEventListener('click', (e) => {
      e.stopPropagation();
      clearPick();
    });

    trigger.addEventListener('click', () => {
      if (hidden.value) return; // 已选中状态点 trigger 不展开（避免误触）
      searchBox.hidden = !searchBox.hidden;
      if (!searchBox.hidden) searchInput.focus();
    });

    let debounceId = null;
    searchInput.addEventListener('input', () => {
      clearTimeout(debounceId);
      const q = searchInput.value.trim();
      if (q.length < 3) {
        resultsEl.innerHTML = '';
        return;
      }
      debounceId = setTimeout(async () => {
        try {
          const r = await getJSON(`/api/users/search?q=${encodeURIComponent(q)}`);
          const items = r.results || [];
          if (items.length === 0) {
            resultsEl.innerHTML = '<li class="empty">没找到匹配用户</li>';
            return;
          }
          resultsEl.innerHTML = '';
          items.forEach(u => {
            const li = document.createElement('li');
            li.className = 'user-result';
            li.innerHTML = `
              ${u.avatar ? `<img src="${u.avatar}" alt="">` : '<div class="no-avatar"></div>'}
              <span class="nick">${escapeHtml(u.nickname || '')}</span>
              <span class="uid">uid ${u.uid}</span>
            `;
            li.addEventListener('click', () => pickUser(u.uid, u.nickname, u.avatar));
            resultsEl.appendChild(li);
          });
        } catch (e) {
          resultsEl.innerHTML = '<li class="empty">搜索失败</li>';
        }
      }, 250);
    });
  }

  function escapeHtml(str) {
    return (str || '')
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
  }

  // ---- Fetch Utils ----
  async function getJSON(path) {
    const res = await fetch(path);
    if (!res.ok) throw new Error('API request failed');
    return await res.json();
  }

  async function postJSON(path, body) {
    const res = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const text = await res.text();
    let data;
    try { data = text ? JSON.parse(text) : null; } catch (_) { data = { raw: text }; }
    return { ok: res.ok, status: res.status, data };
  }

  async function copyText(text) {
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

  // ---- Local Favorites Store ----
  function loadFavorites() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY_FAVS);
      if (!raw) return { groups: { '默认': [] }, order: ['默认'] };
      return JSON.parse(raw);
    } catch (_) {
      return { groups: { '默认': [] }, order: ['默认'] };
    }
  }

  function saveFavorites(favs) {
    localStorage.setItem(STORAGE_KEY_FAVS, JSON.stringify(favs));
  }

  function addMemeToFavorite(id, groupName) {
    const favs = loadFavorites();
    if (!favs.groups[groupName]) {
      favs.groups[groupName] = [];
    }
    if (!favs.order.includes(groupName)) {
      favs.order.push(groupName);
    }
    if (favs.groups[groupName].includes(id)) {
      toast(`该条目已在收藏夹「${groupName}」中`, false);
      return false;
    }
    favs.groups[groupName].push(id);
    saveFavorites(favs);
    toast(`已成功收藏到「${groupName}」`, true);
    return true;
  }

  // ---- Modal Logic ----
  const modal = {
    overlay: null,
    title: null,
    form: null,
    textarea: null,
    modeInput: null,
    idInput: null,
    checkboxes: [],

    init() {
      this.overlay = document.getElementById('global-modal-overlay');
      if (!this.overlay) return;
      this.title = this.overlay.querySelector('.modal-title');
      this.form = this.overlay.querySelector('[data-form="modal-submit-form"]');
      this.textarea = this.overlay.querySelector('textarea[name="content"]');
      this.modeInput = this.overlay.querySelector('#modal-mode');
      this.idInput = this.overlay.querySelector('#modal-item-id');
      this.checkboxes = Array.from(this.overlay.querySelectorAll('input[name="tags"]'));

      // Close modal events
      const closes = this.overlay.querySelectorAll('[data-action="close-modal"]');
      closes.forEach(c => c.addEventListener('click', () => this.close()));
      this.overlay.addEventListener('click', (e) => {
        if (e.target === this.overlay) this.close();
      });
    },

    open(mode, options = {}) {
      if (!this.overlay) this.init();
      if (!this.overlay) return;

      this.modeInput.value = mode;
      this.idInput.value = options.id || '';
      
      // Reset checkboxes
      this.checkboxes.forEach(c => c.checked = false);

      if (mode === 'normal') {
        this.title.textContent = '投稿一条烂梗';
        this.textarea.value = '';
        this.textarea.removeAttribute('readonly');
        this.textarea.placeholder = '写点什么… (最大 255 字)';
      } else if (mode === 'promote') {
        this.title.textContent = '提升热门至投稿库';
        this.textarea.value = options.content || '';
        this.textarea.setAttribute('readonly', 'true');
      }

      this.overlay.classList.add('open');
    },

    close() {
      if (!this.overlay) return;
      this.overlay.classList.remove('open');
    }
  };

  // ---- Homepage Dynamic Loaders ----
  async function loadRandomMeme() {
    const card = document.getElementById('home-random-card');
    const textEl = document.getElementById('home-random-text');
    const refreshBtn = document.getElementById('home-random-refresh');
    if (!card || !textEl) return;

    try {
      const res = await getJSON('/api/random');
      const item = res.data;
      if (item) {
        textEl.textContent = item.content;
        card.dataset.id = item.id;
        card.dataset.content = item.content;
      } else {
        textEl.textContent = '暂无正式投稿';
      }
    } catch (e) {
      textEl.textContent = '加载随机梗失败，请检查服务连接';
    }
  }

  async function loadLatestPreviews() {
    const previewList = document.getElementById('home-latest-previews');
    if (!previewList) return;

    try {
      const res = await getJSON('/api/barrage?sort=new&page=1&size=5');
      const items = res.data?.list || [];
      previewList.innerHTML = '';

      if (items.length === 0) {
        const empty = document.createElement('p');
        empty.className = 'empty';
        empty.textContent = '暂无最新投稿。';
        previewList.appendChild(empty);
        return;
      }

      items.forEach(it => {
        const li = document.createElement('li');
        const submitterHtml = it.submitter
          ? `<span class="submitter-badge" title="由 ${escapeHtml(it.submitter.nickname || '')} 投稿">
               ${it.submitter.avatar ? `<img src="${it.submitter.avatar}" alt="">` : ''}
               <span>${escapeHtml(it.submitter.nickname || '')}</span>
             </span>`
          : '';
        li.innerHTML = `
          <div class="content">${escapeHtml(it.content)}</div>
          <div class="meta">
            <span>#${it.id}</span>
            <span>复制 ${it.cnt}</span>
            ${submitterHtml}
          </div>
          <div class="actions">
            <button class="primary" data-action="copy" data-source="barrage" data-id="${it.id}" data-content="${escapeHtml(it.content)}">一键复制</button>
          </div>
        `;
        previewList.appendChild(li);
      });
    } catch (e) {
      previewList.innerHTML = '<p class="empty" style="color:var(--error)">加载最新投稿预览失败</p>';
    }
  }

  // ---- Theme Toggle ----
  function toggleTheme() {
    const root = document.documentElement;
    const cur = root.getAttribute('data-theme') || 'dark';
    const next = cur === 'dark' ? 'light' : 'dark';
    root.setAttribute('data-theme', next);
    try { localStorage.setItem('sb2099-theme', next); } catch (e) {}
  }

  // ---- Global Actions Event Delegator ----
  document.addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-action]');
    if (!btn) return;
    const action = btn.dataset.action;

    if (action === 'toggle-theme') {
      e.preventDefault();
      toggleTheme();
      return;
    }

    const id = parseInt(btn.dataset.id, 10);
    const source = btn.dataset.source;
    const content = btn.dataset.content || '';

    // 1. Copy Action
    if (action === 'copy') {
      const ok = await copyText(content);
      if (!ok) { toast('复制失败', false); return; }
      const r = await postJSON('/api/copy', { source, id });
      if (r.ok) {
        toast('已成功复制到剪贴板！', true);
        // If it's the home random card, update the click count visual or reload home previews
        const countSpan = btn.closest('li')?.querySelector('.meta span:nth-child(2)');
        if (countSpan && countSpan.textContent.includes('复制')) {
          const current = parseInt(countSpan.textContent.replace('复制', '').trim(), 10) || 0;
          countSpan.textContent = `复制 ${current + 1}`;
        }
      } else if (r.status === 429) {
        toast('操作过于频繁，请稍后再试', false);
      } else {
        toast('复制成功', true);
      }
      return;
    }

    // 2. Report Action
    if (action === 'report') {
      if (!confirm('确认向管理员反馈此条烂梗“不合适”吗？\n（恶意举报可能会导致您的IP被封禁）')) return;
      const r = await postJSON('/api/barrage/report', { id });
      if (r.ok) {
        toast(r.data?.data?.duplicate ? '您已向管理员反馈过该条目' : '感谢反馈，已提交管理员审核', true);
      } else if (r.status === 429) {
        toast('反馈请求过于频繁，请稍后', false);
      } else {
        toast('反馈提交失败', false);
      }
      return;
    }

    // 3. Promote Action
    if (action === 'promote') {
      modal.open('promote', { id, content });
      return;
    }

    // 4. Trigger Modal Submission Form Open
    if (action === 'open-submit-modal') {
      modal.open('normal');
      return;
    }

    // 5. Main Site Local Favorites Manager
    if (action === 'favorite') {
      const favs = loadFavorites();
      const groups = favs.order;
      let targetGroup = '默认';

      if (groups.length > 1) {
        const choice = prompt(
          '请选择收藏分组序号或名称：\n' + 
          groups.map((g, idx) => `${idx + 1}. ${g}`).join('\n') + 
          `\n\n直接回车默认收藏到: "${targetGroup}"`
        );
        if (choice && choice.trim()) {
          const num = parseInt(choice, 10);
          if (num >= 1 && num <= groups.length) {
            targetGroup = groups[num - 1];
          } else if (groups.includes(choice.trim())) {
            targetGroup = choice.trim();
          } else {
            // Create a new group
            if (confirm(`分组「${choice.trim()}」不存在，是否创建新分组并收藏？`)) {
              targetGroup = choice.trim();
            } else {
              return;
            }
          }
        } else if (choice === null) {
          return; // Cancelled
        }
      }
      
      addMemeToFavorite(id, targetGroup);
      return;
    }
  });

  // ---- Page Submit Handlers ----
  document.addEventListener('submit', async (e) => {
    const form = e.target;
    const isMainForm = form.matches('[data-form="submit-barrage"]');
    const isModalForm = form.matches('[data-form="modal-submit-form"]');
    
    if (!isMainForm && !isModalForm) return;
    e.preventDefault();

    const fd = new FormData(form);
    const content = (fd.get('content') || '').toString().trim();
    const tags = Array.from(form.querySelectorAll('input[name="tags"]:checked')).map(i => i.value);

    if (!content) { toast('投稿内容不能为空！', false); return; }
    if (tags.length === 0) { toast('必须至少选择 1 个 Tag 标签', false); return; }

    // 收集 submitter_uid + 匿名选项（picker 在表单内时才有）
    const picker = form.querySelector('[data-user-picker]');
    let submitterUid = null;
    if (picker) {
      const uid = picker.querySelector('input[name="submitter_uid"]').value;
      const anon = picker.querySelector('input[name="anonymous"]').checked;
      if (uid && !anon) submitterUid = uid;
    }

    if (isMainForm || (isModalForm && document.getElementById('modal-mode').value === 'normal')) {
      // Normal Submission
      const r = await postJSON('/api/barrage', { content, tags, submitter_uid: submitterUid });
      if (r.ok) {
        const status = r.data?.data?.status;
        const newId = r.data?.data?.id;
        toast(status === 'pending' ? '投稿已提交，进入待审队列！' : '投稿提交成功，已正式入库！', true);
        // active 状态才弹撤回 toast（pending 稿等管理员决定，撤回意义不大）
        if (status === 'active' && newId) {
          withdrawToast(newId, 60);
        }
        form.reset();
        if (picker) {
          picker.querySelector('input[name="submitter_uid"]').value = '';
          picker.querySelector('.user-picker-chip').hidden = true;
          picker.querySelector('.user-picker-placeholder').hidden = false;
        }
        modal.close();
        // Dynamic reload components or reload page
        setTimeout(() => {
          if (document.getElementById('home-latest-previews')) {
            loadLatestPreviews();
          } else {
            location.reload();
          }
        }, 1000);
      } else if (r.status === 409) {
        toast('投稿库中已有相同文本内容，请勿重复提交', false);
      } else if (r.status === 422) {
        toast('内容命中了敏感词/屏蔽规则，系统已自动拒收', false);
      } else if (r.status === 429) {
        toast('投稿频繁，IP 限流（1 小时内最多投稿 5 条）', false);
      } else {
        toast('投稿提交失败：' + (r.data?.detail || '未知服务器错误'), false);
      }
    } else if (isModalForm && document.getElementById('modal-mode').value === 'promote') {
      // Promotion Mode
      const hotId = parseInt(document.getElementById('modal-item-id').value, 10);
      const r = await postJSON('/api/promote', { live_hot_id: hotId, tags, submitter_uid: submitterUid });
      if (r.ok) {
        const status = r.data?.data?.status;
        const newId = r.data?.data?.id;
        toast(status === 'pending' ? '已成功补充标签，待管理员审核入库！' : '已补充标签，正式合并入投稿库！', true);
        if (status === 'active' && newId) {
          withdrawToast(newId, 60);
        }
        form.reset();
        if (picker) {
          picker.querySelector('input[name="submitter_uid"]').value = '';
          picker.querySelector('.user-picker-chip').hidden = true;
          picker.querySelector('.user-picker-placeholder').hidden = false;
        }
        modal.close();
        setTimeout(() => location.reload(), 1000);
      } else if (r.status === 409) {
        toast('该弹幕早已被提升入库，请勿重复操作', false);
      } else if (r.status === 422) {
        toast('由于内容命中了降噪屏蔽词，提升入库失败', false);
      } else if (r.status === 429) {
        toast('提升入库操作过于频繁，请稍候', false);
      } else {
        toast('提升入库失败，请稍后重试', false);
      }
    }
  });

  // ---- Page Init ----
  function init() {
    modal.init();

    // Wire 所有静态投稿表单里的 user picker（home + modal）
    document.querySelectorAll('[data-user-picker]').forEach(wireUserPicker);

    // Check if on Home Page
    const isHomePage = document.getElementById('home-random-card') !== null;
    if (isHomePage) {
      loadRandomMeme();
      loadLatestPreviews();

      // Home Random Refresh Action
      const refreshBtn = document.getElementById('home-random-refresh');
      if (refreshBtn) {
        refreshBtn.addEventListener('click', async () => {
          const icon = refreshBtn.querySelector('.spin-icon');
          if (icon) {
            icon.style.transform = 'rotate(360deg)';
            setTimeout(() => icon.style.transform = 'rotate(0deg)', 600);
          }
          await loadRandomMeme();
        });
      }

      // Home Random Click-to-copy Action
      const randomCard = document.getElementById('home-random-card');
      if (randomCard) {
        randomCard.addEventListener('click', async (e) => {
          if (e.target.closest('#home-random-refresh')) return; // Avoid refresh trigger
          const content = randomCard.dataset.content;
          const id = parseInt(randomCard.dataset.id, 10);
          if (!content) return;
          const ok = await copyText(content);
          if (!ok) { toast('复制失败', false); return; }
          const r = await postJSON('/api/copy', { source: 'barrage', id });
          if (r.ok) toast('随机梗已成功复制到剪贴板！', true);
          else toast('复制成功', true);
        });
      }
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
