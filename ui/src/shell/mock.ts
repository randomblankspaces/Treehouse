/** Scripted mock run: Nagoya Port warehouses (tasks/t1-nagoya-warehouses.yaml), replayed in real time.
 *  Numbers are illustrative, not measured; the UI labels this client MOCK. */
import { FOCUS_LABEL, focusOf, isKey, type Agent, type Json, type MapMarker, type Narrator, type Place, type RunSnapshot, type RunSummary, type TraceStep, type TreehouseClient } from './contract.ts';

// shortcut: illustrative $/token per agent, replace with backend-measured cost
const AGENTS: (Agent & {price: [number, number]})[] = [
  {agent_id: 'strands-sonnet', label: 'Strands · Claude Sonnet', model_id: 'anthropic.claude-sonnet (mock)', provider: 'Amazon Bedrock (mock)', harness: 'strands-agents worker (mock)', note: 'Default. Strong reasoning, mid cost.', price: [3 / 1e6, 15 / 1e6]},
  {agent_id: 'strands-nova', label: 'Strands · Amazon Nova Pro', model_id: 'amazon.nova-pro (mock)', provider: 'Amazon Bedrock (mock)', harness: 'strands-agents worker (mock)', note: 'AWS-native and cheaper.', price: [0.8 / 1e6, 3.2 / 1e6]},
  {agent_id: 'plain-haiku', label: 'Plain loop · Claude Haiku', model_id: 'anthropic.claude-haiku (mock)', provider: 'Amazon Bedrock (mock)', harness: 'plain tool loop (mock)', note: 'Fastest, cheapest baseline.', price: [1 / 1e6, 5 / 1e6]},
];
let liveAgent = AGENTS[0];
type Beat = {at: number; dur: number; kind: TraceStep['kind']; name: string; parent?: string; id: string;
  think?: string; tin?: number; tout?: number; stop?: string;
  tool?: string; args?: Record<string, Json>; result?: string; bytes?: number;
  why?: string; alts?: [string, string][]; conf?: number; error?: [string, string]};

const AOI: [number, number, number, number] = [136.82, 35.05, 136.92, 35.12];
const BEATS: Beat[] = [
  {id: 'a0', at: 0, dur: 62.5, kind: 'invoke_agent', name: 'invoke_agent worker'},
  {id: 'c1', parent: 'a0', at: 0.3, dur: 3.2, kind: 'chat', name: 'chat', tin: 2140, tout: 310, stop: 'tool_use',
    think: 'The AOI is about 10 × 8 km of port land. A warehouse here is ≥ 1,600 m², so roughly a 40 m side. Scanning 0.5 m aerial over the whole area is too slow and costly; I should narrow with embeddings first, then check candidates on imagery.'},
  {id: 't1', parent: 'a0', at: 3.6, dur: 1.1, kind: 'execute_tool', name: 'execute_tool list_embedding_sources', tool: 'list_embedding_sources', args: {bbox: AOI, year: 2024},
    result: 'aef-10m-annual (64-d, 10 m, 2024) · lgnd-clay-embeddings (1024-d, 1.28 km cells, monthly)',
    why: 'See which foundation-model embeddings cover the AOI and at what resolution before committing.', alts: [['Go straight to aerial imagery', 'Thousands of 0.5 m windows; slow and expensive for a first pass']], conf: 0.8},
  {id: 'c2', parent: 'a0', at: 4.9, dur: 3.6, kind: 'chat', name: 'chat', tin: 3020, tout: 420, stop: 'tool_use',
    think: 'Clay cells are 1.28 km — a single warehouse is a tiny fraction of that cell, so similarity will blur into the whole port. AEF at 10 m pooled to 160 m cells keeps a warehouse as a meaningful part of the cell.'},
  {id: 't2', parent: 'a0', at: 8.7, dur: 4.4, kind: 'execute_tool', name: 'execute_tool build_index', tool: 'build_index', args: {source_id: 'aef-10m-annual', cell_m: 160, year: 2024, bbox: AOI}, bytes: 38_400_000,
    result: '2,912 cells indexed (160 m), 0 missing',
    why: 'AEF 10 m pooled to 160 m cells: fine enough that a ≥ 40 m building moves the cell embedding.', alts: [['LGND Clay 1.28 km', 'Cell far larger than the target; signal diluted'], ['Clay on 160 m chips', 'Not precomputed for this AOI; would need on-the-fly inference']], conf: 0.72},
  {id: 't3', parent: 'a0', at: 13.4, dur: 1.6, kind: 'execute_tool', name: 'execute_tool get_examples', tool: 'get_examples', args: {cls: 'warehouse', positives: 12, negatives: 24, outside_aoi: true},
    result: '12 warehouse + 24 look-alike examples (factories, markets, hangars) from outside the AOI',
    why: 'Labelled examples from outside the AOI so the probe never sees the answer key; negatives target the known look-alikes.', alts: [['Zero-shot text query', 'Report shows ~59 % recall@k for zero-shot vs ~77–80 % with labels']], conf: 0.7},
  {id: 'c3', parent: 'a0', at: 15.2, dur: 3.1, kind: 'chat', name: 'chat', tin: 4410, tout: 380, stop: 'tool_use',
    think: 'With 36 examples a linear probe on the embeddings is cheap and should beat raw cosine similarity. Take a generous top-k so small warehouses are not dropped early; imagery will remove false positives.'},
  {id: 't4', parent: 'a0', at: 18.5, dur: 2.2, kind: 'execute_tool', name: 'execute_tool retrieve', tool: 'retrieve', args: {method: 'linear_probe', k: 400, index: 'aef-10m-annual@160m'},
    result: '400 candidate cells, probe score ≥ 0.61',
    why: 'Recall first: keep 400 of 2,912 cells so small warehouses survive to the imagery check.', alts: [['k = 150', 'Cheaper, but small warehouses are the known failure mode']], conf: 0.66},
  {id: 'c4', parent: 'a0', at: 21.0, dur: 2.8, kind: 'chat', name: 'chat', tin: 5880, tout: 290, stop: 'tool_use',
    think: 'Candidates will include port sheds and factories. Check the top cells on GSI 0.5 m aerial; at 10 m Sentinel the roof types are indistinguishable.'},
  {id: 't5', parent: 'a0', at: 24.0, dur: 6.0, kind: 'execute_tool', name: 'execute_tool imagery_window', tool: 'imagery_window', args: {source_id: 'gsi-seamless-aerial-japan', cells: 48, side_m: 160, gsd_m: 0.5}, bytes: 0,
    error: ['TimeoutError', 'Tile server did not answer within 6 s'],
    why: 'Inspect the 48 highest-scoring cells at 0.5 m to separate warehouses from look-alikes.', alts: [['Sentinel-2 10 m', 'Cannot resolve roof type or loading docks']], conf: 0.75},
  {id: 'c5', parent: 'a0', at: 30.3, dur: 1.9, kind: 'chat', name: 'chat', tin: 6120, tout: 140, stop: 'tool_use',
    think: 'Timeout, not a missing tile. Retry once with smaller batches rather than dropping the imagery check.'},
  {id: 't6', parent: 'a0', at: 32.4, dur: 5.2, kind: 'execute_tool', name: 'execute_tool imagery_window', tool: 'imagery_window', args: {source_id: 'gsi-seamless-aerial-japan', cells: 48, side_m: 160, gsd_m: 0.5, batch: 12}, bytes: 61_200_000,
    result: '48 chips at 0.5 m (4 batches), cloud-free',
    why: 'Retry in batches of 12; the imagery check is the main guard against false positives.', alts: [['Skip imagery', 'Would report every port shed as a warehouse']], conf: 0.8},
  {id: 't7', parent: 'a0', at: 38.0, dur: 14.5, kind: 'execute_tool', name: 'execute_tool strands_label', tool: 'strands_label', args: {sub_agent: 'strands-vision-labeler', model: 'anthropic.claude-sonnet (vision)', chips: 48, labels: ['warehouse', 'factory', 'market', 'hangar', 'unsure']},
    result: '31 warehouse · 11 factory · 6 unsure → 31 rows written to the claims database',
    why: 'Delegate chip labelling to a Strands vision sub-agent with an explicit look-alike label set; it writes each label with its chip as evidence.', alts: [['Label with the probe score only', 'Probe cannot tell a warehouse from a factory roof'], ['Label in this context', 'Fills my context with 48 images; slower and costlier']], conf: 0.7},
  {id: 's1', parent: 't7', at: 38.4, dur: 13.8, kind: 'invoke_agent', name: 'invoke_agent strands-vision-labeler'},
  {id: 's2', parent: 's1', at: 38.6, dur: 6.4, kind: 'chat', name: 'chat (vision, chips 1–24)', tin: 21800, tout: 1320, stop: 'end_turn',
    think: 'Long rectangular roofs with loading bays on one side and truck aprons → warehouse. Chimneys, tanks or pipe racks → factory. Chip 17 is a covered market; chip 22 is ambiguous.'},
  {id: 's3', parent: 's1', at: 45.2, dur: 6.6, kind: 'chat', name: 'chat (vision, chips 25–48)', tin: 21600, tout: 1290, stop: 'end_turn',
    think: 'Chips 31 and 40 look like warehouses but under 40 m on a side; label unsure rather than guess.'},
  {id: 'c6', parent: 'a0', at: 52.8, dur: 3.4, kind: 'chat', name: 'chat', tin: 9420, tout: 460, stop: 'tool_use',
    think: '31 confident labels from 48 chips. Only 48 of 400 candidates were checked on imagery, so the count must come with a range and the unreviewed cells must be stated.'},
  {id: 't8', parent: 'a0', at: 56.4, dur: 1.4, kind: 'execute_tool', name: 'execute_tool aggregate', tool: 'aggregate', args: {confirmed: 31, unsure: 6, unreviewed_candidates: 352},
    result: '31 confirmed; estimated 31–58 in the AOI (unreviewed candidates extrapolated at the observed hit rate)',
    why: 'Report a count with a range instead of a single number, because most candidates were not inspected.', alts: [['Report 31', 'Would silently claim exhaustive coverage']], conf: 0.6},
  {id: 't9', parent: 'a0', at: 58.0, dur: 1.0, kind: 'execute_tool', name: 'execute_tool note_limitation', tool: 'note_limitation', args: {text: '352 candidate cells not checked at 0.5 m; warehouses under ~40 m side likely missed.'},
    result: 'Limitation recorded',
    why: 'Make the coverage gap and the small-building weakness explicit for the reviewer.', alts: [], conf: 0.9},
  {id: 'c7', parent: 'a0', at: 59.2, dur: 3.0, kind: 'chat', name: 'chat', tin: 10380, tout: 520, stop: 'end_turn',
    think: 'Done: method, resolution choice (AEF @160 m, then 0.5 m aerial), searched area, unreviewed area and a ranged count are all stated.'},
];
const TOTAL_MS = 62_500;
const GOAL = 'Find every warehouse in the area of interest (≥ ~1,600 m² floor area). Do not count factories, markets, hangars or other large roofs. Return each as a point with the resources and image windows used, your confidence, the resolution you chose and why, the area searched, any area not reviewed, and a count with a range.';
let goalOverride: string | null = null;

const LABELLER = BEATS.find(b => b.tool === 'strands_label')!;
// 48 chips the Strands labeller looked at; revealed as that step progresses. Kept in the northern,
// landward third of the AOI so they sit on land in the map art.
const MARKERS: MapMarker[] = (() => {
  let seed = 7; const r = () => (seed = (seed * 1664525 + 1013904223) >>> 0) / 2 ** 32;
  const out = Array.from({length: 48}, (_, i): MapMarker => {
    const status = i < 31 ? 'confirmed' : i < 42 ? 'rejected' : 'unsure';
    return {lon: AOI[0] + (0.05 + 0.9 * r()) * (AOI[2] - AOI[0]), lat: AOI[3] - (0.06 + 0.28 * r()) * (AOI[3] - AOI[1]),
      status, label: status === 'confirmed' ? 'warehouse' : status === 'rejected' ? 'factory' : 'unsure',
      confidence: status === 'unsure' ? 0.3 + 0.2 * r() : 0.65 + 0.3 * r(), at_ms: 0};
  });
  for (let i = out.length - 1; i > 0; i--) { const j = Math.floor(r() * (i + 1)); [out[i], out[j]] = [out[j], out[i]]; }
  return out.map((m, i) => ({...m, at_ms: Math.round((LABELLER.at + (i + 1) / out.length * LABELLER.dur) * 1000)}));
})();

function steps(elapsed: number, ids: Map<string, string>, agent = AGENTS[0]): TraceStep[] {
  const [PRICE_IN, PRICE_OUT] = agent.price, MODEL = agent.model_id;
  const out: TraceStep[] = [];
  for (const b of BEATS) {
    const start = b.at * 1000, end = start + b.dur * 1000;
    if (start > elapsed) break;
    const done = end <= elapsed;
    const id = ids.get(b.id)!;
    const step: TraceStep = {span_id: id, parent_span_id: b.parent ? ids.get(b.parent)! : null, kind: b.kind, name: b.name,
      start_ms: start, end_ms: done ? end : null, status: !done ? 'running' : b.error ? 'error' : 'ok',
      attributes: {'gen_ai.operation.name': b.kind, 'treehouse.run.id': 'mock', ...(b.tool ? {'gen_ai.tool.name': b.tool} : {})}};
    if (b.kind === 'chat') step.model = {model_id: MODEL, input_tokens: b.tin!, output_tokens: done ? b.tout! : 0,
      cost_usd: done ? b.tin! * PRICE_IN + b.tout! * PRICE_OUT : 0, thinking: done ? b.think! : null, stop_reason: done ? b.stop! : null};
    if (b.tool) step.tool = {name: b.tool, args: b.args ?? {}, result: done && !b.error ? b.result ?? null : null, bytes_read: done ? b.bytes ?? 0 : 0};
    if (b.why) step.decision = {rationale: b.why, alternatives: (b.alts ?? []).map(([option, reason]) => ({option, reason})), confidence: b.conf ?? 0.5};
    if (done && b.error) step.error = {type: b.error[0], message: b.error[1]};
    out.push(step);
  }
  return out;
}

const RUNS = [
  {run_id: 'mock-nagoya-live', title: 'Nagoya Port warehouses — live replay', live: true},
  {run_id: 'mock-nagoya-recorded', title: 'Nagoya Port warehouses — recorded', live: false},
];
const startedAt = new Map<string, number>();
const spanIds = (runId: string) => new Map(BEATS.map((b, i) => [b.id, `${runId.slice(-4)}${(i + 1).toString(16).padStart(12, '0')}`]));

function snapshotOf(runId: string): RunSnapshot {
  const run = RUNS.find(r => r.run_id === runId);
  if (!run) throw new Error('Run not found');
  if (run.live && !startedAt.has(runId)) startedAt.set(runId, Date.now());
  const elapsed = run.live ? Math.min(Date.now() - startedAt.get(runId)!, TOTAL_MS) : TOTAL_MS;
  const agent = run.live ? liveAgent : AGENTS[0];
  const list = steps(elapsed, spanIds(runId), agent);
  const status = elapsed >= TOTAL_MS ? 'complete' : 'running';
  return {
    run_id: run.run_id, title: run.title, status, synthetic: true,
    started_at: new Date(run.live ? startedAt.get(runId)! : Date.now() - 3_600_000).toISOString(),
    elapsed_ms: elapsed, cost_usd: list.reduce((sum, s) => sum + (s.model?.cost_usd ?? 0), 0),
    input: {task_id: 't1-nagoya-warehouses', title: 'Warehouses in a Nagoya port/logistics district',
      goal: run.live ? goalOverride ?? GOAL : GOAL,
      aoi_bbox: AOI, time_window: ['2024-01-01', '2024-12-31'],
      tools_allowed: ['record_decision', 'list_embedding_sources', 'build_index', 'get_examples', 'retrieve', 'classify', 'strands_label', 'imagery_window', 'aggregate', 'record_claim', 'note_limitation', 'submit_understanding'],
      data_allowlist: [
        {source_id: 'aef-10m-annual', kind: 'embeddings', license: 'CC-BY-4.0'},
        {source_id: 'lgnd-clay-embeddings', kind: 'embeddings', license: 'CC-BY-4.0'},
        {source_id: 'sentinel-2-l2a-cogs', kind: 'imagery', license: 'Copernicus Sentinel'},
        {source_id: 'gsi-seamless-aerial-japan', kind: 'imagery', license: 'GSI Japan (attribution)'}]},
    context: {model_id: agent.model_id, provider: agent.provider, harness: agent.harness,
      system_prompt: 'You are a geospatial analyst. Use only the tools and data sources provided. Record a decision (why, alternatives, confidence) before each action. Never claim coverage you did not inspect.',
      items: [
        {label: 'System prompt', tokens: 410, detail: 'Role, rules, decision-recording requirement'},
        {label: 'Task card', tokens: 380, detail: 'Goal, AOI polygon, time window, class definition'},
        {label: 'Tool schemas', tokens: 1350, detail: '12 tools incl. the Strands labelling sub-agent'},
        {label: 'Tool results', tokens: null, detail: 'Grows each turn; see per-call input tokens'}]},
    steps: list,
    markers: MARKERS.filter(m => m.at_ms! <= elapsed),
  };
}

export const mockClient: TreehouseClient & {replay(runId: string): void} = {
  label: 'MOCK',
  async listRuns() {
    return RUNS.map((r): RunSummary => {
      const s = snapshotOf(r.run_id);
      return {run_id: r.run_id, title: r.title, status: s.status, synthetic: true};
    });
  },
  async snapshot(runId) { return snapshotOf(runId); },
  async places(): Promise<Place[]> {
    return [{place_id: 't1-nagoya-warehouses', title: 'Nagoya Port, Japan — warehouses', goal: GOAL, aoi_bbox: AOI, editable_goal: true}];
  },
  async agents() { return AGENTS.map(({price: _, ...a}) => a); },
  async startRun(req) {
    goalOverride = req.goal.trim() || null; liveAgent = AGENTS.find(a => a.agent_id === req.agent_id) ?? AGENTS[0];
    startedAt.set(RUNS[0].run_id, Date.now()); return RUNS[0].run_id;
  },
  replay(runId) { startedAt.set(runId, Date.now()); },
};

/** Template captions. AWS plan: Bedrock writes the line, Polly returns audio_url. */
export const mockNarrator: Narrator = {
  async line(step) {
    if (step.error) return {text: `A ${step.tool?.name ?? 'tool'} call failed: ${step.error.message}. Watch whether the agent retries or gives up.`, audio_url: null};
    if (step.status !== 'ok' || !step.decision || !isKey(step)) return null;
    return {text: `${FOCUS_LABEL[focusOf(step)]} — ${step.tool!.name}: ${step.decision.rationale}`, audio_url: null};
  },
};
