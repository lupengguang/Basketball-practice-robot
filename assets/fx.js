/* ============================================================
   fx.js —— 全站共享动效脚本
   卡片点击/悬停水波纹:对命中的卡片元素自动补 .ripple-host,
   点击时在点击坐标生成 span.ripple,动画结束后移除。
   ============================================================ */
(function () {
  'use strict';

  /* 各页面实际存在的卡片 class 通用选择器 */
  var CARD_SELECTORS = [
    '.drill', '.gcard', '.dt-coach', '.sw-card', '.star',
    '.kcard', '.ai-card', '.players-card', '.board-card', '.score-card', '.term-card',
    '.card', '.wf-card', '.tilt-card', '.ticket',
    '.out-card', '.duel-card', '.step', '.trio-card', '.panel',
    '.today-card', '.signal-card', '.metric-card',
    '.story-card', '.file-card', '.skill-panel', '.skill-detail',
    '.film', '.tile', '.glass', '.kpi', '.m-card'
  ];
  var CARD_QUERY = CARD_SELECTORS.join(',');

  /* 自动补 ripple-host:已有 position 非 static 时只加 overflow:hidden */
  function makeHost(el) {
    if (el.dataset.fxHost) return;
    el.dataset.fxHost = '1';
    var pos = getComputedStyle(el).position;
    if (pos === 'static') {
      el.classList.add('ripple-host');
    } else if (getComputedStyle(el).overflow === 'visible') {
      el.style.overflow = 'hidden';
    }
  }

  function spawnRipple(host, x, y, small) {
    var rect = host.getBoundingClientRect();
    var d = Math.min(rect.width, rect.height) * 1.2;
    var r = document.createElement('span');
    r.className = 'ripple' + (small ? ' ripple-sm' : '');
    r.style.width = r.style.height = d + 'px';
    r.style.left = (x - rect.left - d / 2) + 'px';
    r.style.top = (y - rect.top - d / 2) + 'px';
    host.appendChild(r);
    r.addEventListener('animationend', function () { r.remove(); }, { once: true });
    /* 兜底:动画事件未触发时定时移除 */
    setTimeout(function () { if (r.parentNode) r.remove(); }, 1200);
  }

  document.addEventListener('click', function (e) {
    var card = e.target.closest ? e.target.closest(CARD_QUERY) : null;
    if (!card) return;
    makeHost(card);
    spawnRipple(card, e.clientX, e.clientY, false);
  }, { passive: true });

  /* hover 进入时触发一次小号波纹 */
  var lastHover = new WeakMap();
  document.addEventListener('mouseover', function (e) {
    var card = e.target.closest ? e.target.closest(CARD_QUERY) : null;
    if (!card) return;
    var now = Date.now();
    if (now - (lastHover.get(card) || 0) < 900) return;
    lastHover.set(card, now);
    makeHost(card);
    var rect = card.getBoundingClientRect();
    spawnRipple(card, rect.left + rect.width / 2, rect.top + rect.height / 2, true);
  }, { passive: true });
})();
