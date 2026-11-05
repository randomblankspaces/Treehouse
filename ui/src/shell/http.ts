/** Adapter over today's local API (`treehouse ui serve`). Reuses the validating decoders in api.ts.
 *  Gaps (see docs/design/SHELL.md): no partial snapshot mid-run, no thinking text, no AOI/time window. */
import { decodeBundle, decodeDatabase, decodeInvestigation, decodeRun, decodeRuns, decodeStarted, decodeTasks, request, type InvestigationDecision, type Run } from '../api.ts';
import type { Agent, Json, MapMarker, RunSnapshot, RunStatus, StepKind, TraceStep, TreehouseClient } from './contract.ts';

const KINDS: StepKind[] = ['invoke_agent', 'chat', 'execute_tool'];
const status = (s: Run['status']): RunStatus => s === 'report_ready' || s === 'sealed' ? 'complete' : s;
const n = (v: Json | undefined) => typeof v === 'number' ? v : 0;
const s = (v: Json | undefined) => typeof v === 'string' ? v : null;
const base = (id: string) => `/api/runs/${encodeURIComponent(id)}`;
const presets = async (signal?: AbortSignal) => (await request('/api/tasks', decodeTasks, signal)).tasks;

export const httpClient: TreehouseClient = {
  label: 'local API',
  async listRuns(signal) {
    const {runs} = await request('/api/runs', decodeRuns, signal);
    return runs.map(r => ({run_id: r.run_id, title: r.title, status: status(r.status), synthetic: r.synthetic}));
  },
  async snapshot(id, signal) {
    const run = await request(base(id), decodeRun, signal);
    const empty: RunSnapshot = {run_id: run.run_id, title: run.title, status: status(run.status), synthetic: run.synthetic,
      started_at: null, elapsed_ms: 0, cost_usd: 0, steps: [], markers: [],
      input: {task_id: run.task_id, title: run.title, goal: '', aoi_bbox: null, time_window: null, tools_allowed: [], data_allowlist: []},
      context: {model_id: '', provider: '', harness: '', system_prompt: null, items: []}};
    if (empty.status !== 'complete') return empty;   // backend serves records only once sealed
    const [bundle, inv, db] = await Promise.all([request(`${base(id)}/bundle`, decodeBundle, signal), request(`${base(id)}/investigation`, decodeInvestigation, signal), request(`${base(id)}/database`, decodeDatabase, signal)]);
    const bySpan = new Map<string, InvestigationDecision>();
    for (const d of inv.decisions) if (d.action) bySpan.set(d.action.span_id, d);
    const spans = bundle.trace_rows.filter(r => KINDS.includes((s(r.attributes['gen_ai.operation.name']) ?? r.op) as StepKind));
    const t0 = Math.min(...spans.map(r => r.start_ns));
    const steps = spans.map((r): TraceStep => {
      const a = r.attributes, kind = (s(a['gen_ai.operation.name']) ?? r.op) as StepKind, d = bySpan.get(r.span_id);
      const tool = s(a['gen_ai.tool.name']);
      return {span_id: r.span_id, parent_span_id: r.parent_span_id, kind, name: r.name,
        start_ms: (r.start_ns - t0) / 1e6, end_ms: (r.end_ns - t0) / 1e6, status: r.error || r.status === 'error' ? 'error' : 'ok',
        model: kind === 'chat' ? {model_id: s(a['gen_ai.request.model']) ?? '', input_tokens: n(a['gen_ai.usage.input_tokens']),
          output_tokens: n(a['gen_ai.usage.output_tokens']), cost_usd: n(a['treehouse.cost.usd']), thinking: null, stop_reason: s(a['treehouse.stop_reason'])} : undefined,
        tool: tool ? {name: tool, args: d?.parameters ?? {}, result: s(a['treehouse.tool.result_id']), bytes_read: n(a['treehouse.tool.bytes_read'])} : undefined,
        decision: d ? {rationale: d.rationale, alternatives: d.alternatives, confidence: d.confidence} : undefined,
        error: r.error ? {type: r.error.type, message: r.error.message} : undefined, attributes: a};
    }).sort((x, y) => x.start_ms - y.start_ms);
    const chat = spans.find(r => r.op === 'chat'), agent = spans.find(r => r.op === 'invoke_agent');
    const markers = db.features.map((f): MapMarker => ({lon: f.geometry.coordinates[0], lat: f.geometry.coordinates[1], label: f.properties.status === 'present' ? f.properties.cls : `${f.properties.cls} (${f.properties.status})`,
      confidence: f.properties.agent_confidence, status: 'confirmed', at_ms: null}));   // every database row is a recorded claim
    return {...empty, steps, markers,
      elapsed_ms: steps.reduce((m, st) => Math.max(m, st.end_ms ?? 0), 0),
      cost_usd: steps.reduce((sum, st) => sum + (st.model?.cost_usd ?? 0), 0),
      input: {...empty.input, title: bundle.card_summary.title, goal: bundle.card_summary.goal},
      context: {model_id: s(chat?.attributes['gen_ai.request.model']) ?? '', provider: s(chat?.attributes['gen_ai.provider.name']) ?? '',
        harness: s(agent?.attributes['treehouse.harness']) ?? '', system_prompt: null,
        items: Object.entries(bundle.manifest_summary.backends).map(([label, detail]) => ({label, tokens: null, detail}))}};
  },
  // The local API starts pinned presets (task + agent). Places are the distinct tasks, agents the distinct
  // model/harness pairs; starting picks the preset that matches both. The prompt is not sent.
  async places(signal) {
    const tasks = await presets(signal), seen = new Set<string>();
    return tasks.filter(t => !seen.has(t.task_id) && seen.add(t.task_id)).map(t => ({place_id: t.task_id, title: t.title, goal: t.goal, aoi_bbox: null, editable_goal: false}));
  },
  async agents(signal) {
    const tasks = await presets(signal), seen = new Map<string, Agent>();
    for (const t of tasks) { const id = `${t.model_id}|${t.harness}`; if (!seen.has(id)) seen.set(id, {agent_id: id, label: `${t.harness} · ${t.model_id}`, model_id: t.model_id, provider: 'local API', harness: t.harness, note: 'As configured in the backend presets.'}); }
    return [...seen.values()];
  },
  async startRun(req) {
    const preset = (await presets()).find(t => t.task_id === req.place_id && `${t.model_id}|${t.harness}` === req.agent_id);
    if (!preset) throw new Error('No backend preset runs this task with that agent.');
    return (await request('/api/runs', decodeStarted, undefined, {preset_id: preset.preset_id})).run_id;
  },
};
