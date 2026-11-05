import { Fragment, StrictMode, useCallback, useEffect, useRef, useState, type CSSProperties, type Ref } from 'react';
import { createRoot } from 'react-dom/client';
import { POSES, RECTS, WINDOW_X, ease, fit, lerpCam, lerpSide, render, toScreen, walkSide, type Boy, type Camera, type Rect, type Side } from './art.ts';
import { client, usingMock } from './client.ts';
import { FOCUS_LABEL, focusOf, isKey, terminal, type Agent, type Narration, type Place, type RunSnapshot, type RunSummary, type TraceStep } from './contract.ts';
import { PHASES, bboxOf, clock, phaseState, sinceStart } from './describe.ts';
import { canPickFolder, exportRun } from './export.ts';
import { useNarration, usePrefs, useSnapshot } from './hooks.ts';
import { pickMarker, renderMap, TILE_CREDIT } from './mapart.ts';
import type { Prefs } from './prefs.ts';
import { EvaluationPanels, PredictionEvidence, money, tokenTotal } from './report.tsx';
import { Settings } from './settings.tsx';
import '@fontsource/pixelify-sans/latin-400.css';   // latin only: files, not data: URIs (the API's CSP blocks those)
import '@fontsource/pixelify-sans/latin-700.css';
import './shell.css';
import './story.css';

document.title = 'Treehouse';

// Pixel icons drawn from character grids: k ink, y gold, o amber, w white, c cyan, b blue, p purple, g green, r red.
const INK: Record<string, string> = {k: '#24182c', y: '#ffd166', o: '#e0a83a', w: '#ffffff', c: '#7fe8d6', b: '#3fb5a3', p: '#9161dc', g: '#69b86a', r: '#ff4d5e'};
const ICONS: Record<string, string[]> = {
  hourglass: ['kkkkkkkk', '.kwwwwk.', '..kyyk..', '...kk...', '...kk...', '..kwyk..', '.kyyyyk.', 'kkkkkkkk'],
  coin: ['..kkkk..', '.kyyyyk.', 'kywyyyok', 'kyyyyyok', 'kyyyyyok', 'kyyyyook', '.kooook.', '..kkkk..'],
  gem: ['..kkkk..', '.kcwcck.', 'kcwccbck', 'kccccbck', '.kccbck.', '..kcbk..', '...kk...', '........'],
  scroll: ['.kkkkkk.', 'kwwwwwwk', 'kwkkkkwk', 'kwwwwwwk', 'kwkkkwwk', 'kwwwwwwk', '.kkkkkk.', '........'],
  star: ['...kk...', '..kyyk..', 'kkkyykkk', 'kyyyyyyk', '.kyyyyk.', '.kykkyk.', 'kyk..kyk', 'kk....kk'],
  lamp: ['..kkkk..', '.kyyyyk.', 'kyywyyyk', 'kyyyyyyk', '.kyyyyk.', '..kkkk..', '..kook..', '..kkkk..'],
  bino: ['........', 'kkk..kkk', 'kpk..kpk', 'kpkkkkpk', 'kckpkpck', 'kcwkkcwk', 'kkk..kkk', '........'],
};
function Icon({name, size = 18}: {name: string; size?: number}) {
  const g = ICONS[name];
  return <svg className="px-icon" width={size} height={size} viewBox="0 0 8 8" shapeRendering="crispEdges" aria-hidden="true">
    {g.flatMap((row, y) => [...row].map((ch, x) => INK[ch] ? <rect key={`${x}-${y}`} x={x} y={y} width={1} height={1} fill={INK[ch]} /> : null))}
  </svg>;
}
type Phase = 'intro' | 'flying' | 'book' | 'map';
/** Path parameter 0..2 for the entry zoom (0..1 sky → room, 1..2 room → book). The first 37 % of the time reaches the
 *  room, accelerating; the rest glides into the book, decelerating to a stop. Velocity is continuous at the room. */
function enterK(t: number) {
  const T1 = 0.37, m = 2 * T1 / (1 - T1);
  if (t < T1) { const u = t / T1; return -2 * u ** 3 + 3 * u * u + m * (u ** 3 - u * u); }
  const u = (t - T1) / (1 - T1); return 2 - (1 - u) ** 2;
}
const kilo = (v: number) => v >= 1000 ? `${(v / 1000).toFixed(1)}k` : String(v);
const SCENES = {
  intro: 'Night. A treehouse sits in a purple tree under the stars; a ladder with yellow rungs leads up to a yellow door. The word treehouse is written on the ground.',
  day: 'Day. A treehouse sits in a purple tree under a blue sky with a few clouds; a ladder with yellow rungs leads up to a yellow door.',
  room: 'Inside the treehouse a boy lies on a striped rug, legs in the air, reading an open book. Binoculars lie beside him; books are scattered around.',
  book: 'The open book. Its pages hold the task for the agent.',
  walk: 'The boy picks up the binoculars and walks to the window.',
  map: 'Through the binoculars: a map of the task area. The agent’s work appears on it as it happens.',
};

function StoryApp() {
  const {prefs, setPrefs, reduce} = usePrefs();
  const mode = prefs.theme === 'light' ? 'day' : 'night';
  const [phase, setPhase] = useState<Phase>(() => new URLSearchParams(location.search).has('run') ? 'map' : prefs.skipIntro ? 'book' : 'intro');
  const [sceneText, setSceneText] = useState(() => prefs.skipIntro ? SCENES.book : mode === 'day' ? SCENES.day : SCENES.intro);
  const [places, setPlaces] = useState<Place[] | null>(null);
  const [agents, setAgents] = useState<Agent[] | null>(null);
  const [runId, setRunId] = useState<string | null>(() => new URLSearchParams(location.search).get('run'));
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [tick, setTick] = useState(0);
  const [startError, setStartError] = useState<string | null>(null);
  const {snap, error} = useSnapshot(phase === 'map' ? runId : null, tick, 500);
  const lines = useNarration(snap, prefs.voice);
  const settings = useRef<HTMLDialogElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const size = useRef({W: innerWidth, H: innerHeight});
  const rest = useRef<{rect: Rect; margin: number; cover: boolean}>(prefs.skipIntro ? {rect: RECTS.book, margin: 0.9, cover: false} : {rect: RECTS.scene, margin: 0.98, cover: false});
  const cam = useRef<Camera>(fit(rest.current.rect, innerWidth, innerHeight, rest.current.margin));
  const boy = useRef<Boy>({pose: 'side', side: POSES.lying, held: false, kick: true});
  const tweens = useRef<{start: number; ms: number; apply: (t: number) => void; done: () => void}[]>([]);
  const skipping = useRef(false);
  const [, force] = useState(0);   // re-render so the book form follows the camera on resize

  useEffect(() => {
    const ctl = new AbortController(), fail = (e: Error) => ctl.signal.aborted || setStartError(String(e.message ?? e));
    client.places(ctl.signal).then(setPlaces).catch(fail); client.agents(ctl.signal).then(setAgents).catch(fail);
    return () => ctl.abort();
  }, []);

  useEffect(() => {
    const ctl = new AbortController();
    client.listRuns(ctl.signal).then(setRuns).catch(e => { if (!ctl.signal.aborted) setStartError(String(e.message ?? e)); });
    return () => ctl.abort();
  }, [tick, phase === 'book']);
  useEffect(() => {
    const url = new URL(location.href);
    if (runId) url.searchParams.set('run', runId); else url.searchParams.delete('run');
    history.replaceState(null, '', `${url.pathname}${url.search}`);
  }, [runId]);
  const openSaved = (id: string) => { setRunId(id); setTick(t => t + 1); setPhase('map'); setSceneText(SCENES.map); };

  // one loop: tweens + world render (paused while the map covers the screen)
  useEffect(() => {
    let raf = 0;
    const frame = (now: number) => {
      for (const tw of [...tweens.current]) {
        const t = skipping.current || reduce ? 1 : Math.min((now - tw.start) / tw.ms, 1);
        tw.apply(t);
        if (t >= 1) { tweens.current = tweens.current.filter(x => x !== tw); tw.done(); }
      }
      const c = canvas.current;
      if (c && phase !== 'map') {
        const dpr = devicePixelRatio || 1, {W, H} = size.current;
        if (c.width !== Math.round(W * dpr)) { c.width = Math.round(W * dpr); c.height = Math.round(H * dpr); }
        const ctx = c.getContext('2d')!;
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        render(ctx, W, H, cam.current, {mode, t: now, boy: boy.current, twinkle: !reduce});
      }
      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(raf);
  }, [phase, mode, reduce]);

  useEffect(() => {
    const onResize = () => {
      size.current = {W: innerWidth, H: innerHeight};
      if (!tweens.current.length) cam.current = fit(rest.current.rect, innerWidth, innerHeight, rest.current.margin, rest.current.cover);
      force(n => n + 1);
    };
    addEventListener('resize', onResize); return () => removeEventListener('resize', onResize);
  }, []);
  useEffect(() => { const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape' && tweens.current.length) skipping.current = true; }; addEventListener('keydown', onKey); return () => removeEventListener('keydown', onKey); }, []);

  const tween = (ms: number, apply: (t: number) => void) => new Promise<void>(done => tweens.current.push({start: performance.now(), ms, apply, done}));
  const fly = (rect: Rect, ms: number, margin = 0.92, cover = false) => {
    const from = cam.current, to = fit(rect, size.current.W, size.current.H, margin, cover);
    rest.current = {rect, margin, cover};
    return tween(ms, t => { cam.current = lerpCam(from, to, ease(t)); });
  };
  const sequence = async (steps: () => Promise<void>) => { skipping.current = false; setPhase('flying'); await steps(); skipping.current = false; };

  const enter = () => sequence(async () => {
    // one continuous move: quick through the sky, then slowing once inside so the room reads on the way to the book
    const W = size.current.W, H = size.current.H, a = cam.current, b = fit(RECTS.room, W, H, 0.98), c = fit(RECTS.book, W, H, 0.9);
    rest.current = {rect: RECTS.book, margin: 0.9, cover: false};
    let inside = false;
    await tween(6000, t => { const k = enterK(t); cam.current = k < 1 ? lerpCam(a, b, k) : lerpCam(b, c, k - 1); if (k > 1 && !inside) { inside = true; setSceneText(SCENES.room); } });
    setSceneText(SCENES.book); setPhase('book');
  });
  const begin = async (place: Place, goal: string, agent: Agent) => {
    setStartError(null);
    try { setRunId(await client.startRun({place_id: place.place_id, goal, agent_id: agent.agent_id})); setTick(t => t + 1); }
    catch (e) { setStartError(String((e as Error).message ?? e)); return; }
    await sequence(async () => {
      await fly(RECTS.room, 1600, 0.98);
      setSceneText(SCENES.walk);
      const pose = (side: Side, held = false) => { boy.current = {pose: 'side', side, held}; };
      const blend = (a: Side, b: Side, ms: number, held = false) => tween(ms, t => pose(lerpSide(a, b, ease(t)), held));
      await blend(POSES.lying, POSES.kneel, 650);                   // gets up
      await blend(POSES.kneel, POSES.stand, 400);
      await tween(700, t => pose(walkSide(POSES.stand, POSES.stand.hx + (POSES.crouch.hx - POSES.stand.hx) * t, t * Math.PI * 3)));
      await blend({...POSES.stand, hx: POSES.crouch.hx}, POSES.crouch, 300);    // grabs the binoculars
      await blend(POSES.crouch, POSES.holding, 350, true);
      await tween(650, t => pose(walkSide(POSES.holding, POSES.holding.hx + (WINDOW_X - POSES.holding.hx) * t, t * Math.PI * 3, true), true));
      boy.current = {pose: 'looking', x: WINDOW_X};
      await tween(300, () => {});
      await fly(RECTS.window, 1800, 1, true);
      setSceneText(SCENES.map); setPhase('map');
    });
  };
  const newTask = () => sequence(async () => {
    boy.current = {pose: 'side', side: POSES.lying, held: false, kick: true};
    cam.current = fit(RECTS.room, size.current.W, size.current.H, 0.98);
    setSceneText(SCENES.room);
    await fly(RECTS.book, 2600, 0.9);
    setSceneText(SCENES.book); setPhase('book');
  });

  const onTree = (x: number, y: number) => { const r = toScreen(cam.current, RECTS.tree, size.current.W, size.current.H); return x >= r.x && x <= r.x + r.w && y >= r.y && y <= r.y + r.h; };
  const bookBox = toScreen(fit(RECTS.book, size.current.W, size.current.H, 0.9), RECTS.book, size.current.W, size.current.H);
  return <div className="shell story" data-theme={prefs.theme} data-text={prefs.text} data-cb={prefs.colorSafe ? 'on' : 'off'} data-motion={reduce ? 'reduce' : 'full'} data-phase={phase}>
    <canvas ref={canvas} className="world" aria-hidden="true"
      onClick={e => { if (phase === 'intro' && onTree(e.clientX, e.clientY)) enter(); }}
      onMouseMove={e => { e.currentTarget.style.cursor = phase === 'intro' && onTree(e.clientX, e.clientY) ? 'pointer' : ''; }} />
    <p className="sr" aria-live="polite">{sceneText}</p>
    <header className="story-bar">
      <span className={`story-brand ${phase === 'map' ? '' : 'sr'}`}>treehouse</span>
      {usingMock && <span className="source">MOCK DATA</span>}
      <button type="button" className="px" onClick={() => setPrefs({...prefs, theme: mode === 'day' ? 'dark' : 'light'})}>{mode === 'day' ? 'Night' : 'Day'}</button>
      <button type="button" className="px" onClick={() => settings.current?.showModal()}>Settings</button>
      <a className="button-link px" href={runId ? `/dev?run=${encodeURIComponent(runId)}` : '/dev'}>Dev view</a>
    </header>
    {phase === 'intro' && <div className="intro-cta px">
      <h1 className="sr">Treehouse</h1>
      <p>Watch an AI agent work. Click the treehouse to step inside.</p>
      <button type="button" className="px primary" autoFocus onClick={enter}>Open the treehouse</button>
    </div>}
    {phase === 'flying' && <button type="button" className="skip-anim px" onClick={() => { skipping.current = true; }}>Skip animation <kbd>Esc</kbd></button>}
    {phase === 'book' && <BookForm places={places} agents={agents} runs={runs} onOpen={openSaved} box={bookBox} error={startError} onBegin={begin} />}
    {phase === 'map' && <MapStage snap={snap} error={error} lines={lines} prefs={prefs} reduce={reduce} mode={mode} onNewTask={newTask} />}
    <Settings ref={settings} prefs={prefs} setPrefs={setPrefs} story />
  </div>;
}

function BookForm({places, agents, runs, onOpen, box, error, onBegin}: {places: Place[] | null; agents: Agent[] | null; runs: RunSummary[]; onOpen: (id: string) => void; box: {x: number; y: number; w: number; h: number}; error: string | null; onBegin: (p: Place, goal: string, a: Agent) => void}) {
  const [agentId, setAgentId] = useState<string>('');
  const agent = agents?.find(a => a.agent_id === agentId) ?? agents?.[0] ?? null;
  const [placeId, setPlaceId] = useState<string>('');
  const place = places?.find(p => p.place_id === placeId) ?? places?.[0] ?? null;
  const [goal, setGoal] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState('');
  const style = {'--bx': `${box.x}px`, '--by': `${box.y}px`, '--bw': `${box.w}px`, '--bh': `${box.h}px`} as CSSProperties;
  return <form className="book" style={style} aria-labelledby="book-h" onSubmit={async e => { e.preventDefault(); if (!place || !agent) return; setBusy(true); await onBegin(place, goal ?? place.goal, agent); setBusy(false); }}>
    <section className="page left">
      <p className="chapter">Chapter one</p>
      <h2 id="book-h">What should the agent find?</h2>
      <label htmlFor="goal" className="sr">Task for the agent</label>
      <textarea id="goal" className="px" rows={9} value={goal ?? place?.goal ?? ''} readOnly={!place?.editable_goal} onChange={e => setGoal(e.target.value)} aria-describedby="goal-note" />
      <p id="goal-note" className="note">{place && !place.editable_goal ? 'Pinned recorded replay. Goal, model and harness must match an available preset; live/custom runs are unavailable.' : 'Edit the prompt or keep the example.'}</p>
    </section>
    <section className="page right">
      <p className="chapter">Chapter two</p>
      <h2>Where, and who goes?</h2>
      <label className="field-block">Place
        <select className="px" value={place?.place_id ?? ''} onChange={e => { setPlaceId(e.target.value); setGoal(null); }} disabled={!places?.length}>
          {places?.map(p => <option key={p.place_id} value={p.place_id}>{p.title}</option>)}
        </select>
      </label>
      {place?.aoi_bbox && <p className="note">Area: {place.aoi_bbox[1]}°N–{place.aoi_bbox[3]}°N, {place.aoi_bbox[0]}°E–{place.aoi_bbox[2]}°E</p>}
      <label className="field-block">Agent
        <select className="px" value={agent?.agent_id ?? ''} onChange={e => setAgentId(e.target.value)} disabled={!agents?.length} aria-describedby="agent-note">
          {agents?.map(a => <option key={a.agent_id} value={a.agent_id}>{a.label}</option>)}
        </select>
      </label>
      {agent && <p id="agent-note" className="note">{agent.note} Model <code>{agent.model_id}</code> in a <i>{agent.harness}</i> harness.</p>}
      {error && <p className="book-error" role="alert">Could not start: {error}</p>}
      <button type="submit" className="px primary" disabled={!place || !agent || busy}>{busy ? 'Starting…' : usingMock ? 'Send the agent (mock)' : 'Replay preset'}</button>
      <label htmlFor="saved-run">Saved runs</label>
      <select id="saved-run" value={saved} onChange={e => setSaved(e.target.value)} disabled={!runs.length}>
        <option value="">Choose a saved run</option>
        {runs.map(r => <option key={r.run_id} value={r.run_id}>{r.title} · {r.status}</option>)}
      </select>
      <button type="button" className="px" disabled={!saved} onClick={() => onOpen(saved)}>Open saved run</button>
    </section>
  </form>;
}

function MapStage({snap, error, lines, prefs, reduce, mode, onNewTask}: {snap: RunSnapshot | null; error: string | null; lines: Narration[]; prefs: Prefs; reduce: boolean; mode: 'night' | 'day'; onNewTask: () => void}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [iris, setIris] = useState(reduce ? 1 : 0);
  const [, rerender] = useState(0);   // 10 Hz tick for the timer and the easing cost readout
  const recv = useRef({elapsed: 0, at: performance.now()});
  const [selectedPrediction, setSelectedPrediction] = useState<string | null>(null);
  const born = useRef<number[]>([]);
  const cost = useRef(0);
  const [floats, setFloats] = useState<{id: number; v: number}[]>([]);
  const lastCost = useRef(0);
  const summary = useRef<HTMLDialogElement>(null);
  const [exported, setExported] = useState<string | null>(null);
  const live = snap ? !terminal(snap.status) : true;
  useEffect(() => { if (snap) recv.current = {elapsed: snap.elapsed_ms ?? 0, at: performance.now()}; }, [snap]);
  useEffect(() => {   // a coin pops up each time the cost goes up
    const c = snap?.cost_usd ?? 0, d = c - lastCost.current; lastCost.current = c;
    if (d <= 0 || reduce || snap?.mode !== 'mock') return;
    const id = performance.now(); setFloats(f => [...f.slice(-3), {id, v: d}]);
    const t = setTimeout(() => setFloats(f => f.filter(x => x.id !== id)), 1400); return () => clearTimeout(t);
  }, [snap?.cost_usd, reduce]);
  const elapsed = useCallback(() => snap?.mode === 'mock' && live ? recv.current.elapsed + performance.now() - recv.current.at : snap?.elapsed_ms ?? 0, [snap, live]);   // run clock, drives map progress
  useEffect(() => { if (reduce) { setIris(1); return; } const t0 = performance.now(); let raf = 0; const f = (t: number) => { const k = Math.min((t - t0) / 1900, 1); setIris(k); if (k < 1) raf = requestAnimationFrame(f); }; raf = requestAnimationFrame(f); return () => cancelAnimationFrame(raf); }, [reduce]);
  useEffect(() => { const id = setInterval(() => { rerender(n => n + 1); if (snap?.cost_usd !== null && snap?.cost_usd !== undefined) cost.current = snap.mode === 'mock' ? cost.current + (snap.cost_usd - cost.current) * (reduce ? 1 : 0.18) : snap.cost_usd; }, 100); return () => clearInterval(id); }, [snap, reduce]);
  useEffect(() => {
    let raf = 0;
    const frame = (t: number) => {
      const c = canvas.current;
      if (c && snap) {
        const dpr = devicePixelRatio || 1, W = c.clientWidth, H = c.clientHeight;
        if (c.width !== Math.round(W * dpr) || c.height !== Math.round(H * dpr)) { c.width = Math.round(W * dpr); c.height = Math.round(H * dpr); }
        while (born.current.length < snap.markers.length) born.current.push(t);
        const ctx = c.getContext('2d')!; ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        renderMap(ctx, W, H, {mode, t, animate: !reduce, colorSafe: prefs.colorSafe, bbox: bboxOf(snap), steps: snap.steps, elapsed: elapsed(), markers: snap.markers, illustrative: snap.mode === 'mock', born: born.current});
      }
      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(raf);
  }, [snap, mode, reduce, prefs.colorSafe, elapsed]);

  const steps = snap?.steps ?? [];
  const latest = (f: (s: TraceStep) => boolean) => [...steps].reverse().find(f);
  const active = latest(s => s.status === 'running' && s.kind === 'execute_tool') ?? latest(s => s.status === 'running' && s.kind === 'chat') ?? latest(s => !!s.decision) ?? null;
  const count = (st: string) => snap?.markers.filter(m => m.status === st).length ?? 0;
  const vmin = Math.min(innerWidth, innerHeight), r0 = vmin * 0.24;
  const r = iris < 0.15 ? r0 * ease(iris / 0.15) : iris < 0.55 ? r0 : r0 + (Math.max(innerWidth, innerHeight) - r0) * ease((iris - 0.55) / 0.45);
  const irisStyle = iris < 1 ? {'--r': `${r}px`, '--dx': `${Math.min(r0 * 0.78, r * 0.78)}px`} as CSSProperties : undefined;
  return <div className="map-stage">
    <section className={`map-view ${iris < 1 ? 'iris' : ''}`} style={irisStyle} aria-label="Map of the task area">
      <canvas ref={canvas} className="map-canvas" role="img" aria-label={`Map of the task area. ${count('present')} predicted present, ${count('absent')} absent and ${count('cannot_assess')} cannot assess so far.`}
        onClick={e => { if (!snap) return; const r = e.currentTarget.getBoundingClientRect(); const m = pickMarker(r.width, r.height, bboxOf(snap), snap.markers, e.clientX - r.left, e.clientY - r.top); if (m) setSelectedPrediction(`${m.trial_id}:${m.claim_id}`); }} />
      <div className="legend px">
        <ul aria-label="Map legend">
          {snap?.mode === 'mock' && <><li><i className="sw embed" />Mock embedded cell</li><li><i className="sw cand" />Mock candidate</li></>}
          <li><i className="sw pin" />Predicted present <b>{count('present')}</b></li><li><i className="sw rej" />Absent <b>{count('absent')}</b></li><li><i className="sw uns" />Cannot assess <b>{count('cannot_assess')}</b></li>
        </ul>
        <p className="credit">{TILE_CREDIT} · browser basemap, not agent evidence. Drawn fallback is illustrative.</p>
      </div>
    </section>
    <aside className="panel" aria-label="Run summary">
      <p className="kicker"><Icon name="bino" /> Through the binoculars</p>
      <h2>{snap?.input.title ?? 'Starting the agent…'}</h2>
      {snap && <p className="agent-line"><Icon name="star" size={14} /> Agent: <b>{snap.context.model_id}</b> · {snap.context.harness}</p>}
      {snap && <p className="note">{snap.mode} · {snap.provenance.embeddings} · vision {snap.provenance.vision}</p>}
      {error && <p className="alert" role="alert">Lost contact with the run: {error}</p>}
      <dl className="meters">
        <div className="px"><dt><Icon name="hourglass" /> {live ? 'Since start' : 'Took'}</dt><dd>{snap ? clock(sinceStart(snap)) : 'unavailable'}</dd></div>
        <div className="px coinbox"><dt><Icon name="coin" /> {snap?.mode === 'replay' ? 'Recorded cost' : 'Cost'}</dt><dd>{snap ? money(snap.cost_usd) : 'unavailable'}</dd>
          <span className="floats" aria-hidden="true">{floats.map(f => <span key={f.id} className="float"><Icon name="coin" size={12} /> +${f.v.toFixed(4)}</span>)}</span></div>
        <div className="px"><dt><Icon name="gem" /> Tokens</dt><dd>{snap ? tokenTotal(snap) : 'unavailable'}</dd></div>
        <div className="px"><dt><Icon name="lamp" /> Status</dt><dd className={live ? 'livestat' : `st st-${snap?.status ?? 'queued'}`}>{live ? `${snap?.mode ?? 'unknown'} pending` : snap?.status}</dd></div>
      </dl>
      {active && <section className={`bubble px ${isKey(active) ? 'key' : ''}`} aria-label="What the agent is doing" key={active.span_id}>
        <p className="eyebrow">{live ? 'Deciding now' : 'Last decision'}</p>
        {isKey(active) && <p className="keytag"><Icon name="star" size={14} /> Key decision · {FOCUS_LABEL[focusOf(active)]}</p>}
        <p className="what">{active.tool ? <code>{active.tool.name}</code> : active.kind === 'chat' ? 'Thinking…' : active.name}</p>
        {active.decision && <p className="why">{active.decision.rationale}</p>}
      </section>}
      {prefs.captions && <p className="caption px" aria-live="polite"><Icon name="scroll" /> <span>{lines[0]?.text ?? 'The narrator speaks at each key decision.'}</span></p>}
      <section aria-labelledby="quest-h">
        <h3 id="quest-h" className="quest-h">Quest log</h3>
        <ol className="phases">
          {PHASES.map(([label, tools]) => { const state = phaseState(steps, tools, !live); return <li key={label} className={state}><span className="box" aria-hidden="true" /> {label} <span className="sr">({state})</span>{state === 'recovered' && <span className="mini">recovered from an error</span>}</li>; })}
        </ol>
      </section>
      {snap && <PredictionEvidence snap={snap} selected={selectedPrediction} onSelect={setSelectedPrediction} />}
      <div className="actions">
        <button type="button" className={`px ${live ? '' : 'primary'}`} onClick={() => summary.current?.showModal()} disabled={!snap}>{live ? 'Summary so far' : 'Read the full summary'}</button>
        <button type="button" className="px" onClick={async () => { if (!snap) return; try { setExported(await exportRun(snap, lines)); } catch (e) { if ((e as Error).name !== 'AbortError') setExported(`Export failed: ${(e as Error).message}`); } }} disabled={!snap}>{canPickFolder() ? 'Export to a folder' : 'Download export'}</button>
        <button type="button" className="px" onClick={onNewTask}>New task</button>
      </div>
      {exported && <p className="note" role="status">{exported}</p>}
    </aside>
    {snap && <Summary ref={summary} snap={snap} lines={lines} count={count} />}
  </div>;
}


function Summary({ref, snap, lines, count}: {ref: Ref<HTMLDialogElement>; snap: RunSnapshot; lines: Narration[]; count: (s: string) => number}) {
  const keys = snap.steps.filter(isKey), errors = snap.steps.filter(s => s.error), thoughts = snap.steps.filter(s => s.model?.thinking);
  const labeller = snap.steps.find(s => s.tool?.name === 'strands_label');
  const tools = snap.steps.flatMap(s => s.tool ? [s.tool] : []);
  const bytes = tools.length && tools.every(t => t.bytes_read !== null) ? tools.reduce((b, t) => b + t.bytes_read!, 0) : null;
  const recovery = (e: TraceStep) => snap.steps.find(s => s.start_ms > e.start_ms && s.tool?.name === e.tool?.name);
  return <dialog ref={ref} className="summary" aria-labelledby="sum-h">
    <form method="dialog" className="summary-head"><h2 id="sum-h">The full story</h2><button type="submit">Close</button></form>
    <div className="summary-body">
      <section><h3>What it was asked</h3><p>{snap.input.goal}</p>
        <dl className="kv"><dt>Area</dt><dd>{snap.input.aoi_bbox?.join(', ') ?? '—'}</dd><dt>Window</dt><dd>{snap.input.time_window?.join(' → ') ?? '—'}</dd>
          <dt>Data allowed</dt><dd>{snap.input.data_allowlist.map(d => d.source_id).join(', ') || '—'}</dd></dl></section>
      <section><h3>What it was given</h3>
        <dl className="kv"><dt>Model</dt><dd>{snap.context.model_id}</dd><dt>Harness</dt><dd>{snap.context.harness}</dd>
          {snap.context.items.map(i => <Fragment key={i.label}><dt>{i.label}</dt><dd>{i.detail}{i.tokens ? ` · ${kilo(i.tokens)} tokens` : ''}</dd></Fragment>)}</dl></section>
      <section><h3>How it worked: key decisions</h3>
        <ol className="decisions">{keys.map(k => <li key={k.span_id}>
          <p><span className={`tag f-${focusOf(k)}`}>{FOCUS_LABEL[focusOf(k)]}</span> <code>{k.tool?.name}</code> <span className={`st st-${k.status}`}>{k.status}</span></p>
          {k.decision && <><p>{k.decision.rationale}</p><p className="note">Self-reported confidence {Math.round(k.decision.confidence * 100)} %</p>
            {k.decision.alternatives.length > 0 && <ul>{k.decision.alternatives.map(a => <li key={a.option}>Not chosen — <b>{a.option}</b>: {a.reason}</li>)}</ul>}</>}
        </li>)}</ol></section>
      {thoughts.length > 0 && <section><h3>Recorded model text</h3>
        <ol className="thoughts">{thoughts.map(t => <li key={t.span_id}><span className="num">{clock(t.start_ms)}</span> {t.model!.thinking}</li>)}</ol></section>}
      <section><h3>How it built the database</h3>
        <p>{labeller ? <>It handed {String(labeller.tool?.args.chips ?? 'the')} image chips to the Strands labelling sub-agent. {labeller.decision?.rationale}</> : 'No Strands labelling step was recorded.'}</p>
        <p>{count('present')} predicted present · {count('absent')} absent · {count('cannot_assess')} cannot assess. Class labels, status and confidence are the agent’s own reports.</p></section>
      <section><h3>Problems and recovery</h3>
        {errors.length ? <ul>{errors.map(e => { const r = recovery(e); return <li key={e.span_id}><code>{e.tool?.name}</code>: {e.error!.type}: {e.error!.message}. {r ? `It retried (${r.status}).` : 'It did not retry.'}</li>; })}</ul> : <p>None.</p>}</section>
      <EvaluationPanels snap={snap} />
      <section><h3>Cost and time</h3>
        <dl className="kv"><dt>Time</dt><dd>{snap.elapsed_ms === null ? 'unavailable' : `${(snap.elapsed_ms / 1000).toFixed(1)} s (${snap.timing_basis ?? 'recorded trace'})`}</dd><dt>Cost</dt><dd>{money(snap.cost_usd)}</dd>
          <dt>Steps</dt><dd>{snap.steps.length}</dd><dt>Data read</dt><dd>{bytes === null ? 'unavailable' : `${(bytes / 1e6).toFixed(1)} MB`}</dd></dl></section>
      {lines.length > 0 && <section><h3>Narration</h3><ol>{[...lines].reverse().map((l, i) => <li key={i}>{l.text}</li>)}</ol></section>}
      <p><a href={`/dev?run=${encodeURIComponent(snap.run_id)}`}>Open every span in the dev view</a></p>
    </div>
  </dialog>;
}

createRoot(document.getElementById('root')!).render(<StrictMode><StoryApp /></StrictMode>);
