// WanderFolk start page: start a trip, join one by its link, and list the trips opened on this device.
// The kit's system.js checks the required fields on submit; this file sends the trip to the API.

const tripUrl = (id) => `/trip/?trip=${encodeURIComponent(id)}`;

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

// A server-side reason shown under the field it is about, like the kit's own errors.
function fieldError(input, text) {
  const err = document.getElementById(`${input.id}-err`);
  input.setAttribute('aria-invalid', 'true');
  if (err) { err.textContent = text; err.hidden = false; }
  input.focus();
}

function busy(form, on) {
  const button = form.querySelector('[type="submit"]');
  if (!button) return;
  button.disabled = on;
  button.toggleAttribute('aria-busy', on);
}

// ---- start a trip ----
const create = document.getElementById('create');
const status = create?.querySelector('[data-form-status]');

api('/config').then((cfg) => {
  if (!cfg?.create_code_required) return;
  document.getElementById('code-field').hidden = false;
  const code = document.getElementById('f-code');
  code.disabled = false;
  code.required = true;
}).catch(() => {});

create?.addEventListener('submit', async (e) => {
  e.preventDefault();
  if (!create.checkValidity()) return; // system.js has marked the fields to fix
  const f = new FormData(create);
  busy(create, true);
  const wait = setTimeout(() => { status.textContent = 'Starting the trip'; }, 300);
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
    if (/access code/i.test(msg)) fieldError(document.getElementById('f-code'), msg);
    else if (/earlier trip/i.test(msg)) fieldError(document.getElementById('f-earlier'), msg);
    else if (/name/i.test(msg) && !/person|people/i.test(msg)) fieldError(document.getElementById('f-name'), msg);
    else if (/person|people/i.test(msg)) fieldError(document.getElementById('f-members'), msg);
    status.textContent = msg;
  } finally {
    clearTimeout(wait);
    busy(create, false);
  }
});

// ---- join a trip by its link or code ----
const join = document.getElementById('join-form');
join?.addEventListener('submit', async (e) => {
  e.preventDefault();
  if (!join.checkValidity()) return;
  const input = document.getElementById('f-link');
  const say = join.querySelector('[data-form-status]');
  busy(join, true);
  try {
    const { id } = await api(`/lookup?link=${encodeURIComponent(input.value.trim())}`);
    location.href = tripUrl(id);
  } catch (err) {
    fieldError(input, err.status === 404 ? "That link doesn't match a trip. Check it with whoever sent it." : err.message);
    say.textContent = err.message;
  } finally {
    busy(join, false);
  }
});

// ---- trips opened on this device (the trip app keeps this list) ----
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
      arrow.textContent = '→';
      a.append(arrow);
      li.append(a);
      list.append(li);
    }
    document.getElementById('recent-box').hidden = false;
  }
} catch {
  /* private mode: nothing to list */
}
