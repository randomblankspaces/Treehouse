/** The decision tree and the plain-language run summary, shared by the dev view and the story view.
 *  Everything here is built from the public run snapshot (snap.decisions, snap.markers, snap.steps); no
 *  new backend call. Readable on a phone: nodes are collapsible and the layout is a single column there. */
import { useMemo, useState } from 'react';
import { focusOf, FOCUS_LABEL, type DecisionNode, type MapMarker, type RunSnapshot, type TraceStep } from './contract.ts';

/** Focus of a decision, by its tool name (the tree has no full TraceStep to pass to focusOf). */
const focusOfTool = (tool: string | null) => focusOf({tool: tool ? {name: tool} : undefined} as TraceStep);

const pct = (v: number | null | undefined) => v === null || v === undefined ? 'unavailable' : `${Math.round(v * 100)}%`;
const VERDICT_CHIP: Record<DecisionNode['verdict'], {glyph: string; word: string}> = {
  sound: {glyph: '✓', word: 'sound'}, invalid: {glyph: '✗', word: 'invalid'}, not_evaluated: {glyph: '⚠', word: 'not evaluated'},
};
/** Status by shape as well as colour (accessibility): present ● filled, cannot_assess ◇ hollow, absent ✕. */
export const STATUS_SHAPE: Record<string, {glyph: string; word: string}> = {
  present: {glyph: '●', word: 'present'}, cannot_assess: {glyph: '◇', word: 'cannot assess'}, absent: {glyph: '✕', word: 'absent'},
  intact: {glyph: '●', word: 'intact'}, damaged: {glyph: '◇', word: 'damaged'}, destroyed: {glyph: '✕', word: 'destroyed'},
};

type Node = DecisionNode & {children: Node[]};

/** Assemble the flat decisions list into a forest keyed by parent_id. */
function buildForest(decisions: DecisionNode[]): Node[] {
  const nodes = new Map<string, Node>(decisions.map(d => [d.decision_id, {...d, children: []}]));
  const roots: Node[] = [];
  for (const node of nodes.values()) {
    const parent = node.parent_id ? nodes.get(node.parent_id) : null;
    if (parent && parent !== node) parent.children.push(node); else roots.push(node);
  }
  const bySeq = (a: Node, b: Node) => (a.sequence ?? 0) - (b.sequence ?? 0);
  roots.sort(bySeq);
  for (const node of nodes.values()) node.children.sort(bySeq);
  return roots;
}

/** The decision_ids on the path from a claim's decision up to the root, for highlighting. */
function pathToRoot(decisions: DecisionNode[], decisionId: string | null): Set<string> {
  const byId = new Map(decisions.map(d => [d.decision_id, d]));
  const path = new Set<string>(); let id = decisionId;
  while (id && byId.has(id) && !path.has(id)) { path.add(id); id = byId.get(id)!.parent_id; }
  return path;
}

/** The build_index decision carries the cell/chip size and the rejected embedding sources. */
function scaleDecision(decisions: DecisionNode[]) { return decisions.find(d => d.tool === 'build_index') ?? null; }
function cellSizeOf(step: TraceStep | undefined) {
  const v = step?.tool?.args?.cell_size_m ?? step?.tool?.args?.cell_m;
  return typeof v === 'number' ? `${v} m` : null;
}

export function DecisionTree({snap, selectedClaim, onSelectClaim}:
  {snap: RunSnapshot; selectedClaim: string | null; onSelectClaim?: (id: string | null) => void}) {
  const decisions = snap.decisions ?? [];
  const forest = useMemo(() => buildForest(decisions), [decisions]);
  const marker = snap.markers.find(m => `${m.trial_id}:${m.claim_id}` === selectedClaim) ?? null;
  const litPath = useMemo(() => marker ? pathToRoot(decisions, marker.decision_id) : new Set<string>(), [decisions, marker]);
  const scale = scaleDecision(decisions);
  const scaleStep = scale ? snap.steps.find(s => s.decision_id === scale.decision_id) : undefined;

  if (!decisions.length) return <section className="dtree" aria-label="Decision tree">
    <h2>Decision tree</h2>
    <p className="hint">No recorded decisions are available for this run, so the decision tree cannot be shown.</p>
  </section>;

  return <section className="dtree" aria-label="Decision tree">
    <h2>Decision tree</h2>
    <p className="dtree-intro">Follow the agent from the task it accepted (the root) through every choice to the sites it recorded (the leaves). The branch it took is solid; the options it turned down are greyed out. Select a site to light up the path that produced it.</p>
    {scale && <ScaleCard node={scale} cell={cellSizeOf(scaleStep)} />}
    <ol className="dtree-roots">{forest.map(node => <TreeNode key={node.decision_id} node={node} depth={0}
      lit={litPath} markers={snap.markers} selectedClaim={selectedClaim} onSelectClaim={onSelectClaim} />)}</ol>
    {marker && <ClaimConfidence marker={marker} />}
  </section>;
}

/** Pinned scale card: the cell/chip-size and foundation-model decision, chosen vs rejected, with the why. */
function ScaleCard({node, cell}: {node: DecisionNode; cell: string | null}) {
  const chip = VERDICT_CHIP[node.verdict];
  return <article className="scale-card" aria-label="Scale and foundation-model decision">
    <p className="scale-eyebrow">Scale decision · how the agent chose to see the area</p>
    <h3>{cell ? <>Cell / chip size <b>{cell}</b></> : 'Foundation-model and cell-size choice'}</h3>
    <p className="scale-why">{node.rationale}</p>
    <p className="scale-chosen"><span className="chosen">Chosen: <b>{node.tool}{cell ? ` · ${cell}` : ''}</b></span>
      <span className={`verdict v-${node.verdict}`} title={`RV verdict: ${chip.word}`}>{chip.glyph} {chip.word}</span></p>
    {node.alternatives.length > 0 && <ul className="scale-rejected">{node.alternatives.map((a, i) =>
      <li key={i}><span className="rejected">Rejected: <b>{a.option}</b></span> — {a.reason}</li>)}</ul>}
    <p className="scale-conf"><span>Agent confidence</span>
      <span className="bar" aria-hidden="true"><span style={{inlineSize: `${Math.round((node.confidence ?? 0) * 100)}%`}} /></span>
      <span className="num">{pct(node.confidence)}</span></p>
  </article>;
}

function TreeNode({node, depth, lit, markers, selectedClaim, onSelectClaim}:
  {node: Node; depth: number; lit: Set<string>; markers: MapMarker[]; selectedClaim: string | null;
   onSelectClaim?: (id: string | null) => void}) {
  const [open, setOpen] = useState(depth < 2);
  const onPath = lit.has(node.decision_id);
  const chip = VERDICT_CHIP[node.verdict];
  const isClaim = node.tool === 'record_claim';
  const claimMarkers = node.claim_ids.map(cid => markers.find(m => m.trial_id === node.trial_id && m.claim_id === cid)).filter((m): m is MapMarker => !!m);
  const hasChildren = node.children.length > 0;
  return <li className={`dnode ${onPath ? 'on-path' : ''} ${isClaim ? 'leaf' : ''}`} style={{['--depth' as string]: depth}}>
    <div className="dnode-head">
      {hasChildren
        ? <button type="button" className="twirl" aria-expanded={open} onClick={() => setOpen(o => !o)}><span aria-hidden="true">{open ? '▾' : '▸'}</span><span className="sr">{open ? 'Collapse' : 'Expand'} branch</span></button>
        : <span className="twirl leaf-mark" aria-hidden="true">{isClaim ? '◆' : '•'}</span>}
      <div className="dnode-body">
        <p className="dnode-title">
          {node.is_root && <span className="root-tag">Root</span>}
          <span className={`focus f-${focusOfTool(node.tool)}`}>{node.tool ? FOCUS_LABEL[focusOfTool(node.tool)] : 'Step'}</span>
          <code>{node.tool ?? node.action_id ?? node.decision_id}</code>
          <span className={`verdict v-${node.verdict}`} title={`RV verdict: ${chip.word}`}>{chip.glyph} {chip.word}</span>
        </p>
        <p className="dnode-why">{node.rationale}</p>
        <p className="dnode-conf">
          <span className="bar" aria-label={`Confidence ${pct(node.confidence)}`}><span style={{inlineSize: `${Math.round((node.confidence ?? 0) * 100)}%`}} /></span>
          <span className="num">{pct(node.confidence)}</span>
        </p>
        {node.alternatives.length > 0 && <ul className="dnode-alts" aria-label="Branches not taken">
          {node.alternatives.map((a, i) => <li key={i} className="not-taken"><b>{a.option}</b> — {a.reason}</li>)}
        </ul>}
        {claimMarkers.length > 0 && <ul className="dnode-claims">{claimMarkers.map(m => {
          const id = `${m.trial_id}:${m.claim_id}`, shape = STATUS_SHAPE[m.status] ?? {glyph: '•', word: m.status};
          return <li key={id}><button type="button" className={`claim-leaf ${id === selectedClaim ? 'on' : ''}`}
            aria-pressed={id === selectedClaim} onClick={() => onSelectClaim?.(id === selectedClaim ? null : id)}>
            <span className={`shape s-${m.status}`} aria-hidden="true">{shape.glyph}</span> {m.label} · <span className="sr">{shape.word}, </span>{pct(m.confidence)}
          </button></li>;
        })}</ul>}
        {node.rv.length > 0 && <details className="dnode-rv"><summary>Rule checks ({node.rv.length})</summary>
          <ul>{node.rv.map((r, i) => <li key={i} className={`rv-${r.verdict}`}><b>{r.rule_id}</b> {r.verdict}: {r.reason}</li>)}</ul></details>}
        <details className="dnode-think"><summary>Thinking</summary>
          <p>{thinkingFor(node) ?? 'No model thinking text is exposed for this decision. The recorded rationale above is the agent\u2019s own stated reason.'}</p></details>
      </div>
    </div>
    {hasChildren && open && <ol className="dnode-children">{node.children.map(child =>
      <TreeNode key={child.decision_id} node={child} depth={depth + 1} lit={lit} markers={markers}
        selectedClaim={selectedClaim} onSelectClaim={onSelectClaim} />)}</ol>}
  </li>;
}

/** Model thinking text is only exposed on chat spans, not decisions; the public projection withholds it. */
function thinkingFor(_node: DecisionNode): string | null { return null; }

/** How this claim's confidence was formed: stated, which checks raised or lowered it, earned vs unearned. */
function ClaimConfidence({marker}: {marker: MapMarker}) {
  const cp = marker.confidence_provenance;
  const shape = STATUS_SHAPE[marker.status] ?? {glyph: '•', word: marker.status};
  return <aside className="claim-conf" aria-label="How this claim's confidence was formed">
    <h3><span className={`shape s-${marker.status}`} aria-hidden="true">{shape.glyph}</span> {marker.label} <span className="sr">({shape.word})</span> · claim {marker.claim_id}</h3>
    {!cp ? <p className="hint">No confidence provenance was recorded for this claim.</p> : <>
      <p className="stated">Stated confidence <b>{pct(cp.stated)}</b> — <span className={`earned e-${cp.label}`}>{cp.label}</span></p>
      {cp.raised.length > 0 && <div><p className="lbl">Checks that raised confidence</p><ul className="raised">{cp.raised.map((r, i) => <li key={i}>↑ {r}</li>)}</ul></div>}
      {cp.lowered.length > 0 && <div><p className="lbl">Checks that lowered confidence</p><ul className="lowered">{cp.lowered.map((r, i) => <li key={i}>↓ {r}</li>)}</ul></div>}
      {!cp.raised.length && !cp.lowered.length && <p className="hint">No independent check along the path raised or lowered this claim.</p>}
      <p className="note">{cp.label === 'earned' ? 'A passed independent check supports this confidence.'
        : cp.label === 'unearned' ? 'High stated confidence with no passed independent check: treat as unearned.'
        : 'Confidence is neither strongly supported nor contradicted by recorded checks.'}
        {cp.cited_evidence ? ' The claim cited supporting evidence.' : ' The claim cited no supporting evidence.'}</p>
    </>}
  </aside>;
}

/** Plain-language run summary. Both interfaces end with this. */
export function PlainRunSummary({snap}: {snap: RunSnapshot}) {
  const decisions = snap.decisions ?? [];
  const scale = scaleDecision(decisions);
  const scaleStep = scale ? snap.steps.find(s => s.decision_id === scale.decision_id) : undefined;
  const cell = cellSizeOf(scaleStep);
  const present = snap.markers.filter(m => m.status === 'present' || m.status === 'intact');
  const count = (s: string) => snap.markers.filter(m => m.status === s).length;
  const confidences = present.map(m => m.confidence).filter((c): c is number => c !== null);
  const avgConf = confidences.length ? confidences.reduce((a, b) => a + b, 0) / confidences.length : null;
  const earned = present.filter(m => m.confidence_provenance?.label === 'earned').length;
  const unearned = present.filter(m => m.confidence_provenance?.label === 'unearned').length;
  const model = scale?.alternatives[0];
  const rejected = model ? ` It turned down ${model.option} (${model.reason}).` : '';
  const limits = snap.provenance.limitations;
  const earnedLine = present.length === 0 ? 'No present sites were recorded.'
    : earned === present.length ? 'Every present site rested on a passed independent check (earned confidence).'
    : earned === 0 ? 'None of the present sites rested on a passed independent check, so that confidence is not yet earned.'
    : `${earned} of ${present.length} present sites rested on a passed independent check; ${unearned} carried high confidence with no such check (unearned).`;
  return <section className="run-summary" aria-label="Plain-language run summary">
    <h2>In plain words</h2>
    <p><b>What was asked.</b> {snap.input.goal || 'The task goal was not provided by the backend.'}</p>
    <p><b>How it chose to look.</b> {scale
      ? <>The agent used <b>{scale.tool}</b>{cell ? <> at a <b>{cell}</b> cell</> : ''} to see the area. {scale.rationale}.{rejected}</>
      : 'No foundation-model or cell-size decision was recorded.'}</p>
    <p><b>What it found.</b> {present.length} site{present.length === 1 ? '' : 's'} marked present{count('cannot_assess') ? `, ${count('cannot_assess')} it could not assess` : ''}{count('absent') ? `, ${count('absent')} judged absent` : ''}. These are the agent\u2019s own reports, not confirmed ground truth.</p>
    <p><b>How confident, and was it earned.</b> {avgConf === null ? 'No per-site confidence was recorded.' : <>Average stated confidence on present sites was about <b>{pct(avgConf)}</b>.</>} {earnedLine}</p>
    <p><b>What it could not check.</b> {limits.length ? <ul className="summary-limits">{limits.map((t, i) => <li key={i}>{t}</li>)}</ul> : 'No limitations were recorded.'}</p>
  </section>;
}
