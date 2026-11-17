// WanderFolk start page: the moving range and lake, the road and campervan, the "try it" preview, and the start / join forms.

const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
const tripUrl = (id) => `/trip/?trip=${encodeURIComponent(id)}`;

// ---------- the bar turns solid once the sky has scrolled away ----------
const bar = document.getElementById('bar');
const hero = document.querySelector('.hero');
const onScrollBar = () => bar.classList.toggle('is-solid', scrollY > hero.offsetHeight - 80);
addEventListener('scroll', onScrollBar, { passive: true });
onScrollBar();

// ---------- depth: the ranges shift with the pointer, and drift apart as you scroll ----------
const ranges = [...document.querySelectorAll('.range')];
if (!reduced) {
  let px = 0, py = 0, tx = 0, ty = 0, raf = 0;
  const paint = () => {
    tx += (px - tx) * 0.08; ty += (py - ty) * 0.08;
    const s = Math.min(scrollY, innerHeight);
    for (const el of ranges) {
      const d = +el.dataset.depth;
      el.style.setProperty('--px', `${(tx * d * 26).toFixed(2)}px`);
      el.style.setProperty('--py', `${(ty * d * 12 + s * (1 - d) * -0.25).toFixed(2)}px`);
    }
    raf = Math.abs(px - tx) + Math.abs(py - ty) > 0.001 ? requestAnimationFrame(paint) : 0;
  };
  const kick = () => { if (!raf) raf = requestAnimationFrame(paint); };
  hero.addEventListener('pointermove', (e) => {
    if (e.pointerType !== 'mouse') return;
    px = e.clientX / innerWidth - 0.5; py = e.clientY / innerHeight - 0.5; kick();
  });
  hero.addEventListener('pointerleave', () => { px = 0; py = 0; kick(); });
  addEventListener('scroll', () => { if (scrollY < innerHeight * 1.2) { raf = 0; paint(); } }, { passive: true });
}

// ---------- a campervan drives down the road as you scroll, and each camp lights up when it gets there ----------
const road = document.getElementById('trail');
const wrap = document.querySelector('.camps-wrap');
const van = document.getElementById('van');
const camps = [...document.querySelectorAll('.camp')];
if (road && wrap && van) {
  const svg = road.ownerSVGElement;
  const len = road.getTotalLength();
  const phone = matchMedia('(max-width: 860px)');
  let box, stops = [], idle = 0, parked = true, lastPuff = 0, turn = 90, here = { x: 0, y: 0 };

  // the road is drawn in a 100 x 1000 box stretched over the camps; these turn its points into pixels on the page
  const measure = () => {
    const w = wrap.getBoundingClientRect(), r = svg.getBoundingClientRect();
    box = { x: r.left - w.left, y: r.top - w.top, sx: r.width / 100, sy: r.height / 1000, h: w.height };
  };
  const at = (l) => { const p = road.getPointAtLength(Math.min(len, Math.max(0, l))); return { x: box.x + p.x * box.sx, y: box.y + p.y * box.sy }; };
  // the road always heads down the page, so the spot at a given height can be found by halving
  const atY = (y) => {
    let lo = 0, hi = len;
    for (let i = 0; i < 22; i++) { const mid = (lo + hi) / 2; if (at(mid).y < y) lo = mid; else hi = mid; }
    return lo;
  };

  // put each camp's marker on the road, level with the camp
  const placeCamps = () => {
    measure();
    stops = camps.map((c) => {
      const y = c.offsetTop + (phone.matches ? 19 : c.offsetHeight / 2);
      const pt = at(atY(y));
      c.style.setProperty('--mx', `${pt.x - c.offsetLeft}px`);
      return y;
    });
  };

  const drive = () => {
    const top = wrap.getBoundingClientRect().top;
    const y = Math.min(box.h, Math.max(0, innerHeight * 0.6 - top));
    const l = atY(y), ahead = at(l + 8), behind = at(l - 8);
    here = at(l);
    turn = Math.atan2(ahead.y - behind.y, ahead.x - behind.x) * 180 / Math.PI;   // nose points the way the road runs
    van.style.setProperty('--vx', `${here.x}px`);
    van.style.setProperty('--vy', `${here.y}px`);
    van.style.setProperty('--turn', `${turn.toFixed(1)}deg`);
    camps.forEach((c, i) => c.classList.toggle('is-reached', stops[i] <= y + 1));
  };

  // a puff of exhaust from the tailpipe, left behind on the road where the van was
  const puff = (big) => {
    const a = turn * Math.PI / 180, ux = Math.cos(a), uy = Math.sin(a);
    const back = van.offsetWidth / 2 + 2, side = van.offsetWidth * 0.14;   // the pipe sits at the back, a little to one side
    const p = document.createElement('i');
    p.className = 'puff';
    const drift = big ? 26 + Math.random() * 18 : 14 + Math.random() * 10, wob = (Math.random() - 0.5) * 22;
    p.style.cssText = `--x:${(here.x - ux * back - uy * side).toFixed(1)}px;--y:${(here.y - uy * back + ux * side).toFixed(1)}px;` +
      `--dx:${(-ux * drift - uy * wob).toFixed(1)}px;--dy:${(-uy * drift + ux * wob).toFixed(1)}px;` +
      `--o:${big ? 0.9 : 0.45};--grow:${big ? 3.2 + Math.random() : 2.2};--life:${big ? 1.7 : 1.1}s`;
    p.addEventListener('animationend', () => p.remove());
    wrap.appendChild(p);
  };

  const onScroll = () => {
    drive();
    if (reduced) return;
    const now = performance.now();
    if (parked) {
      // starting from cold: a big cloud first, then a few more as it pulls away
      parked = false;
      for (let i = 0; i < 6; i++) setTimeout(() => puff(true), i * 90);
      lastPuff = now;
    } else if (now - lastPuff > 260) {
      puff(false); lastPuff = now;
    }
    van.classList.add('is-driving');
    clearTimeout(idle);
    idle = setTimeout(() => { van.classList.remove('is-driving'); parked = true; }, 900);
  };
  const layout = () => { placeCamps(); drive(); };
  addEventListener('scroll', onScroll, { passive: true });
  addEventListener('resize', layout);
  document.fonts?.ready.then(layout);
  layout();
}

// ---------- "What's your group into?": a quick local preview, not the real planner ----------
const PLACES = [
  { name: 'Lake Tahoe', tags: ['snow', 'lake', 'hike', 'slow'], line: 'California. Snowy peaks above a deep blue lake, cabins and easy trails.' },
  { name: 'Glacier National Park', tags: ['snow', 'lake', 'hike'], line: 'Montana. Glacial lakes, alpine roads and the hikes people talk about for years.' },
  { name: 'Stowe', tags: ['snow', 'slow', 'food'], line: 'Vermont. Snowy hills, maple everything and cozy inns.' },
  { name: 'Aspen', tags: ['snow', 'hike', 'wine', 'food'], line: 'Colorado. Ski days, Maroon Bells and long dinners in a pretty mountain town.' },
  { name: 'Kenai Fjords', tags: ['snow', 'hike', 'lake'], line: 'Alaska. Glaciers, whales and huge wild country.' },
  { name: 'Great Smoky Mountains', tags: ['hike', 'slow', 'budget'], line: 'Tennessee. Misty ridges, waterfalls and cheap cabins.' },
  { name: 'Zion', tags: ['hike', 'budget'], line: 'Utah. Slot canyons, red cliffs and starry desert nights.' },
  { name: 'Acadia', tags: ['hike', 'beach', 'food'], line: 'Maine. Rocky coast, sunrise hikes and lobster rolls.' },
  { name: 'Door County', tags: ['lake', 'slow', 'wine', 'budget'], line: 'Wisconsin. Lake towns, cherry orchards and fish boils.' },
  { name: 'Traverse City', tags: ['lake', 'beach', 'wine'], line: 'Michigan. Sand dunes, freshwater beaches and wineries.' },
  { name: 'Maui', tags: ['beach', 'hike', 'slow'], line: 'Hawaii. Warm beaches, waterfalls and a volcano sunrise.' },
  { name: 'Florida Keys', tags: ['beach', 'slow', 'food'], line: 'Florida. Island hopping, clear water and Key West sunsets.' },
  { name: 'San Juan', tags: ['beach', 'food', 'city'], line: 'Puerto Rico. Old city streets and warm water, no passport needed.' },
  { name: 'Charleston', tags: ['beach', 'food', 'slow'], line: 'South Carolina. Historic streets, Lowcountry food and Folly Beach.' },
  { name: 'Big Sur', tags: ['beach', 'hike', 'slow'], line: 'California. Cliffs over the Pacific and long, quiet evenings.' },
  { name: 'New Orleans', tags: ['food', 'city'], line: 'Louisiana. Jazz on every corner and the best food crawl in the country.' },
  { name: 'Nashville', tags: ['city', 'food'], line: 'Tennessee. Live music every night and hot chicken after.' },
  { name: 'New York City', tags: ['city', 'food'], line: 'New York. Shows, museums and a food crawl through Queens.' },
  { name: 'Chicago', tags: ['city', 'food', 'lake'], line: 'Illinois. Lakefront rides, architecture cruises and deep dish.' },
  { name: 'Austin', tags: ['city', 'food', 'budget'], line: 'Texas. Tacos, swimming holes and music after dark.' },
  { name: 'Kansas City', tags: ['food', 'budget', 'city'], line: 'Missouri. Barbecue and jazz without the big-city prices.' },
  { name: 'Napa Valley', tags: ['wine', 'food', 'slow'], line: 'California. Vineyards, long lunches and nothing planned before ten.' },
  { name: 'Willamette Valley', tags: ['wine', 'slow', 'hike'], line: 'Oregon. Pinot country, forest walks and quiet farm stays.' },
  { name: 'Asheville', tags: ['hike', 'food', 'budget', 'slow'], line: 'North Carolina. Blue Ridge views, craft beer and veggie-friendly food.' },
];
const vibes = document.getElementById('vibes');
const result = document.getElementById('result');
let current = PLACES[0];
const pick = () => {
  const on = [...vibes.querySelectorAll('input:checked')].map((i) => i.value);
  const scored = PLACES.map((p) => ({ p, s: on.filter((t) => p.tags.includes(t)).length }));
  scored.sort((a, b) => b.s - a.s);
  const best = on.length ? scored[0] : { p: PLACES[0], s: 0 };
  const changed = best.p !== current;
  current = best.p;
  document.getElementById('r-name').textContent = current.name;
  document.getElementById('r-line').textContent = current.line;
  document.getElementById('r-score').textContent = on.length ? `Fits ${best.s} of ${on.length} pick${on.length === 1 ? '' : 's'}` : 'Pick a few to see a match';
  document.getElementById('r-bar').parentElement.style.setProperty('--fit', `${on.length ? Math.round((best.s / on.length) * 100) : 0}%`);
  document.getElementById('r-bar').style.width = `${on.length ? Math.round((best.s / on.length) * 100) : 0}%`;
  document.getElementById('r-plan').textContent = `Plan ${current.name} with friends`;
  if (changed && !reduced) { result.classList.remove('is-changing'); void result.offsetWidth; result.classList.add('is-changing'); }
};
vibes?.addEventListener('change', pick);
pick();
document.getElementById('r-plan')?.addEventListener('click', () => {
  const name = document.getElementById('f-name');
  if (!name.value.trim()) name.value = `${current.name} trip`;
  document.getElementById('start').scrollIntoView({ behavior: reduced ? 'auto' : 'smooth' });
  setTimeout(() => document.getElementById('f-members').focus({ preventScroll: true }), reduced ? 0 : 600);
});

// ---------- forms ----------
async function api(path, opts = {}) {
  let res;
  try {
    res = await fetch(`/api${path}`, {
      method: opts.method || 'GET',
      headers: opts.body ? { 'Content-Type': 'application/json' } : undefined,
      body: opts.body ? JSON.stringify(opts.body) : undefined,
    });
  } catch {
    throw new Error("Can't reach WanderFolk. Check your connection and try again.");
  }
  const data = await res.json().catch(() => null);
  if (!res.ok) throw Object.assign(new Error(typeof data?.detail === 'string' ? data.detail : 'Something went wrong. Try again.'), { status: res.status });
  return data;
}

function showError(input, text) {
  const err = document.getElementById(`${input.id}-err`);
  input.setAttribute('aria-invalid', 'true');
  if (err) { if (text) err.textContent = text; err.hidden = false; }
}
function clearError(input) {
  input.removeAttribute('aria-invalid');
  const err = document.getElementById(`${input.id}-err`);
  if (err) err.hidden = true;
}
// Checks the required fields on submit; returns true when the form can be sent.
function check(form) {
  const bad = [...form.querySelectorAll('[required]:not(:disabled)')].filter((el) => !el.value.trim());
  form.querySelectorAll('input, textarea').forEach((el) => { if (!bad.includes(el)) clearError(el); });
  bad.forEach((el) => showError(el));
  const status = form.querySelector('[data-form-status]');
  if (bad.length) {
    status.textContent = bad.length === 1 ? '1 field to fill in.' : `${bad.length} fields to fill in.`;
    bad[0].focus();
    return false;
  }
  status.textContent = '';
  return true;
}
document.querySelectorAll('form input, form textarea').forEach((el) =>
  el.addEventListener('input', () => { if (el.getAttribute('aria-invalid') === 'true' && el.value.trim()) clearError(el); }));
function busy(form, on) {
  const button = form.querySelector('[type="submit"]');
  button.disabled = on;
  button.toggleAttribute('aria-busy', on);
}

// start a trip
const create = document.getElementById('create');
api('/config').then((cfg) => {
  if (!cfg?.create_code_required) return;
  document.getElementById('code-field').hidden = false;
  const code = document.getElementById('f-code');
  code.disabled = false;
  code.required = true;
}).catch(() => {});

create.addEventListener('submit', async (e) => {
  e.preventDefault();
  if (!check(create)) return;
  const f = new FormData(create);
  const status = create.querySelector('[data-form-status]');
  busy(create, true);
  const wait = setTimeout(() => { status.textContent = 'Starting the trip…'; }, 300);
  try {
    const { id } = await api('/trips', {
      method: 'POST',
      body: {
        name: f.get('name') || '', origin: f.get('origin') || '', days: Number(f.get('days') || 3),
        members: f.get('members') || '', earlier: f.get('earlier') || '', code: f.get('code') || '',
      },
    });
    location.href = tripUrl(id);
  } catch (err) {
    const msg = err.message;
    if (/access code/i.test(msg)) showError(document.getElementById('f-code'), msg);
    else if (/earlier trip/i.test(msg)) { document.querySelector('.more').open = true; showError(document.getElementById('f-earlier'), msg); }
    else if (/person|people/i.test(msg)) showError(document.getElementById('f-members'), msg);
    else if (/name/i.test(msg)) showError(document.getElementById('f-name'), msg);
    status.textContent = msg;
  } finally {
    clearTimeout(wait);
    busy(create, false);
  }
});

// join a trip by its link or code
const join = document.getElementById('join-form');
join.addEventListener('submit', async (e) => {
  e.preventDefault();
  if (!check(join)) return;
  const input = document.getElementById('f-link');
  const status = join.querySelector('[data-form-status]');
  busy(join, true);
  try {
    const { id } = await api(`/lookup?link=${encodeURIComponent(input.value.trim())}`);
    location.href = tripUrl(id);
  } catch (err) {
    const msg = err.status === 404 ? "That code or link doesn't match a trip. Check it with whoever sent it." : err.message;
    showError(input, msg);
    status.textContent = msg;
  } finally {
    busy(join, false);
  }
});

// trips opened on this device (the trip app keeps this list)
try {
  const recent = JSON.parse(localStorage.getItem('wf.recent') || '[]');
  if (Array.isArray(recent) && recent.length) {
    const list = document.getElementById('recent');
    for (const t of recent.slice(0, 4)) {
      const li = document.createElement('li');
      const a = document.createElement('a');
      a.href = tripUrl(t.id);
      a.textContent = t.name;
      const arrow = document.createElement('span');
      arrow.setAttribute('aria-hidden', 'true');
      arrow.textContent = '⛰';
      a.append(arrow);
      li.append(a);
      list.append(li);
    }
    document.getElementById('recent-box').hidden = false;
  }
} catch {
  /* private mode: nothing to list */
}
