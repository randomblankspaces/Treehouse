import type { Ref } from 'react';
import type { Prefs } from './prefs.ts';

export function Settings({ref, prefs, setPrefs, story = false}: {ref: Ref<HTMLDialogElement>; prefs: Prefs; setPrefs: (p: Prefs) => void; story?: boolean}) {
  const set = <K extends keyof Prefs>(k: K, v: Prefs[K]) => setPrefs({...prefs, [k]: v});
  const radio = <K extends 'theme' | 'text' | 'motion'>(k: K, label: string, options: [Prefs[K], string][]) =>
    <fieldset><legend>{label}</legend>{options.map(([v, l]) => <label key={v} className="check"><input type="radio" name={k} checked={prefs[k] === v} onChange={() => set(k, v)} /> {l}</label>)}</fieldset>;
  return <dialog ref={ref} className="settings" aria-labelledby="set-h">
    <form method="dialog">
      <h2 id="set-h">Display and accessibility</h2>
      {radio('theme', story ? 'Theme (night / day)' : 'Theme', [['dark', story ? 'Night' : 'Dark'], ['light', story ? 'Day' : 'Light'], ['contrast', 'High contrast']])}
      {radio('text', 'Text size', [['100', '100 %'], ['125', '125 %'], ['150', '150 %']])}
      {radio('motion', 'Motion', [['system', 'Follow system'], ['reduce', 'Reduce (cuts instead of zooms)'], ['full', 'Full']])}
      <fieldset><legend>Assistance</legend>
        <label className="check"><input type="checkbox" checked={prefs.colorSafe} onChange={e => set('colorSafe', e.target.checked)} /> Colour-blind-safe palette</label>
        <label className="check"><input type="checkbox" checked={prefs.captions} onChange={e => set('captions', e.target.checked)} /> Narrator captions</label>
        <label className="check"><input type="checkbox" checked={prefs.voice} onChange={e => set('voice', e.target.checked)} /> Narrator voice (when available)</label>
        {story && <label className="check"><input type="checkbox" checked={prefs.skipIntro} onChange={e => set('skipIntro', e.target.checked)} /> Skip the intro next time</label>}
      </fieldset>
      <button type="submit">Done</button>
    </form>
  </dialog>;
}
