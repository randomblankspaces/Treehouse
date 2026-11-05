import { Fragment, StrictMode, useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react';
import { createRoot } from 'react-dom/client';
import { client } from './client.ts';
import { FOCUS_LABEL, focusOf, isKey, terminal, type Json, type RunSnapshot, type RunSummary, type TraceStep } from './contract.ts';
import { KIND_WORD, PHASES, asOf, bboxOf, gist, phaseState, sentence, sinceStart, title } from './describe.ts';
import { pick, pickMarker, renderMap, TILE_CREDIT } from './mapart.ts';
import { useNarration, usePrefs, useRunNarration, useSnapshot } from './hooks.ts';
import { isColorSafe, type Prefs } from './prefs.ts';
import { EvaluationPanels, PredictionEvidence, money, tokenTotal } from './report.tsx';
import { Settings } from './settings.tsx';
import { DecisionTree, PlainRunSummary } from './tree.tsx';
import { ExecutionMap } from './execmap.tsx';
import './shell.css';
import './tree.css';

const clock = (ms: number | null) => { if (ms === null) return 'unavailable'; const t = Math.max(0, ms) / 1000; return `${String(Math.floor(t / 60)).padStart(2, '0')}:${(t % 60).toFixed(1).padStart(4, '0')}`; };
const usd = money;
const kilo = (v: number | null) => v === null ? 'unavailable' : v >= 1000 ? `${(v / 1000).toFixed(1)}k` : String(v);
const mb = (v: number | null) => v === null ? 'unavailable' : v >= 1e6 ? `${(v / 1e6).toFixed(1)} MB` : v >= 1e3 ? `${(v / 1e3).toFixed(1)} kB` : `${v} B`;
const STATUS: Record<TraceStep['status'], string> = {ok: '✓ ok', error: '✕ failed', running: '… running'};
const PHASE_GLYPH = {pending: '○', active: '●', done: '✓', recovered: '✓', error: '✕', skipped: '–'} as const;
type Filter = 'all' | 'key' | 'errors';
const short = (v: Json) => typeof v === 'string' ? v : JSON.stringify(v);

function readUrl() { const p = new URLSearchParams(location.search); return {run: p.get('run'), step: p.get('step')}; }
function writeUrl(run: string | null, step: string | null) {
  const p = new URLSearchParams(); if (run) p.set('run', run); if (step) p.set('step', step);
  history.replaceState(null, '', `${location.pathname}${p.size ? '?' + p : ''}`);
}

function Logo() {
  // Pixel treehouse after the logo: purple canopy, yellow roof and door, dark trunk. 12 × 12 grid.
  const px: [number, number, number, number, string][] = [[2, 0, 8, 1, 'canopy'], [1, 1, 10, 3, 'canopy'], [2, 4, 8, 1, 'canopy'], [3, 4, 6, 1, 'roof'], [4, 5, 4, 3, 'house'], [5, 6, 2, 2, 'roof'], [5, 8, 2, 3, 'trunk'], [1, 11, 10, 1, 'trunk']];
  return <svg className="logo" viewBox="0 0 12 12" aria-hidden="true" shapeRendering="crispEdges">{px.map(([x, y, w, h, c], i) => <rect key={i} x={x} y={y} width={w} height={h} className={c} />)}</svg>;
}

document.title = 'Treehouse · Dev';

function DevApp() {
  const {prefs, setPrefs, reduce} = usePrefs();
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  const [listError, setListError] = useState<string | null>(null);
  const [runId, setRunId] = useState<string | null>(readUrl().run);
  const [stepId, setStepId] = useState<string | null>(readUrl().step);
  const [follow, setFollow] = useState(!readUrl().step);
  const [filter, setFilter] = useState<Filter>('all');
  const [selectedClaim, setSelectedClaim] = useState<string | null>(null);   // shared by the tree and the map
  const [tick, setTick] = useState(0);   // bumps to restart polling after a replay
  const [now, setNow] = useState(Date.now());
  const settings = useRef<HTMLDialogElement>(null);
  const {snap, error: snapError} = useSnapshot(runId, tick);
  const lines = useNarration(snap, prefs.voice);
  const runNarr = useRunNarration(snap, prefs.voice);
  const error = listError ?? snapError;
  const live = snap ? !terminal(snap.status) : false;

  useEffect(() => {
    const ctl = new AbortController();
    client.listRuns(ctl.signal).then(list => { setRuns(list); setRunId(id => id && list.some(r => r.run_id === id) ? id : list[0]?.run_id ?? null); })
      .catch(e => ctl.signal.aborted || setListError(String(e.message ?? e)));
    return () => ctl.abort();
  }, [tick]);
  useEffect(() => writeUrl(runId, follow ? null : stepId), [runId, stepId, follow]);
  useEffect(() => { if (!live) return; const id = setInterval(() => setNow(Date.now()), 500); return () => clearInterval(id); }, [live]);

  const steps = snap?.steps ?? [];
  const byId = useMemo(() => new Map(steps.map(s => [s.span_id, s])), [steps]);
  const depth = (s: TraceStep) => { let d = 0, p = s.parent_span_id; while (p && byId.has(p) && d < 8) { d++; p = byId.get(p)!.parent_span_id; } return d; };
  const counts = {all: steps.length, key: steps.filter(isKey).length, errors: steps.filter(s => s.status === 'error').length};
  const visible = steps.filter(s => filter === 'all' || (filter === 'key' ? isKey(s) : s.status === 'error'));
  const selected = (follow ? steps[steps.length - 1] : byId.get(stepId ?? '')) ?? visible[0] ?? null;
  const total = Math.max(snap?.elapsed_ms ?? 1, 1);
  const keys = steps.filter(isKey);

  const choose = (id: string) => { setFollow(false); setStepId(id); };
  const onTraceKey = (e: KeyboardEvent<HTMLOListElement>) => {
    const i = visible.findIndex(s => s.span_id === selected?.span_id);
    const next = e.key === 'ArrowDown' ? i + 1 : e.key === 'ArrowUp' ? i - 1 : e.key === 'Home' ? 0 : e.key === 'End' ? visible.length - 1 : null;
    if (next === null || !visible[next]) return;
    e.preventDefault(); choose(visible[next].span_id);
    document.getElementById(`step-${visible[next].span_id}`)?.focus();
  };
  const switchRun = (id: string) => { setRunId(id); setFollow(true); setStepId(null); };

  return <div className="shell dev" data-theme={prefs.theme} data-text={prefs.text} data-cb={isColorSafe(prefs) ? 'on' : 'off'} data-palette={prefs.palette} data-motion={reduce ? 'reduce' : 'full'}>
    <a className="skip" href="#trace">Skip to trace</a>
    <header className="bar">
      <a className="brand" href={runId ? `/?run=${encodeURIComponent(runId)}` : "/"}><Logo /><span>treehouse</span><b>dev</b></a>
      <label className="field">Run
        <select value={runId ?? ''} onChange={e => switchRun(e.target.value)} disabled={!runs?.length}>
          {runs?.map(r => <option key={r.run_id} value={r.run_id}>{r.title} · {r.status}</option>)}
        </select>
      </label>
      {snap && <dl className="stats">
        <div><dt>Status</dt><dd className={`st st-${snap.status}`}>{live ? `${snap.mode} pending` : snap.status}</dd></div>
        <div><dt>{live ? 'Since start' : 'Took'}</dt><dd>{clock(sinceStart(snap, now))}</dd></div>
        <div><dt>Cost</dt><dd>{usd(snap.cost_usd)}</dd></div>
        <div><dt>Tokens in / out</dt><dd>{tokenTotal(snap)} total</dd></div>
        <div><dt>Steps</dt><dd>{steps.length}</dd></div>
      </dl>}
      <span className="source" title="Where this data comes from">{client.label} · {snap?.mode ?? 'unknown'}{snap?.synthetic ? ' · synthetic' : ''}</span>
      {client.replay && runId && <button type="button" onClick={() => { client.replay!(runId); switchRun(runId); setTick(t => t + 1); }}>Replay</button>}
      <button type="button" onClick={() => settings.current?.showModal()}>Settings</button>
    </header>
    {live && <div className="live" role="progressbar" aria-label="Run in progress" aria-valuetext={`${clock(sinceStart(snap!, now))} since start`}><span /></div>}
    <details className="howto">
      <summary>How to read this page</summary>
      <ul>
        <li><span className="kind k-invoke_agent">Agent</span> the whole run (or a helper agent inside a tool). <span className="kind k-chat">Model</span> the model reading its context and deciding what to do. <span className="kind k-execute_tool">Tool</span> an action it took.</li>
        <li><span className="star">★</span> marks a <b>key decision</b>: using a foundation model or reading data. Each one carries the agent's own reason and the options it turned down.</li>
        <li>Click any step (or use ↑ ↓) to see why it happened, what the model was thinking, its inputs and result. <b>Up to / Into</b> moves between a step and the steps inside it.</li>
      </ul>
    </details>
    {error && <p className="alert" role="alert">Could not load run data: {error}</p>}
    {!snap && !error && <p className="empty">Loading run…</p>}
    {snap && <>
      <ol className="phase-strip" aria-label="Progress through the task">
        {PHASES.map(([label, tools]) => { const st = phaseState(steps, tools, !live); return <li key={label} className={`ph ph-${st}`}><span aria-hidden="true">{PHASE_GLYPH[st]}</span> {label}<span className="sr"> ({st})</span></li>; })}
      </ol>
      <section className="overview" aria-label="Run overview">
        <article className="card">
          <h2><span className="n">1</span> What it was asked</h2>
          <p className="goal">{snap.input.goal || 'Not provided by the backend.'}</p>
          <dl className="kv">
            <dt>Area</dt><dd>{snap.input.aoi_bbox ? `${snap.input.aoi_bbox.slice(0, 2).join(', ')} → ${snap.input.aoi_bbox.slice(2).join(', ')}` : '—'}</dd>
            <dt>Time window</dt><dd>{snap.input.time_window?.join(' → ') ?? '—'}</dd>
          </dl>
          <details><summary>Data and tools it may use ({snap.input.data_allowlist.length} + {snap.input.tools_allowed.length})</summary>
            <dl className="kv"><dt>Data</dt><dd>{snap.input.data_allowlist.map(d => `${d.source_id} (${d.kind})`).join(' · ') || '—'}</dd><dt>Tools</dt><dd>{snap.input.tools_allowed.join(' · ') || '—'}</dd></dl></details>
        </article>
        <article className="card">
          <h2><span className="n">2</span> Who did it, with what context</h2>
          <dl className="kv">
            <dt>Model</dt><dd>{snap.context.model_id || '—'}</dd>
            <dt>Harness</dt><dd>{snap.context.harness || '—'}</dd>
            <dt>Provider</dt><dd>{snap.context.provider || '—'}</dd>
            {snap.context.items.map(i => <Fragment key={i.label}><dt>{i.label}</dt><dd>{i.tokens !== null && <span className="num">{kilo(i.tokens)} tok · </span>}{i.detail}</dd></Fragment>)}
          </dl>
          {snap.context.system_prompt && <details><summary>System prompt</summary><pre>{snap.context.system_prompt}</pre></details>}
        </article>
        <article className="card">
          <h2><span className="n">3</span> Key decisions <span className="count">{keys.length}</span></h2>
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
        {runNarr && <p className="narr-summary"><span className="voice-label">{runNarr.source === 'polly' ? 'Voice: Amazon Polly' : 'Voice: browser speech'}</span> {runNarr.text}</p>}
      </section>}
      <ExecutionMap snap={snap} selectedClaim={selectedClaim} onSelectClaim={setSelectedClaim} />
      <DecisionTree snap={snap} selectedClaim={selectedClaim} onSelectClaim={setSelectedClaim} />
      <main className="work">
        <section className="trace" aria-labelledby="trace-h">
          <div className="trace-head">
            <h2 id="trace-h">Every step, in order</h2>
            <div role="group" aria-label="Filter steps" className="seg">
              {(['all', 'key', 'errors'] as Filter[]).map(f => <button type="button" key={f} aria-pressed={filter === f} onClick={() => setFilter(f)}>{f === 'all' ? 'All' : f === 'key' ? 'Key decisions' : 'Errors'} <span className="c">{counts[f]}</span></button>)}
            </div>
            <label className="check"><input type="checkbox" checked={follow} onChange={e => { setFollow(e.target.checked); if (!e.target.checked && selected) setStepId(selected.span_id); }} /> Follow live</label>
          </div>
          <ol id="trace" className="rows" aria-label="Trace steps; use arrow keys to move" onKeyDown={onTraceKey}>
            {visible.map(s => {
              const end = s.end_ms ?? snap.elapsed_ms ?? s.start_ms;
              return <li key={s.span_id} className={`row ${isKey(s) ? 'key' : ''} ${s.status}`}>
                <button type="button" id={`step-${s.span_id}`} aria-current={s.span_id === selected?.span_id} tabIndex={s.span_id === selected?.span_id ? 0 : -1} onClick={() => choose(s.span_id)}>
                  <span className="t num">+{clock(s.start_ms)}</span>
                  <span className="main" style={{paddingInlineStart: `${depth(s) * 1.1}rem`}}>
                    <span className="line1"><span className={`kind k-${s.kind}`}>{KIND_WORD[s.kind]}</span>{isKey(s) && <span className="star" title={`Key decision: ${FOCUS_LABEL[focusOf(s)]}`}>★<span className="sr"> key decision, {FOCUS_LABEL[focusOf(s)]}</span></span>}<span className="ttl">{title(s)}</span></span>
                    <span className="line2">{gist(s)}</span>
                  </span>
                  <span className={`st st-${s.status}`}>{STATUS[s.status]}</span>
                  <span className="dur num">{((end - s.start_ms) / 1000).toFixed(1)}s</span>
                  <span className="wf" aria-hidden="true"><i style={{left: `${s.start_ms / total * 100}%`, width: `${Math.max((end - s.start_ms) / total * 100, 0.6)}%`}} /></span>
                </button>
              </li>;
            })}
          </ol>
        </section>
        <div className="side">
          <DevMap snap={snap} step={follow ? null : selected} night={prefs.theme !== 'light'} reduce={reduce} palette={prefs.palette} selectedClaim={selectedClaim} onSelectClaim={setSelectedClaim} />
          <section className="inspector" aria-labelledby="insp-h">
            {selected ? <Inspector step={selected} byId={byId} steps={steps} choose={choose} /> : <p className="empty" id="insp-h">No step selected.</p>}
          </section>
        </div>
      </main>
      <PlainRunSummary snap={snap} />
    </>}
    <Settings ref={settings} prefs={prefs} setPrefs={setPrefs} />
  </div>;
}

/** The map beside the trace: the run as it stood at the selected step (or live), drawn technically. */
function DevMap({snap, step, night, reduce, palette, selectedClaim, onSelectClaim}: {snap: RunSnapshot; step: TraceStep | null; night: boolean; reduce: boolean; palette: Prefs['palette']; selectedClaim: string | null; onSelectClaim: (id: string | null) => void}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [scrub, setScrub] = useState<number | null>(null);
  const selectedPrediction = selectedClaim;
  const setSelectedPrediction = onSelectClaim;
  const [hover, setHover] = useState<ReturnType<typeof pick>>(null);
  useEffect(() => setScrub(null), [step?.span_id]);
  const t = scrub ?? (step ? step.end_ms ?? snap.elapsed_ms : snap.elapsed_ms) ?? 0;
  const view = asOf(snap, t), bbox = bboxOf(snap);
  useEffect(() => {
    let raf = 0;
    const frame = (now: number) => {
      const c = canvas.current;
      if (c) {
        const dpr = devicePixelRatio || 1, W = c.clientWidth, H = c.clientHeight;
        if (c.width !== Math.round(W * dpr) || c.height !== Math.round(H * dpr)) { c.width = Math.round(W * dpr); c.height = Math.round(H * dpr); }
        const ctx = c.getContext('2d')!; ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        renderMap(ctx, W, H, {mode: night ? 'night' : 'day', t: now, animate: !reduce, colorSafe: palette !== 'default', palette, bbox, steps: view.steps, elapsed: t, markers: view.markers, born: [], illustrative: snap.mode === 'mock', technical: snap.mode === 'mock', focus: step?.tool?.name ?? null});
      }
      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(raf);
  }, [view, t, bbox, night, reduce, palette, step]);
  const n = (st: string) => view.markers.filter(m => m.status === st).length;
  const running = view.steps.filter(x => x.status === 'running' && x.kind === 'execute_tool').map(x => x.tool?.name);
  return <section className="mapbox" aria-labelledby="map-h">
    <div className="map-head">
      <h2 id="map-h">Map</h2>
      <span className={`badge ${step || scrub !== null ? 'at' : 'livemap'}`}>{scrub !== null ? 'scrubbed' : step ? `at step: ${title(step)}` : 'latest'}</span>
      <span className="num">+{clock(t)}</span>
    </div>
    <canvas ref={canvas} className="devmap" role="img" aria-label={`Map of the task area at +${clock(t)}: ${n('present')} predicted present, ${n('absent')} absent, ${n('cannot_assess')} cannot assess.`}
      onClick={e => { const r = e.currentTarget.getBoundingClientRect(); const m = pickMarker(r.width, r.height, bbox, view.markers, e.clientX - r.left, e.clientY - r.top); if (m) setSelectedPrediction(`${m.trial_id}:${m.claim_id}`); }}
      onMouseMove={e => { const r = e.currentTarget.getBoundingClientRect(); setHover(pick(r.width, r.height, bbox, e.clientX - r.left, e.clientY - r.top)); }} onMouseLeave={() => setHover(null)} />
    <label className="scrub">Run clock <input type="range" min={0} max={Math.max(1, Math.round(snap.elapsed_ms ?? 0))} step={100} disabled={snap.elapsed_ms === null} value={Math.round(t)} onChange={e => setScrub(Number(e.target.value))} aria-valuetext={`+${clock(t)}`} />
      {scrub !== null && <button type="button" className="linkish" onClick={() => setScrub(null)}>reset</button>}</label>
    <dl className="kv readout">
      <dt>Cursor</dt><dd>{hover ? `${hover.lat.toFixed(5)}°N ${hover.lon.toFixed(5)}°E · cell ${hover.col},${hover.row}` : 'hover the map'}</dd>
      <dt>Active tools</dt><dd>{running.length ? running.join(', ') : 'none'}</dd>
      <dt>Labels so far</dt><dd>{n('present')} predicted present · {n('absent')} absent · {n('cannot_assess')} cannot assess</dd>
      <dt>Browser basemap</dt><dd>{TILE_CREDIT}. Display only; not evidence the agent inspected imagery. Drawn fallback is illustrative.</dd>
    </dl>
    <PredictionEvidence snap={snap} selected={selectedPrediction} onSelect={setSelectedPrediction} />
    <EvaluationPanels snap={snap} />
  </section>;
}

function Inspector({step, byId, steps, choose}: {step: TraceStep; byId: Map<string, TraceStep>; steps: TraceStep[]; choose: (id: string) => void}) {
  const parent = step.parent_span_id ? byId.get(step.parent_span_id) : null;
  const children = steps.filter(s => s.parent_span_id === step.span_id);
  const args = Object.entries(step.tool?.args ?? {});
  return <>
    <p className="meta"><span className={`kind k-${step.kind}`}>{KIND_WORD[step.kind]}</span><span className={`st st-${step.status}`}>{STATUS[step.status]}</span>
      <span className="num">+{clock(step.start_ms)} → {step.end_ms === null ? 'now' : `+${clock(step.end_ms)}`}</span>
      {isKey(step) && <span className={`tag f-${focusOf(step)}`}>★ {FOCUS_LABEL[focusOf(step)]}</span>}</p>
    <h2 id="insp-h">{title(step)}</h2>
    <p className="plain">{sentence(step)}</p>
    {step.error && <div className="alert" role="note"><b>{step.error.type}</b>: {step.error.message}</div>}
    {step.decision && <section className="block why-block">
      <h3>Why it did this</h3>
      <p>{step.decision.rationale}</p>
      <p className="conf"><span>Its own confidence</span><meter min={0} max={1} value={step.decision.confidence} /><span className="num">{Math.round(step.decision.confidence * 100)}%</span></p>
      {step.decision.alternatives.length > 0 && <><h4>What it turned down</h4><ul>{step.decision.alternatives.map(a => <li key={a.option}><b>{a.option}</b> — {a.reason}</li>)}</ul></>}
    </section>}
    {step.model && <section className="block">
      <h3>Recorded model response text</h3>
      {step.model.thinking ? <p className="thinking">{step.model.thinking}</p> : <p className="hint">{step.status === 'running' ? 'The model is responding…' : 'No model response text is exposed for this call. The run’s recorded rationale summary appears in the evaluation report.'}</p>}
      <dl className="kv"><dt>Model</dt><dd>{step.model.model_id}</dd><dt>Read / wrote</dt><dd className="num">{kilo(step.model.input_tokens)} / {kilo(step.model.output_tokens)} tokens</dd>
        <dt>Cost</dt><dd className="num">{usd(step.model.cost_usd)}</dd><dt>Then</dt><dd>{step.model.stop_reason === 'tool_use' ? 'called a tool' : step.model.stop_reason === 'end_turn' ? 'finished its turn' : step.model.stop_reason ?? '—'}</dd></dl>
    </section>}
    {step.tool && <section className="block">
      <h3>Inputs</h3>
      {args.length ? <table className="args"><tbody>{args.map(([k, v]) => <tr key={k}><th scope="row">{k}</th><td>{short(v)}</td></tr>)}</tbody></table> : <p className="hint">No inputs recorded.</p>}
      <h3>Result</h3>
      {step.tool.result_metadata && <pre>{JSON.stringify(step.tool.result_metadata, null, 2)}</pre>}
      <p>{step.tool.result ?? (step.status === 'running' ? 'Waiting…' : step.error ? 'No result: the call failed.' : '—')}</p>
      {step.tool.bytes_read !== null && step.tool.bytes_read > 0 && <p className="hint">Read {mb(step.tool.bytes_read)} of data.</p>}
    </section>}
    <section className="block">
      <h3>Around this step</h3>
      <ul className="drill">
        {parent && <li>Up to: <button type="button" className="linkish" onClick={() => choose(parent.span_id)}>{title(parent)}</button></li>}
        {children.map(c => <li key={c.span_id}>Into: <button type="button" className="linkish" onClick={() => choose(c.span_id)}>{title(c)}</button></li>)}
        {!parent && !children.length && <li className="hint">No steps above or inside this one.</li>}
      </ul>
      <details><summary>Raw trace data (OpenTelemetry span)</summary><pre>{JSON.stringify({span_id: step.span_id, parent_span_id: step.parent_span_id, name: step.name, ...step.attributes}, null, 2)}</pre></details>
    </section>
  </>;
}

createRoot(document.getElementById('root')!).render(<StrictMode><DevApp /></StrictMode>);
