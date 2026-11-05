/** Dev-view live console and a Claude Code-style run transcript.
 *  The console shows only when the server runs with `treehouse ui serve --live`: write a prompt (it names the
 *  place), pick a Bedrock model, run the agent, then watch the run land in the dev view (map dots, decision
 *  tree, tool calls). The agent picks the foundation model itself; the transcript shows which one it used. */
import { useEffect, useState } from 'react';
import type { Json, RunSnapshot, TraceStep } from './contract.ts';
import './console.css';

type Place = {task_id: string; title: string; lon: number; lat: number; needs_vision: boolean; synthetic: boolean; foundation_models: string[]};
type Model = {key: string; family: string; invoke_id: string; vision: boolean; verified: boolean};
type Options = {places: Place[]; models: Model[]; running: string | null};
type Status = {run_id: string; state: 'running' | 'done' | 'failed' | 'cancelled'; exit_code: number | null; elapsed_s: number; log_tail: string[]; model_turns?: number; recent?: {kind: string; name: string; why?: string}[]};

const FM_LABEL: Record<string, string> = {
  'lgnd-clay-embeddings': 'Clay v1.5 (LGND)', 'aef-10m-annual': 'AlphaEarth (AEF) 10 m', 'synth-embeddings': 'Synthetic embeddings',
};
const fmLabel = (id: string) => FM_LABEL[id] ?? id;

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) { let d = res.statusText; try { d = (await res.json()).detail ?? d; } catch { /* not JSON */ } throw new Error(String(d)); }
  return res.json() as Promise<T>;
}

/** "t1-nagoya-warehouses-real" -> "Nagoya · warehouses real": the place, then what is searched there. */
const shortName = (taskId: string) => {
  const parts = taskId.replace(/^t\d+-/, '').split('-');
  const place = parts[0] ? parts[0][0].toUpperCase() + parts[0].slice(1) : taskId;
  return parts.length > 1 ? `${place} · ${parts.slice(1).join(' ')}` : place;
};

function WorldPicker({places, value}: {places: Place[]; value: string}) {
  const pad = 8;
  const lons = places.map(p => p.lon), lats = places.map(p => p.lat);
  const lo0 = lons.length ? Math.min(...lons) - pad : -180, lo1 = lons.length ? Math.max(...lons) + pad * 3.5 : 180;   // room for labels east of the dots
  const la0 = lats.length ? Math.min(...lats) - pad : -90, la1 = lats.length ? Math.max(...lats) + pad : 90;
  const cx = (lo0 + lo1) / 2, cy = (la0 + la1) / 2;
  const w = Math.max(30, lo1 - lo0), h = Math.max(20, la1 - la0);
  const x0 = cx - w / 2, y0 = cy - h / 2;
  const u = Math.max(w, h) / 400; // one unit of stroke scale
  const step = w > 120 ? 30 : w > 50 ? 10 : 5;
  const ticks = (a: number, z: number) => { const r: number[] = []; for (let v = Math.ceil(a / step) * step; v <= z; v += step) r.push(v); return r; };
  // places at (nearly) the same spot are fanned out on a small ring so each stays clickable
  const groups = new Map<string, Place[]>();
  places.forEach(p => { const k = `${Math.round(p.lon / (w / 40))},${Math.round(p.lat / (h / 40))}`; groups.set(k, [...(groups.get(k) ?? []), p]); });
  const pos = new Map<string, [number, number]>();
  groups.forEach(g => g.forEach((p, i) => {
    const r = g.length > 1 ? 2.2 * Math.max(w, h) / 100 : 0, ang = (2 * Math.PI * i) / g.length - Math.PI / 2;
    pos.set(p.task_id, [p.lon + r * Math.cos(ang), p.lat + r * Math.sin(ang)]);
  }));
  const fs = Math.max(w, h) / 45;
  return <svg className="world" viewBox={`${x0} ${-(y0 + h)} ${w} ${h}`} role="img" aria-label={`Places with data: ${places.map(p => shortName(p.task_id)).join(', ')}${value ? `; this prompt runs on ${shortName(value)}` : ''}`}>
    {ticks(la0, la1).map(l => <line key={`la${l}`} x1={x0} x2={x0 + w} y1={-l} y2={-l} className={l === 0 ? 'eq' : 'grat'} style={{strokeWidth: (l === 0 ? 1.25 : 1) * u}} />)}
    {ticks(lo0, lo1).map(l => <line key={`lo${l}`} y1={-(y0 + h)} y2={-y0} x1={l} x2={l} className="grat" style={{strokeWidth: u}} />)}
    {places.map(p => { const [lon, lat] = pos.get(p.task_id) ?? [p.lon, p.lat]; const on = p.task_id === value; return <g key={p.task_id} className={`pl ${on ? 'on' : ''}`} transform={`translate(${lon} ${-lat})`}>
      <circle r={(on ? 10 : 6.5) * u} style={{strokeWidth: (on ? 2.5 : 1.5) * u}} /><title>{p.title}</title>
      <text className="lbl" x={fs * 0.9} y={fs * 0.35} fontSize={fs} style={{strokeWidth: fs * 0.12}}>{shortName(p.task_id)}</text>
    </g>; })}
  </svg>;
}

type Resolved = {task_id: string; title: string; matched: string[]; alternatives: string[]};
const EXAMPLES = ['Find every warehouse in the Nagoya port area', 'Where are the fuel tanks in Chittagong?', 'Map the warehouses in Gifu'];

/** Prompt-first console: write what you want found and where, pick the Bedrock model, launch. The server
 *  resolves the prompt to the place it has data for (shown before launch), then runs the Strands agent. */
export function LiveConsole({onRun}: {onRun: (runId: string) => void}) {
  const [opts, setOpts] = useState<Options | null | 'off'>(null);
  const [prompt, setPrompt] = useState('');
  const [resolved, setResolved] = useState<Resolved | null>(null);
  const [hint, setHint] = useState<string | null>(null);
  const [model, setModel] = useState('');
  const [status, setStatus] = useState<Status & {prompt?: string | null; resolved?: Resolved | null} | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirm, setConfirm] = useState(false);

  useEffect(() => {
    fetch('/api/live/options').then(r => r.ok ? r.json() as Promise<Options> : Promise.reject(new Error('off')))
      .then(o => { setOpts(o); setModel(o.models.find(m => m.verified)?.key ?? o.models[0]?.key ?? '');
        if (o.running) setStatus({run_id: o.running, state: 'running', exit_code: null, elapsed_s: 0, log_tail: []}); })   // resume after a reload
      .catch(() => setOpts('off'));
  }, []);
  useEffect(() => {   // live preview of where the prompt will run
    const q = prompt.trim();
    if (q.length < 3) { setResolved(null); setHint(null); return; }
    const ctl = new AbortController();
    const id = setTimeout(() => fetch(`/api/live/resolve?prompt=${encodeURIComponent(q)}`, {signal: ctl.signal})
      .then(r => json<Resolved>(r)).then(r => { setResolved(r); setHint(null); })
      .catch(e => { if (!ctl.signal.aborted) { setResolved(null); setHint(String(e.message ?? e)); } }), 250);
    return () => { clearTimeout(id); ctl.abort(); };
  }, [prompt]);
  useEffect(() => {
    if (!status || status.state !== 'running') return;
    const id = setInterval(() => fetch(`/api/live/runs/${encodeURIComponent(status.run_id)}`).then(r => json<Status>(r)).then(s => {
      setStatus(s); if (s.state === 'done') onRun(s.run_id);
    }).catch(e => { setError(String(e.message ?? e)); setStatus(s => s && {...s, state: 'failed'}); }), 2000);   // e.g. server restarted: stop polling
    return () => clearInterval(id);
  }, [status?.run_id, status?.state]);

  if (opts === 'off' || opts === null) return null;
  const p = opts.places.find(x => x.task_id === resolved?.task_id);
  const m = opts.models.find(x => x.key === model);
  const incompatible = !!p && !!m && p.needs_vision && !m.vision;
  const busy = status?.state === 'running';
  const launch = async () => {
    setError(null);
    try {
      const r = await fetch('/api/live/runs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({prompt: prompt.trim(), model_key: model})});
      const s = await json<{run_id: string; resolved: Resolved}>(r);
      setStatus({run_id: s.run_id, state: 'running', exit_code: null, elapsed_s: 0, log_tail: [], prompt: prompt.trim(), resolved: s.resolved}); setConfirm(false);
    } catch (e) { setError(String((e as Error).message ?? e)); }
  };

  return <section className="console" aria-labelledby="console-h">
    <div className="console-head">
      <h2 id="console-h">Agent console</h2>
      <ul className="stack" aria-label="Services this console uses">
        <li>Strands agent on Amazon Bedrock</li><li>Amazon Polly narration</li><li>AgentCore Evaluations</li>
      </ul>
    </div>
    <div className="console-grid">
      <div className="console-form">
        <label className="field" htmlFor="console-prompt">Prompt</label>
        <textarea id="console-prompt" className="prompt" rows={3} value={prompt} maxLength={500} disabled={busy}
          placeholder="Find every warehouse in the Nagoya port area" onChange={e => setPrompt(e.target.value)} aria-describedby="prompt-where" />
        <div className="examples" aria-label="Example prompts">{EXAMPLES.map(x => <button type="button" key={x} className="chip" onClick={() => setPrompt(x)} disabled={busy}>{x}</button>)}</div>
        <p id="prompt-where" className="where" aria-live="polite">{resolved ? <>Runs on: <b>{shortName(resolved.task_id)}</b> <span className="hint">({resolved.title})</span></>
          : hint ? <span className="warn">{hint}</span> : <span className="hint">Name a place and what to find. Places with data: Nagoya, Gifu, Chattogram.</span>}</p>
        <label className="field" htmlFor="console-model">Bedrock model</label>
        <select id="console-model" value={model} onChange={e => setModel(e.target.value)} disabled={busy}>
          {opts.models.map(x => <option key={x.key} value={x.key} disabled={!!p?.needs_vision && !x.vision}>{x.key} · {x.family}{x.verified ? '' : ' · unverified'}{p?.needs_vision && !x.vision ? ' · no vision' : ''}</option>)}
        </select>
        {p && <p className="fm"><span>Foundation models the agent can use here:</span> {p.foundation_models.map(fmLabel).join(' · ')}. <span className="hint">It picks one; the transcript shows which and why.</span></p>}
        {incompatible && <p className="warn">This place needs a model with vision.</p>}
        <label className="check"><input type="checkbox" checked={confirm} onChange={e => setConfirm(e.target.checked)} disabled={busy} /> I understand this calls Amazon Bedrock and spends money</label>
        <button type="button" className="primary" onClick={launch} disabled={!confirm || busy || incompatible || !resolved || !model}>{busy ? 'Agent running…' : 'Run agent'}</button>
        {error && <p className="alert" role="alert">{error}</p>}
      </div>
      <WorldPicker places={opts.places} value={resolved?.task_id ?? ''} />
    </div>
    {status && <div className="console-status">
      <p aria-live="polite"><b>{status.state === 'running' ? 'Running' : status.state === 'done' ? 'Finished' : status.state === 'cancelled' ? 'Stopped' : 'Failed'}</b> · {status.elapsed_s.toFixed(0)} s · {m?.key ?? status.run_id}{status.resolved ? ` · ${shortName(status.resolved.task_id)}` : ''}</p>
      {status.prompt && <p className="said">› {status.prompt}</p>}
      {status.state === 'running' && <ol className="tx" aria-label="Live progress">
        <li className="tx-think"><span className="dot">✻</span> {status.model_turns ?? 0} model turns so far</li>
        {(status.recent ?? []).map((r, i) => <li key={i} className="tx-tool ok">
          <div><span className="dot">●</span> <b>{r.name}</b></div>
          {r.why && <div className="why">⎿ why: {r.why}</div>}
        </li>)}
      </ol>}
      {status.state === 'running' && <button type="button" className="linkish" onClick={() => fetch(`/api/live/runs/${encodeURIComponent(status.run_id)}/cancel`, {method: 'POST'})
        .then(r => json<{state: string}>(r)).then(() => setStatus(s => s && {...s, state: 'cancelled'})).catch(e => setError(String(e.message ?? e)))}>Stop run</button>}
      {status.state === 'cancelled' && <p className="hint">Stopped. The run was not sealed or scored; you can launch another.</p>}
      {status.state === 'failed' && <pre className="tail">{status.log_tail.slice(-12).join('\n')}</pre>}
      {status.state === 'done' && <button type="button" className="linkish" onClick={() => onRun(status.run_id)}>Open the run</button>}
    </div>}
  </section>;
}

const brief = (v: Json): string => { const s = typeof v === 'string' ? v : JSON.stringify(v); return s.length > 60 ? s.slice(0, 57) + '…' : s; };
const argsLine = (args: Record<string, Json>) => Object.entries(args).slice(0, 4).map(([k, v]) => `${k}=${brief(v)}`).join(', ');
const sourceOf = (s: TraceStep) => { const a = s.tool?.args ?? {}; const v = a.source_id ?? a.source ?? a.embedding_source; return typeof v === 'string' ? v : null; };

/** The run as a terminal transcript: each model turn, each tool call with its recorded reason, rejected
 *  alternatives and the outcome (✓ / ✕), plus the foundation models the agent actually used. */
export function Transcript({snap}: {snap: RunSnapshot}) {
  const used = [...new Set(snap.steps.filter(s => s.status !== 'error').map(sourceOf).filter((x): x is string => !!x))];
  const fails = snap.steps.filter(s => s.status === 'error').length;
  const calls = snap.steps.filter(s => s.tool).length;
  return <section className="transcript" aria-labelledby="tx-h">
    <div className="console-head"><h2 id="tx-h">Agent transcript</h2>
      <span className="hint">{snap.context.model_id || 'model'} · {calls} tool calls · {fails} failed · foundation model used: {used.length ? used.map(fmLabel).join(', ') : 'none recorded'}</span></div>
    <ol className="tx">
      {snap.steps.map(s => {
        if (s.tool) return <li key={s.span_id} className={`tx-tool ${s.status}`}>
          <div><span className="dot">●</span> <b>{s.tool.name}</b><span className="args">({argsLine(s.tool.args)})</span></div>
          {s.decision?.rationale && <div className="why">⎿ why: {s.decision.rationale}</div>}
          {!!s.decision?.alternatives?.length && <div className="alt">⎿ turned down: {s.decision.alternatives.map(a => a.reason ? `${a.option} (${a.reason})` : a.option).join(' · ')}</div>}
          <div className="res">{s.status === 'error' ? `⎿ ✕ ${s.error?.type ?? 'error'}: ${s.error?.message ?? ''}` : s.status === 'running' ? '⎿ … running' : `⎿ ✓ ok${s.tool.bytes_read ? ` · ${s.tool.bytes_read} bytes read` : ''}`}</div>
        </li>;
        if (s.model?.thinking) return <li key={s.span_id} className="tx-think"><span className="dot">✻</span> {s.model.thinking.length > 400 ? s.model.thinking.slice(0, 397) + '…' : s.model.thinking}</li>;
        return null;
      })}
      {!snap.steps.length && <li className="hint">No steps recorded yet.</li>}
    </ol>
  </section>;
}
