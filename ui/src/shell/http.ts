/** Adapter over today's local API (`treehouse ui serve`). Reuses the validating decoders in api.ts.
 *  Gaps (see docs/design/SHELL.md): no partial snapshot mid-run, no thinking text, no AOI/time window. */
import { decodeRuns, decodeStarted, decodeTasks, request, type Run } from '../api.ts';
import { decodeSnapshot } from './snapshot.ts';
import type { Agent, RunStatus, TreehouseClient } from './contract.ts';

const status = (s: Run['status']): RunStatus => s === 'report_ready' || s === 'sealed' ? 'complete' : s;
const base = (id: string) => `/api/runs/${encodeURIComponent(id)}`;
const presets = async (signal?: AbortSignal) => (await request('/api/tasks', decodeTasks, signal)).tasks;

export const httpClient: TreehouseClient = {
  label: 'local API',
  async listRuns(signal) {
    const {runs} = await request('/api/runs', decodeRuns, signal);
    return runs.map(r => ({run_id: r.run_id, title: r.title, status: status(r.status), synthetic: r.synthetic}));
  },
  async snapshot(id, signal) {
    const snapshot = await request(`${base(id)}/snapshot`, decodeSnapshot, signal);
    if (snapshot.run_id !== id) throw new Error('The server returned a different run.');
    return snapshot;
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
    if (!preset) throw new Error('No backend preset runs this task with that agent. Live/custom configuration is unavailable.');
    if (req.goal !== preset.goal) throw new Error('Pinned preset goals are read-only; the edited goal was not launched.');
    return (await request('/api/runs', decodeStarted, undefined, {preset_id: preset.preset_id})).run_id;
  },
};
