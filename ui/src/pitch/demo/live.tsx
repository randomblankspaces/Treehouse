/** Demo mode C — start one NEW agent run on Amazon Bedrock from the slide, then open it in the app.
 *  Server side: src/treehouse/ui/pitch_live.py, off unless the operator sets TREEHOUSE_PITCH_LIVE=1. The task,
 *  config and model are pinned on the server; this page only presses Start and polls. Costs real money. */
import { useCallback, useEffect, useState } from 'react';
import type { DemoProps } from './modes.ts';

type Status = {enabled: boolean; reason: string; title?: string; model_key: string | null; harness: string | null; task: string};
type Phase = {kind: 'idle'} | {kind: 'starting'} | {kind: 'running'; runId: string; status: string; since: number}
  | {kind: 'done'; runId: string} | {kind: 'failed'; message: string; runId?: string};

async function json<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, {...init, headers: {accept: 'application/json', ...(init?.headers ?? {})}});
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error((body as {detail?: string}).detail ?? `HTTP ${r.status}`);
  return body as T;
}

export function LiveDemo(_: DemoProps) {
  const [status, setStatus] = useState<Status | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [phase, setPhase] = useState<Phase>({kind: 'idle'});
  const [now, setNow] = useState(Date.now());

  const refresh = useCallback(() => {
    json<Status>('/api/pitch/live').then(setStatus, e => setError(e instanceof Error ? e.message : 'unavailable'));
  }, []);
  useEffect(refresh, [refresh]);

  const pollingId = phase.kind === 'running' ? phase.runId : null;
  useEffect(() => {
    if (!pollingId) return;
    const poll = async () => {
      try {
        const s = await json<{status: string; message?: string}>(`/api/runs/${encodeURIComponent(pollingId)}`);
        if (s.status === 'report_ready' || s.status === 'sealed') setPhase({kind: 'done', runId: pollingId});
        else if (s.status === 'failed') setPhase({kind: 'failed', runId: pollingId, message: s.message ?? 'The live run failed.'});
        else setPhase(p => p.kind === 'running' && p.status !== s.status ? {...p, status: s.status} : p);
      } catch { /* transient: keep polling */ }
    };
    const every = window.setInterval(poll, 3000);
    const tick = window.setInterval(() => setNow(Date.now()), 1000);
    return () => { clearInterval(every); clearInterval(tick); };
  }, [pollingId]);

  async function start() {
    setPhase({kind: 'starting'});
    try {
      const r = await json<{run_id: string}>('/api/pitch/live', {method: 'POST', headers: {'content-type': 'application/json'}, body: '{}'});
      setPhase({kind: 'running', runId: r.run_id, status: 'queued', since: Date.now()});
    } catch (e) {
      setPhase({kind: 'failed', message: e instanceof Error ? e.message : 'Could not start.'});
      refresh();
    }
  }

  if (error) return <div className="panel notice">
    <h3>The Treehouse server isn’t reachable from this page</h3>
    <p>Serve the app on the presenter machine with AWS credentials, the spend guard and the live switch:</p>
    <pre>{`uv sync --extra api --extra aws --extra strands\nuv run treehouse budget status   # must exit 0\nnpm --prefix ui run build\nTREEHOUSE_PITCH_LIVE=1 uv run --extra api treehouse ui serve --store out/pitch/store\n# open http://127.0.0.1:8765/pitch?demo=live`}</pre>
  </div>;
  if (!status) return <div className="panel">Checking whether live runs are allowed…</div>;

  const running = phase.kind === 'running' || phase.kind === 'starting';
  return <div className="live-demo">
    <div className="panel live-card">
      <h3>{status.title ?? 'Pinned live task'}</h3>
      <dl>
        <dt>Agent</dt><dd>{status.harness} on Amazon Bedrock · {status.model_key}</dd>
        <dt>Task</dt><dd><code>{status.task}</code></dd>
        <dt>Guard</dt><dd className={status.enabled ? 'ok' : 'off'}>{status.reason}</dd>
      </dl>
      <button className="start" onClick={start} disabled={!status.enabled || running}>
        {phase.kind === 'starting' ? 'Starting…' : phase.kind === 'running' ? 'Agent is running…' : '▶ Start a live run'}
      </button>
      <p className="hint">Takes a few minutes and costs about a dollar of Bedrock time. If it fails, switch to “Recorded run”.</p>
    </div>
    <div className="panel live-status" aria-live="polite">
      {phase.kind === 'idle' && <p>Press Start: the agent will investigate the Nagoya port district, recording a decision before every tool call. When it finishes, the run is sealed and scored here.</p>}
      {phase.kind === 'starting' && <p>Asking the server to start…</p>}
      {phase.kind === 'running' && <>
        <p className="big-num"><b>{Math.floor((now - phase.since) / 1000)}s</b> {phase.status}</p>
        <p><code>{phase.runId}</code></p>
        <div className="pulse" aria-hidden="true" />
      </>}
      {phase.kind === 'done' && <>
        <p className="big-num"><b>Sealed &amp; scored</b></p>
        <iframe src={`/?run=${encodeURIComponent(phase.runId)}`} title={`Live run ${phase.runId}`} className="app-frame small" />
        <p><a href={`/?run=${encodeURIComponent(phase.runId)}`} target="_blank" rel="noopener">Open full screen ↗</a> · <a href={`/dev?run=${encodeURIComponent(phase.runId)}`} target="_blank" rel="noopener">Dev view ↗</a></p>
      </>}
      {phase.kind === 'failed' && <p className="err">{phase.message}</p>}
    </div>
  </div>;
}
