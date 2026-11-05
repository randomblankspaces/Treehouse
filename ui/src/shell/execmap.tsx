/** Execution map: the whole run at a glance, read without words. One lane per kind of work, one node per
 *  decision, failed tool call or claim, left to right in time. Shape and colour both carry status
 *  (sound ●, invalid ● in the error colour, failed call ✕ with a count, option not taken ○, claim ◆), so it
 *  works in every theme and colour-safe palette. Hover any node for its reason; select a claim to light it. */
import { useMemo } from 'react';
import { focusOf, FOCUS_LABEL, type DecisionNode, type Focus, type MapMarker, type RunSnapshot, type TraceStep } from './contract.ts';

const LANES: Focus[] = ['planning', 'foundation_model', 'data_access', 'claim', 'limitation', 'other'];
const LANE_H = 56, COL_W = 70, PAD_L = 128, PAD_T = 10;
const pct = (v: number | null | undefined) => v === null || v === undefined ? 'n/a' : `${Math.round(v * 100)}%`;

type Item =
  | {kind: 'decision'; lane: Focus; t: number; d: DecisionNode}
  | {kind: 'claim'; lane: Focus; t: number; d: DecisionNode; m: MapMarker | null}
  | {kind: 'fail'; lane: Focus; t: number; tool: string; type: string; count: number};

function build(snap: RunSnapshot): Item[] {
  const firstStep = new Map<string, number>();
  for (const s of snap.steps) if (s.decision_id && !firstStep.has(s.decision_id)) firstStep.set(s.decision_id, s.start_ms);
  const items: Item[] = [];
  let last = 0;
  for (const d of [...(snap.decisions ?? [])].sort((a, b) => (a.sequence ?? 0) - (b.sequence ?? 0))) {
    const t = firstStep.get(d.decision_id) ?? last;
    last = t;
    const lane = focusOf({tool: d.tool ? {name: d.tool} : undefined} as TraceStep);
    if (d.claim_ids.length) items.push({kind: 'claim', lane: 'claim', t, d, m: snap.markers.find(m => d.claim_ids.includes(m.claim_id)) ?? null});
    else items.push({kind: 'decision', lane, t, d});
  }
  for (const s of snap.steps) if (s.status === 'error' && s.kind === 'execute_tool')
    items.push({kind: 'fail', lane: focusOf(s), t: s.start_ms + 0.5, tool: s.tool?.name ?? s.name, type: s.error?.type ?? 'error', count: 1});
  items.sort((a, b) => a.t - b.t);
  // consecutive failures of the same tool become one node with a count
  return items.reduce<Item[]>((out, it) => {
    const prev = out[out.length - 1];
    if (it.kind === 'fail' && prev?.kind === 'fail' && prev.tool === it.tool) prev.count += 1; else out.push(it);
    return out;
  }, []);
}

const claimClass = (m: MapMarker | null) => m?.confidence_provenance?.label === 'earned' ? 'n-sound'
  : m?.confidence_provenance?.label === 'unearned' ? 'n-invalid' : 'n-ne';
const verdictClass = (d: DecisionNode) => d.verdict === 'sound' ? 'n-sound' : d.verdict === 'invalid' ? 'n-invalid' : 'n-ne';

export function ExecutionMap({snap, selectedClaim, onSelectClaim}:
  {snap: RunSnapshot; selectedClaim: string | null; onSelectClaim?: (id: string | null) => void}) {
  const items = useMemo(() => build(snap), [snap]);
  if (!items.length) return null;
  const lanes = LANES.filter(l => items.some(i => i.lane === l));
  const y = (l: Focus) => PAD_T + lanes.indexOf(l) * LANE_H + LANE_H / 2;
  const x = (i: number) => PAD_L + i * COL_W + COL_W / 2;
  const W = PAD_L + items.length * COL_W + 12, H = PAD_T * 2 + lanes.length * LANE_H;
  const nDec = items.filter(i => i.kind !== 'fail').length;
  const nInvalid = items.filter(i => i.kind !== 'fail' && i.d.verdict === 'invalid').length;
  const nFail = items.reduce((n, i) => n + (i.kind === 'fail' ? i.count : 0), 0);
  const claims = items.filter((i): i is Extract<Item, {kind: 'claim'}> => i.kind === 'claim');
  const nEarned = claims.filter(c => c.m?.confidence_provenance?.label === 'earned').length;

  return <section className="execmap" aria-label="Execution map">
    <h2>Execution map</h2>
    <p className="execmap-kpis">
      <span><b>{nDec}</b> decisions</span>
      <span className={nInvalid ? 'bad' : ''}><b>{nInvalid}</b> judged invalid</span>
      <span className={nFail ? 'bad' : ''}><b>{nFail}</b> failed tool calls</span>
      <span className={claims.length && !nEarned ? 'bad' : ''}><b>{nEarned}/{claims.length}</b> claims with earned confidence</span>
    </p>
    <div className="execmap-scroll">
      <svg width={W} height={H} role="img" aria-label={`Execution map: ${nDec} decisions, ${nInvalid} invalid, ${nFail} failed tool calls, ${nEarned} of ${claims.length} claims earned`}>
        {lanes.map((l, k) => <g key={l}>
          <rect className={`lane-band${k % 2 ? ' alt' : ''}`} x={0} y={PAD_T + k * LANE_H} width={W} height={LANE_H} />
          <text className="lane-label" x={10} y={y(l) + 4}>{FOCUS_LABEL[l]}</text>
        </g>)}
        <polyline className="flow" points={items.map((it, i) => `${x(i)},${y(it.lane)}`).join(' ')} />
        {items.map((it, i) => {
          const cx = x(i), cy = y(it.lane);
          if (it.kind === 'fail') return <g key={i} className="n-fail">
            <title>{`${it.tool} failed ×${it.count}: ${it.type}`}</title>
            <line x1={cx - 6} y1={cy - 6} x2={cx + 6} y2={cy + 6} /><line x1={cx - 6} y1={cy + 6} x2={cx + 6} y2={cy - 6} />
            {it.count > 1 && <text className="node-count" x={cx + 8} y={cy - 8}>×{it.count}</text>}
            <text className="node-label" x={cx} y={cy + 20}>{it.tool.slice(0, 11)}</text>
          </g>;
          const d = it.d, r = 6 + 7 * (d.confidence ?? 0.4);
          const why = `${d.tool ?? 'decision'} · ${d.verdict.replace('_', ' ')} · confidence ${pct(d.confidence)}\n${d.rationale}` +
            (d.alternatives.length ? `\nNot taken: ${d.alternatives.map(a => a.option).join('; ')}` : '');
          const alts = d.alternatives.slice(0, 3).map((_, k) => <g key={k} className="alt">
            <line x1={cx} y1={cy - r} x2={cx + (k - 1) * 11} y2={cy - r - 11} /><circle cx={cx + (k - 1) * 11} cy={cy - r - 14} r={3} />
          </g>);
          if (it.kind === 'claim') {
            const key = it.m ? `${it.m.trial_id}:${it.m.claim_id}` : null, on = key !== null && key === selectedClaim;
            const s = 9;
            return <g key={i} className={`n-claim ${claimClass(it.m)}${on ? ' on' : ''}`} role="button" tabIndex={0}
              aria-label={`Claim ${it.m?.label ?? ''}: ${it.m?.confidence_provenance?.label ?? 'unestablished'} confidence ${pct(it.m?.confidence)}`}
              onClick={() => key && onSelectClaim?.(on ? null : key)}
              onKeyDown={e => { if ((e.key === 'Enter' || e.key === ' ') && key) { e.preventDefault(); onSelectClaim?.(on ? null : key); } }}>
              <title>{`${why}\nClaim confidence: ${pct(it.m?.confidence)} (${it.m?.confidence_provenance?.label ?? 'unestablished'})`}</title>
              <polygon points={`${cx},${cy - s} ${cx + s},${cy} ${cx},${cy + s} ${cx - s},${cy}`} />
              <text className="node-label" x={cx} y={cy + 22}>{(it.m?.label ?? 'claim').slice(0, 11)}</text>
            </g>;
          }
          return <g key={i} className={`n-dec ${verdictClass(d)}`}>
            <title>{why}</title>
            {alts}
            <circle cx={cx} cy={cy} r={r} />
            <text className="node-label" x={cx} y={cy + r + 12}>{(d.tool ?? 'decision').slice(0, 11)}</text>
          </g>;
        })}
      </svg>
    </div>
    <ul className="execmap-legend" aria-label="Legend">
      <li><svg width="14" height="14"><circle className="n-sound" cx="7" cy="7" r="6" /></svg> sound decision (size = confidence)</li>
      <li><svg width="14" height="14"><circle className="n-invalid" cx="7" cy="7" r="6" /></svg> invalid decision</li>
      <li><svg width="14" height="14" className="n-fail"><line x1="2" y1="2" x2="12" y2="12" /><line x1="2" y1="12" x2="12" y2="2" /></svg> failed tool call (×count)</li>
      <li><svg width="14" height="14" className="alt"><circle cx="7" cy="7" r="4" /></svg> option considered, not taken</li>
      <li><svg width="14" height="14"><polygon className="n-sound" points="7,1 13,7 7,13 1,7" /></svg> claim: earned / <svg width="14" height="14"><polygon className="n-invalid" points="7,1 13,7 7,13 1,7" /></svg> unearned confidence</li>
    </ul>
  </section>;
}
