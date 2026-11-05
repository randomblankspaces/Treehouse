/** "By the numbers": cost, speed and what the evaluation caught, from committed evidence only.
 *  Data: data/stats.json, built by scripts/build_pitch_stats.py from the Bedrock spend ledger and the live
 *  experiment matrix. Each block says whether it is measured, synthetic-keyed, or a projection. */
import run from './data/recorded-run.json';
import stats from './data/stats.json';
import { d, Slide } from './ui.tsx';

const usd = (v: number, digits = 2) => `$${v.toFixed(digits)}`;
const pct = (v: number | null | undefined) => v == null ? '—' : `${Math.round(v * 100)}%`;
const cfg = stats.matrix.configs as Record<string, {model: string; card: string; [k: string]: unknown}>;
const metric = (label: string, name: string) => (cfg[label]?.[name] as {mean: number | null} | undefined)?.mean ?? null;

const NAGOYA = 't1-nagoya-warehouses|claude-sonnet-5-5|strands';
const GIFU = 't5-gifu-warehouses|claude-sonnet-5-5|strands';
const NOVA = 'nova-pro', SONNET = 'claude-sonnet-5-5';

function Basis({kind}: {kind: 'measured' | 'synthetic' | 'projection'}) {
  const text = {measured: 'Measured · live runs', synthetic: 'Live agent · synthetic answer key', projection: 'Projection · from measured means'}[kind];
  return <span className={`basis ${kind}`}>{text}</span>;
}

/** Two bars, one axis (recall, 0–100 %), labelled directly; hover gives the exact value and basis. */
function RecallBars() {
  const agent = metric(NAGOYA, 'output.recall') ?? 0;
  const base = stats.matrix.baseline.linear_probe_recall;
  const rows = [
    {k: 'Agent (Sonnet, Strands)', v: agent, cls: 'agent', tip: `Agent recall ${pct(agent)} · mean of 3 live runs, Nagoya`},
    {k: 'Plain classifier, same data', v: base, cls: 'base', tip: `Linear probe recall ${pct(base)} · mean of 3 seeds, offline`},
  ];
  return <figure className="recall" aria-label="Recall: agent versus a plain classifier on the same synthetic Nagoya data">
    {rows.map(r => <div key={r.k} className="recall-row" title={r.tip}>
      <span className="recall-k">{r.k}</span>
      <span className="recall-track"><span className={`recall-bar ${r.cls}`} style={{width: `${Math.max(r.v * 100, 1.5)}%`}} /></span>
      <b className="recall-v">{pct(r.v)}</b>
    </div>)}
    <figcaption>Share of the 30 reference warehouses found (recall), Nagoya.</figcaption>
  </figure>;
}

export function Numbers() {
  const L = stats.ledger, M = stats.matrix, P = stats.projection;
  const sonnet = L.by_model[SONNET as keyof typeof L.by_model], nova = L.by_model[NOVA as keyof typeof L.by_model];
  const novaTools = cfg[`t1-nagoya-warehouses|${NOVA}|strands`]?.['cost.tool_calls'] as {interval_95: [number, number] | null} | undefined;
  return <Slide id="numbers" className="numbers">
    <p className="eyebrow r">By the numbers</p>
    <h2 className="r" style={d(1)}>Cheap to run. <em>Catches what output checks miss.</em></h2>
    <div className="num-grid">
      <article className="card r" style={d(2)}>
        <Basis kind="measured" />
        <h3>Cost &amp; speed</h3>
        <div className="hero-num"><b>{usd(M.usd_per_run.mean)}</b><span>average per evaluated agent run<br />(range {usd(M.usd_per_run.min)}–{usd(M.usd_per_run.max)}, {M.n_runs} runs)</span></div>
        <div className="hero-num"><b>{Math.round(M.wall_seconds.mean)} s</b><span>average wall time per run</span></div>
        <div className="hero-num"><b>{usd(L.usd)}</b><span>all {L.calls} Bedrock calls of the hackathon, {(L.input_tokens / 1e6).toFixed(1)} M tokens</span></div>
        <p className="fine">Per call: Sonnet {usd(sonnet.usd_per_call, 3)} · Nova Pro {usd(nova.usd_per_call, 3)}. Source: Bedrock spend ledger, not the AWS bill.</p>
      </article>
      <article className="card r" style={d(3)}>
        <Basis kind="synthetic" />
        <h3>What the evaluation caught</h3>
        <RecallBars />
        <ul className="caught">
          <li><b>{pct(metric(GIFU, 'output.recall'))}</b> recall in Gifu with no new labels: the transfer gap is measured, not assumed.</li>
          <li><b>Cheap ≠ good:</b> Nova Pro is {(sonnet.usd_per_call / nova.usd_per_call).toFixed(1)}× cheaper per call, but its runs used {novaTools?.interval_95?.[0] ?? '?'}–{novaTools?.interval_95?.[1] ?? '?'} tool calls; one quit for {usd(M.usd_per_run.min)}.</li>
          <li><b>{run.trace.errors} of {run.trace.spans}</b> steps in the demo run were blocked by the gateway, and the sealed record shows each one.</li>
        </ul>
      </article>
      <article className="card r" style={d(4)}>
        <Basis kind="projection" />
        <h3>After release</h3>
        <div className="hero-num"><b>≈ {usd(P.bedrock_usd, 0)}</b><span>Bedrock cost to evaluate the full ADB benchmark: {P.scope.places} places × {P.scope.asset_classes} asset classes × {P.scope.models} models × {P.scope.seeds} seeds = {P.runs} runs</span></div>
        <div className="hero-num"><b>{Math.round(P.bedrock_usd / P.imagery_budget_usd * 100)}%</b><span>of the benchmark’s ${P.imagery_budget_usd.toLocaleString()} imagery budget</span></div>
        <div className="hero-num"><b>≈ {Math.round(P.sequential_hours)} h</b><span>one after another, or minutes in parallel with Step Functions Distributed Map (designed)</span></div>
      </article>
    </div>
    <ol className="actions r" style={d(6)}>
      <li><b>Evaluate every agent before trusting its map:</b> under $1 and about a minute per run.</li>
      <li><b>Never judge an agent by its output alone:</b> this one looked busy and found {pct(metric(NAGOYA, 'output.recall'))} of what a plain classifier found {pct(stats.matrix.baseline.linear_probe_recall)} of.</li>
      <li><b>Pick models on evaluated results, not price per token.</b></li>
    </ol>
    <p className="source r" style={d(7)}>{M.note} Sources: .spend/spend.jsonl, fixtures/live/experiments/metrics.json ({L.first} to {L.last}); benchmark scope and imagery budget from the ADB/LGND inception report.</p>
  </Slide>;
}
