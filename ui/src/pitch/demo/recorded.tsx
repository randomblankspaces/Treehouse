/** Demo mode A — a real live Bedrock run (exp-nagoya-sonnet-1), replayed from its recording, in three stages.
 *  Data: data/recorded-run.json, built by scripts/build_pitch_demo.py from the same snapshot the UI API serves.
 *  Its embeddings and answer key are SYNTHETIC fixtures; the page says so and never shows it as real accuracy. */
import run from '../data/recorded-run.json';
import type { DemoProps } from './modes.ts';

type Marker = {lon: number; lat: number; status: string; confidence: number | null; earned: string | null; lowered: string[]};
type Decision = {decision_id: string; tool: string | null; rationale: string; verdict: string; confidence: number | null;
  alternatives: {option: string; reason: string}[]; rv: {rule_id: string; verdict: string; reason: string}[]};

const markers = run.markers as Marker[];
const decisions = run.decisions as Decision[];
const appLink = `/?run=${encodeURIComponent(run.run_id)}`;
const BLOCK_LABEL: Record<string, string> = {
  missing_decision: 'no decision recorded first',
  not_allowed: 'source not allowed',
  not_configured: 'tool not configured',
};
const pct = (v: number | null | undefined) => v == null ? '—' : `${Math.round(v)}%`;

function AoiMap({show}: {show: number}) {
  const [w, s, e, n] = run.aoi_bbox as [number, number, number, number];
  const W = 420, H = Math.round(W * (n - s) / ((e - w) * Math.cos((s + n) / 2 * Math.PI / 180)));
  const x = (lon: number) => (lon - w) / (e - w) * W;
  const y = (lat: number) => (n - lat) / (n - s) * H;
  const km = 1 / (111.32 * Math.cos((s + n) / 2 * Math.PI / 180));   // degrees of longitude per km
  const lines = [];
  for (let lon = w + km; lon < e; lon += km) lines.push(<line key={`v${lon}`} x1={x(lon)} y1={0} x2={x(lon)} y2={H} />);
  for (let lat = s + 1 / 111.32; lat < n; lat += 1 / 111.32) lines.push(<line key={`h${lat}`} x1={0} y1={y(lat)} x2={W} y2={y(lat)} />);
  return <svg className="aoi" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Area of interest with ${markers.length} claimed warehouse sites`}>
    <rect width={W} height={H} className="aoi-bg" />
    <g className="aoi-grid">{lines}</g>
    {markers.slice(0, show).map((m, i) => <g key={i} className="aoi-pt" transform={`translate(${x(m.lon)} ${y(m.lat)})`}>
      <circle r={7} className={m.earned === 'earned' ? 'earned' : 'unearned'} /><text x={10} y={4}>{i + 1}</text>
    </g>)}
    <text x={8} y={H - 8} className="aoi-label">Nagoya port district · 1 km grid · {run.aoi_bbox.join(', ')}</text>
  </svg>;
}

function StageInvestigate() {
  const path = decisions.filter(dd => dd.tool !== 'record_claim');
  return <div className="stage-grid">
    <div className="panel">
      <h3>Decision path <small>(recorded before each tool ran)</small></h3>
      <ol className="dpath">
        {path.map((dd, i) => <li key={dd.decision_id} style={{animationDelay: `${i * 70}ms`}}>
          <code>{dd.tool}</code><span>{dd.rationale}</span>
          {dd.alternatives[0] && <em>not: {dd.alternatives[0].option}</em>}
        </li>)}
      </ol>
    </div>
    <div className="panel">
      <h3>Its answer: {markers.length} claimed warehouse sites</h3>
      <AoiMap show={markers.length} />
      <p className="goal">“{run.goal.split('. ')[0]}.”</p>
    </div>
  </div>;
}

function StageCapture() {
  const t = run.trace;
  const tools = Object.entries(t.tools).filter(([k]) => !['chat', 'invoke_agent'].includes(k));
  const max = Math.max(...tools.map(([, v]) => v as number));
  return <div className="stage-grid">
    <div className="panel">
      <h3>The trace</h3>
      <div className="kpis">
        <div><b>{t.spans}</b><span>spans, hash-chained</span></div>
        <div><b>{t.model_calls}</b><span>Bedrock calls</span></div>
        <div><b>{Math.round((t.input_tokens + t.output_tokens) / 1000)}k</b><span>tokens</span></div>
        <div><b>${run.cost_usd?.toFixed(2)}</b><span>recorded cost</span></div>
      </div>
      <h4>Tool calls</h4>
      <ul className="bars">{tools.map(([k, v]) => <li key={k}><code>{k}</code><span className="bar" style={{width: `${(v as number) / max * 100}%`}} /><b>{v as number}</b></li>)}</ul>
    </div>
    <div className="panel">
      <h3>Where it struggled</h3>
      <p className="big-num"><b>{t.errors}</b> actions blocked by the gateway</p>
      <ul className="blocked">{Object.entries(t.blocked).map(([k, v]) => <li key={k}><b>{v as number}</b> {BLOCK_LABEL[k] ?? k}</li>)}</ul>
      <p>The agent recovered and finished. Every refusal stays in the sealed record, so reviewers see the struggle, not only the final answer.</p>
    </div>
  </div>;
}

function StageScore() {
  const rules = run.scores.reasoning_rules.scores[0];
  const unearned = markers.filter(m => m.earned !== 'earned').length;
  const reasons = [...new Set(markers.flatMap(m => m.lowered))];
  const invalid = decisions.filter(dd => dd.verdict === 'invalid').length;
  return <div className="stage-grid three">
    <div className="panel score">
      <h3>(a) Reasoning</h3>
      <p className="big-num"><b>{pct(rules?.value)}</b></p>
      <p>{rules?.numerator}/{rules?.denominator} workflow rules passed · {invalid} decisions flagged invalid</p>
    </div>
    <div className="panel score">
      <h3>(b) Confidence</h3>
      <p className="big-num"><b>{unearned}/{markers.length}</b></p>
      <p>claims stated at {markers[0]?.confidence} confidence, but <strong>not earned</strong>:</p>
      <ul className="reasons">{reasons.map(r => <li key={r}>{r}</li>)}</ul>
    </div>
    <div className="panel score muted">
      <h3>(c) Accuracy</h3>
      <p className="big-num"><b>held out</b></p>
      <p>Scored only against a separate answer key the agent’s role cannot read. Here the key is a synthetic fixture, so accuracy is a pipeline check, not a real-world score (next slide).</p>
    </div>
  </div>;
}

export function RecordedDemo({stage}: DemoProps) {
  return <div className="recorded">
    <div className="run-meta">
      <span className="badge live">Recorded live · {run.harness} on Amazon Bedrock · {run.model_id}</span>
      <span className="badge warn">Embeddings &amp; answer key: synthetic fixtures</span>
      <a className="badge link" href={appLink}>Open this run in Treehouse ↗</a>
    </div>
    <div className="stage-view" key={stage}>
      {stage === 0 && <StageInvestigate />}
      {stage === 1 && <StageCapture />}
      {stage >= 2 && <StageScore />}
    </div>
  </div>;
}
