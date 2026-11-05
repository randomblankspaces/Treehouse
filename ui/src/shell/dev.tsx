import { Fragment, StrictMode, useEffect, useMemo, useRef, useState, type KeyboardEvent, type Ref } from 'react';
import { createRoot } from 'react-dom/client';
import { FOCUS_LABEL, focusOf, isKey, terminal, type Narration, type RunSnapshot, type RunSummary, type TraceStep, type TreehouseClient } from './contract.ts';
import { httpClient } from './http.ts';
import { mockClient, mockNarrator } from './mock.ts';
import { loadPrefs, savePrefs, type Prefs } from './prefs.ts';
import './dev.css';

const env = import.meta.env.VITE_TREEHOUSE_API;
const useMock = import.meta.env.DEV ? env !== 'http' : env === 'mock';
const client: TreehouseClient & {replay?(id: string): void} = useMock ? mockClient : httpClient;
const narrator = mockNarrator;   // shortcut: template captions; swap for the Bedrock + Polly narrator when the backend has it

const clock = (ms: number) => { const t = Math.max(0, ms) / 1000; return `${String(Math.floor(t / 60)).padStart(2, '0')}:${(t % 60).toFixed(1).padStart(4, '0')}`; };
const usd = (v: number) => `$${v.toFixed(v < 1 ? 4 : 2)}`;
const kilo = (v: number) => v >= 1000 ? `${(v / 1000).toFixed(1)}k` : String(v);
const mb = (v: number) => v >= 1e6 ? `${(v / 1e6).toFixed(1)} MB` : v >= 1e3 ? `${(v / 1e3).toFixed(1)} kB` : `${v} B`;
const KIND: Record<TraceStep['kind'], [string, string]> = {invoke_agent: ['◆', 'agent'], chat: ['▸', 'model'], execute_tool: ['⚙', 'tool']};
const STATUS: Record<TraceStep['status'], string> = {ok: '✓ ok', error: '✕ error', running: '… running'};
type Filter = 'all' | 'key' | 'errors';

function readUrl() { const p = new URLSearchParams(location.search); return {run: p.get('run'), step: p.get('step')}; }
function writeUrl(run: string | null, step: string | null) {
  const p = new URLSearchParams(); if (run) p.set('run', run); if (step) p.set('step', step);
  history.replaceState(null, '', `${location.pathname}${p.size ? '?' + p : ''}`);
}

function Logo() {
  // Pixel treehouse after the logo: purple canopy, yellow roof and door, black trunk. 12 × 12 grid.
  const px: [number, number, number, number, string][] = [[2, 0, 8, 1, 'canopy'], [1, 1, 10, 3, 'canopy'], [2, 4, 8, 1, 'canopy'], [3, 4, 6, 1, 'roof'], [4, 5, 4, 3, 'house'], [5, 6, 2, 2, 'roof'], [5, 8, 2, 3, 'trunk'], [1, 11, 10, 1, 'trunk']];
  return <svg className="logo" viewBox="0 0 12 12" aria-hidden="true" shapeRendering="crispEdges">{px.map(([x, y, w, h, c], i) => <rect key={i} x={x} y={y} width={w} height={h} className={c} />)}</svg>;
}

document.title = 'Treehouse · Dev';

function DevApp() {
  const [prefs, setPrefs] = useState<Prefs>(loadPrefs);
  const [systemReduce, setSystemReduce] = useState(() => matchMedia('(prefers-reduced-motion: reduce)').matches);
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  const [runId, setRunId] = useState<string | null>(readUrl().run);
  const [snap, setSnap] = useState<RunSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [stepId, setStepId] = useState<string | null>(readUrl().step);
  const [follow, setFollow] = useState(!readUrl().step);
  const [filter, setFilter] = useState<Filter>('all');
  const [lines, setLines] = useState<Narration[]>([]);
  const [tick, setTick] = useState(0);   // bumps to restart polling after a replay
  const narrated = useRef(new Set<string>());
  const settings = useRef<HTMLDialogElement>(null);

  useEffect(() => { const m = matchMedia('(prefers-reduced-motion: reduce)'); const on = () => setSystemReduce(m.matches); m.addEventListener('change', on); return () => m.removeEventListener('change', on); }, []);
  useEffect(() => savePrefs(prefs), [prefs]);
  useEffect(() => {
    const ctl = new AbortController();
    client.listRuns(ctl.signal).then(list => { setRuns(list); setRunId(id => id && list.some(r => r.run_id === id) ? id : list[0]?.run_id ?? null); })
      .catch(e => ctl.signal.aborted || setError(String(e.message ?? e)));
    return () => ctl.abort();
  }, [tick]);
  useEffect(() => {
    if (!runId) return;
    const ctl = new AbortController(); let timer = 0;
    const poll = () => client.snapshot(runId, ctl.signal).then(s => { setSnap(s); setError(null); if (!terminal(s.status)) timer = window.setTimeout(poll, 1000); })
      .catch(e => { if (!ctl.signal.aborted) { setError(String(e.message ?? e)); timer = window.setTimeout(poll, 3000); } });
    poll();
    return () => { ctl.abort(); clearTimeout(timer); };
  }, [runId, tick]);
  useEffect(() => writeUrl(runId, follow ? null : stepId), [runId, stepId, follow]);
  // Narrate each step once, when it finishes.
  useEffect(() => {
    if (!snap) return;
    for (const st of snap.steps) {
      if (st.status === 'running' || narrated.current.has(st.span_id)) continue;
      narrated.current.add(st.span_id);
      narrator.line(st, snap).then(n => {
        if (!n) return;
        setLines(l => [n, ...l].slice(0, 6));
        if (n.audio_url && prefs.voice) void new Audio(n.audio_url).play().catch(() => {});
      });
    }
  }, [snap, prefs.voice]);

  const steps = snap?.steps ?? [];
  const byId = useMemo(() => new Map(steps.map(s => [s.span_id, s])), [steps]);
  const depth = (s: TraceStep) => { let d = 0, p = s.parent_span_id; while (p && byId.has(p) && d < 8) { d++; p = byId.get(p)!.parent_span_id; } return d; };
  const visible = steps.filter(s => filter === 'all' || (filter === 'key' ? isKey(s) : s.status === 'error'));
  const selected = (follow ? steps[steps.length - 1] : byId.get(stepId ?? '')) ?? visible[0] ?? null;
  const total = Math.max(snap?.elapsed_ms ?? 1, 1);
  const tokens = steps.reduce((t, s) => [t[0] + (s.model?.input_tokens ?? 0), t[1] + (s.model?.output_tokens ?? 0)], [0, 0]);
  const keys = steps.filter(isKey);
  const reduce = prefs.motion === 'reduce' || (prefs.motion === 'system' && systemReduce);

  const choose = (id: string) => { setFollow(false); setStepId(id); };
  const onTraceKey = (e: KeyboardEvent<HTMLOListElement>) => {
    const i = visible.findIndex(s => s.span_id === selected?.span_id);
    const next = e.key === 'ArrowDown' ? i + 1 : e.key === 'ArrowUp' ? i - 1 : e.key === 'Home' ? 0 : e.key === 'End' ? visible.length - 1 : null;
    if (next === null || !visible[next]) return;
    e.preventDefault(); choose(visible[next].span_id);
    document.getElementById(`step-${visible[next].span_id}`)?.focus();
  };
  const switchRun = (id: string) => { setRunId(id); setSnap(null); setFollow(true); setStepId(null); setLines([]); narrated.current.clear(); };

  return <div className="dev" data-theme={prefs.theme} data-text={prefs.text} data-cb={prefs.colorSafe ? 'on' : 'off'} data-motion={reduce ? 'reduce' : 'full'}>
    <a className="skip" href="#trace">Skip to trace</a>
    <header className="bar">
      <div className="brand"><Logo /><span>treehouse</span><b>dev</b></div>
      <label className="field">Run
        <select value={runId ?? ''} onChange={e => switchRun(e.target.value)} disabled={!runs?.length}>
          {runs?.map(r => <option key={r.run_id} value={r.run_id}>{r.title} · {r.status}</option>)}
        </select>
      </label>
      {snap && <dl className="stats">
        <div><dt>Status</dt><dd className={`st st-${snap.status}`}>{snap.status === 'running' ? '● live' : snap.status}</dd></div>
        <div><dt>Elapsed</dt><dd>{clock(snap.elapsed_ms)}</dd></div>
        <div><dt>Cost</dt><dd>{usd(snap.cost_usd)}</dd></div>
        <div><dt>Tokens in / out</dt><dd>{kilo(tokens[0])} / {kilo(tokens[1])}</dd></div>
        <div><dt>Steps</dt><dd>{steps.length}</dd></div>
      </dl>}
      <span className="source" title="Where this data comes from">{client.label}{snap?.synthetic ? ' · synthetic' : ''}</span>
      {client.replay && runId && <button type="button" onClick={() => { client.replay!(runId); switchRun(runId); setTick(t => t + 1); }}>Replay</button>}
      <button type="button" onClick={() => settings.current?.showModal()}>Settings</button>
    </header>
    {snap && !terminal(snap.status) && <div className="live" role="progressbar" aria-label="Run in progress" aria-valuetext={`${clock(snap.elapsed_ms)} elapsed`}><span /></div>}
    {error && <p className="alert" role="alert">Could not load run data: {error}</p>}
    {!snap && !error && <p className="empty">Loading run…</p>}
    {snap && <>
      <section className="overview" aria-label="Run overview">
        <article className="card">
          <h2>Input</h2>
          <p className="goal">{snap.input.goal || 'Not provided by the backend.'}</p>
          <dl className="kv">
            <dt>Task</dt><dd>{snap.input.task_id}</dd>
            <dt>Area</dt><dd>{snap.input.aoi_bbox ? `${snap.input.aoi_bbox.slice(0, 2).join(', ')} → ${snap.input.aoi_bbox.slice(2).join(', ')}` : '—'}</dd>
            <dt>Window</dt><dd>{snap.input.time_window?.join(' → ') ?? '—'}</dd>
            <dt>Data</dt><dd>{snap.input.data_allowlist.map(d => `${d.source_id} (${d.kind})`).join(' · ') || '—'}</dd>
            <dt>Tools</dt><dd>{snap.input.tools_allowed.join(' · ') || '—'}</dd>
          </dl>
        </article>
        <article className="card">
          <h2>Context</h2>
          <dl className="kv">
            <dt>Model</dt><dd>{snap.context.model_id || '—'}</dd>
            <dt>Provider</dt><dd>{snap.context.provider || '—'}</dd>
            <dt>Harness</dt><dd>{snap.context.harness || '—'}</dd>
            {snap.context.items.map(i => <Fragment key={i.label}><dt>{i.label}</dt><dd>{i.tokens !== null && <span className="num">{kilo(i.tokens)} tok · </span>}{i.detail}</dd></Fragment>)}
          </dl>
          {snap.context.system_prompt && <details><summary>System prompt</summary><pre>{snap.context.system_prompt}</pre></details>}
        </article>
        <article className="card">
          <h2>Key decisions <span className="count">{keys.length}</span></h2>
          <p className="hint">Foundation-model use and data access, with the agent's own reason.</p>
          <ol className="keys">
            {keys.map(k => <li key={k.span_id}><button type="button" className={`linkish ${k.span_id === selected?.span_id ? 'on' : ''}`} onClick={() => choose(k.span_id)}>
              <span className={`tag f-${focusOf(k)}`}>{FOCUS_LABEL[focusOf(k)]}</span> <code>{k.tool?.name}</code> <span className={`st st-${k.status}`}>{STATUS[k.status]}</span>
              {k.decision && <span className="why">{k.decision.rationale}</span>}
            </button></li>)}
            {!keys.length && <li className="hint">None yet.</li>}
          </ol>
        </article>
      </section>
      {prefs.captions && <section className="narrator" aria-label="Narrator">
        <h2>Narrator</h2>
        <p aria-live="polite">{lines[0]?.text ?? 'Waiting for the first key decision…'}</p>
        {lines.length > 1 && <details><summary>Earlier lines</summary><ol>{lines.slice(1).map((l, i) => <li key={i}>{l.text}</li>)}</ol></details>}
      </section>}
      <main className="work">
        <section className="trace" aria-labelledby="trace-h">
          <div className="trace-head">
            <h2 id="trace-h">Trace</h2>
            <div role="group" aria-label="Filter steps" className="seg">
              {(['all', 'key', 'errors'] as Filter[]).map(f => <button type="button" key={f} aria-pressed={filter === f} onClick={() => setFilter(f)}>{f === 'all' ? 'All' : f === 'key' ? 'Key decisions' : 'Errors'}</button>)}
            </div>
            <label className="check"><input type="checkbox" checked={follow} onChange={e => { setFollow(e.target.checked); if (!e.target.checked && selected) setStepId(selected.span_id); }} /> Follow live</label>
          </div>
          <ol id="trace" className="rows" aria-label="Trace steps; use arrow keys to move" onKeyDown={onTraceKey}>
            {visible.map(s => {
              const [glyph, kind] = KIND[s.kind], end = s.end_ms ?? snap.elapsed_ms;
              return <li key={s.span_id} className={`row ${isKey(s) ? 'key' : ''} ${s.status}`}>
                <button type="button" id={`step-${s.span_id}`} aria-current={s.span_id === selected?.span_id} tabIndex={s.span_id === selected?.span_id ? 0 : -1} onClick={() => choose(s.span_id)}>
                  <span className="t num">{clock(s.start_ms)}</span>
                  <span className="name" style={{paddingInlineStart: `${depth(s) * 1.1}rem`}}><span aria-hidden="true">{glyph}</span> <span className="sr">{kind}: </span>{isKey(s) && <><span className="star" aria-hidden="true">★ </span><span className="sr">key decision, {FOCUS_LABEL[focusOf(s)]}: </span></>}{s.tool?.name ?? s.name}</span>
                  <span className={`st st-${s.status}`}>{STATUS[s.status]}</span>
                  <span className="dur num">{((end - s.start_ms) / 1000).toFixed(1)}s</span>
                  <span className="wf" aria-hidden="true"><i style={{left: `${s.start_ms / total * 100}%`, width: `${Math.max((end - s.start_ms) / total * 100, 0.6)}%`}} /></span>
                </button>
              </li>;
            })}
          </ol>
        </section>
        <section className="inspector" aria-labelledby="insp-h">
          {selected ? <Inspector step={selected} byId={byId} steps={steps} choose={choose} /> : <p className="empty" id="insp-h">No step selected.</p>}
        </section>
      </main>
    </>}
    <Settings ref={settings} prefs={prefs} setPrefs={setPrefs} />
  </div>;
}

function Inspector({step, byId, steps, choose}: {step: TraceStep; byId: Map<string, TraceStep>; steps: TraceStep[]; choose: (id: string) => void}) {
  const parent = step.parent_span_id ? byId.get(step.parent_span_id) : null;
  const children = steps.filter(s => s.parent_span_id === step.span_id);
  return <>
    <h2 id="insp-h">{step.tool?.name ?? step.name}</h2>
    <p className="meta"><span>{KIND[step.kind][1]} · {step.kind}</span><span className={`st st-${step.status}`}>{STATUS[step.status]}</span>
      <span className="num">{clock(step.start_ms)} → {step.end_ms === null ? 'now' : clock(step.end_ms)}</span>
      {isKey(step) && <span className={`tag f-${focusOf(step)}`}>★ {FOCUS_LABEL[focusOf(step)]}</span>}</p>
    {step.error && <div className="alert" role="note"><b>{step.error.type}</b>: {step.error.message}</div>}
    {step.decision && <section className="block why-block">
      <h3>Why — the agent's recorded reason</h3>
      <p>{step.decision.rationale}</p>
      <p className="conf"><span>Self-reported confidence</span><meter min={0} max={1} value={step.decision.confidence} /><span className="num">{Math.round(step.decision.confidence * 100)}%</span></p>
      {step.decision.alternatives.length > 0 && <><h4>Alternatives it considered</h4><ul>{step.decision.alternatives.map(a => <li key={a.option}><b>{a.option}</b> — {a.reason}</li>)}</ul></>}
    </section>}
    {step.model && <section className="block">
      <h3>Model call</h3>
      <dl className="kv"><dt>Model</dt><dd>{step.model.model_id}</dd><dt>Tokens in / out</dt><dd className="num">{kilo(step.model.input_tokens)} / {kilo(step.model.output_tokens)}</dd>
        <dt>Cost</dt><dd className="num">{usd(step.model.cost_usd)}</dd><dt>Stop</dt><dd>{step.model.stop_reason ?? '—'}</dd></dl>
      <h4>Thinking</h4>
      {step.model.thinking ? <pre className="thinking">{step.model.thinking}</pre> : <p className="hint">{step.status === 'running' ? 'Model is responding…' : 'Not recorded by the backend for this call.'}</p>}
    </section>}
    {step.tool && <section className="block">
      <h3>Tool call</h3>
      <pre>{JSON.stringify(step.tool.args, null, 2)}</pre>
      <dl className="kv"><dt>Result</dt><dd>{step.tool.result ?? (step.status === 'running' ? 'Waiting…' : '—')}</dd><dt>Bytes read</dt><dd className="num">{mb(step.tool.bytes_read)}</dd></dl>
    </section>}
    <section className="block">
      <h3>Drill</h3>
      <ul className="drill">
        {parent && <li>Up: <button type="button" className="linkish" onClick={() => choose(parent.span_id)}>{parent.tool?.name ?? parent.name}</button></li>}
        {children.map(c => <li key={c.span_id}>Into: <button type="button" className="linkish" onClick={() => choose(c.span_id)}>{c.tool?.name ?? c.name}</button></li>)}
        {!parent && !children.length && <li className="hint">No parent or child spans.</li>}
      </ul>
      <details><summary>Raw span attributes</summary><pre>{JSON.stringify({span_id: step.span_id, parent_span_id: step.parent_span_id, ...step.attributes}, null, 2)}</pre></details>
    </section>
  </>;
}

function Settings({ref, prefs, setPrefs}: {ref: Ref<HTMLDialogElement>; prefs: Prefs; setPrefs: (p: Prefs) => void}) {
  const set = <K extends keyof Prefs>(k: K, v: Prefs[K]) => setPrefs({...prefs, [k]: v});
  const radio = <K extends 'theme' | 'text' | 'motion'>(k: K, label: string, options: [Prefs[K], string][]) =>
    <fieldset><legend>{label}</legend>{options.map(([v, l]) => <label key={v} className="check"><input type="radio" name={k} checked={prefs[k] === v} onChange={() => set(k, v)} /> {l}</label>)}</fieldset>;
  return <dialog ref={ref} className="settings" aria-labelledby="set-h">
    <form method="dialog">
      <h2 id="set-h">Display and accessibility</h2>
      {radio('theme', 'Theme', [['dark', 'Dark'], ['light', 'Light'], ['contrast', 'High contrast']])}
      {radio('text', 'Text size', [['100', '100 %'], ['125', '125 %'], ['150', '150 %']])}
      {radio('motion', 'Motion', [['system', 'Follow system'], ['reduce', 'Reduce'], ['full', 'Full']])}
      <fieldset><legend>Assistance</legend>
        <label className="check"><input type="checkbox" checked={prefs.colorSafe} onChange={e => set('colorSafe', e.target.checked)} /> Colour-blind-safe palette</label>
        <label className="check"><input type="checkbox" checked={prefs.captions} onChange={e => set('captions', e.target.checked)} /> Narrator captions</label>
        <label className="check"><input type="checkbox" checked={prefs.voice} onChange={e => set('voice', e.target.checked)} /> Narrator voice (when available)</label>
      </fieldset>
      <button type="submit">Done</button>
    </form>
  </dialog>;
}

createRoot(document.getElementById('root')!).render(<StrictMode><DevApp /></StrictMode>);
