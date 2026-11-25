(function () {
  var root = document.documentElement;

  /* Light / dark switch. Remembers the choice in this browser when it can. */
  var tbtn = document.getElementById('theme-toggle');
  function isDark() {
    var t = root.getAttribute('data-theme');
    if (t) return t === 'dark';
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  }
  function labelTheme() { if (tbtn) tbtn.textContent = isDark() ? 'Light theme' : 'Dark theme'; }
  try {
    var saved = localStorage.getItem('theme');
    if ((saved === 'dark' || saved === 'light') && !root.getAttribute('data-theme')) root.setAttribute('data-theme', saved);
  } catch (e) {}
  labelTheme();
  if (tbtn) tbtn.addEventListener('click', function () {
    var next = isDark() ? 'light' : 'dark';
    root.setAttribute('data-theme', next);
    try { localStorage.setItem('theme', next); } catch (e) {}
    labelTheme();
  });

  var pbtn = document.getElementById('print-cv');
  if (pbtn) pbtn.addEventListener('click', function () { window.print(); });

  /* On narrow screens the timeline scrolls: start at the most recent years */
  var tl = document.querySelector('.tl-scroll');
  if (tl) tl.scrollLeft = tl.scrollWidth;

  /* Publication filters */
  var filters = document.getElementById('filters');
  var shown = document.getElementById('pub-shown');
  function applyFilter(f) {
    var pubs = document.querySelectorAll('#publications .pub');
    var n = 0;
    pubs.forEach(function (li) {
      var ok = f === 'all' ||
        (f === 'pre' && li.dataset.pre === '1') ||
        (f === 'lead' && li.dataset.lead === '1') ||
        (f.indexOf('thread:') === 0 && li.dataset.thread === f.slice(7));
      li.hidden = !ok;
      if (ok) n++;
    });
    document.querySelectorAll('#publications .year-group').forEach(function (g) {
      g.hidden = !g.querySelector('.pub:not([hidden])');
    });
    if (shown) shown.textContent = f === 'all' ? '' : 'Showing ' + n + ' of ' + pubs.length + '. ';
  }
  if (filters) filters.addEventListener('click', function (e) {
    var b = e.target.closest('button[data-f]');
    if (!b) return;
    filters.querySelectorAll('button').forEach(function (x) { x.setAttribute('aria-pressed', x === b ? 'true' : 'false'); });
    applyFilter(b.dataset.f);
  });

  /* Highlight the current section in the menu */
  var nav = document.getElementById('jump');
  if (nav && 'IntersectionObserver' in window) {
    var links = {};
    nav.querySelectorAll('a').forEach(function (a) { links[a.getAttribute('href').slice(1)] = a; });
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        Object.keys(links).forEach(function (id) {
          if (id === en.target.id) links[id].setAttribute('aria-current', 'true');
          else links[id].removeAttribute('aria-current');
        });
      });
    }, { rootMargin: '-20% 0px -70% 0px' });
    Object.keys(links).forEach(function (id) { var s = document.getElementById(id); if (s) io.observe(s); });
  }

  /* Interactive map: nearest city to the pointer */
  var svg = document.getElementById('map');
  var info = document.getElementById('map-info');
  var dataEl = document.getElementById('map-data');
  if (svg && info && dataEl) {
    var cities = [];
    try { cities = JSON.parse(dataEl.textContent); } catch (e) {}
    var ring = document.getElementById('map-ring');
    var hint = info.innerHTML;
    var pinned = -1, current = -1;
    function text(tag, cls, s) { var el = document.createElement(tag); el.className = cls; el.textContent = s; return el; }
    function show(i) {
      if (i === current) return;
      current = i;
      if (i < 0) { info.innerHTML = hint; ring.setAttribute('cx', -99); ring.setAttribute('cy', -99); return; }
      var c = cities[i];
      ring.setAttribute('cx', c.x); ring.setAttribute('cy', c.y);
      info.textContent = '';
      info.appendChild(text('span', 'mi-city', c.c + ', ' + c.k));
      info.appendChild(text('span', 'mi-n', c.n + (c.n === 1 ? ' shared record' : ' shared records')));
      if (c.p && c.p.length) info.appendChild(text('span', 'mi-people', c.p.join(', ')));
      info.appendChild(text('span', 'mi-inst', c.i.join(' · ')));
    }
    function nearest(evt) {
      var m = svg.getScreenCTM();
      if (!m) return -1;
      var p = svg.createSVGPoint();
      p.x = evt.clientX; p.y = evt.clientY;
      p = p.matrixTransform(m.inverse());
      var best = -1, bd = 18 * 18;
      for (var i = 0; i < cities.length; i++) {
        var dx = cities[i].x - p.x, dy = cities[i].y - p.y, d = dx * dx + dy * dy;
        if (d < bd) { bd = d; best = i; }
      }
      return best;
    }
    svg.addEventListener('pointermove', function (e) {
      if (e.pointerType === 'touch') return;
      var i = nearest(e);
      show(i >= 0 ? i : pinned);
    });
    svg.addEventListener('pointerleave', function () { show(pinned); });
    svg.addEventListener('click', function (e) { pinned = nearest(e); current = -2; show(pinned); });
  }
})();
