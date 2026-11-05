/** Export a run: input, context, thinking, trace, decisions, narration, map markers.
 *  Chromium: the user picks a folder once and we write files into a new subfolder (File System Access API).
 *  Elsewhere: one JSON bundle download plus the readable summary. */
import { FOCUS_LABEL, focusOf, isKey, type Narration, type RunSnapshot } from './contract.ts';

type DirHandle = {getDirectoryHandle(name: string, o: {create: true}): Promise<DirHandle>;
  getFileHandle(name: string, o: {create: true}): Promise<{createWritable(): Promise<{write(d: string): Promise<void>; close(): Promise<void>}>}>};
type Picker = (o?: {mode: 'readwrite'; id?: string}) => Promise<DirHandle>;

const usd = (v: number) => `$${v.toFixed(4)}`;
export function summaryMarkdown(s: RunSnapshot, lines: Narration[]) {
  const keys = s.steps.filter(isKey), errors = s.steps.filter(x => x.error);
  const tokens = s.steps.reduce((t, x) => t + (x.model?.input_tokens ?? 0) + (x.model?.output_tokens ?? 0), 0);
  const count = (st: string) => s.markers.filter(m => m.status === st).length;
  return [
    `# ${s.title}`, '', `Run \`${s.run_id}\` · ${s.status} · ${(s.elapsed_ms / 1000).toFixed(1)} s · ${usd(s.cost_usd)} · ${tokens.toLocaleString()} tokens${s.synthetic ? ' · synthetic/mock data' : ''}`, '',
    '## Input', s.input.goal, '', `- Task: ${s.input.task_id}`, `- Area (W,S,E,N): ${s.input.aoi_bbox?.join(', ') ?? '—'}`, `- Time window: ${s.input.time_window?.join(' → ') ?? '—'}`,
    `- Data: ${s.input.data_allowlist.map(d => d.source_id).join(', ') || '—'}`, `- Tools: ${s.input.tools_allowed.join(', ') || '—'}`, '',
    '## Context', `- Model: ${s.context.model_id}`, `- Provider: ${s.context.provider}`, `- Harness: ${s.context.harness}`, ...s.context.items.map(i => `- ${i.label}: ${i.detail}${i.tokens ? ` (${i.tokens} tokens)` : ''}`), '',
    '## Key decisions', ...keys.flatMap(k => [`### ${FOCUS_LABEL[focusOf(k)]}: ${k.tool?.name} (${k.status})`, k.decision?.rationale ?? '', k.decision ? `Self-reported confidence: ${Math.round(k.decision.confidence * 100)} %` : '',
      ...(k.decision?.alternatives ?? []).map(a => `- Not chosen: ${a.option}: ${a.reason}`), '']),
    '## Thinking', ...s.steps.filter(x => x.model?.thinking).map(x => `- [${(x.start_ms / 1000).toFixed(1)} s] ${x.model!.thinking}`), '',
    '## How the database was built', `${count('confirmed')} confirmed · ${count('rejected')} rejected · ${count('unsure')} unsure (labels as recorded by the agent; not graded here).`, '',
    '## Errors', ...(errors.length ? errors.map(e => `- ${e.tool?.name ?? e.name}: ${e.error!.type}: ${e.error!.message}`) : ['None.']), '',
    '## Narration', ...[...lines].reverse().map(l => `- ${l.text}`), '',
  ].join('\n');
}

export function exportFiles(s: RunSnapshot, lines: Narration[]): Record<string, string> {
  const j = (v: unknown) => JSON.stringify(v, null, 2);
  return {
    'README.md': summaryMarkdown(s, lines),
    'input.json': j(s.input),
    'context.json': j(s.context),
    'trace.json': j(s.steps),
    'decisions.json': j(s.steps.filter(x => x.decision).map(x => ({span_id: x.span_id, tool: x.tool?.name, focus: focusOf(x), status: x.status, ...x.decision}))),
    'thinking.json': j(s.steps.filter(x => x.model).map(x => ({span_id: x.span_id, start_ms: x.start_ms, thinking: x.model!.thinking}))),
    'markers.geojson': j({type: 'FeatureCollection', features: s.markers.map(m => ({type: 'Feature', geometry: {type: 'Point', coordinates: [m.lon, m.lat]}, properties: {label: m.label, status: m.status, confidence: m.confidence}}))}),
    'narration.txt': [...lines].reverse().map(l => l.text).join('\n'),
    'run.json': j({schema_version: 'treehouse.shell-export/1', exported_at: new Date().toISOString(), run: s, narration: [...lines].reverse()}),
  };
}

export const canPickFolder = () => typeof (window as unknown as {showDirectoryPicker?: Picker}).showDirectoryPicker === 'function';

/** Returns a short description of where the files went. Throws AbortError if the user cancels. */
export async function exportRun(s: RunSnapshot, lines: Narration[]): Promise<string> {
  const files = exportFiles(s, lines);
  const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-');
  const name = `treehouse-${s.run_id}-${stamp}`.replace(/[^A-Za-z0-9_.-]/g, '_');
  const picker = (window as unknown as {showDirectoryPicker?: Picker}).showDirectoryPicker;
  if (picker) {
    const root = await picker({mode: 'readwrite', id: 'treehouse-exports'});
    const dir = await root.getDirectoryHandle(name, {create: true});
    for (const [file, text] of Object.entries(files)) { const w = await (await dir.getFileHandle(file, {create: true})).createWritable(); await w.write(text); await w.close(); }
    return `Saved ${Object.keys(files).length} files to the folder “${name}”.`;
  }
  const download = (file: string, text: string, type: string) => {
    const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([text], {type})); a.download = file; a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  };
  download(`${name}.json`, files['run.json'], 'application/json');
  download(`${name}.md`, files['README.md'], 'text/markdown');
  return `Downloaded ${name}.json and ${name}.md (this browser cannot write to a folder).`;
}
