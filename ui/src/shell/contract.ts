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
export type TraceStep = {
  span_id: string; parent_span_id: string | null; kind: StepKind; name: string;
  start_ms: number; end_ms: number | null; status: StepStatus;
  model?: {model_id: string; input_tokens: number; output_tokens: number; cost_usd: number; thinking: string | null; stop_reason: string | null};
  tool?: {name: string; args: Record<string, Json>; result: string | null; bytes_read: number};
  decision?: Decision;           // the model's recorded reason for this action
  error?: {type: string; message: string};
  attributes: Record<string, Json>;
};
export type RunSummary = {run_id: string; title: string; status: RunStatus; synthetic: boolean};
export type RunSnapshot = RunSummary & {
  started_at: string | null; elapsed_ms: number; cost_usd: number;
  input: RunInput; context: RunContext; steps: TraceStep[];
};
export interface TreehouseClient {
  readonly label: string;   // shown in the header, e.g. "MOCK" or "local API"
  listRuns(signal?: AbortSignal): Promise<RunSummary[]>;
  /** Poll while status is queued/running; a partial snapshot is expected mid-run. */
  snapshot(runId: string, signal?: AbortSignal): Promise<RunSnapshot>;
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
