// sb2099 极简前端交互：复制、不合适、入库提升、投稿提交。无构建链。

(function () {
  'use strict';

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

  document.addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-action]');
    if (!btn) return;
    const action = btn.dataset.action;
    const id = parseInt(btn.dataset.id, 10);
    const source = btn.dataset.source;
    const content = btn.dataset.content || '';

    if (action === 'copy') {
      const ok = await copyText(content);
      if (!ok) { toast('复制失败', false); return; }
      const r = await postJSON('/api/copy', { source, id });
      if (r.ok) toast('已复制', true);
      else if (r.status === 429) toast('复制太频繁，稍后再试', false);
      else toast('复制成功（计数失败）', true);
      return;
    }

    if (action === 'report') {
      if (!confirm('确认对此条投稿反馈"不合适"？')) return;
      const r = await postJSON('/api/barrage/report', { id });
      if (r.ok) toast(r.data?.data?.duplicate ? '已反馈过' : '已反馈', true);
      else if (r.status === 429) toast('反馈过于频繁', false);
      else if (r.status === 404) toast('条目不存在', false);
      else toast('反馈失败', false);
      return;
    }

    if (action === 'promote') {
      const tagsRaw = prompt('给这条投稿打 tag（逗号分隔的 value，例如 00,02）：', '99');
      if (!tagsRaw) return;
      const tags = tagsRaw.split(',').map(s => s.trim()).filter(Boolean);
      const r = await postJSON('/api/promote', { live_hot_id: id, tags });
      if (r.ok) toast('已加入投稿库', true);
      else if (r.status === 409) toast('已在投稿库', false);
      else if (r.status === 429) toast('入库太频繁', false);
      else if (r.status === 422) toast('内容被屏蔽词命中，无法入库', false);
      else toast('入库失败', false);
      return;
    }
  });

  // 投稿表单
  document.addEventListener('submit', async (e) => {
    const form = e.target;
    if (!form.matches('[data-form="submit-barrage"]')) return;
    e.preventDefault();
    const fd = new FormData(form);
    const content = (fd.get('content') || '').toString().trim();
    const tags = Array.from(form.querySelectorAll('input[name="tags"]:checked')).map(i => i.value);
    if (!content) { toast('内容为空', false); return; }
    if (tags.length === 0) { toast('至少选一个 tag', false); return; }
    const r = await postJSON('/api/barrage', { content, tags });
    if (r.ok) {
      const status = r.data?.data?.status;
      toast(status === 'pending' ? '已提交，待审核' : '已提交', true);
      form.reset();
      setTimeout(() => location.reload(), 600);
    } else if (r.status === 409) {
      toast('投稿库已有相同内容', false);
    } else if (r.status === 422) {
      toast('包含违禁内容，请修改', false);
    } else if (r.status === 429) {
      toast('投稿太频繁，1 小时内最多 5 条', false);
    } else if (r.status === 400) {
      toast('内容/tag 不符合要求：' + (r.data?.detail || ''), false);
    } else {
      toast('投稿失败', false);
    }
  });
})();
