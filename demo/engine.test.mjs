import test from 'node:test';
import assert from 'node:assert/strict';
import { DemoLab, createDemoRequest } from './engine.mjs';

test('503 to 200 retains payload, stable key and both attempts', () => {
  const lab = new DemoLab(); const event = lab.capture();
  const fail = lab.replay(event.id, 'demo-failure'); const ok = lab.replay(event.id, 'demo-success');
  assert.equal(fail.status_code, 503); assert.equal(ok.status_code, 200);
  assert.equal(fail.idempotency_key, ok.idempotency_key);
  assert.equal(lab.get(event.id).body_text, event.body_text);
  assert.equal(lab.get(event.id).attempts.length, 2);
});
test('sessions stay isolated; reset restores sample data', () => {
  const a = new DemoLab(), b = new DemoLab(); a.capture();
  assert.equal(b.list().stats.events, 3); a.reset(); assert.equal(a.list().stats.events, 3);
});
test('timeouts count as failures without an HTTP status', () => {
  const lab = new DemoLab(); const result = lab.replay(lab.events[0].id, 'demo-timeout');
  assert.equal(result.status_code, null); assert.equal(result.status, 'failed');
  assert.equal(lab.list().stats.outcomes.failed, 2);
});
test('arbitrary destinations and routes are rejected', async () => {
  const lab = new DemoLab(); assert.throws(() => lab.replay(lab.events[0].id, 'https://example.com'));
  await assert.rejects(createDemoRequest(lab)('/unknown'));
});
test('pagination and raw download preserve the original event', async () => {
  const lab = new DemoLab(); for (let i = 0; i < 21; i++) lab.capture();
  assert.equal(lab.list(20, 20).items.length, 4);
  const event = lab.events[0]; const response = await createDemoRequest(lab)(`/api/events/${event.id}/body`);
  assert.equal(await response.text(), event.body_text);
});
