// WanderFolk start page: the moving range, the trail, the "try it" preview, and the start / join forms.

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

// ---------- light snow over the range (runs only while the hero is on screen) ----------
const canvas = document.getElementById('snow');
if (canvas && !reduced) {
  const ctx = canvas.getContext('2d');
  let flakes = [], w = 0, h = 0, on = true, raf = 0;
  const size = () => {
    const r = Math.min(devicePixelRatio || 1, 2);
    w = canvas.clientWidth; h = canvas.clientHeight;
    canvas.width = w * r; canvas.height = h * r; ctx.setTransform(r, 0, 0, r, 0, 0);
    const n = Math.round(Math.min(140, w * h / 9000));
    flakes = Array.from({ length: n }, () => ({ x: Math.random() * w, y: Math.random() * h, r: Math.random() * 2 + 0.6, s: Math.random() * 0.5 + 0.25, d: Math.random() * Math.PI * 2 }));
  };
  const tick = () => {
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = 'rgba(255,255,255,0.85)';
    for (const f of flakes) {
      f.y += f.s; f.d += 0.01; f.x += Math.sin(f.d) * 0.3;
      if (f.y > h) { f.y = -4; f.x = Math.random() * w; }
      ctx.beginPath(); ctx.arc(f.x, f.y, f.r, 0, Math.PI * 2); ctx.fill();
    }
    raf = on ? requestAnimationFrame(tick) : 0;
  };
  size(); addEventListener('resize', size);
  new IntersectionObserver(([e]) => { on = e.isIntersecting; if (on && !raf) tick(); }).observe(hero);
  tick();
}

// ---------- the trail draws itself as you climb, and each camp lights up when reached ----------
const trail = document.getElementById('trail');
const wrap = document.querySelector('.camps-wrap');
const camps = [...document.querySelectorAll('.camp')];
if (trail && wrap) {
  const len = trail.getTotalLength();
  trail.style.setProperty('--len', len);
  const climb = () => {
    const r = wrap.getBoundingClientRect();
    const p = Math.min(1, Math.max(0, (innerHeight * 0.6 - r.top) / r.height));
    trail.style.setProperty('--off', reduced ? 0 : len * (1 - p));
    const line = innerHeight * 0.6;
    for (const c of camps) c.classList.toggle('is-reached', reduced || c.getBoundingClientRect().top + c.offsetHeight / 2 < line);
  };
  addEventListener('scroll', climb, { passive: true });
  addEventListener('resize', climb);
  climb();
}

// ---------- "What's your group into?": a quick local preview, not the real planner ----------
const PLACES = [
  { name: 'Lake Tahoe', tags: ['snow', 'lake', 'hike', 'slow'], line: 'Snowy peaks above a deep blue lake, cabins and easy trails.' },
  { name: 'Yosemite Valley', tags: ['snow', 'hike', 'lake'], line: 'Granite walls, waterfalls and the big hikes people talk about for years.' },
  { name: 'Big Sur', tags: ['beach', 'hike', 'slow'], line: 'Cliffs over the Pacific, coastal trails and long, quiet evenings.' },
  { name: 'Santa Cruz', tags: ['beach', 'food', 'budget', 'city'], line: 'Boardwalk, surf, tacos by the beach and a short drive home.' },
  { name: 'Napa Valley', tags: ['wine', 'food', 'slow'], line: 'Vineyards, long lunches and nothing planned before ten.' },
  { name: 'Mendocino', tags: ['beach', 'slow', 'food', 'budget'], line: 'A quiet coast town with vegetarian cafes and headland walks.' },
  { name: 'Mammoth Lakes', tags: ['snow', 'lake', 'hike', 'budget'], line: 'High-country lakes under snowy ridges, cheaper than the big resorts.' },
  { name: 'San Diego', tags: ['beach', 'city', 'food'], line: 'Sunny beaches by day, tacos and city nights after.' },
  { name: 'Sonoma Coast', tags: ['wine', 'beach', 'slow'], line: 'Wine country meets wild beaches, cabins by the sea.' },
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
    const msg = err.status === 404 ? "That link doesn't match a trip. Check it with whoever sent it." : err.message;
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
