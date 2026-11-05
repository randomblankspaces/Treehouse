/** Architecture slide, drawn to AWS Architecture Center diagram conventions: AWS Cloud and Region group
 *  boundaries, service tiles in the AWS category colours (AI/ML teal, compute orange, storage green, security
 *  red, management pink), left-to-right flow and numbered black step callouts explained in a legend.
 *  The editable source is docs/architecture/treehouse-aws.drawio (draw.io AWS 4 shapes); keep the two in sync.
 *  Tiles use simple glyphs rather than the official AWS icon artwork, so nothing is fetched at runtime. */
import { d, Slide } from './ui.tsx';

const C = {ai: '#01A88D', compute: '#ED7100', storage: '#7AA116', security: '#DD344C', mgmt: '#E7157B', generic: '#5A6B86'};

type Tile = {id: string; x: number; y: number; fill: string; glyph: string; name: string; sub?: string; status?: 'live' | 'deployed'};
// Grid: columns A..D inside the Region, a bottom row inside the AWS Cloud but outside the Region.
const A = 270, B = 460, CC = 650, D = 850, TOP = 160, MID = 330, LOW = 450, BOTTOM = 580;
const TILES: Tile[] = [
  {id: 'bedrock', x: A, y: TOP, fill: C.ai, glyph: '✳', name: 'Amazon Bedrock', sub: 'Sonnet · Nova Pro · Haiku', status: 'live'},
  {id: 'strands', x: A, y: MID, fill: C.ai, glyph: '↻', name: 'Strands Agents', sub: 'agent loop under test', status: 'live'},
  {id: 'mcp', x: B, y: MID, fill: C.generic, glyph: '⇄', name: 'Tool gateway', sub: 'decision-bound MCP tools', status: 'live'},
  {id: 'runstore', x: CC, y: TOP, fill: C.storage, glyph: '▣', name: 'Amazon S3', sub: 'Object Lock run store', status: 'live'},
  {id: 'keys', x: CC, y: LOW, fill: C.security, glyph: '⚿', name: 'AWS KMS', sub: 'answer-key bucket', status: 'deployed'},
  {id: 'lambda', x: D, y: TOP, fill: C.compute, glyph: 'λ', name: 'AWS Lambda', sub: 'Treehouse evaluators', status: 'deployed'},
  {id: 'agentcore', x: D, y: MID, fill: C.ai, glyph: '✓', name: 'AgentCore', sub: 'Evaluations', status: 'live'},
  {id: 'cloudwatch', x: D, y: LOW, fill: C.mgmt, glyph: '◔', name: 'CloudWatch', sub: 'Transaction Search', status: 'live'},
  {id: 'opendata', x: B, y: BOTTOM, fill: C.storage, glyph: '▤', name: 'AWS Open Data', sub: 'LGND Clay v1.5 on S3', status: 'live'},
  {id: 'polly', x: D, y: BOTTOM, fill: C.ai, glyph: '♪', name: 'Amazon Polly', sub: 'report narrator', status: 'live'},
];
const S = 60;  // tile size
const H = S / 2 + 4, LABEL = S / 2 + 42;   // gap to a tile edge; room below a tile for its two label lines
const REPORT = {x: 1060, y: MID - 40, w: 120, h: 80};

/** Orthogonal connectors (AWS diagram convention): a list of points, drawn as a polyline. */
type Edge = {pts: [number, number][]; n?: number; at?: [number, number]; deny?: boolean; both?: boolean; label?: [number, number, string, ('start' | 'end')?]};
const EDGES: Edge[] = [
  {pts: [[96, TOP], [A - H, TOP]], n: 1, at: [165, TOP - 18]},
  {pts: [[A, TOP + LABEL], [A, MID - H]], both: true, label: [A + 10, (TOP + LABEL + MID - H) / 2 + 4, 'agent loop']},
  {pts: [[A + H, MID], [B - H, MID]], n: 2, at: [(A + B) / 2, MID - 18]},
  {pts: [[B, MID + LABEL], [B, BOTTOM - H]], label: [B - 10, 486, 'reads embeddings', 'end']},
  {pts: [[B + H, MID - 10], [555, MID - 10], [555, TOP], [CC - H, TOP]], n: 3, at: [555, (TOP + MID) / 2]},
  {pts: [[B + H, MID + 10], [575, MID + 10], [575, LOW], [CC - H, LOW]], deny: true},
  {pts: [[CC + H, TOP], [D - H, TOP]], n: 4, at: [(CC + D) / 2, TOP - 18]},
  {pts: [[CC + H, LOW - 12], [750, LOW - 12], [750, TOP + 16], [D - H, TOP + 16]], label: [744, 300, 'grader role', 'end']},
  {pts: [[D, TOP + LABEL], [D, MID - H]]},
  {pts: [[D, LOW - H], [D, MID + LABEL]]},
  {pts: [[D + H, MID], [REPORT.x - 4, MID]], n: 5, at: [(D + REPORT.x) / 2 + 20, MID - 18]},
  {pts: [[D + H, BOTTOM], [REPORT.x + REPORT.w / 2, BOTTOM], [REPORT.x + REPORT.w / 2, REPORT.y + REPORT.h + 46]]},
];

function TileG({t, i}: {t: Tile; i: number}) {
  return <g className="tile" style={d(i)} transform={`translate(${t.x - S / 2} ${t.y - S / 2})`}>
    <rect width={S} height={S} rx={6} fill={t.fill} />
    <text x={S / 2} y={S / 2 + 1} className="glyph" textAnchor="middle" dominantBaseline="central">{t.glyph}</text>
    <text x={S / 2} y={S + 19} className="tile-name" textAnchor="middle">{t.name}</text>
    {t.sub && <text x={S / 2} y={S + 36} className="tile-sub" textAnchor="middle">{t.sub}</text>}
    {t.status && <g transform={`translate(${S + 2} -2)`}><circle r={7} className={`st ${t.status}`} /><title>{t.status === 'live' ? 'Ran live' : 'Deployed (CDK)'}</title></g>}
  </g>;
}

function EdgeG({e, i}: {e: Edge; i: number}) {
  const path = 'M' + e.pts.map(p => p.join(' ')).join(' L');
  const corner = e.pts[Math.min(2, e.pts.length - 1)];
  return <g className={`edge ${e.deny ? 'deny' : ''}`} style={d(4 + i * 0.6)}>
    <path d={path} markerEnd={e.deny ? 'url(#arrow-deny)' : 'url(#arrow)'} markerStart={e.both ? 'url(#arrow)' : undefined} pathLength={1} />
    {e.deny && <g transform={`translate(${(corner[0] + e.pts[3][0]) / 2} ${corner[1]})`}>
      <circle r={11} className="deny-badge" /><text textAnchor="middle" dominantBaseline="central" className="deny-x">✕</text>
    </g>}
    {e.deny && <text x={587} y={392} className="deny-label">worker role:</text>}
    {e.deny && <text x={587} y={410} className="deny-label">explicit IAM Deny</text>}
    {e.label && <text x={e.label[0]} y={e.label[1]} textAnchor={e.label[3] ?? 'start'} className="edge-label">{e.label[2]}</text>}
    {e.n && e.at && <g className="callout" transform={`translate(${e.at[0]} ${e.at[1]})`}>
      <circle r={13} /><text textAnchor="middle" dominantBaseline="central">{e.n}</text>
    </g>}
  </g>;
}

const LEGEND = [
  {n: 1, t: 'An analyst’s task card (question, area, allowed sources, budget) starts a Strands agent on Amazon Bedrock.'},
  {n: 2, t: 'Every tool call goes through the gateway, which refuses any action without a recorded decision. MCP tools read real Clay embeddings from AWS Open Data.'},
  {n: 3, t: 'The finished run is hash-chained and sealed to S3 Object Lock (COMPLIANCE). Answer keys sit in a KMS bucket the agent’s role is explicitly denied.'},
  {n: 4, t: 'Lambda evaluators re-check every claim; AgentCore Evaluations score tool use and trajectory from the CloudWatch spans.'},
  {n: 5, t: 'The report: a decision tree, separate score panels and an Amazon Polly narrator.'},
];

export function Architecture() {
  return <Slide id="architecture" className="arch">
    <p className="eyebrow r">Solution architecture</p>
    <h2 className="r" style={d(1)}>Built on AWS, <em>sealed before it is scored</em>.</h2>
    <div className="arch-body">
      <figure className="diagram r" style={d(2)}>
        <svg viewBox="0 0 1200 700" role="img" aria-labelledby="arch-title arch-desc">
          <title id="arch-title">Treehouse AWS architecture</title>
          <desc id="arch-desc">An analyst's task card goes to a Strands agent on Amazon Bedrock in us-east-1. The agent calls
            decision-bound MCP tools that read LGND Clay embeddings from AWS Open Data. The sealed run is written to
            Amazon S3 Object Lock; answer keys are in a KMS-encrypted bucket the worker role cannot read. AWS Lambda
            evaluators and Amazon Bedrock AgentCore Evaluations score the run from CloudWatch spans, and the report
            is narrated by Amazon Polly.</desc>
          <defs>
            <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M0 0 L10 5 L0 10 z" className="arrowhead" /></marker>
            <marker id="arrow-deny" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M0 0 L10 5 L0 10 z" className="arrowhead deny" /></marker>
          </defs>
          {/* AWS Cloud group */}
          <g className="group cloud">
            <rect x={140} y={20} width={850} height={660} rx={2} />
            <rect x={140} y={20} width={30} height={30} className="group-tab" />
            <text x={155} y={35} className="group-icon" textAnchor="middle" dominantBaseline="central">☁</text>
            <text x={180} y={41} className="group-label">AWS Cloud</text>
          </g>
          {/* Region group */}
          <g className="group region">
            <rect x={170} y={66} width={790} height={460} rx={2} />
            <rect x={170} y={66} width={30} height={30} className="group-tab" />
            <text x={185} y={81} className="group-icon" textAnchor="middle" dominantBaseline="central">⚑</text>
            <text x={210} y={87} className="group-label">Region · us-east-1 · single sandbox account</text>
          </g>
          {/* Outside the cloud: the analyst and the report */}
          <g className="tile" style={d(0)} transform={`translate(34 ${TOP - 34})`}>
            <circle cx={30} cy={14} r={13} className="person" /><path d="M6 58 Q30 22 54 58 Z" className="person" />
            <text x={30} y={80} className="tile-name" textAnchor="middle">ADB analyst</text>
            <text x={30} y={97} className="tile-sub" textAnchor="middle">task card</text>
          </g>
          <g className="tile" style={d(10)} transform={`translate(${REPORT.x} ${REPORT.y})`}>
            <rect width={REPORT.w} height={REPORT.h} rx={6} className="screen" />
            <path d="M16 58 L38 36 L58 48 L82 22 L104 42" className="screen-line" />
            <text x={REPORT.w / 2} y={REPORT.h + 20} className="tile-name" textAnchor="middle">Treehouse report</text>
            <text x={REPORT.w / 2} y={REPORT.h + 37} className="tile-sub" textAnchor="middle">decision tree · panels</text>
          </g>
          {EDGES.map((e, i) => <EdgeG key={i} e={e} i={i} />)}
          {TILES.map((t, i) => <TileG key={t.id} t={t} i={i + 1} />)}
          <text x={170} y={668} className="iac">Provisioned with AWS CDK: RunStoreStack + EvalStack</text>
        </svg>
        <figcaption className="arch-key">
          <span><i className="st live" /> ran live</span><span><i className="st deployed" /> deployed with CDK</span>
          <span>Editable source: <code>docs/architecture/treehouse-aws.drawio</code></span>
        </figcaption>
      </figure>
      <ol className="legend">
        {LEGEND.map((l, i) => <li key={l.n} className="r" style={d(4 + i)}><span className="num" aria-hidden="true">{l.n}</span><span>{l.t}</span></li>)}
      </ol>
    </div>
  </Slide>;
}
