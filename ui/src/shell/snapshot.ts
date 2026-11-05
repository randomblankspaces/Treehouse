/** Fail closed on malformed public snapshots, including unavailable results without reasons. */
import { EVALUATIONS, type RunSnapshot } from './contract.ts';

const fail = (): never => { throw new Error('The server returned an unsupported or malformed snapshot. No results were displayed.'); };
const object = (v: unknown): Record<string, unknown> => v !== null && typeof v === 'object' && !Array.isArray(v) ? v as Record<string, unknown> : fail();
const text = (v: unknown) => { if (typeof v !== 'string') fail(); };
const number = (v: unknown) => { if (typeof v !== 'number' || !Number.isFinite(v)) fail(); };
const nullable = (v: unknown, check: (v: unknown) => void) => { if (v !== null) check(v); };
const choice = (v: unknown, allowed: string[]) => { if (typeof v !== 'string' || !allowed.includes(v)) fail(); };
const array = (v: unknown, check: (v: unknown) => void) => { if (!Array.isArray(v)) return fail(); v.forEach(check); };
const json = (v: unknown): void => {
  if (v === null || typeof v === 'boolean' || typeof v === 'string') return;
  if (typeof v === 'number') return number(v);
  if (Array.isArray(v)) return v.forEach(json);
  Object.values(object(v)).forEach(json);
};

export function decodeSnapshot(value: unknown): RunSnapshot {
  const s = object(value);
  for (const k of ['run_id', 'title']) text(s[k]);
  if (typeof s.synthetic !== 'boolean') fail();
  choice(s.status, ['queued', 'running', 'complete', 'failed']);
  choice(s.mode, ['live', 'replay', 'fake', 'mock', 'unknown']);
  nullable(s.started_at, text); nullable(s.elapsed_ms, number); nullable(s.cost_usd, number);
  const p = object(s.provenance);
  choice(p.embeddings, ['synthetic_reference_derived', 'synthetic', 'real', 'unknown']);
  choice(p.reference, ['synthetic', 'real', 'none', 'unknown']); choice(p.vision, ['used', 'not_used', 'unknown']);
  array(p.limitations, text);
  const evaluation = object(s.evaluation);
  for (const name of EVALUATIONS) {
    const section = object(evaluation[name]);
    choice(section.status, ['available', 'unavailable', 'method_test_only']); json(section.value); nullable(section.reason, text);
    if (section.scores !== undefined) array(section.scores, value => {
      const score = object(value); text(score.metric); text(score.basis);
      choice(score.unit, ['percent', 'raw']); choice(score.status, ['available', 'unavailable', 'method_test_only']);
      for (const key of ['value', 'numerator', 'denominator']) nullable(score[key], number);
      nullable(score.reason, text); if (score.trial_id !== undefined) text(score.trial_id);
      if (score.status === 'unavailable') { if (score.value !== null || !score.reason) fail(); }
      else {
        number(score.value); number(score.denominator);
        if ((score.denominator as number) <= 0) fail();
        if (score.unit === 'percent' && ((score.value as number) < 0 || (score.value as number) > 100)) fail();
        if (score.status === 'method_test_only' && !score.reason) fail();
      }
    });
    if (section.status === 'unavailable'  && section.value !== null) fail();
    if (section.status !== 'unavailable' && section.value === null) fail();
    if (section.status !== 'available' && (typeof section.reason !== 'string' || !section.reason.trim())) fail();
  }
  if (s.thinking_summary !== undefined) {
    const summary = object(s.thinking_summary);
    choice(summary.status, ['available', 'unavailable']); choice(summary.basis, ['recorded_decisions']);
    text(summary.text); nullable(summary.reason, text);
    if (summary.status === 'available' ? !summary.text : !summary.reason) fail();
  }
  const input = object(s.input), context = object(s.context);
  for (const k of ['task_id', 'title', 'goal']) text(input[k]);
  for (const [key, size, check] of [['aoi_bbox', 4, number], ['time_window', 2, text]] as const) {
    if (input[key] !== null) { array(input[key], check); if ((input[key] as unknown[]).length !== size) fail(); }
  }
  array(input.tools_allowed, text); array(input.data_allowlist, v => { const d = object(v); for (const k of ['source_id', 'kind', 'license']) text(d[k]); });
  for (const k of ['model_id', 'provider', 'harness']) text(context[k]);
  array(context.items, v => { const i = object(v); text(i.label); text(i.detail); nullable(i.tokens, number); });
  // Prompts are withheld by the public projection, regardless of future server additions.
  context.system_prompt = null;
  array(s.steps, v => {
    const step = object(v); text(step.span_id); text(step.name); nullable(step.parent_span_id, text);
    choice(step.kind, ['invoke_agent', 'chat', 'execute_tool']); choice(step.status, ['running', 'ok', 'error']);
    number(step.start_ms); nullable(step.end_ms, number); json(step.attributes);
    if (step.model) { const m = object(step.model); text(m.model_id); for (const k of ['input_tokens', 'output_tokens', 'cost_usd']) nullable(m[k], number); nullable(m.thinking, text); nullable(m.stop_reason, text); }
    if (step.tool) { const t = object(step.tool); text(t.name); object(t.args); json(t.args); nullable(t.result, text); nullable(t.bytes_read, number); }
    if (step.decision) { const d = object(step.decision); text(d.rationale); number(d.confidence); array(d.alternatives, v => { const a = object(v); text(a.option); text(a.reason); }); }
    if (step.error) { const e = object(step.error); text(e.type); text(e.message); }
  });
  array(s.markers, v => {
    const m = object(v); for (const k of ['lon', 'lat']) number(m[k]); nullable(m.confidence, number); nullable(m.at_ms, number);
    for (const k of ['label', 'claim_id', 'trial_id']) text(m[k]); nullable(m.decision_id, text);
    choice(m.status, ['present', 'absent', 'cannot_assess', 'intact', 'damaged', 'destroyed']);
    array(m.evidence_refs, v => { const r = object(v); text(r.result_id); text(r.role); });
  });
  return s as unknown as RunSnapshot;
}
