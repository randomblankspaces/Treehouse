/** The view through the binoculars: GSI aerial tiles (Japan; attribution required) under glowing overlays
 *  driven by the run's own steps. Without tiles (offline, or outside Japan) a drawn map stands in. */
import type { Mode } from './art.ts';
import type { MapMarker, TraceStep } from './contract.ts';

export const COLS = 62, ROWS = 48;   // ≈ 160 m cells over the Nagoya Port AOI
export const TILE_CREDIT = 'Aerial imagery: GSI Japan (地理院タイル)';
export type MapState = {mode: Mode; t: number; animate: boolean; colorSafe: boolean; bbox: [number, number, number, number] | null;
  steps: TraceStep[]; elapsed: number; markers: MapMarker[]; born: number[];
  technical?: boolean;   // dev view: cell grid, indices, corner coordinates
  focus?: string | null;   // a tool name: its layer stays bright, the rest dims
};
const LAYER: Record<string, 'index' | 'candidates' | 'chips' | 'labels'> = {list_embedding_sources: 'index', build_index: 'index', get_examples: 'candidates', retrieve: 'candidates', classify: 'candidates', imagery_window: 'chips', stac_search: 'chips', strands_label: 'labels', record_claim: 'labels', aggregate: 'labels', note_limitation: 'labels'};
/** Screen placement of the task area; shared by the renderer and hover picking. */
export function layout(W: number, H: number, bbox: [number, number, number, number] | null) {
  const [w, s, e, n] = bbox ?? [0, 0, 0.01, 0.01];
  const z = Math.min(17, Math.max(10, Math.ceil(Math.log2(W * (devicePixelRatio || 1) * 0.8 / (lonX(e, 0) - lonX(w, 0))))));
  const x1 = lonX(w, z), x2 = lonX(e, z), y1 = latY(n, z), y2 = latY(s, z);
  const k = Math.min(W * 0.92 / (x2 - x1), H * 0.9 / (y2 - y1));
  const ox = W / 2 - (x1 + x2) / 2 * k, oy = H / 2 - (y1 + y2) / 2 * k;
  return {w, s, e, n, z, k, ox, oy, A: {x: x1 * k + ox, y: y1 * k + oy, w: (x2 - x1) * k, h: (y2 - y1) * k}};
}
/** Lon/lat and cell under a screen point, or null outside the task area. */
export function pick(W: number, H: number, bbox: [number, number, number, number] | null, px: number, py: number) {
  const L = layout(W, H, bbox), u = (px - L.A.x) / L.A.w, v = (py - L.A.y) / L.A.h;
  if (u < 0 || v < 0 || u > 1 || v > 1) return null;
  return {lon: L.w + u * (L.e - L.w), lat: L.n - v * (L.n - L.s), col: Math.floor(u * COLS), row: Math.floor(v * ROWS)};
}

const hash = (n: number) => { const x = Math.sin(n * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); };
const ease = (t: number) => 1 - (1 - t) ** 3;
const CANDIDATES = Array.from({length: COLS * ROWS}, (_, i) => ({c: i % COLS, r: Math.floor(i / COLS), h: hash(i * 7.3)}))
  .filter(x => x.r < ROWS * 0.4 && x.h < 0.3).sort((a, b) => a.h - b.h).slice(0, 400);

// --- tiles ---------------------------------------------------------------------------------------
const TILE = 256;
const lonX = (lon: number, z: number) => (lon + 180) / 360 * 2 ** z * TILE;
const latY = (lat: number, z: number) => { const r = lat * Math.PI / 180; return (1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2 * 2 ** z * TILE; };
type Tile = {img: HTMLImageElement; ok: boolean};
const tiles = new Map<string, Tile>();
function tile(z: number, x: number, y: number): Tile {
  const key = `${z}/${x}/${y}`;
  let t = tiles.get(key);
  if (!t) {
    const img = new Image(), ref: Tile = {img, ok: false};
    img.onload = () => { ref.ok = true; };
    img.src = `https://cyberjapandata.gsi.go.jp/xyz/seamlessphoto/${key}.jpg`;
    tiles.set(key, ref); t = ref;
  }
  return t;
}

function progress(steps: TraceStep[], tool: string, elapsed: number) {
  const s = [...steps].reverse().find(x => x.tool?.name === tool);
  if (!s) return 0;
  if (s.status !== 'running') return 1;
  return 1 - Math.exp(-(elapsed - s.start_ms) / 2500);
}

export function renderMap(ctx: CanvasRenderingContext2D, W: number, H: number, st: MapState) {
  const night = st.mode === 'night';
  ctx.fillStyle = night ? '#0b0a18' : '#dfe9f0'; ctx.fillRect(0, 0, W, H);
  const {w, s, e, n, z, k, ox, oy, A} = layout(W, H, st.bbox);
  const cw = A.w / COLS, ch = A.h / ROWS;
  const dim = (layer: string) => { ctx.globalAlpha = st.focus && LAYER[st.focus] && LAYER[st.focus] !== layer ? 0.25 : 1; };
  const at = (lon: number, lat: number) => ({x: lonX(lon, z) * k + ox, y: latY(lat, z) * k + oy});

  // drawn fallback: water, a soft coast and piers (covered by tiles once they load)
  const coast = (u: number) => 0.66 + 0.035 * Math.sin(u * 9) + 0.025 * Math.sin(u * 23 + 1);
  ctx.fillStyle = night ? '#1b2c52' : '#8cc6e8'; ctx.fillRect(0, A.y + A.h * 0.55, W, H);
  ctx.fillStyle = night ? '#3a3448' : '#e6dfcd'; ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(W, 0); ctx.lineTo(W, A.y + coast(1) * A.h);
  for (let i = 40; i >= 0; i--) { const u = i / 40; ctx.lineTo(A.x + u * A.w, A.y + coast(u) * A.h); }
  ctx.lineTo(0, A.y + coast(0) * A.h); ctx.closePath(); ctx.fill();
  for (const p of [0.16, 0.34, 0.5, 0.66, 0.88]) ctx.fillRect(A.x + (p - 0.03) * A.w, A.y + coast(p) * A.h - 2, A.w * 0.06, A.h * 0.2);
  // aerial tiles (GSI covers Japan only; elsewhere the drawn map stands)
  ctx.imageSmoothingEnabled = true;
  const S = TILE * k, japan = w > 122 && e < 154 && s > 20 && n < 46;
  if (japan) for (let ty = Math.floor(-oy / S); ty <= Math.floor((H - oy) / S); ty++) for (let tx = Math.floor(-ox / S); tx <= Math.floor((W - ox) / S); tx++) {
    if (ty < 0 || tx < 0 || ty >= 2 ** z || tx >= 2 ** z) continue;
    const t = tile(z, tx, ty);
    if (t.ok) ctx.drawImage(t.img, Math.floor(tx * S + ox), Math.floor(ty * S + oy), Math.ceil(S) + 1, Math.ceil(S) + 1);
  }
  // mood: moonlit at night; dim outside the task area
  if (night) { ctx.fillStyle = 'rgba(16,10,52,0.32)'; ctx.fillRect(0, 0, W, H); }
  ctx.fillStyle = night ? 'rgba(4,3,14,0.55)' : 'rgba(20,15,28,0.35)';
  ctx.beginPath(); ctx.rect(0, 0, W, H); ctx.rect(A.x, A.y, A.w, A.h); ctx.fill('evenodd');

  ctx.save(); ctx.beginPath(); ctx.rect(A.x, A.y, A.w, A.h); ctx.clip();
  // 1. embeddings: a glowing sweep turns the area into 160 m cells
  dim('index');
  const pIndex = progress(st.steps, 'build_index', st.elapsed);
  if (pIndex > 0) {
    const edge = A.x + pIndex * A.w;
    for (let r = 0; r < ROWS; r++) for (let c = 0; c < COLS; c++) {
      const x = A.x + c * cw; if (x > edge) break;
      const a = pIndex < 1 ? 0.12 + 0.2 * hash(c * 3 + r * 11) : 0.035 + 0.05 * hash(c * 3 + r * 11);
      ctx.fillStyle = `rgba(160,110,255,${a})`; ctx.fillRect(x + 0.5, A.y + r * ch + 0.5, cw - 1, ch - 1);
    }
    if (pIndex < 1) {
      ctx.globalCompositeOperation = 'lighter';
      const g = ctx.createLinearGradient(edge - cw * 4, 0, edge + cw, 0);
      g.addColorStop(0, 'rgba(150,90,255,0)'); g.addColorStop(0.75, 'rgba(170,120,255,0.55)'); g.addColorStop(0.95, 'rgba(255,255,255,0.9)'); g.addColorStop(1, 'rgba(255,255,255,0)');
      ctx.fillStyle = g; ctx.fillRect(edge - cw * 4, A.y, cw * 5, A.h);
      const frame = st.animate ? Math.floor(st.t / 70) : 0;
      for (let r = 0; r < ROWS; r++) if (hash(r * 19 + frame * 7) > 0.72) { ctx.fillStyle = hash(r + frame) > 0.5 ? '#ffe28a' : '#ffffff'; ctx.fillRect(edge - cw * (1 + hash(r * 3 + frame) * 3), A.y + r * ch + ch * 0.3, Math.max(2, cw * 0.4), Math.max(2, ch * 0.4)); }
      ctx.globalCompositeOperation = 'source-over';
    }
  }
  // 2. retrieval: candidates glow in rank order
  const N = progress(st.steps, 'retrieve', st.elapsed) * CANDIDATES.length;
  if (N > 0) {
    ctx.shadowColor = 'rgba(255,209,102,0.9)'; ctx.shadowBlur = 6; ctx.strokeStyle = '#ffd166'; ctx.lineWidth = 1.5;
    ctx.globalAlpha = st.focus && LAYER[st.focus] ? (LAYER[st.focus] === 'candidates' ? 1 : 0.2) : st.markers.length ? 0.35 : 0.9;
    CANDIDATES.forEach((x, i) => { const f = Math.min(Math.max(N - i, 0), 1); if (!f) return; const sz = Math.min(cw, ch) * (0.4 + 0.6 * ease(f)) - 2; ctx.strokeRect(A.x + (x.c + 0.5) * cw - sz / 2, A.y + (x.r + 0.5) * ch - sz / 2, sz, sz); });
    ctx.globalAlpha = 1; ctx.shadowBlur = 0;
  }
  // 3. imagery: inspected chips get a photo frame
  const imagery = st.steps.filter(x => x.tool?.name === 'imagery_window'), last = imagery[imagery.length - 1];
  dim('chips');
  if (imagery.some(x => x.status === 'ok')) { ctx.strokeStyle = 'rgba(255,255,255,0.85)'; ctx.lineWidth = 1; for (const x of CANDIDATES.slice(0, 48)) { ctx.fillStyle = 'rgba(255,255,255,0.12)'; ctx.fillRect(A.x + x.c * cw, A.y + x.r * ch, cw, ch); ctx.strokeRect(A.x + x.c * cw + 0.5, A.y + x.r * ch + 0.5, cw - 1, ch - 1); } }
  ctx.globalAlpha = 1;
  if (st.technical) {   // cell grid with indices every 10 cells
    ctx.strokeStyle = 'rgba(255,255,255,0.10)'; ctx.lineWidth = 1; ctx.beginPath();
    for (let c = 0; c <= COLS; c++) { ctx.moveTo(A.x + c * cw, A.y); ctx.lineTo(A.x + c * cw, A.y + A.h); }
    for (let r = 0; r <= ROWS; r++) { ctx.moveTo(A.x, A.y + r * ch); ctx.lineTo(A.x + A.w, A.y + r * ch); }
    ctx.stroke(); ctx.fillStyle = 'rgba(255,255,255,0.75)'; ctx.font = '600 9px ui-monospace, Menlo, monospace';
    for (let c = 0; c < COLS; c += 10) ctx.fillText(String(c), A.x + c * cw + 2, A.y + 10);
    for (let r = 10; r < ROWS; r += 10) ctx.fillText(String(r), A.x + 2, A.y + r * ch + 10);
  }
  ctx.restore();
  // ... and a reticle glides across the top candidates; a failed call flashes red
  if (last && (last.status === 'running' || (last.status === 'error' && st.elapsed - (last.end_ms ?? 0) < 4000))) {
    const ph = st.animate ? st.t / 420 : 0, i = Math.floor(ph) % 47, f = ease(ph % 1), a = CANDIDATES[i], b = CANDIDATES[i + 1];
    const X = A.x + (a.c + (b.c - a.c) * f + 0.5) * cw, Y = A.y + (a.r + (b.r - a.r) * f + 0.5) * ch, R = Math.max(14, cw * 1.6), L = R * 0.45;
    const bad = last.status === 'error';
    ctx.shadowColor = bad ? 'rgba(255,90,79,0.9)' : 'rgba(255,255,255,0.9)'; ctx.shadowBlur = 10; ctx.strokeStyle = bad ? '#ff5a4f' : '#ffffff'; ctx.lineWidth = 2.5;
    ctx.beginPath();
    for (const [dx, dy] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) { ctx.moveTo(X + dx * R, Y + dy * (R - L)); ctx.lineTo(X + dx * R, Y + dy * R); ctx.lineTo(X + dx * (R - L), Y + dy * R); }
    ctx.moveTo(X - 5, Y); ctx.lineTo(X + 5, Y); ctx.moveTo(X, Y - 5); ctx.lineTo(X, Y + 5); ctx.stroke(); ctx.shadowBlur = 0;
    pill(ctx, X + R + 6, Y - R, bad ? 'TIMEOUT' : 'GSI 0.5 m', bad ? '#ff5a4f' : 'rgba(20,15,28,0.85)', bad ? '#1a0a0a' : '#ffffff');
  }
  // 4. labels from the Strands sub-agent: pins drop in with a ripple
  dim('labels');
  const red = st.colorSafe ? '#d55e00' : '#ff4d5e', Rp = Math.max(6, Math.min(10, cw * 0.55));
  st.markers.forEach((m, i) => {
    const p = at(m.lon, m.lat), age = st.t - (st.born[i] ?? 0);
    const pop = !st.animate || age > 420 ? 1 : age < 260 ? ease(age / 260) * 1.2 : 1.2 - 0.2 * ((age - 260) / 160);
    if (st.animate && age < 900) { ctx.strokeStyle = `rgba(255,255,255,${0.7 * (1 - age / 900)})`; ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(p.x, p.y, 4 + age / 900 * 22, 0, 6.29); ctx.stroke(); }
    const r = Rp * pop;
    ctx.shadowColor = 'rgba(0,0,0,0.45)'; ctx.shadowBlur = 6; ctx.shadowOffsetY = 2;
    if (m.status === 'confirmed') {
      ctx.fillStyle = red; ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.arc(p.x, p.y - r * 1.5, r, Math.PI * 0.78, Math.PI * 2.22); ctx.closePath(); ctx.fill();
      ctx.shadowBlur = 0; ctx.shadowOffsetY = 0; ctx.fillStyle = '#ffffff'; ctx.beginPath(); ctx.arc(p.x, p.y - r * 1.5, r * 0.38, 0, 6.29); ctx.fill();
    } else if (m.status === 'rejected') {
      ctx.fillStyle = night ? '#8d86a0' : '#6b6478'; ctx.beginPath(); ctx.arc(p.x, p.y, r * 0.75, 0, 6.29); ctx.fill(); ctx.shadowBlur = 0; ctx.shadowOffsetY = 0;
      ctx.strokeStyle = '#ffffff'; ctx.lineWidth = 2; const d = r * 0.35; ctx.beginPath(); ctx.moveTo(p.x - d, p.y - d); ctx.lineTo(p.x + d, p.y + d); ctx.moveTo(p.x + d, p.y - d); ctx.lineTo(p.x - d, p.y + d); ctx.stroke();
    } else {
      ctx.shadowBlur = 0; ctx.shadowOffsetY = 0; ctx.strokeStyle = '#ffd166'; ctx.lineWidth = 2.5; ctx.beginPath(); ctx.arc(p.x, p.y, r * 0.8, 0, 6.29); ctx.stroke();
      ctx.fillStyle = '#ffd166'; ctx.font = `700 ${Math.round(r * 1.1)}px system-ui, sans-serif`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText('?', p.x, p.y + 0.5); ctx.textAlign = 'start'; ctx.textBaseline = 'alphabetic';
    }
    ctx.shadowBlur = 0; ctx.shadowOffsetY = 0;
  });
  ctx.globalAlpha = 1;
  // frame of the task area (marching dashes), scale bar
  ctx.shadowColor = 'rgba(255,209,102,0.8)'; ctx.shadowBlur = 8; ctx.strokeStyle = '#ffd166'; ctx.lineWidth = 2; ctx.setLineDash([8, 6]); ctx.lineDashOffset = st.animate ? -st.t / 60 : 0;
  ctx.strokeRect(A.x, A.y, A.w, A.h); ctx.setLineDash([]); ctx.shadowBlur = 0;
  if (st.technical) {
    ctx.fillStyle = '#ffd166'; ctx.font = '600 10px ui-monospace, Menlo, monospace';
    ctx.fillText(`${n.toFixed(3)}°N ${w.toFixed(3)}°E`, A.x, A.y - 6);
    const br = `${s.toFixed(3)}°N ${e.toFixed(3)}°E`; ctx.fillText(br, A.x + A.w - ctx.measureText(br).width, A.y + A.h + 14);
    ctx.fillText(`z${z} · ${COLS}×${ROWS} cells`, A.x + A.w - 120, A.y - 6);
  }
  const kmPx = A.w / ((e - w) * 111.32 * Math.cos((s + n) / 2 * Math.PI / 180));
  if (Number.isFinite(kmPx) && kmPx > 4 && kmPx < A.w / 2) {
    const bx = A.x + A.w - kmPx - 12, by = A.y + A.h - 14;
    ctx.fillStyle = 'rgba(20,15,28,0.8)'; ctx.fillRect(bx - 6, by - 16, kmPx + 12, 24);
    ctx.fillStyle = '#ffffff'; ctx.fillRect(bx, by, kmPx, 3); ctx.fillRect(bx, by - 4, 2, 7); ctx.fillRect(bx + kmPx - 2, by - 4, 2, 7);
    ctx.font = '600 11px system-ui, sans-serif'; ctx.fillText('1 km', bx + kmPx / 2 - 12, by - 4);
  }
}

function pill(ctx: CanvasRenderingContext2D, x: number, y: number, text: string, bg: string, fg: string) {
  ctx.font = '700 11px ui-monospace, Menlo, monospace';
  const w = ctx.measureText(text).width + 12;
  ctx.fillStyle = bg; ctx.beginPath(); ctx.roundRect(x, y, w, 18, 4); ctx.fill();
  ctx.fillStyle = fg; ctx.fillText(text, x + 6, y + 13);
}
