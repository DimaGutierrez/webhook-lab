import { DemoLab, createDemoRequest } from './engine.mjs';
const lab = new DemoLab();
const demoRequest = createDemoRequest(lab);
const $ = (id) => document.getElementById(id);
let token = 'demo', config = null, events = [], selected = null, offset = 0;
let detailSequence = 0, listSequence = 0, toastTimer;
const pageSize = 20;

function notify(message) {
  $('toast').textContent = message;
  $('toast').hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { $('toast').hidden = true; }, 4500);
}
async function api(path, options = {}) {
  const response = await demoRequest(path, {
    ...options,
    headers: { Authorization: `Bearer ${token}`, ...options.headers },
  });
  if (!response.ok) {
    const result = await response.json().catch(() => ({}));
    const detail = typeof result.detail === 'string' ? result.detail : `Request failed (${response.status})`;
    throw new Error(detail);
  }
  return response;
}
function badge(status) {
  const element = document.createElement('span');
  const allowed = ['captured', 'delivered', 'failed', 'pending', 'interrupted'];
  const value = allowed.includes(status) ? status : 'captured';
  element.className = `badge ${value}`;
  element.textContent = value.toUpperCase();
  return element;
}
const date = (value) => new Date(value).toLocaleString([], {
  month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit',
});

function renderEvents() {
  const query = $('search').value.toLowerCase();
  const list = $('event-list');
  list.replaceChildren();
  const matches = events.filter((event) => (
    `${event.id} ${event.headers['x-event-type'] || ''} ${event.headers['x-github-event'] || ''}`
  ).toLowerCase().includes(query));
  for (const event of matches) {
    const row = document.createElement('button');
    row.className = `event-row${event.id === selected ? ' selected' : ''}`;
    row.setAttribute('aria-pressed', String(event.id === selected));
    const info = document.createElement('span');
    const title = document.createElement('strong');
    title.textContent = event.headers['x-event-type'] || event.headers['x-github-event'] || 'webhook.received';
    const subtitle = document.createElement('small');
    subtitle.textContent = `${event.id.slice(0, 8)} · ${date(event.received_at)}`;
    info.append(title, subtitle);
    row.append(info, badge(event.last_status));
    row.addEventListener('click', () => selectEvent(event.id).catch(report));
    list.append(row);
  }
  if (!matches.length) {
    const empty = document.createElement('p');
    empty.className = 'list-empty';
    empty.textContent = query ? 'No matches on this page.' : 'Your inbox is ready. Send your first event.';
    list.append(empty);
  }
}
function report(error) { notify(error.message || 'Something went wrong. Please try again.'); }

async function refresh() {
  const sequence = ++listSequence;
  const result = await (await api(`/api/events?limit=${pageSize}&offset=${offset}`)).json();
  if (sequence !== listSequence || !token) return;
  events = result.items;
  const stats = result.stats;
  $('stat-events').textContent = stats.events;
  $('nav-count').textContent = stats.events;
  $('list-count').textContent = stats.events;
  $('stat-attempts').textContent = stats.attempts;
  $('stat-delivered').textContent = stats.outcomes.delivered || 0;
  $('stat-failed').textContent = stats.outcomes.failed || 0;
  $('prev').disabled = offset === 0;
  $('next').disabled = offset + pageSize >= stats.events;
  $('page-info').textContent = stats.events ? `${offset + 1}–${offset + events.length} of ${stats.events}` : 'No events yet';
  renderEvents();
}

function tab(name) {
  document.querySelectorAll('[data-tab]').forEach((button) => {
    const active = button.dataset.tab === name;
    button.classList.toggle('active', active);
    button.setAttribute('aria-selected', String(active));
    $(`panel-${button.dataset.tab}`).hidden = !active;
  });
}

async function selectEvent(id) {
  const sequence = ++detailSequence;
  selected = id;
  renderEvents();
  const event = await (await api(`/api/events/${id}`)).json();
  if (sequence !== detailSequence || !token) return;
  $('empty-detail').hidden = true;
  $('event-detail').hidden = false;
  $('detail-id').textContent = event.id;
  $('detail-meta').textContent = `${date(event.received_at)} · ${event.size.toLocaleString()} bytes · POST`;
  $('content-type').textContent = event.headers['content-type'] || 'application/octet-stream';
  try { $('payload').textContent = JSON.stringify(JSON.parse(event.body_text), null, 2); }
  catch { $('payload').textContent = event.body_text || '(empty body)'; }
  $('headers').textContent = JSON.stringify(event.headers, null, 2);
  $('attempt-count').textContent = event.attempts.length;
  $('attempts').replaceChildren();
  if (!event.attempts.length) {
    const empty = document.createElement('p');
    empty.className = 'list-empty';
    empty.textContent = 'No replays yet. Try a demo destination below.';
    $('attempts').append(empty);
  }
  for (const attempt of event.attempts) {
    const item = document.createElement('div');
    item.className = 'attempt';
    const heading = document.createElement('div');
    const label = document.createElement('span');
    label.textContent = `${attempt.target} ${attempt.status_code ? `· HTTP ${attempt.status_code}` : ''}`;
    heading.append(label, badge(attempt.status));
    const meta = document.createElement('p');
    meta.textContent = `${date(attempt.started_at)} · simulated ${attempt.duration_ms ?? '—'} ms${attempt.error ? ` · ${attempt.error}` : ''}`;
    item.append(heading, meta);
    $('attempts').append(item);
  }
}

async function startDemo() {
  config = await (await api('/api/config')).json();
  $('target').replaceChildren();
  for (const target of config.targets) {
    const option = document.createElement('option');
    option.value = target.id; option.textContent = target.name; $('target').append(option);
  }
  await refresh(); await selectEvent(events[0].id); tab('payload');
}
$('reset').addEventListener('click', async () => {
  lab.reset(); offset = 0; selected = null; $('search').value = '';
  await startDemo(); notify('Demo reset. Only fictional sample events remain.');
});
$('sample').addEventListener('click', async () => {
  $('sample').disabled = true;
  try {
    const response = await demoRequest(config.inbox_path, {
      method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Event-Type': 'order.created' },
      body: JSON.stringify({
        id: `evt_${crypto.randomUUID().slice(0, 8)}`, type: 'order.created',
        created_at: new Date().toISOString(),
        data: { order_id: 'ORD-1042', amount: 4900, currency: 'USD', customer: 'demo@example.com' },
        demo: true,
      }, null, 2),
    });
    if (!response.ok) throw new Error(`Capture failed (${response.status})`);
    const result = await response.json();
    offset = 0; $('search').value = '';
    await refresh(); await selectEvent(result.id); tab('payload');
    notify('Sample added in this tab. Try a simulated failed replay, then a success.');
  } catch (error) { report(error); }
  finally { $('sample').disabled = false; }
});
$('replay').addEventListener('click', async () => {
  if (!selected) return;
  const id = selected;
  $('replay').disabled = true; $('replay').textContent = 'Replaying…';
  try {
    const result = await (await api(`/api/events/${id}/replay`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target: $('target').value }),
    })).json();
    await refresh();
    if (selected === id) { await selectEvent(id); tab('attempts'); }
    notify(result.status === 'delivered' ? `Simulated delivery · HTTP ${result.status_code}` : result.error);
  } catch (error) { report(error); }
  finally { $('replay').disabled = false; $('replay').textContent = '↻ Replay'; }
});
$('download').addEventListener('click', async () => {
  if (!selected) return;
  try {
    const id = selected;
    const blob = await (await api(`/api/events/${id}/body`)).blob();
    const url = URL.createObjectURL(blob), link = document.createElement('a');
    link.href = url; link.download = `${id}.bin`; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (error) { report(error); }
});
$('refresh').addEventListener('click', () => refresh().catch(report));
$('search').addEventListener('input', renderEvents);
$('prev').addEventListener('click', () => { offset = Math.max(0, offset - pageSize); refresh().catch(report); });
$('next').addEventListener('click', () => { offset += pageSize; refresh().catch(report); });
document.querySelectorAll('[data-tab]').forEach((button) => button.addEventListener('click', () => tab(button.dataset.tab)));

startDemo().catch(report);
