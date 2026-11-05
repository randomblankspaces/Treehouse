/** The demo slide: a mode picker (recorded / embedded app / live) above the chosen mode. A multi-stage mode
 *  turns the section into a scroll sequence: the content stays pinned while each screen of scroll reveals the
 *  next stage (1 → 2 → 3). `?demo=<id>` preselects a mode; the D key cycles modes. */
import { useEffect, useRef, useState } from 'react';
import { d, Slide } from '../ui.tsx';
import { DEMO_MODES } from './modes.ts';

export const STAGE_TITLES = ['The agent investigates', 'Every step is captured', 'The run is scored'];

export function DemoSection() {
  const [modeId, setModeId] = useState(() => {
    const want = new URLSearchParams(location.search).get('demo');
    return DEMO_MODES.find(m => m.id === want)?.id ?? DEMO_MODES[0].id;
  });
  const mode = DEMO_MODES.find(m => m.id === modeId) ?? DEMO_MODES[0];
  const outer = useRef<HTMLDivElement>(null);
  const [stage, setStage] = useState(0);

  useEffect(() => {
    const url = new URL(location.href);
    url.searchParams.set('demo', mode.id);
    history.replaceState(null, '', url);
  }, [mode.id]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t && ['INPUT', 'TEXTAREA', 'SELECT'].includes(t.tagName)) return;
      if ((e.key === 'd' || e.key === 'D') && !e.metaKey && !e.ctrlKey && !e.altKey) {
        setModeId(id => DEMO_MODES[(DEMO_MODES.findIndex(m => m.id === id) + 1) % DEMO_MODES.length].id);
      }
    };
    addEventListener('keydown', onKey);
    return () => removeEventListener('keydown', onKey);
  }, []);

  useEffect(() => {
    if (mode.stages <= 1) { setStage(0); return; }
    const onScroll = () => {
      const el = outer.current;
      if (!el) return;
      const r = el.getBoundingClientRect();
      const travelled = -r.top / innerHeight;   // screens scrolled past the section top
      setStage(Math.max(0, Math.min(mode.stages - 1, Math.floor(travelled + 0.5))));
    };
    onScroll();
    addEventListener('scroll', onScroll, {passive: true});
    addEventListener('resize', onScroll);
    return () => { removeEventListener('scroll', onScroll); removeEventListener('resize', onScroll); };
  }, [mode.stages]);

  const Mode = mode.Component;
  return <Slide id="demo" className="demo" tall>
    <div ref={outer} className="demo-track" style={{height: `${mode.stages * 100}vh`}}>
      <div className="demo-sticky">
        <div className="demo-head">
          <div>
            <p className="eyebrow r">Demo</p>
            <h2 className="r" style={d(1)}>Watch one agent run, <em>observed → sealed → scored</em>.</h2>
          </div>
          <div className="mode-picker r" style={d(2)} role="radiogroup" aria-label="Demo mode">
            {DEMO_MODES.map(m => <button key={m.id} role="radio" aria-checked={m.id === mode.id} title={m.hint}
              className={m.id === mode.id ? 'on' : ''} onClick={() => setModeId(m.id)}>{m.label}</button>)}
          </div>
        </div>
        {mode.stages > 1 && <ol className="stages" aria-label="Demo stages">
          {STAGE_TITLES.slice(0, mode.stages).map((t, i) => <li key={t} className={i === stage ? 'on' : i < stage ? 'done' : ''}
            aria-current={i === stage ? 'step' : undefined}>
            <span className="num">{i + 1}</span>{t}</li>)}
        </ol>}
        <div className="demo-body r" style={d(3)}><Mode stage={stage} stages={mode.stages} /></div>
        <p className="mode-hint">{mode.hint}</p>
      </div>
    </div>
  </Slide>;
}
