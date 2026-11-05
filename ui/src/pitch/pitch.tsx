/** /pitch — the scrolling presentation: problem → working backwards → architecture → demo → numbers → impact → future.
 *  Each <Slide> is one screen; its children fade in as it scrolls into view. Keyboard: ↓/↑, PageDown/PageUp,
 *  Space, Home/End move one slide; T toggles light/dark (projectors); D cycles the demo mode.
 *  Nothing here calls AWS on load; demo mode "live" calls the server only when the presenter presses Start. */
import { StrictMode, useCallback, useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Architecture } from './architecture.tsx';
import { DemoSection } from './demo/DemoSection.tsx';
import { Numbers } from './numbers.tsx';
import { Context, Future, Impact, Problem, Solution, WorkingBackwards } from './slides.tsx';
import { reducedMotion, SLIDES, type SlideId } from './ui.tsx';
import '@fontsource/pixelify-sans/latin-700.css';
import './pitch.css';

document.title = 'Treehouse · Pitch';

function Nav({active}: {active: SlideId}) {
  return <nav className="dots" aria-label="Slides">
    {SLIDES.map((s, i) => <a key={s.id} href={`#${s.id}`} aria-current={s.id === active ? 'step' : undefined} title={s.label}>
      <span className="dot" aria-hidden="true" /><span className="dot-label">{i + 1}. {s.label}</span>
    </a>)}
  </nav>;
}

function PitchApp() {
  const [theme, setTheme] = useState<'dark' | 'light'>(() => new URLSearchParams(location.search).get('theme') === 'light' ? 'light' : 'dark');
  const [active, setActive] = useState<SlideId>('problem');
  const [progress, setProgress] = useState(0);

  // Active slide = the one whose top is nearest above the middle of the screen.
  useEffect(() => {
    const onScroll = () => {
      const mid = innerHeight * 0.45;
      let current: SlideId = 'problem';
      for (const s of SLIDES) { const el = document.getElementById(s.id); if (el && el.getBoundingClientRect().top <= mid) current = s.id; }
      setActive(current);
      const max = document.documentElement.scrollHeight - innerHeight;
      setProgress(max > 0 ? Math.min(1, scrollY / max) : 0);
    };
    onScroll();
    addEventListener('scroll', onScroll, {passive: true});
    addEventListener('resize', onScroll);
    return () => { removeEventListener('scroll', onScroll); removeEventListener('resize', onScroll); };
  }, []);

  const go = useCallback((delta: number) => {
    const i = SLIDES.findIndex(s => s.id === active);
    const next = SLIDES[Math.max(0, Math.min(SLIDES.length - 1, i + delta))];
    const el = document.getElementById(next.id);
    if (!el) return;
    // Inside the tall demo section, step through its stages before leaving it.
    if (active === 'demo' && el.id !== 'demo') {
      const demo = document.getElementById('demo')!;
      const r = demo.getBoundingClientRect();
      const stage = innerHeight;
      if (delta > 0 && r.bottom - innerHeight > stage * 0.5) { scrollBy({top: stage, behavior: reducedMotion() ? 'auto' : 'smooth'}); return; }
      if (delta < 0 && r.top < -stage * 0.5) { scrollBy({top: -stage, behavior: reducedMotion() ? 'auto' : 'smooth'}); return; }
    }
    el.scrollIntoView({behavior: reducedMotion() ? 'auto' : 'smooth'});
  }, [active]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t && (['INPUT', 'TEXTAREA', 'SELECT', 'BUTTON'].includes(t.tagName) || t.isContentEditable) && e.key === ' ') return;
      if (t && ['INPUT', 'TEXTAREA', 'SELECT'].includes(t.tagName)) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (['ArrowDown', 'PageDown'].includes(e.key) || (e.key === ' ' && !e.shiftKey)) { e.preventDefault(); go(1); }
      else if (['ArrowUp', 'PageUp'].includes(e.key) || (e.key === ' ' && e.shiftKey)) { e.preventDefault(); go(-1); }
      else if (e.key === 'Home') { e.preventDefault(); document.getElementById(SLIDES[0].id)?.scrollIntoView(); }
      else if (e.key === 'End') { e.preventDefault(); document.getElementById(SLIDES[SLIDES.length - 1].id)?.scrollIntoView(); }
      else if (e.key === 't' || e.key === 'T') setTheme(v => v === 'dark' ? 'light' : 'dark');
    };
    addEventListener('keydown', onKey);
    return () => removeEventListener('keydown', onKey);
  }, [go]);

  useEffect(() => { document.documentElement.dataset.pitchTheme = theme; }, [theme]);

  return <div className="pitch" data-theme={theme}>
    <div className="progress" aria-hidden="true"><span style={{transform: `scaleX(${progress})`}} /></div>
    <header className="topbar">
      <a className="brand" href="/" title="Open the Treehouse app"><span className="brand-mark" aria-hidden="true">⌂</span>treehouse</a>
      <span className="topbar-sub">Clay Earth Dataset Foundry · ADB agentic eval</span>
      <button className="theme-toggle" onClick={() => setTheme(v => v === 'dark' ? 'light' : 'dark')} aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}>{theme === 'dark' ? '☀ Light' : '☾ Dark'}</button>
    </header>
    <Nav active={active} />
    <main>
      <Problem />
      <Context />
      <WorkingBackwards />
      <Solution />
      <Architecture />
      <DemoSection />
      <Numbers />
      <Impact />
      <Future />
    </main>
    <p className="keys-hint" aria-hidden="true">↓ / ↑ next · T theme</p>
  </div>;
}

createRoot(document.getElementById('root')!).render(<StrictMode><PitchApp /></StrictMode>);
