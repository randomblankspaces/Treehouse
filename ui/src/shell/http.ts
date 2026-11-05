/** Adapter over today's local API (`treehouse ui serve`). Reuses the validating decoders in api.ts.
 *  Gaps (see docs/design/SHELL.md): no partial snapshot mid-run, no thinking text, no AOI/time window. */
import { decodeRuns, decodeStarted, decodeTasks, request, type Run } from '../api.ts';
import { decodeSnapshot } from './snapshot.ts';
import type { Agent, RunStatus, TreehouseClient } from './contract.ts';

const status = (s: Run['status']): RunStatus => s === 'report_ready' || s === 'sealed' ? 'complete' : s;
const base = (id: string) => `/api/runs/${encodeURIComponent(id)}`;
const presets = async (signal?: AbortSignal) => (await request('/api/tasks', decodeTasks, signal)).tasks;

/** With `treehouse ui serve --live` the server offers real Bedrock models and the places they can run on.
 *  Without it (404) the story view keeps the pinned replay presets. */
type LiveOptions = {places: {task_id: string; title: string; goal: string}[]; models: {key: string; family: string; invoke_id: string; verified: boolean}[]};
let liveCache: Promise<LiveOptions | null> | null = null;
const liveOptions = () => liveCache ??= fetch('/api/live/options').then(r => r.ok ? r.json() as Promise<LiveOptions> : null).catch(() => null);
const LIVE = 'bedrock:';
const wait = (ms: number) => new Promise(r => setTimeout(r, ms));

export const httpClient: TreehouseClient = {
  label: 'Treehouse API',
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
    const live = await liveOptions();
    if (live) return live.places.map(p => ({place_id: p.task_id, title: p.title, goal: p.goal, aoi_bbox: null, editable_goal: false}));
    const tasks = await presets(signal), seen = new Set<string>();
    return tasks.filter(t => !seen.has(t.task_id) && seen.add(t.task_id)).map(t => ({place_id: t.task_id, title: t.title, goal: t.goal, aoi_bbox: null, editable_goal: false}));
  },
  async agents(signal) {
    const live = await liveOptions();
    if (live) return live.models.map(m => ({agent_id: LIVE + m.key, label: `Strands · Amazon Bedrock · ${m.key}`, model_id: m.invoke_id,
      provider: 'Amazon Bedrock', harness: 'strands', note: `Live run on Amazon Bedrock (${m.family})${m.verified ? '' : ', unverified model'}. Each run spends money.`}));
    const tasks = await presets(signal), seen = new Map<string, Agent>();
    for (const t of tasks) { const id = `${t.model_id}|${t.harness}`; if (!seen.has(id)) seen.set(id, {agent_id: id, label: `${t.harness} · ${t.model_id}`, model_id: t.model_id, provider: 'local API', harness: t.harness, note: 'As configured in the backend presets.'}); }
    return [...seen.values()];
  },
  async startRun(req) {
    if (req.agent_id.startsWith(LIVE)) {   // a real Bedrock run: start it, then wait until it is sealed in the store
      const res = await fetch('/api/live/runs', {method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({task_id: req.place_id, model_key: req.agent_id.slice(LIVE.length)})});
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(String(body.detail ?? res.statusText));
      for (let i = 0; i < 600; i++) {
        await wait(2000);
        const st = await fetch(`/api/live/runs/${encodeURIComponent(body.run_id)}`).then(r => r.json()).catch(() => null);
        if (st?.state === 'done') return body.run_id as string;
        if (st?.state === 'failed') throw new Error('The live run failed; see the dev view for its log.');
      }
      throw new Error('The live run is taking too long; open it later from the dev view.');
    }
    const preset = (await presets()).find(t => t.task_id === req.place_id && `${t.model_id}|${t.harness}` === req.agent_id);
    if (!preset) throw new Error('No backend preset runs this task with that agent. Live/custom configuration is unavailable.');
    if (req.goal !== preset.goal) throw new Error('Pinned preset goals are read-only; the edited goal was not launched.');
    return (await request('/api/runs', decodeStarted, undefined, {preset_id: preset.preset_id})).run_id;
  },
};
