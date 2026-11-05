/** Plain-language views of a run, shared by the storybook and the dev view. */
import { FOCUS_LABEL, focusOf, isKey, terminal, type RunSnapshot, type TraceStep } from './contract.ts';

/** The run as it stood at run-clock time t (for time travel in the dev map). */
export function asOf(s: RunSnapshot, t: number): RunSnapshot {
  const steps = s.steps.filter(x => x.start_ms <= t).map(x => x.end_ms !== null && x.end_ms > t ? {...x, end_ms: null, status: 'running' as const, error: undefined, tool: x.tool && {...x.tool, result: null}} : x);
  return {...s, steps, elapsed_ms: s.elapsed_ms === null ? null : Math.min(t, s.elapsed_ms), markers: s.markers.filter(m => m.at_ms === null || m.at_ms <= t)};
}

/** Time since the task was sent; frozen at the run's length once it finishes. */
export function sinceStart(s: RunSnapshot, now = Date.now()) {
  if (terminal(s.status) || !s.started_at) return s.elapsed_ms;
  return Math.max(s.elapsed_ms ?? 0, now - Date.parse(s.started_at));
}
export const clock = (ms: number | null) => { if (ms === null) return 'unavailable'; const t = Math.max(0, ms) / 1000; return `${String(Math.floor(t / 60)).padStart(2, '0')}:${String(Math.floor(t % 60)).padStart(2, '0')}`; };

export const PHASES: [string, string[]][] = [
  ['Choose embeddings', ['list_embedding_sources']], ['Build the index', ['build_index']], ['Learn from examples', ['get_examples']],
  ['Find candidates', ['retrieve', 'classify']], ['Look closer (aerial imagery)', ['imagery_window', 'stac_search']],
  ['Label with Strands', ['strands_label']], ['Count and state limits', ['aggregate', 'note_limitation', 'record_claim']],
];
export type PhaseState = 'pending' | 'active' | 'done' | 'recovered' | 'error' | 'skipped';
export function phaseState(steps: TraceStep[], tools: string[], done: boolean): PhaseState {
  const mine = steps.filter(s => s.tool && tools.includes(s.tool.name));
  if (!mine.length) return done ? 'skipped' : 'pending';
  if (mine.some(s => s.status === 'running')) return 'active';
  if (mine[mine.length - 1].status === 'error') return 'error';
  return mine.some(s => s.status === 'error') ? 'recovered' : 'done';
}

export const KIND_WORD: Record<TraceStep['kind'], string> = {invoke_agent: 'Agent', chat: 'Model', execute_tool: 'Tool'};
/** Short title for a step, e.g. "Thinks", "Strands sub-agent", "build_index". */
export function title(s: TraceStep) {
  if (s.kind === 'execute_tool') return s.tool?.name ?? s.name;
  if (s.kind === 'chat') return s.parent_span_id && !s.name.startsWith('chat') ? s.name : s.name === 'chat' ? 'Thinks' : s.name.replace(/^chat\s*/, 'Thinks ');
  return s.parent_span_id ? `Sub-agent: ${s.name.replace(/^invoke_agent\s*/, '')}` : 'Whole run';
}
/** One line of what happened, for list rows. */
export function gist(s: TraceStep) {
  if (s.error) return `Failed: ${s.error.message}`;
  if (s.status === 'running') return s.kind === 'chat' ? 'Thinking…' : 'Working…';
  if (s.kind === 'chat') return s.model?.thinking ?? `${s.model?.input_tokens ?? 'unavailable'} tokens in, ${s.model?.output_tokens ?? 'unavailable'} out`;
  if (s.kind === 'execute_tool') return s.decision?.rationale ?? s.tool?.result ?? '';
  return s.parent_span_id ? 'A helper agent, run inside the tool call above.' : 'Everything the agent did, start to finish.';
}
/** A sentence a newcomer can read. */
export function sentence(s: TraceStep) {
  const took = s.end_ms === null ? 'is still running' : `took ${((s.end_ms - s.start_ms) / 1000).toFixed(1)} s`;
  const how = s.status === 'error' ? `and failed (${s.error?.type ?? 'error'})` : s.status === 'ok' ? 'and succeeded' : '';
  if (s.kind === 'execute_tool') return `The agent called the tool ${s.tool?.name}${isKey(s) ? `, a ${FOCUS_LABEL[focusOf(s)].toLowerCase()} step` : ''}. It ${took} ${how}.`;
  if (s.kind === 'chat') return `The model read ${s.model?.input_tokens?.toLocaleString() ?? 'unavailable'} tokens of context and decided what to do next. It ${took}.`;
  return s.parent_span_id ? `A helper agent ran inside the tool call above. It ${took}.` : `The whole agent run. It ${took} ${how}.`;
}

/** Map bounds when the task has no AOI: the recorded markers plus a margin. */
export function bboxOf(s: RunSnapshot): [number, number, number, number] | null {
  if (s.input.aoi_bbox) return s.input.aoi_bbox;
  if (!s.markers.length) return null;
  const lon = s.markers.map(m => m.lon), lat = s.markers.map(m => m.lat), pad = 0.002;
  return [Math.min(...lon) - pad, Math.min(...lat) - pad, Math.max(...lon) + pad, Math.max(...lat) + pad];
}

/** Plain words for provenance ids shown to people. */
const WORDS: Record<string, string> = {replay: 'Replay of a recorded live run', live: 'Live run', mock: 'Scripted mock',
  real: 'real LGND Clay embeddings', synthetic: 'synthetic embeddings', synthetic_reference_derived: 'synthetic embeddings (derived from the reference)',
  unknown: 'embeddings: unknown', vision_not_used: 'no vision model used', vision_used: 'vision model used'};
export const words = (id: string) => WORDS[id] ?? id.replace(/_/g, ' ');
