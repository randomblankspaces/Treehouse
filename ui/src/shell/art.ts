/** Pixel art drawn in code. One world, nested scales, one camera:
 *   E (exterior, 1 E = 2 art px) ⊃ house (48 × 28 E) = I (interior, 384 × 224, 1 I = 1/8 E = 1 art px) ⊃ book (1/64 E).
 *  Static art is baked once per mode into bitmaps and drawn with nearest-neighbour scaling (crisp at any zoom);
 *  light (glows, fireflies, fairy lights, beams) and the boy are drawn per frame. */

export type Rect = {x: number; y: number; w: number; h: number};
export type Camera = {cx: number; cy: number; z: number};   // z = CSS px per E unit
export type Mode = 'night' | 'day';
/** Side-view skeleton (facing right), I units. Angles in degrees: 0 points down, 90 forward, 180 up. Index 0 = near limb. */
export type Side = {hx: number; hy: number; torso: number; head: number; thighs: [number, number]; shins: [number, number]; uppers: [number, number]; fores: [number, number]};
export type Boy = {pose: 'side'; side: Side; held: boolean; kick?: boolean} | {pose: 'looking'; x: number};
export type Scene = {mode: Mode; t: number; boy: Boy; twinkle: boolean};

// --- layout ------------------------------------------------------------------------------------
const HOUSE: Rect = {x: 136, y: 92, w: 48, h: 28};
const I_SCALE = 1 / 8;
const iToE = (r: Rect): Rect => ({x: HOUSE.x + r.x * I_SCALE, y: HOUSE.y + r.y * I_SCALE, w: r.w * I_SCALE, h: r.h * I_SCALE});
const BOOK_I: Rect = {x: 184, y: 190, w: 44, h: 24};
const WINDOW_I: Rect = {x: 208, y: 40, w: 128, h: 96};
export const RECTS = {
  scene: {x: 40, y: 8, w: 240, h: 204} as Rect,   // crown to wordmark, room left for the bottom bar
  house: HOUSE,
  room: {x: HOUSE.x - 2, y: HOUSE.y - 2, w: HOUSE.w + 4, h: HOUSE.h + 4} as Rect,
  book: iToE(BOOK_I),
  window: iToE({x: 216, y: 44, w: 112, h: 52}),
  tree: {x: 72, y: 20, w: 176, h: 142} as Rect,   // clickable area on the intro: crown, cabin and trunk
};
export const WINDOW_X = 272;   // I x where he stands to look out
export const POSES: Record<'lying' | 'kneel' | 'stand' | 'crouch' | 'holding', Side> = {
  lying: {hx: 140, hy: 197, torso: 97, head: 150, thighs: [-86, -84], shins: [160, 172], uppers: [20, 10], fores: [80, 75]},
  kneel: {hx: 158, hy: 186, torso: 172, head: 180, thighs: [70, 2], shins: [0, -95], uppers: [15, -10], fores: [40, 10]},
  stand: {hx: 164, hy: 170, torso: 180, head: 182, thighs: [3, -3], shins: [0, 0], uppers: [5, -5], fores: [15, 0]},
  crouch: {hx: 222, hy: 188, torso: 120, head: 135, thighs: [75, 60], shins: [-10, -20], uppers: [40, 30], fores: [10, 15]},
  holding: {hx: 222, hy: 170, torso: 180, head: 182, thighs: [3, -3], shins: [0, 0], uppers: [60, 50], fores: [140, 130]},
};
const mix = (a: number, b: number, t: number) => a + (b - a) * t;
const mix2 = (a: [number, number], b: [number, number], t: number): [number, number] => [mix(a[0], b[0], t), mix(a[1], b[1], t)];
export function lerpSide(a: Side, b: Side, t: number): Side {
  return {hx: mix(a.hx, b.hx, t), hy: mix(a.hy, b.hy, t), torso: mix(a.torso, b.torso, t), head: mix(a.head, b.head, t),
    thighs: mix2(a.thighs, b.thighs, t), shins: mix2(a.shins, b.shins, t), uppers: mix2(a.uppers, b.uppers, t), fores: mix2(a.fores, b.fores, t)};
}
/** A walk cycle on top of a standing pose; `armsFixed` keeps the arms (e.g. holding binoculars). */
export function walkSide(base: Side, x: number, phase: number, armsFixed = false): Side {
  const k = Math.sin(phase), sw = 24 * k;
  return {...base, hx: x, hy: base.hy - Math.abs(k) * 1.5, thighs: [sw, -sw], shins: [sw - 12 * Math.max(0, -k), -sw - 12 * Math.max(0, k)],
    uppers: armsFixed ? base.uppers : [-18 * k, 18 * k], fores: armsFixed ? base.fores : [-10 * k + 10, 10 * k + 10]};
}

// --- colour ------------------------------------------------------------------------------------
const hash = (n: number) => { const x = Math.sin(n * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); };
const h2 = (x: number, y: number) => hash(x * 57.3 + y * 131.7);
function rgb(hex: string) { const n = parseInt(hex.slice(1), 16); return [n >> 16, (n >> 8) & 255, n & 255]; }
/** Night = moonlit: darken and shift blue. Emissive colours (lights) are exempt. */
function shade(hex: string, mode: Mode, k: [number, number, number] = [0.42, 0.42, 0.66]) {
  if (mode === 'day') return hex;
  const [r, g, b] = rgb(hex);
  return `rgb(${Math.round(r * k[0] + 6)},${Math.round(g * k[1] + 4)},${Math.round(b * k[2] + 14)})`;
}
const C = {
  bark: '#6b4329', barkDark: '#3f2617', barkLight: '#8a5a38', wood: '#8c5a33', woodDark: '#61391f', woodLight: '#a8703f', frame: '#3b2414',
  roof: '#e0a83a', roofDark: '#b67a1f', roofDeep: '#8a5a16', roofLight: '#f5c75e',
  leafDeep: '#2d1652', leafDark: '#4a2386', leaf: '#6d34b8', leafLight: '#9161dc', leafHi: '#b994f0', blossom: '#ffd166', berry: '#ff7aa8', green: '#4f9a5c',
  grass: '#3f8a4c', grassDark: '#2c6638', grassLight: '#69b86a', soil: '#3a2a22', hill: '#8fbf96', hillFar: '#b5d7b3',
  vine: '#2f7a55', vineLight: '#4fae78', door: '#f6c945', doorDark: '#c99a1c', cream: '#f4ecdc', ink: '#24182c',
  glass: '#ffd27a', glassHot: '#ffb347', mush: '#7fe8d6', mushDark: '#3fb5a3', stone: '#9a8f86',
};

const ground = (mode: Mode) => mode === 'day' ? '#5a9a52' : shade(C.soil, mode);   // meadow by day, soil by night

// --- baking --------------------------------------------------------------------------------------
type Paint = (x: number, y: number, w: number, h: number, c: string) => void;
function bake(w: number, h: number, draw: (p: Paint) => void) {
  const c = document.createElement('canvas'); c.width = w; c.height = h;
  const ctx = c.getContext('2d')!;
  draw((x, y, ww, hh, col) => { ctx.fillStyle = col; ctx.fillRect(Math.round(x), Math.round(y), Math.max(1, Math.round(ww)), Math.max(1, Math.round(hh))); });
  return c;
}
// Exterior bitmap covers E x ∈ [-160, 480], y ∈ [0, 180] at 2 art px per E.
const EX = {x0: -160, w: 640, h: 180, k: 2};

/** A foliage cluster: lit from the top-left, jagged edge, blossoms and berries. */
function cluster(p: Paint, cx: number, cy: number, r: number, mode: Mode, seed: number) {
  const parts: [number, number, number][] = [[cx, cy, r]];
  for (let i = 0; i < 4; i++) { const a = hash(seed + i) * 6.28; parts.push([cx + Math.cos(a) * r * 0.75, cy + Math.sin(a) * r * 0.6, r * (0.45 + hash(seed + i + 9) * 0.25)]); }
  for (const [x0, y0, rr] of parts) for (let y = Math.floor(y0 - rr - 1); y <= y0 + rr + 1; y++) for (let x = Math.floor(x0 - rr - 1); x <= x0 + rr + 1; x++) {
    const dx = x - x0, dy = y - y0, n = h2(x, y), d = Math.hypot(dx, dy) / rr;
    if (d > 1 + (n - 0.5) * 0.3) continue;
    const lit = (-dx * 0.55 - dy) / rr + (n - 0.5) * 0.35;
    let col = lit > 0.62 ? C.leafHi : lit > 0.18 ? C.leafLight : lit > -0.35 ? C.leaf : lit > -0.75 ? C.leafDark : C.leafDeep;
    if (n > 0.972 && lit > -0.3) col = C.blossom; else if (n < 0.012) col = C.berry; else if (n > 0.955 && lit < -0.2) col = C.green;
    p(x, y, 1, 1, shade(col, mode));
  }
}
/** A tapering limb along a polyline, with a dark underside and a lit top edge. */
function limb(p: Paint, pts: [number, number][], w0: number, w1: number, mode: Mode) {
  const total = pts.slice(1).reduce((s, q, i) => s + Math.hypot(q[0] - pts[i][0], q[1] - pts[i][1]), 0);
  let run = 0;
  for (let i = 1; i < pts.length; i++) {
    const [ax, ay] = pts[i - 1], [bx, by] = pts[i], len = Math.hypot(bx - ax, by - ay);
    for (let s = 0; s <= len; s += 0.5) {
      const x = ax + (bx - ax) * s / len, y = ay + (by - ay) * s / len, w = w0 + (w1 - w0) * (run + s) / total;
      p(x - w / 2, y - w / 2 + 0.5, w, w, shade(C.barkDark, mode));
      p(x - w / 2, y - w / 2, w, w * 0.75, shade(h2(Math.round(x * 2), Math.round(y * 2)) > 0.85 ? C.barkDark : C.bark, mode));
      if (w > 2) p(x - w / 2 + 0.5, y - w / 2, Math.max(0.5, w * 0.35), 0.5, shade(C.barkLight, mode));
    }
    run += len;
  }
}

function exteriorLayers(mode: Mode) {
  const X = (e: number) => (e - EX.x0) * EX.k, Y = (e: number) => e * EX.k;   // E → bitmap px
  const LIMBS: [[number, number][], number, number][] = [
    [[[154, 125], [130, 116], [107, 107], [88, 104], [75, 106]], 5, 1.5],
    [[[167, 126], [194, 118], [218, 111], [237, 107], [250, 109]], 5.5, 1.5],
    [[[150, 85], [131, 70], [113, 60], [98, 56]], 4, 1.5],
    [[[171, 84], [190, 69], [209, 59], [224, 55]], 4, 1.5],
    [[[160, 70], [158, 50], [161, 35], [159, 26]], 3.5, 1.5],
    [[[120, 112], [116, 98], [110, 88]], 2, 1], [[[203, 115], [208, 101], [214, 92]], 2, 1], [[[123, 64], [116, 48]], 1.5, 1], [[[199, 64], [206, 48]], 1.5, 1],
  ];
  // crown: clusters along limbs + an envelope, skipping the cabin (front clusters drawn later)
  const crown: [number, number, number][] = [];
  LIMBS.forEach(([pts], li) => pts.slice(1).forEach(([x, y], i) => crown.push([x + (hash(li * 9 + i) - 0.5) * 8, y - 3 - hash(li + i * 3) * 6, 7 + hash(li * 5 + i) * 5])));
  for (let i = 0; i < 46; i++) { const a = hash(i + 500) * 6.28, d = Math.sqrt(hash(i + 900)); crown.push([160 + Math.cos(a) * 92 * d, 70 + Math.sin(a) * 44 * d, 7 + hash(i + 77) * 6]); }
  const inCabin = (x: number, y: number) => x > 128 && x < 192 && y > 58 && y < 126;
  const P0 = (p: Paint): Paint => (x, y, w, h, c) => p(X(x), Y(y), w * EX.k, h * EX.k, c);
  const back = bake(EX.w * EX.k, EX.h * EX.k, p => {
    const P = P0(p);
    // hills
    for (let x = -160; x < 480; x += 0.5) {
      const far = 134 + 7 * Math.sin(x / 23) + 4 * Math.sin(x / 9 + 2), near = 145 + 6 * Math.sin(x / 31 + 1) + 3 * Math.sin(x / 11);
      P(x, far, 0.5, 160 - far, shade(C.hillFar, mode, [0.3, 0.32, 0.55])); P(x, near, 0.5, 160 - near, shade(C.hill, mode, [0.28, 0.3, 0.5]));
    }
    // ground: soil, grass edge, tufts and flowers
    P(-160, 160, 640, 20, ground(mode));
    for (let x = -160; x < 480; x += 0.5) {
      const g = 1 + Math.round(h2(x * 2, 1) * 2) * 0.5;
      P(x, 160 - g, 0.5, g + 1.5, shade(h2(x * 2, 3) > 0.5 ? C.grass : C.grassDark, mode));
      if (h2(x * 2, 5) > 0.93) P(x, 158 - g, 0.5, 0.5, shade(C.grassLight, mode));
      if (h2(x * 2, 7) > 0.985) P(x, 157.5 - g, 0.5, 0.5, shade(h2(x, 9) > 0.5 ? C.blossom : C.berry, mode));
    }
    for (let i = 0; i < 70; i++) P(70 + hash(i + 40) * 180, 160 + hash(i + 41) * 6, 0.5, 0.5, shade(C.leafLight, mode));   // fallen petals
    crown.forEach(([x, y, r], i) => { if (!inCabin(x, y)) cluster(p, X(x), Y(y), r * EX.k, mode, i); });
    // trunk with roots and bark grain
    for (let y = 108; y < 161; y += 0.5) {
      const t = (y - 108) / 52, hw = 7 + t * 4 + Math.max(0, y - 150) * 1.4;
      for (let x = 160 - hw; x < 160 + hw; x += 0.5) {
        const u = (x - (160 - hw)) / (2 * hw), n = h2(Math.round(x * 2), Math.round(y * 2));
        P(x, y, 0.5, 0.5, shade(u < 0.22 ? C.barkDark : u > 0.78 ? C.barkLight : (Math.sin(x * 3.1 + y * 0.4) > 0.75 || n > 0.93) ? C.barkDark : C.bark, mode));
      }
    }
    for (const [x, d] of [[146, -1], [174, 1], [152, -0.5]]) for (let s = 0; s < 12; s += 0.5) P(x + d * s, 158 + s * 0.15, 2.5, 1.5, shade(C.barkDark, mode));
    LIMBS.forEach(([pts, a, b]) => limb(P, pts, a, b, mode));
    for (const [x, y] of [[166, 136], [168, 141], [151, 146]]) { P(x, y, 5, 1, shade('#ff9ec4', mode)); P(x + 0.5, y + 1, 4, 0.5, shade('#d9709a', mode)); }
    // platform, braces, ladder with yellow rungs
    P(126, 120, 68, 3, shade(C.woodDark, mode)); P(126, 120, 68, 1, shade(C.woodLight, mode));
    for (let x = 127; x < 193; x += 6) P(x, 121, 0.5, 2, shade(C.frame, mode));
    for (let s = 0; s < 14; s++) { P(140 + s * 1.1, 123 + s, 1.5, 1.5, shade(C.woodDark, mode)); P(180 - s * 1.1, 123 + s, 1.5, 1.5, shade(C.woodDark, mode)); }
    P(142, 123, 1.5, 37, shade(C.woodDark, mode)); P(150, 123, 1.5, 37, shade(C.woodDark, mode));
    for (let y = 127; y < 160; y += 5) { P(143.5, y, 6.5, 1.5, shade(C.door, mode)); P(143.5, y + 1, 6.5, 0.5, shade(C.doorDark, mode)); }
    // vines from the platform
    for (let i = 0; i < 9; i++) { const x = 128 + hash(i + 70) * 62, len = 6 + hash(i + 71) * 18; for (let s = 0; s < len; s += 0.5) P(x + Math.sin(s / 3 + i) * 0.8, 123 + s, 0.5, 0.5, shade(C.vine, mode)); for (let s = 3; s < len; s += 4) P(x + Math.sin(s / 3 + i) * 0.8 - 0.5, 123 + s, 1, 1, shade(C.vineLight, mode)); }
    // roof: steep and shingled, with a chimney and finial
    P(171, 64, 6, 18, shade(C.stone, mode)); P(170, 63, 8, 2, shade('#6f655d', mode));
    for (let y = 60; y < 93; y += 0.5) {
      const hw = (y - 60) * 1.05 + 1.5, row = Math.floor((y - 60) / 2.5);
      for (let x = 160 - hw; x < 160 + hw; x += 0.5) {
        const shg = Math.floor((x + (row % 2) * 1.5) / 3), edge = (y - 60) % 2.5 < 0.5;
        P(x, y, 0.5, 0.5, shade(edge ? C.roofDeep : h2(shg, row) > 0.7 ? C.roofLight : h2(shg, row) < 0.25 ? C.roofDark : C.roof, mode));
      }
    }
    P(158.5, 55, 3, 5, shade(C.woodDark, mode)); P(159, 53, 2, 2, shade(C.door, mode));
    for (let x = 122; x < 199; x += 0.5) P(x, 92, 0.5, 1, shade(C.roofDeep, mode));
  });
  const facade = bake(EX.w * EX.k, EX.h * EX.k, p => {
    const P = P0(p);
    for (let y = HOUSE.y; y < HOUSE.y + HOUSE.h; y += 2.5) { P(HOUSE.x, y, HOUSE.w, 2.5, shade(h2(y, 1) > 0.5 ? C.wood : C.woodLight, mode)); P(HOUSE.x, y + 2, HOUSE.w, 0.5, shade(C.woodDark, mode)); }
    P(HOUSE.x, HOUSE.y, 1.5, HOUSE.h, shade(C.frame, mode)); P(HOUSE.x + HOUSE.w - 1.5, HOUSE.y, 1.5, HOUSE.h, shade(C.frame, mode));
    P(161, 96, 18, 14, shade(C.frame, mode)); P(162, 97, 16, 12, mode === 'night' ? C.glass : '#9fd3f5');
    if (mode === 'night') P(162, 103, 16, 6, C.glassHot);
    P(169.5, 97, 1, 12, shade(C.frame, mode)); P(162, 102.5, 16, 1, shade(C.frame, mode)); P(160, 109, 20, 1.5, shade(C.woodDark, mode));
    P(141, 103, 11, 17, shade(C.frame, mode)); P(142, 104, 9, 16, shade(C.door, mode)); P(142, 104, 1, 16, shade(C.doorDark, mode));
    P(145, 107, 3, 3, mode === 'night' ? C.glass : '#9fd3f5'); P(149.5, 112, 1, 1, shade(C.frame, mode));
    P(154, 102, 0.5, 3, shade(C.frame, mode)); P(153, 105, 2.5, 3.5, shade(C.frame, mode)); P(153.5, 105.5, 1.5, 2.5, mode === 'night' ? C.glass : '#e8d9a8');
  });
  const front = bake(EX.w * EX.k, EX.h * EX.k, p => {
    crown.forEach(([x, y, r], i) => { if (inCabin(x, y) && (x < 140 || x > 182)) cluster(p, X(x), Y(y), r * 0.8 * EX.k, mode, i + 300); });
    const P = P0(p);
    for (const [x, s] of [[147, 1], [174, 1.4], [178, 0.9]]) { P(x, 157 - 2 * s, 3 * s, 1.5 * s, mode === 'night' ? C.mush : shade(C.mush, mode)); P(x + s, 158.5 - 0.5 * s, s, 2 * s, shade(C.cream, mode)); }
  });
  return {back, facade, front};
}

function interiorLayer(mode: Mode) {
  const k: [number, number, number] = [0.62, 0.55, 0.78];
  const S = (c: string) => shade(c, mode, k);
  return bake(384, 224, P => {
    for (let x = 0; x < 384; x += 16) { P(x, 0, 16, 176, S(h2(x, 2) > 0.5 ? '#b07a4c' : '#a06c40')); P(x, 0, 1, 176, S('#7a4a2a')); for (let y = 10 + hash(x) * 40; y < 176; y += 50) P(x + 7, y, 2, 2, S('#7a4a2a')); }
    P(0, 0, 384, 6, S('#6b4024'));
    for (let y = 176; y < 224; y += 8) { P(0, y, 384, 8, S(h2(1, y) > 0.5 ? '#7a4a2a' : '#6b4024')); P(0, y, 384, 1, S('#4f2f19')); }
    // the inside of the yellow door
    P(46, 94, 76, 82, S('#3b2414')); P(50, 98, 68, 78, S('#f6c945')); P(50, 98, 4, 78, S('#c99a1c')); P(102, 136, 6, 6, S('#3b2414'));
    // window with the sky outside
    P(WINDOW_I.x - 6, WINDOW_I.y - 6, WINDOW_I.w + 12, WINDOW_I.h + 12, S('#3b2414'));
    for (let y = 0; y < WINDOW_I.h; y += 2) { const t = y / WINDOW_I.h; P(WINDOW_I.x, WINDOW_I.y + y, WINDOW_I.w, 2, mode === 'night' ? `rgb(${Math.round(20 + t * 30)},${Math.round(16 + t * 24)},${Math.round(54 + t * 40)})` : `rgb(${Math.round(150 + t * 60)},${Math.round(205 + t * 30)},250)`); }
    if (mode === 'night') { for (let i = 0; i < 14; i++) P(WINDOW_I.x + 4 + hash(i + 300) * 118, WINDOW_I.y + 4 + hash(i + 400) * 86, 2, 2, '#fff6d8'); for (let y = -10; y <= 10; y++) { const hw = Math.sqrt(100 - y * y); P(300 - hw, 62 + y, hw * 2, 1, '#f6e7b0'); } }
    else { P(226, 60, 34, 8, '#ffffff'); P(232, 54, 20, 6, '#ffffff'); P(286, 96, 30, 6, '#ffffff'); }
    P(WINDOW_I.x + 62, WINDOW_I.y, 4, WINDOW_I.h, S('#3b2414')); P(WINDOW_I.x, WINDOW_I.y + 46, WINDOW_I.w, 4, S('#3b2414'));
    P(WINDOW_I.x - 10, WINDOW_I.y + WINDOW_I.h + 6, WINDOW_I.w + 20, 5, S('#6b4024'));
    for (let i = 0; i < 6; i++) P(WINDOW_I.x - 4 + i * 4, WINDOW_I.y + WINDOW_I.h + 1 - (i % 2) * 2, 4, 5, S('#4f9a5c'));
    // shelf with books and a globe
    P(140, 70, 60, 4, S('#4f2f19'));
    ([['#6d34b8', 22], ['#f6c945', 26], ['#ff7aa8', 20], ['#4f9a5c', 24], ['#f4ecdc', 22], ['#9161dc', 26]] as [string, number][]).forEach(([c, hh], i) => { P(142 + i * 6, 70 - hh, 5, hh, S(c)); P(142 + i * 6, 70 - hh + 4, 5, 1, S('#24182c')); });
    for (let y = -7; y <= 7; y++) { const hw = Math.sqrt(49 - y * y); P(186 - hw, 58 + y, hw * 2, 1, S(y < -2 ? '#5aa0e0' : y > 3 ? '#4f9a5c' : '#7cc0e8')); }
    P(185, 65, 2, 5, S('#4f2f19'));
    // wall map with red pins (a hint of what is coming)
    P(150, 96, 44, 32, S('#3b2414')); P(152, 98, 40, 28, S('#e9e2d1')); P(152, 116, 40, 10, S('#7cc0e8'));
    for (const [x, y] of [[160, 104], [172, 108], [182, 102], [166, 112]]) { P(x, y, 3, 3, S('#ff4d4d')); P(x + 1, y + 3, 1, 2, S('#24182c')); }
    P(270, 0, 2, 20, S('#24182c')); P(262, 20, 18, 7, S('#3b2414'));
    // rug in brand stripes, cushions, books, a plant
    for (let i = 0; i < 7; i++) { const inset = i === 0 || i === 6 ? 8 : 0; P(36 + inset, 190 + i * 4, 264 - inset * 2, 4, S(i % 2 ? '#f6c945' : '#6d34b8')); }
    for (let x = 36; x < 300; x += 6) { P(x, 186, 2, 4, S('#f4ecdc')); P(x, 218, 2, 4, S('#f4ecdc')); }
    P(318, 196, 34, 6, S('#6d34b8')); P(322, 190, 28, 6, S('#f6c945')); P(320, 184, 30, 6, S('#f4ecdc')); P(320, 184, 30, 1, S('#24182c'));
    P(6, 200, 26, 7, S('#ff7aa8')); P(8, 206, 24, 6, S('#4f9a5c'));
    P(342, 150, 20, 26, S('#c46a3a')); P(340, 150, 24, 4, S('#a3532a'));
    for (let i = 0; i < 11; i++) P(334 + hash(i) * 32, 112 + hash(i + 5) * 36, 9, 6, S(i % 3 ? '#4f9a5c' : '#69b86a'));
  });
}

const cache = new Map<string, unknown>();
function memo<T>(key: string, make: () => T): T { if (!cache.has(key)) cache.set(key, make()); return cache.get(key) as T; }

// --- the boy: a small rig rasterised into a grid each frame ------------------------------------
const BOY_PAL = ['', '#24182c', '#f0b48a', '#d08e66', '#4a2a1c', '#6b4329', '#f6c945', '#d9a521', '#5a35a0', '#3f2478', '#f4ecdc', '#ff8fa8', '#24182c'];
const OUT = 1, SKIN = 2, SKIN_D = 3, HAIR = 4, HAIR_L = 5, SHIRT = 6, SHIRT_D = 7, PANTS = 8, PANTS_D = 9, SOCK = 10, BLUSH = 11, EYE = 12;
function drawBoy(I: Paint, boy: Boy, t: number, animate: boolean) {
  const W = 220, H = 150, ox = Math.round(boy.pose === 'side' ? boy.side.hx : boy.x) - 110, oy = 80, g = new Uint8Array(W * H);
  const set = (x: number, y: number, c: number) => { x = Math.round(x - ox); y = Math.round(y - oy); if (x >= 0 && y >= 0 && x < W && y < H) g[y * W + x] = c; };
  const disc = (cx: number, cy: number, r: number, c: number) => { for (let y = -Math.ceil(r); y <= r; y++) for (let x = -Math.ceil(r); x <= r; x++) if (x * x + y * y <= r * r + r * 0.6) set(cx + x, cy + y, c); };
  const seg = (x1: number, y1: number, x2: number, y2: number, w: number, c: number) => { const n = Math.max(1, Math.ceil(Math.hypot(x2 - x1, y2 - y1))); for (let i = 0; i <= n; i++) disc(x1 + (x2 - x1) * i / n, y1 + (y2 - y1) * i / n, w / 2, c); };
  type Part = {k: 's' | 'd' | 'p'; a: number[]; w: number; c: number};
  const parts: Part[] = [];
  const S = (x1: number, y1: number, x2: number, y2: number, w: number, c: number) => parts.push({k: 's', a: [x1, y1, x2, y2], w, c});
  const D = (x: number, y: number, r: number, c: number) => parts.push({k: 'd', a: [x, y], w: r, c});
  const R = (x: number, y: number, w: number, h: number, c: number) => parts.push({k: 'p', a: [x, y, w, h], w: 0, c});
  if (boy.pose === 'side') {
    const b = boy.side, kick = boy.kick && animate ? [Math.sin(t / 380) * 8, Math.sin(t / 380 + 2.2) * 7] : [0, 0];
    const dir = (deg: number, len: number) => [Math.sin(deg * Math.PI / 180) * len, Math.cos(deg * Math.PI / 180) * len];
    const [tx, ty] = dir(b.torso, 30), [sx2, sy2] = dir(b.torso, 26), nx = b.hx + tx, ny = b.hy + ty, shx = b.hx + sx2, shy = b.hy + sy2;
    const [hdx, hdy] = dir(b.head, 13), hx = nx + hdx, hy = ny + hdy;
    const arm = (i: 0 | 1, sleeve: number) => { const [ux, uy] = dir(b.uppers[i], 13), ex = shx + ux, ey = shy + uy, [fx, fy] = dir(b.fores[i], 13); S(shx, shy, ex, ey, 7, sleeve); S(ex, ey, ex + fx, ey + fy, 6, SKIN); D(ex + fx, ey + fy, 3.5, SKIN); return [ex + fx, ey + fy]; };
    const leg = (i: 0 | 1, col: number) => { const [kx, ky] = dir(b.thighs[i], 18), knx = b.hx + kx, kny = b.hy + ky, [fx, fy] = dir(b.shins[i] + kick[i], 18); S(b.hx, b.hy, knx, kny, 11, col); S(knx, kny, knx + fx, kny + fy, 10, col); D(knx + fx, kny + fy, 4.5, SOCK); };
    arm(1, SHIRT_D); leg(1, PANTS_D); leg(0, PANTS);
    S(b.hx, b.hy, nx, ny, 19, SHIRT); S(b.hx + 2, b.hy + 3, b.hx + tx * 0.7 + 2, b.hy + ty * 0.7 + 3, 6, SHIRT_D);
    D(hx, hy, 13, HAIR); D(hx + 4, hy + 3, 10, SKIN); D(hx - 5, hy - 6, 6, HAIR_L);
    R(hx + 8, hy - 1, 2, 4, EYE); R(hx + 7, hy + 6, 4, 2, BLUSH); R(hx + 14, hy + 2, 2, 2, SKIN); R(hx - 3, hy + 3, 3, 4, SKIN_D);
    const [px, py] = arm(0, SHIRT);
    if (boy.held) { D(px + 2, py - 3, 4, OUT); D(px + 9, py - 3, 4, OUT); R(px, py - 7, 4, 2, SHIRT); R(px + 7, py - 7, 4, 2, SHIRT); }
  } else {
    const fy = 206, cx = boy.x, top = fy;
    S(cx - 6, top - 34, cx - 6, fy - 4, 10, PANTS_D); S(cx + 6, top - 34, cx + 6, fy - 4, 10, PANTS);
    D(cx - 6, fy - 2, 4.5, OUT); D(cx + 6, fy - 2, 4.5, OUT);
    S(cx, top - 62, cx, top - 32, 26, SHIRT); S(cx - 9, top - 36, cx + 9, top - 36, 6, SHIRT_D);
    S(cx - 12, top - 58, cx - 20, top - 70, 7, SHIRT); S(cx - 20, top - 70, cx - 9, top - 80, 6, SKIN);
    S(cx + 12, top - 58, cx + 20, top - 70, 7, SHIRT); S(cx + 20, top - 70, cx + 9, top - 80, 6, SKIN);
    D(cx - 8, top - 82, 4, OUT); D(cx + 8, top - 82, 4, OUT); R(cx - 10, top - 86, 4, 2, SHIRT); R(cx + 6, top - 86, 4, 2, SHIRT);
    D(cx - 12, top - 74, 3, SKIN); D(cx + 12, top - 74, 3, SKIN); D(cx, top - 76, 12, HAIR); D(cx - 4, top - 81, 5, HAIR_L);
  }
  // outline pass, then fills: one clean silhouette
  for (const p of parts) { if (p.k === 's') seg(p.a[0], p.a[1], p.a[2], p.a[3], p.w + 3, OUT); else if (p.k === 'd') disc(p.a[0], p.a[1], p.w + 1.5, OUT); }
  for (const p of parts) { if (p.k === 's') seg(p.a[0], p.a[1], p.a[2], p.a[3], p.w, p.c); else if (p.k === 'd') disc(p.a[0], p.a[1], p.w, p.c); else for (let y = 0; y < p.a[3]; y++) for (let x = 0; x < p.a[2]; x++) set(p.a[0] + x, p.a[1] + y, p.c); }
  for (let y = 0; y < H; y++) { let x = 0; while (x < W) { const c = g[y * W + x]; let e = x + 1; while (e < W && g[y * W + e] === c) e++; if (c) I(ox + x, oy + y, e - x, 1, BOY_PAL[c]); x = e; } }
}

// --- camera ------------------------------------------------------------------------------------
export function fit(r: Rect, W: number, H: number, margin = 0.92, cover = false): Camera {
  const zx = W / r.w, zy = H / r.h;
  return {cx: r.x + r.w / 2, cy: r.y + r.h / 2, z: (cover ? Math.max(zx, zy) : Math.min(zx, zy)) * margin};
}
/** Zoom in log space; move the centre so the target point glides in (no swing past it). */
export function lerpCam(a: Camera, b: Camera, t: number): Camera {
  const z = Math.exp(Math.log(a.z) + (Math.log(b.z) - Math.log(a.z)) * t);
  const k = Math.abs(1 / b.z - 1 / a.z) < 1e-9 ? t : (1 / z - 1 / a.z) / (1 / b.z - 1 / a.z);
  return {cx: a.cx + (b.cx - a.cx) * k, cy: a.cy + (b.cy - a.cy) * k, z};
}
export const ease = (t: number) => t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2;
export function toScreen(cam: Camera, r: Rect, W: number, H: number) {
  return {x: (r.x - cam.cx) * cam.z + W / 2, y: (r.y - cam.cy) * cam.z + H / 2, w: r.w * cam.z, h: r.h * cam.z};
}

// --- renderer ----------------------------------------------------------------------------------
const STARS = Array.from({length: 110}, (_, i) => ({x: -150 + hash(i) * 620, y: hash(i + 99) * 135, p: hash(i + 7) * 6.28, big: hash(i + 3) > 0.9}));
const FLIES = Array.from({length: 26}, (_, i) => ({x: 70 + hash(i + 11) * 180, y: 40 + hash(i + 12) * 115, p: hash(i + 13) * 6.28, s: 0.6 + hash(i + 14)}));
const PETALS = Array.from({length: 34}, (_, i) => ({x: hash(i + 21) * 320, p: hash(i + 22), s: 0.5 + hash(i + 23)}));
const BULBS: [string, string][] = [['#ffd166', 'rgba(255,210,100,A)'], ['#ff7aa8', 'rgba(255,120,170,A)'], ['#7fe8d6', 'rgba(120,230,210,A)'], ['#b994f0', 'rgba(185,148,240,A)']];

export function render(ctx: CanvasRenderingContext2D, W: number, H: number, cam: Camera, s: Scene) {
  const night = s.mode === 'night', T = s.twinkle ? s.t : 0;
  const sx = (x: number) => (x - cam.cx) * cam.z + W / 2, sy = (y: number) => (y - cam.cy) * cam.z + H / 2;
  const box = (x: number, y: number, w: number, h: number, c: string) => {
    const x0 = Math.round(sx(x)), x1 = Math.round(sx(x + w)), y0 = Math.round(sy(y)), y1 = Math.round(sy(y + h));
    if (x1 <= 0 || y1 <= 0 || x0 >= W || y0 >= H) return;
    ctx.fillStyle = c; ctx.fillRect(x0, y0, Math.max(1, x1 - x0), Math.max(1, y1 - y0));
  };
  const glow = (x: number, y: number, r: number, color: string, a: number) => {
    const X = sx(x), Y = sy(y), R = r * cam.z;
    if (a <= 0 || X + R < 0 || Y + R < 0 || X - R > W || Y - R > H) return;
    const g = ctx.createRadialGradient(X, Y, 0, X, Y, R); g.addColorStop(0, color.replace('A', String(a))); g.addColorStop(1, color.replace('A', '0'));
    ctx.fillStyle = g; ctx.fillRect(X - R, Y - R, R * 2, R * 2);
  };
  const blit = (img: HTMLCanvasElement, r: Rect) => { const q = toScreen(cam, r, W, H); ctx.drawImage(img, q.x, q.y, q.w, q.h); };
  ctx.imageSmoothingEnabled = false;
  const h = toScreen(cam, HOUSE, W, H);
  const inside = h.x <= 0 && h.y <= 0 && h.x + h.w >= W && h.y + h.h >= H;
  const houseZ = Math.min(W / HOUSE.w, H / HOUSE.h);
  const facade = Math.min(Math.max((Math.log(houseZ * 0.75) - Math.log(cam.z)) / (Math.log(houseZ * 0.75) - Math.log(houseZ * 0.3)), 0), 1);
  const ext = memo(`ext-${s.mode}`, () => exteriorLayers(s.mode));
  const EXR: Rect = {x: EX.x0, y: 0, w: EX.w, h: EX.h};

  if (!inside) {
    const g = ctx.createLinearGradient(0, sy(0), 0, sy(160));
    if (night) { g.addColorStop(0, '#070514'); g.addColorStop(0.55, '#1a1238'); g.addColorStop(1, '#3a2560'); } else { g.addColorStop(0, '#5ab4f2'); g.addColorStop(0.6, '#9ad6fb'); g.addColorStop(1, '#fde9c2'); }
    ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
    ctx.globalCompositeOperation = 'lighter';
    if (night) {
      for (const st of STARS) { ctx.globalAlpha = 0.45 + 0.55 * (s.twinkle ? (Math.sin(T / 500 + st.p * 3) + 1) / 2 : 0.8); box(st.x, st.y, 0.5, 0.5, '#fff6d8'); if (st.big) { box(st.x - 1, st.y, 2.5, 0.5, '#bfb4ff'); box(st.x, st.y - 1, 0.5, 2.5, '#bfb4ff'); } }
      ctx.globalAlpha = 1;
      glow(262, 34, 40, 'rgba(255,236,170,A)', 0.28);
    } else glow(262, 34, 55, 'rgba(255,240,180,A)', 0.55);
    ctx.globalCompositeOperation = 'source-over';
    for (let y = -11; y <= 11; y += 0.5) { const hw = Math.sqrt(Math.max(0, 121 - y * y)); box(262 - hw, 34 + y, hw * 2, 0.5, night ? '#f6e7b0' : '#fff2a8'); }
    if (night) { for (const [x, y, r] of [[258, 30, 2.5], [266, 38, 1.8], [264, 28, 1.2]]) box(x - r / 2, y - r / 2, r, r, '#d9c78e'); }
    else { const d = (T / 300) % 420; for (const [cx, cy, w] of [[40, 30, 26], [180, 46, 34], [300, 24, 22]]) { const x = ((cx + d) % 420) - 60; box(x, cy, w, 4, '#ffffff'); box(x + w * 0.2, cy - 3, w * 0.5, 3, '#ffffff'); box(x + w * 0.5, cy - 5, w * 0.3, 2, '#ffffff'); box(x, cy + 3.5, w, 1, '#dbeefe'); } }
    ctx.fillStyle = ground(s.mode); ctx.fillRect(0, Math.round(sy(170)), W, H);   // ground runs to the bottom edge
    blit(ext.back, EXR);
  }

  // interior, clipped to the cabin
  ctx.save(); ctx.beginPath(); ctx.rect(Math.round(h.x), Math.round(h.y), Math.round(h.w), Math.round(h.h)); ctx.clip();
  blit(memo(`int-${s.mode}`, () => interiorLayer(s.mode)), HOUSE);
  const I: Paint = (x, y, w, hh, c) => box(HOUSE.x + x * I_SCALE, HOUSE.y + y * I_SCALE, w * I_SCALE, hh * I_SCALE, c);
  const iglow = (x: number, y: number, r: number, c: string, a: number) => glow(HOUSE.x + x * I_SCALE, HOUSE.y + y * I_SCALE, r * I_SCALE, c, a);
  {
    const B = (x: number, y: number, w: number, hh: number, c: string) => I(BOOK_I.x + x / 8, BOOK_I.y + y / 8, w / 8, hh / 8, c);
    B(0, 0, 352, 192, '#8a5a16'); B(6, 4, 340, 182, '#e0a83a'); B(16, 12, 156, 166, '#f7f0dc'); B(180, 12, 156, 166, '#f7f0dc'); B(172, 8, 8, 176, '#b67a1f');
    for (let y = 28; y < 166; y += 12) { B(28, y, 120 - hash(y) * 40, 3, '#cfc4a8'); B(192, y, 120 - hash(y + 5) * 40, 3, '#cfc4a8'); }
    if (s.boy.pose === 'side' && !s.boy.held) { I(240, 200, 9, 9, '#24182c'); I(251, 200, 9, 9, '#24182c'); I(248, 203, 4, 3, '#24182c'); I(241, 199, 7, 2, '#f6c945'); I(252, 199, 7, 2, '#f6c945'); }
  }
  drawBoy(I, s.boy, T, s.twinkle);
  ctx.globalCompositeOperation = 'lighter';
  iglow(271, 30, 150, night ? 'rgba(255,190,100,A)' : 'rgba(255,230,170,A)', night ? 0.32 : 0.12);
  I(264, 27, 14, 4, '#ffe9a8');
  const beam = night ? 'rgb(170,190,255)' : 'rgb(255,240,190)';
  for (let i = 0; i < 10; i++) { ctx.globalAlpha = (night ? 0.05 : 0.07) * (1 - i / 10); I(WINDOW_I.x - i * 6, WINDOW_I.y + 10 + i * 13, WINDOW_I.w, 13, beam); }
  ctx.globalAlpha = 1;
  if (cam.z < houseZ * 3) for (let i = 0; i < 18; i++) { const x = WINDOW_I.x - 30 + hash(i + 50) * 150 + Math.sin(T / 1300 + i) * 6, y = WINDOW_I.y + 30 + ((hash(i + 60) * 140 + T / 90 * (0.3 + hash(i) * 0.4)) % 140); I(x, y, 1, 1, night ? 'rgba(200,210,255,0.55)' : 'rgba(255,250,220,0.8)'); }
  for (let i = 0; i <= 16; i++) { const x = i * 24, y = 12 + Math.sin(i / 16 * Math.PI) * 14, [c, gc] = BULBS[i % 4], on = s.twinkle ? 0.6 + 0.4 * Math.sin(T / 400 + i) : 1; I(x - 1, y, 3, 4, c); iglow(x, y + 2, 14, gc, (night ? 0.5 : 0.18) * on); }
  ctx.globalCompositeOperation = 'source-over';
  ctx.restore();

  if (!inside) {
    if (facade > 0) { ctx.globalAlpha = facade; blit(ext.facade, EXR); blit(ext.front, EXR); ctx.globalAlpha = 1; }
    for (let i = 0; i < 5; i++) { const k = ((T / 2600 + i / 5) % 1), r = 1.5 + k * 3.5; ctx.globalAlpha = (1 - k) * (night ? 0.35 : 0.6); box(174 - r / 2 + Math.sin(k * 6 + i) * 3, 60 - k * 34 - r / 2, r, r, night ? '#8a82a8' : '#ffffff'); }
    ctx.globalAlpha = 1;
    ctx.globalCompositeOperation = 'lighter';
    for (let i = 0; i <= 12; i++) { const x = 124 + i * 6, y = 93 + Math.sin(i / 12 * Math.PI) * 3, [c, gc] = BULBS[i % 4], on = s.twinkle ? 0.6 + 0.4 * Math.sin(T / 350 + i * 1.7) : 1; box(x, y, 1, 1, c); if (night) glow(x + 0.5, y + 0.5, 4, gc, 0.55 * on); }
    if (night) {
      const flick = s.twinkle ? 0.9 + 0.1 * Math.sin(T / 90) * Math.sin(T / 37) : 1;
      glow(170, 103, 26, 'rgba(255,180,80,A)', 0.4 * flick * Math.max(facade, 0.3)); glow(146.5, 108.5, 10, 'rgba(255,190,90,A)', 0.4 * flick); glow(154.2, 107, 9, 'rgba(255,200,100,A)', 0.6 * flick);
      for (const [x, y] of [[148.5, 155], [176, 154], [179, 156]]) glow(x, y, 7, 'rgba(120,240,220,A)', 0.4);
      for (const f of FLIES) { const x = f.x + Math.sin(T / (1700 * f.s) + f.p) * 9, y = f.y + Math.cos(T / (2300 * f.s) + f.p * 2) * 6, a = s.twinkle ? 0.4 + 0.6 * Math.max(0, Math.sin(T / (600 * f.s) + f.p)) : 0.8; box(x, y, 0.6, 0.6, '#fff3b0'); glow(x + 0.3, y + 0.3, 5, 'rgba(255,200,80,A)', 0.45 * a); }
    }
    ctx.globalCompositeOperation = 'source-over';
    if (!night) for (const p of PETALS) { const y = ((p.p * 180 + T / 70 * p.s) % 190) - 10, x = (p.x + Math.sin(T / 900 + p.p * 9) * 10 + T / 160) % 330 - 5; box(x, y, 0.7, 0.5, '#b994f0'); }
    // wordmark on the ground
    const word = 'treehouse', k = 1.6, x0 = 160 - (word.length * 5 - 1) * k / 2;
    [...word].forEach((ch, i) => GLYPHS[ch].forEach((row, r) => [...row].forEach((v, c) => { if (v === '#') { box(x0 + (i * 5 + c) * k + 0.4, 166 + r * k + 0.4, k, k, '#120c18'); box(x0 + (i * 5 + c) * k, 166 + r * k, k, k, '#f4ecdc'); } })));
    if (night) { const v = ctx.createRadialGradient(W / 2, H / 2, Math.min(W, H) * 0.35, W / 2, H / 2, Math.max(W, H) * 0.75); v.addColorStop(0, 'rgba(5,3,15,0)'); v.addColorStop(1, 'rgba(5,3,15,0.55)'); ctx.fillStyle = v; ctx.fillRect(0, 0, W, H); }
  }
}

// 4 × 6 pixel glyphs for the wordmark.
const GLYPHS: Record<string, string[]> = {
  t: ['.#..', '###.', '.#..', '.#..', '.#..', '..##'], r: ['....', '#.##', '##..', '#...', '#...', '#...'],
  e: ['....', '.##.', '#..#', '####', '#...', '.###'], h: ['#...', '#...', '###.', '#..#', '#..#', '#..#'],
  o: ['....', '.##.', '#..#', '#..#', '#..#', '.##.'], u: ['....', '#..#', '#..#', '#..#', '#..#', '.###'],
  s: ['....', '.###', '#...', '.##.', '...#', '###.'],
};
