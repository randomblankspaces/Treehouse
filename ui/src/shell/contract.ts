/** Shell seam: everything both interfaces (storybook and dev) read. Backends plug in by implementing
 *  TreehouseClient and Narrator; nothing else in the shell touches the network. */
import type { Json } from '../api.ts';
export type { Json };

/** OpenTelemetry GenAI operation names, as the backend records them. */
export type StepKind = 'invoke_agent' | 'chat' | 'execute_tool';
export type StepStatus = 'running' | 'ok' | 'error';
export type RunStatus = 'queued' | 'running' | 'complete' | 'failed';
/** Why a step matters to a reviewer. Key = foundation_model | data_access. */
export type Focus = 'foundation_model' | 'data_access' | 'planning' | 'claim' | 'limitation' | 'other';

export type RunInput = {
  task_id: string; title: string; goal: string;
  aoi_bbox: [number, number, number, number] | null;   // [west, south, east, north]
  time_window: [string, string] | null;
  tools_allowed: string[];
  data_allowlist: {source_id: string; kind: string; license: string}[];
};
export type RunContext = {
  model_id: string; provider: string; harness: string;
  system_prompt: string | null;
  items: {label: string; tokens: number | null; detail: string}[];   // what filled the context window
};
export type Decision = {rationale: string; alternatives: {option: string; reason: string}[]; confidence: number};
/** RV verdict for one decision, folded for the tree chip. */
export type DecisionVerdict = 'sound' | 'invalid' | 'not_evaluated';
export type RvResult = {rule_id: string; verdict: 'pass' | 'fail' | 'not_applicable'; reason: string};
/** A node in the agent's decision tree, linked to its parent by parent_id (root = parent_id null). */
export type DecisionNode = {
  decision_id: string; parent_id: string | null; parent_source: 'recorded' | 'derived'; is_root: boolean;
  trial_id: string; tool: string | null; action_id: string | null;
  rationale: string; alternatives: {option: string; reason: string}[]; confidence: number | null;
  sequence: number | null; status: string; verdict: DecisionVerdict; rv: RvResult[]; claim_ids: string[];
};
/** How a claim's confidence was formed (F3): stated, and which checks raised or lowered it. */
export type ConfidenceProvenance = {
  stated: number | null; label: 'earned' | 'unearned' | 'unestablished';
  cited_evidence: boolean; raised: string[]; lowered: string[];
};
export type TraceStep = {
  span_id: string; trial_id?: string; decision_id?: string; parent_span_id: string | null; kind: StepKind; name: string;
  start_ms: number; end_ms: number | null; status: StepStatus;
  model?: {model_id: string; input_tokens: number | null; output_tokens: number | null; cost_usd: number | null; thinking: string | null; stop_reason: string | null};
  tool?: {name: string; args: Record<string, Json>; result: string | null; bytes_read: number | null; result_metadata?: Json};
  decision?: Decision;           // the model's recorded reason for this action
  error?: {type: string; message: string};
  attributes: Record<string, Json>;
};
export type RunSummary = {run_id: string; title: string; status: RunStatus; synthetic: boolean};
/** Recorded agent predictions; presence never establishes independent ground truth. */
export type MapMarker = {lon: number; lat: number; label: string; confidence: number | null;
  status: 'present' | 'absent' | 'cannot_assess' | 'intact' | 'damaged' | 'destroyed'; at_ms: number | null;
  claim_id: string; trial_id: string; evidence_refs: {result_id: string; role: string}[]; decision_id: string | null;
  confidence_provenance?: ConfidenceProvenance | null};
export type NumericScore = {metric: string; value: number | null; unit: 'percent' | 'raw'; numerator: number | null; denominator: number | null; basis: string; status: 'available' | 'unavailable' | 'method_test_only'; reason: string | null; trial_id?: string};
export type EvaluationSection = {scores?: NumericScore[]; status: 'available' | 'unavailable' | 'method_test_only'; value: Json; reason: string | null};
export const EVALUATIONS = ['reasoning_rules', 'reviewer', 'agentcore', 'output', 'calibration', 'predicted_accuracy'] as const;
export type RunSnapshot = RunSummary & {
  mode: 'live' | 'replay' | 'fake' | 'mock' | 'unknown';
  thinking_summary?: {status: 'available' | 'unavailable'; basis: 'recorded_decisions'; text: string; reason: string | null};
  provenance: {embeddings: 'synthetic_reference_derived' | 'synthetic' | 'real' | 'unknown';
    reference: 'synthetic' | 'real' | 'none' | 'unknown'; vision: 'used' | 'not_used' | 'unknown'; limitations: string[]};
  evaluation: Record<typeof EVALUATIONS[number], EvaluationSection>;
  started_at: string | null; elapsed_ms: number | null; cost_usd: number | null;
  cost_basis?: string; timing_basis?: string;
  input: RunInput; context: RunContext; steps: TraceStep[]; markers: MapMarker[];
  decisions?: DecisionNode[];
};
/** A task the backend can start: a pinned preset with a place and a default prompt. */
export type Place = {place_id: string; title: string; goal: string; aoi_bbox: [number, number, number, number] | null; editable_goal: boolean};
export type StartRequest = {place_id: string; goal: string; agent_id: string};
/** Who does the task: a model behind a harness. The thing Treehouse evaluates. */
export type Agent = {agent_id: string; label: string; model_id: string; provider: string; harness: string; note: string};
export interface TreehouseClient {
  readonly label: string;   // shown in the header, e.g. "MOCK" or "local API"
  listRuns(signal?: AbortSignal): Promise<RunSummary[]>;
  /** Poll while status is queued/running; a partial snapshot is expected mid-run. */
  snapshot(runId: string, signal?: AbortSignal): Promise<RunSnapshot>;
  places(signal?: AbortSignal): Promise<Place[]>;
  agents(signal?: AbortSignal): Promise<Agent[]>;
  startRun(req: StartRequest): Promise<string>;   // returns run_id
}
export type Narration = {text: string; audio_url: string | null};
export interface Narrator { line(step: TraceStep, run: RunSnapshot): Promise<Narration | null> }

const FOCUS: Record<string, Focus> = {
  list_embedding_sources: 'foundation_model', build_index: 'foundation_model', retrieve: 'foundation_model',
  classify: 'foundation_model', strands_label: 'foundation_model',
  get_examples: 'data_access', imagery_window: 'data_access', stac_search: 'data_access',
  record_decision: 'planning', submit_understanding: 'planning', aggregate: 'planning',
  record_claim: 'claim', note_limitation: 'limitation',
};
export const focusOf = (step: TraceStep): Focus => (step.tool && FOCUS[step.tool.name]) || 'other';
export const isKey = (step: TraceStep) => ['foundation_model', 'data_access'].includes(focusOf(step));
export const FOCUS_LABEL: Record<Focus, string> = {
  foundation_model: 'Foundation model', data_access: 'Data access', planning: 'Planning',
  claim: 'Claim', limitation: 'Limitation', other: 'Step',
};
export const terminal = (s: RunStatus) => s === 'complete' || s === 'failed';
