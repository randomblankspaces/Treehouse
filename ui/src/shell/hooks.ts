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

export type RunNarration = {text: string; source: 'polly' | 'browser' | 'none'; audioUrl: string | null};

/** sha256 of a string as lowercase hex (matches the Polly sidecar's text_sha256). */
async function sha256Hex(text: string): Promise<string> {
  const data = new TextEncoder().encode(text);
  const digest = await crypto.subtle.digest('SHA-256', data);
  return [...new Uint8Array(digest)].map(b => b.toString(16).padStart(2, '0')).join('');
}

/** Run-level spoken summary. Loads the pre-rendered Polly sidecar at /narration/<run>.json and plays the MP3
 *  only when sha256(shown text) matches the sidecar's sha256; otherwise falls back to the browser's speech
 *  synthesiser on the same text. Speaks once per run when `voice` is on and motion is not reduced. */
export function useRunNarration(snap: RunSnapshot | null, voice: boolean) {
  const [narr, setNarr] = useState<RunNarration | null>(null);
  const spoken = useRef<string>('');
  useEffect(() => {
    if (!snap || !terminal(snap.status)) { setNarr(null); return; }
    let cancelled = false;
    (async () => {
      let result: RunNarration | null = null;
      try {
        const res = await fetch(`/narration/${encodeURIComponent(snap.run_id)}.json`, {cache: 'no-store'});
        if (res.ok) {
          const side = await res.json() as {text?: unknown; sha256?: unknown};
          if (typeof side.text === 'string' && typeof side.sha256 === 'string') {
            const match = (await sha256Hex(side.text)) === side.sha256;
            result = match
              ? {text: side.text, source: 'polly', audioUrl: `/narration/${encodeURIComponent(snap.run_id)}.mp3`}
              : {text: side.text, source: 'browser', audioUrl: null};
          }
        }
      } catch { /* no sidecar served (e.g. mock/dev): fall back below */ }
      if (!result) {
        try {  // live mode only: server synthesizes Polly on demand; 404 elsewhere is ignored
          const res = await fetch(`/api/voice/runs/${encodeURIComponent(snap.run_id)}`, {cache: 'no-store'});
          if (res.ok) {
            const v = await res.json() as {text?: unknown; audio_url?: unknown};
            if (typeof v.text === 'string' && typeof v.audio_url === 'string') result = {text: v.text, source: 'polly', audioUrl: v.audio_url};
          }
        } catch { /* no live voice: browser speech below */ }
      }
      const summary = snap.thinking_summary;
      if (!result && summary?.status === 'available' && summary.text) result = {text: summary.text, source: 'browser', audioUrl: null};
      if (cancelled) return;
      setNarr(result);
    })();
    return () => { cancelled = true; };
  }, [snap?.run_id, snap?.status]);

  // Speak once per run when voice is enabled.
  useEffect(() => {
    if (!voice || !narr || spoken.current === narr.text) return;
    spoken.current = narr.text;
    if (narr.source === 'polly' && narr.audioUrl) {
      const audio = new Audio(narr.audioUrl);
      audio.play().catch(() => speak(narr.text));   // if the MP3 404s, fall back to speech
    } else {
      speak(narr.text);
    }
  }, [voice, narr]);
  return narr;
}

function speak(text: string) {
  try {
    const synth = window.speechSynthesis;
    if (!synth) return;
    synth.cancel();
    synth.speak(new SpeechSynthesisUtterance(text));
  } catch { /* speech unavailable: captions still show the text */ }
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
    if (terminal(snap.status) && !ids.has('__run_end')) {
      ids.add('__run_end');
      const claims = snap.markers.length;
      const end: Narration = {text: `Run ${snap.status.replaceAll('_', ' ')}: ${claims} claim${claims === 1 ? '' : 's'} recorded.`, audio_url: null};
      // after the step lines above have resolved, so this stays on top
      void Promise.resolve().then(() => { if (seen.current.key === key) setLines(l => [end, ...l].slice(0, 8)); });
    }
  }, [snap, voice]);
  return lines;
}
