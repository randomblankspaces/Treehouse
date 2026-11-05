// Self-check for the shell seam: mock replay, key-decision mapping, narrator. Run: npm run test:shell
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { isKey, focusOf, terminal } from '../src/shell/contract.ts';
import { mockClient, mockNarrator } from '../src/shell/mock.ts';

test('recorded mock run is complete and well formed', async () => {
  const runs = await mockClient.listRuns();
  assert.equal(runs.length, 2);
  const s = await mockClient.snapshot('mock-nagoya-recorded');
  assert.ok(terminal(s.status));
  assert.equal(s.steps.length, 20);
  const ids = new Set(s.steps.map(x => x.span_id));
  assert.equal(ids.size, s.steps.length, 'span ids unique');
  for (const x of s.steps) {
    assert.notEqual(x.status, 'running');
    if (x.parent_span_id) assert.ok(ids.has(x.parent_span_id), 'parent exists');
  }
  assert.ok(s.cost_usd > 0);
  const errors = s.steps.filter(x => x.status === 'error');
  assert.equal(errors.length, 1);
  assert.equal(errors[0].tool?.result, null, 'failed call has no result');
});

test('key decisions are foundation-model use and data access, incl. Strands', async () => {
  const s = await mockClient.snapshot('mock-nagoya-recorded');
  const keys = s.steps.filter(isKey).map(x => x.tool?.name);
  assert.ok(keys.includes('strands_label') && keys.includes('build_index') && keys.includes('imagery_window'));
  assert.ok(!keys.includes('note_limitation'));
  const strands = s.steps.find(x => x.tool?.name === 'strands_label');
  assert.equal(focusOf(strands), 'foundation_model');
  assert.ok(s.steps.some(x => x.parent_span_id === strands.span_id), 'Strands sub-agent spans nest under the tool call');
});

test('live mock starts partial; narrator speaks only for key steps and errors', async () => {
  const live = await mockClient.snapshot('mock-nagoya-live');
  assert.equal(live.status, 'running');
  assert.ok(live.steps.length < 20);
  const s = await mockClient.snapshot('mock-nagoya-recorded');
  const chat = s.steps.find(x => x.kind === 'chat');
  assert.equal(await mockNarrator.line(chat, s), null);
  const err = s.steps.find(x => x.status === 'error');
  assert.match((await mockNarrator.line(err, s)).text, /failed/);
});

test('the chosen agent runs the task and the timer counts from the start', async () => {
  const { sinceStart } = await import('../src/shell/describe.ts');
  const agents = await mockClient.agents();
  assert.ok(agents.length >= 2);
  const pick = agents[1];
  const id = await mockClient.startRun({place_id: 't1-nagoya-warehouses', goal: 'Find warehouses', agent_id: pick.agent_id});
  const s = await mockClient.snapshot(id);
  assert.equal(s.context.model_id, pick.model_id);
  assert.equal(s.input.goal, 'Find warehouses');
  const later = Date.parse(s.started_at) + 30_000;
  assert.equal(sinceStart(s, later), 30_000, 'live: wall clock since start');
  const done = await mockClient.snapshot('mock-nagoya-recorded');
  assert.equal(sinceStart(done, later), done.elapsed_ms, 'finished: frozen at run length');
});
