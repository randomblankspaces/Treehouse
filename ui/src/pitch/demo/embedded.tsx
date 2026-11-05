/** Demo mode B — the real Treehouse app (story or dev view) embedded in the slide. Needs the Python server:
 *  `uv run --extra api treehouse ui serve --store <store with the run>`; the server's CSP allows framing by
 *  its own origin only (frame-ancestors 'self'). Pick any stored run. */
import { useEffect, useState } from 'react';
import type { DemoProps } from './modes.ts';

type RunRow = {run_id: string; title: string; status: string};
const DEFAULT_RUN = 'exp-nagoya-sonnet-1';

export function EmbeddedDemo(_: DemoProps) {
  const [runs, setRuns] = useState<RunRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [runId, setRunId] = useState(DEFAULT_RUN);
  const [view, setView] = useState<'story' | 'dev'>('story');

  useEffect(() => {
    const ctl = new AbortController();
    fetch('/api/runs', {signal: ctl.signal, headers: {accept: 'application/json'}})
      .then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
      .then((v: {runs: RunRow[]}) => {
        setRuns(v.runs);
        if (v.runs.length && !v.runs.some(r => r.run_id === DEFAULT_RUN)) setRunId(v.runs[0].run_id);
      })
      .catch(e => { if (!ctl.signal.aborted) setError(e instanceof Error ? e.message : 'unavailable'); });
    return () => ctl.abort();
  }, []);

  if (error) return <div className="panel notice">
    <h3>The Treehouse server isn’t reachable from this page</h3>
    <p>Start it on the presenter machine, then reload:</p>
    <pre>{`uv run python scripts/replay_live.py ${DEFAULT_RUN} --store out/pitch/store\nnpm --prefix ui run build\nuv run --extra api treehouse ui serve --store out/pitch/store\n# open http://127.0.0.1:8765/pitch?demo=embedded`}</pre>
  </div>;
  if (!runs) return <div className="panel">Reading stored runs…</div>;
  if (!runs.length) return <div className="panel notice">No runs in the served store. Replay one first (see docs/PITCH.md).</div>;

  const src = view === 'story' ? `/?run=${encodeURIComponent(runId)}` : `/dev?run=${encodeURIComponent(runId)}`;
  return <div className="embedded">
    <div className="embed-bar">
      <label>Run <select value={runId} onChange={e => setRunId(e.target.value)}>
        {runs.map(r => <option key={r.run_id} value={r.run_id}>{r.title} · {r.run_id}</option>)}
      </select></label>
      <div className="seg" role="radiogroup" aria-label="View">
        <button role="radio" aria-checked={view === 'story'} className={view === 'story' ? 'on' : ''} onClick={() => setView('story')}>Story view</button>
        <button role="radio" aria-checked={view === 'dev'} className={view === 'dev' ? 'on' : ''} onClick={() => setView('dev')}>Dev view</button>
      </div>
      <a href={src} target="_blank" rel="noopener">Open full screen ↗</a>
    </div>
    <iframe key={src} src={src} title={`Treehouse ${view} view of ${runId}`} className="app-frame" />
  </div>;
}
