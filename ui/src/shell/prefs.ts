/** Display and accessibility settings, shared by the storybook and dev interfaces. Per-viewer only. */
export type Prefs = {theme: 'dark' | 'light' | 'contrast'; text: '100' | '125' | '150'; motion: 'system' | 'reduce' | 'full';
  colorSafe: boolean; captions: boolean; voice: boolean; skipIntro: boolean};
const KEY = 'treehouse.shell.prefs';
const DEFAULTS: Prefs = {theme: 'dark', text: '100', motion: 'system', colorSafe: false, captions: true, voice: false, skipIntro: false};
const OPTIONS = {theme: ['dark', 'light', 'contrast'], text: ['100', '125', '150'], motion: ['system', 'reduce', 'full']} as const;

export function loadPrefs(): Prefs {
  try {
    const raw: unknown = JSON.parse(localStorage.getItem(KEY) ?? '{}');
    if (!raw || typeof raw !== 'object') return DEFAULTS;
    const r = raw as Record<string, unknown>, out = {...DEFAULTS};
    for (const k of ['theme', 'text', 'motion'] as const) if ((OPTIONS[k] as readonly unknown[]).includes(r[k])) (out as Record<string, unknown>)[k] = r[k];
    for (const k of ['colorSafe', 'captions', 'voice', 'skipIntro'] as const) if (typeof r[k] === 'boolean') out[k] = r[k];
    return out;
  } catch { return DEFAULTS; }
}
export function savePrefs(p: Prefs) { try { localStorage.setItem(KEY, JSON.stringify(p)); } catch { /* storage blocked: settings last for this visit only */ } }
