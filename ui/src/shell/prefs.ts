/** Display and accessibility settings, shared by the storybook and dev interfaces. Per-viewer only. */
/** Colour-vision-safe palettes. 'default' is the brand palette; the rest are status-safe choices:
 *  Okabe–Ito (red–green safe), a blue–yellow safe pair, and monochrome (no colour dependence at all). */
export type Palette = 'default' | 'okabe-ito' | 'blue-yellow' | 'monochrome';
export type Prefs = {theme: 'dark' | 'light' | 'contrast'; text: '100' | '125' | '150'; motion: 'system' | 'reduce' | 'full';
  palette: Palette; captions: boolean; voice: boolean; skipIntro: boolean};
const KEY = 'treehouse.shell.prefs';
const DEFAULTS: Prefs = {theme: 'dark', text: '100', motion: 'system', palette: 'default', captions: true, voice: false, skipIntro: false};
const OPTIONS = {theme: ['dark', 'light', 'contrast'], text: ['100', '125', '150'], motion: ['system', 'reduce', 'full'],
  palette: ['default', 'okabe-ito', 'blue-yellow', 'monochrome']} as const;
/** True when any colour-vision-safe palette is active (the map uses this to pick safe marker fills). */
export const isColorSafe = (p: Prefs) => p.palette !== 'default';

export function loadPrefs(): Prefs {
  try {
    const raw: unknown = JSON.parse(localStorage.getItem(KEY) ?? '{}');
    if (!raw || typeof raw !== 'object') return DEFAULTS;
    const r = raw as Record<string, unknown>, out = {...DEFAULTS};
    for (const k of ['theme', 'text', 'motion', 'palette'] as const) if ((OPTIONS[k] as readonly unknown[]).includes(r[k])) (out as Record<string, unknown>)[k] = r[k];
    for (const k of ['captions', 'voice', 'skipIntro'] as const) if (typeof r[k] === 'boolean') out[k] = r[k];
    // Back-compat: an older stored `colorSafe: true` maps to the Okabe–Ito palette.
    if (out.palette === 'default' && r.colorSafe === true) out.palette = 'okabe-ito';
    return out;
  } catch { return DEFAULTS; }
}
export function savePrefs(p: Prefs) { try { localStorage.setItem(KEY, JSON.stringify(p)); } catch { /* storage blocked: settings last for this visit only */ } }
