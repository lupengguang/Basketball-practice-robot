/* 训练体系详情页共用交互:光标 / 导航滚动态 / 显现 / 3D 倾斜 */
(function () {
  var dot = document.querySelector('.cursor-dot');
  var ring = document.querySelector('.cursor-ring');
  var mx = innerWidth / 2, my = innerHeight / 2, rx = mx, ry = my;
  if (dot && ring) {
    addEventListener('mousemove', function (e) {
      mx = e.clientX; my = e.clientY;
      dot.style.left = mx + 'px'; dot.style.top = my + 'px';
    });
    (function loop() {
      rx += (mx - rx) * .14; ry += (my - ry) * .14;
      ring.style.left = rx + 'px'; ring.style.top = ry + 'px';
      requestAnimationFrame(loop);
    })();
    document.querySelectorAll('a,button,.drill,.dt-coach,.sw-card').forEach(function (el) {
      el.addEventListener('mouseenter', function () { ring.classList.add('hovering'); });
      el.addEventListener('mouseleave', function () { ring.classList.remove('hovering'); });
    });
  }

  var nav = document.getElementById('nav');
  if (nav) addEventListener('scroll', function () {
    nav.classList.toggle('scrolled', scrollY > 40);
  }, { passive: true });

  var io = new IntersectionObserver(function (es) {
    es.forEach(function (e) {
      if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); }
    });
  }, { threshold: .12 });
  document.querySelectorAll('.reveal').forEach(function (el) { io.observe(el); });

  var fine = matchMedia('(hover:hover) and (min-width:1001px)').matches;
  document.querySelectorAll('[data-tilt]').forEach(function (card) {
    if (!fine) return;
    card.addEventListener('mousemove', function (e) {
      var r = card.getBoundingClientRect();
      var x = (e.clientX - r.left) / r.width - .5;
      var y = (e.clientY - r.top) / r.height - .5;
      card.style.transform = 'perspective(1000px) rotateY(' + (x * 7) + 'deg) rotateX(' + (-y * 7) + 'deg) translateY(-8px)';
    });
    card.addEventListener('mouseleave', function () {
      card.style.transform = 'perspective(1000px) rotateY(0) rotateX(0) translateY(0)';
    });
  });

  /* 训练要点横向轮播(首尾克隆无缝循环) */
  var wc = document.getElementById('drillCarousel');
  if (wc) {
    var track = document.getElementById('drillTrack');
    var dots  = wc.querySelectorAll('#drillDots i');
    var prev  = document.getElementById('drillPrev');
    var next  = document.getElementById('drillNext');
    var real  = [].slice.call(track.querySelectorAll('.drill'));
    var gap   = 22;
    var slideW = real[0].offsetWidth + gap;
    var idx = 0, isAnim = false, timer = null;
    var total = real.length;

    // 首尾克隆
    var firstClone = real[0].cloneNode(true); firstClone.classList.add('clone');
    var lastClone  = real[total - 1].cloneNode(true); lastClone.classList.add('clone');
    track.appendChild(firstClone);
    track.insertBefore(lastClone, real[0]);
    track.style.transition = 'none';
    track.style.transform = 'translateX(' + (-slideW) + 'px)';
    void track.offsetWidth;
    track.style.transition = '';

    function updateDots() {
      for (var i = 0; i < dots.length; i++) dots[i].classList.toggle('on', i === idx);
    }
    function resetPos(i) {
      idx = i;
      track.style.transition = 'none';
      track.style.transform = 'translateX(' + (-(idx + 1) * slideW) + 'px)';
      void track.offsetWidth;
      track.style.transition = '';
      updateDots();
    }
    function go(dir) {
      if (isAnim) return;
      isAnim = true;
      idx = (idx + dir + total) % total;
      track.style.transform = 'translateX(' + (-(idx + 1) * slideW) + 'px)';
      updateDots();
      setTimeout(function () {
        if ((dir === -1 && idx === 0) || (dir === 1 && idx === total - 1)) {
          var target = dir === -1 ? (-(total * slideW)) : (-slideW);
          track.style.transition = 'none';
          track.style.transform = 'translateX(' + target + 'px)';
          void track.offsetWidth;
          track.style.transition = '';
        }
        isAnim = false;
      }, 760);
    }

    prev.addEventListener('click', function () { go(-1); auto(); });
    next.addEventListener('click', function () { go(1);  auto(); });
    for (var i = 0; i < dots.length; i++) {
      (function (j) { dots[j].addEventListener('click', function () { resetPos(j); auto(); }); })(i);
    }

    // 触摸/鼠标拖拽
    var startX = null;
    track.addEventListener('touchstart', function (e) { startX = e.touches[0].clientX; clearInterval(timer); }, { passive: true });
    track.addEventListener('touchend', function (e) {
      if (startX !== null) {
        var dx = e.changedTouches[0].clientX - startX;
        if (Math.abs(dx) > 50) go(dx < 0 ? 1 : -1);
        startX = null; auto();
      }
    });
    var dragX = null;
    track.addEventListener('mousedown', function (e) { dragX = e.clientX; clearInterval(timer); });
    document.addEventListener('mouseup', function (e) {
      if (dragX !== null) {
        var dx = e.clientX - dragX;
        if (Math.abs(dx) > 60) go(dx < 0 ? 1 : -1);
        dragX = null; auto();
      }
    });

    function auto() { clearInterval(timer); timer = setInterval(function () { go(1); }, 4500); }
    auto();

    wc.addEventListener('mouseenter', function () { clearInterval(timer); });
    wc.addEventListener('mouseleave', auto);

    // 响应式重算
    addEventListener('resize', function () {
      slideW = real[0].offsetWidth + gap;
      track.style.transition = 'none';
      track.style.transform = 'translateX(' + (-(idx + 1) * slideW) + 'px)';
      void track.offsetWidth; track.style.transition = '';
    });
  }
})();
