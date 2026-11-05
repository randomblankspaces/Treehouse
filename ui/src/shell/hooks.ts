import { useEffect, useRef, useState } from 'react';
import { client, narrator } from './client.ts';
import { terminal, type Narration, type RunSnapshot } from './contract.ts';
import { loadPrefs, savePrefs, type Prefs } from './prefs.ts';

export function usePrefs() {
  const [prefs, setPrefs] = useState<Prefs>(loadPrefs);
  const [system, setSystem] = useState(() => matchMedia('(prefers-reduced-motion: reduce)').matches);
  useEffect(() => { const m = matchMedia('(prefers-reduced-motion: reduce)'); const on = () => setSystem(m.matches); m.addEventListener('change', on); return () => m.removeEventListener('change', on); }, []);
  useEffect(() => savePrefs(prefs), [prefs]);
  const reduce = prefs.motion === 'reduce' || (prefs.motion === 'system' && system);
  return {prefs, setPrefs, reduce};
}

/** Polls a run until it is terminal. Bump `tick` to restart (e.g. after starting the run again). */
export function useSnapshot(runId: string | null, tick = 0, everyMs = 1000) {
  const [snap, setSnap] = useState<RunSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    setSnap(null);
    if (!runId) return;
    const ctl = new AbortController(); let timer = 0;
    const poll = () => client.snapshot(runId, ctl.signal).then(s => { setSnap(s); setError(null); if (!terminal(s.status)) timer = window.setTimeout(poll, everyMs); })
      .catch(e => { if (!ctl.signal.aborted) { setError(String(e?.message ?? e)); timer = window.setTimeout(poll, 3000); } });
    poll();
    return () => { ctl.abort(); clearTimeout(timer); };
  }, [runId, tick, everyMs]);
  return {snap, error};
}

/** Narrates each finished step once; newest line first. Resets when the run (or its restart) changes. */
export function useNarration(snap: RunSnapshot | null, voice: boolean) {
  const [lines, setLines] = useState<Narration[]>([]);
  const seen = useRef({key: '', ids: new Set<string>()});
  useEffect(() => {
    if (!snap) return;
    const key = `${snap.run_id}@${snap.started_at}`;
    if (seen.current.key !== key) { seen.current = {key, ids: new Set()}; setLines([]); }
    const ids = seen.current.ids;
    for (const st of snap.steps) {
      if (st.status === 'running' || ids.has(st.span_id)) continue;
      ids.add(st.span_id);
      narrator.line(st, snap).then(n => {
        if (!n || seen.current.key !== key) return;
        setLines(l => [n, ...l].slice(0, 8));
        if (n.audio_url && voice) void new Audio(n.audio_url).play().catch(() => {});
      });
    }
  }, [snap, voice]);
  return lines;
}
