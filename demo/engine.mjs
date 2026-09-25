// Browser-only simulation. No network requests, credentials or shared storage.
export class DemoLab {
  constructor() { this.events = []; this.reset(); }
  capture(type = 'order.created') {
    if (this.events.length >= 100) throw new Error('Demo limit: 100 events. Reset the demo to start again.');
    const id = crypto.randomUUID();
    const body_text = JSON.stringify({ id: `evt_${id.slice(0, 8)}`, type,
      data: { order_id: 'ORD-1042', amount: 4900, currency: 'USD', customer: 'demo@example.com' }, demo: true }, null, 2);
    const event = { id, body_text, size: new TextEncoder().encode(body_text).length,
      received_at: new Date().toISOString(), headers: { 'content-type': 'application/json', 'x-event-type': type },
      attempts: [], last_status: 'captured' };
    this.events.unshift(event);
    return structuredClone(event);
  }
  get(id) {
    const event = this.events.find(e => e.id === id);
    if (!event) throw new Error('Event not found. Select an event from the inbox.');
    return event;
  }
  replay(id, target) {
    if (!['demo-success', 'demo-failure', 'demo-timeout'].includes(target)) throw new Error('Choose a simulated destination.');
    const event = this.get(id);
    if (event.attempts.length >= 50) throw new Error('Demo limit: 50 attempts per event.');
    const status_code = target === 'demo-success' ? 200 : target === 'demo-failure' ? 503 : null;
    const attempt = { id: crypto.randomUUID(), target, status_code,
      status: status_code === 200 ? 'delivered' : 'failed', started_at: new Date().toISOString(),
      duration_ms: target === 'demo-timeout' ? 5000 : target === 'demo-success' ? 42 : 18,
      error: target === 'demo-timeout' ? 'Simulated timeout (no request sent)' : status_code === 503 ? 'Simulated HTTP 503' : null,
      idempotency_key: id };
    event.attempts.unshift(attempt); event.last_status = attempt.status;
    return structuredClone(attempt);
  }
  list(offset = 0, limit = 20) {
    const attempts = this.events.flatMap(e => e.attempts);
    return { items: structuredClone(this.events.slice(offset, offset + limit)), stats: {
      events: this.events.length, attempts: attempts.length,
      outcomes: { delivered: attempts.filter(a => a.status === 'delivered').length,
        failed: attempts.filter(a => a.status === 'failed').length } } };
  }
  reset() {
    this.events = [];
    this.capture('customer.created');
    const failed = this.capture('payment.failed'); this.replay(failed.id, 'demo-failure');
    this.capture('order.created');
  }
}

export function createDemoRequest(lab) {
  return async function demoRequest(path, options = {}) {
    const url = new URL(path, 'https://demo.invalid');
    const route = url.pathname;
    let data;
    if (route === '/api/config') data = { inbox_path: '/demo-inbox', targets: [
      { id: 'demo-failure', name: 'Simulated · unavailable (503)' },
      { id: 'demo-success', name: 'Simulated · accepts (200)' },
      { id: 'demo-timeout', name: 'Simulated · timeout' } ] };
    else if (route === '/demo-inbox' && options.method === 'POST') data = lab.capture();
    else if (route === '/api/events') data = lab.list(Number(url.searchParams.get('offset') || 0), Number(url.searchParams.get('limit') || 20));
    else {
      const match = route.match(/^\/api\/events\/([^/]+)(?:\/(replay|body))?$/);
      if (!match) throw new Error('This demo has no external webhook endpoint.');
      const event = lab.get(match[1]);
      if (match[2] === 'body') return new Response(event.body_text, { headers: { 'Content-Type': 'application/json' } });
      data = match[2] === 'replay' ? lab.replay(event.id, JSON.parse(options.body).target) : structuredClone(event);
    }
    return new Response(JSON.stringify(data), { headers: { 'Content-Type': 'application/json' } });
  };
}
