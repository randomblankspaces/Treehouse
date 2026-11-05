/** Slide content. Keep each slide to one headline, one visual and three points at most: these are presented.
 *  Sources: ADB/LGND GeoAI Evals Inception Report (Oct 2026), Clay hackathon vision + technical documents,
 *  docs/ARCHITECTURE.md and docs/FUTURE-FEATURES.md. Every number says where it comes from. */
import { d, Slide } from './ui.tsx';

export function Problem() {
  return <Slide id="problem" className="hero">
    <p className="eyebrow r">The problem</p>
    <h1 className="r" style={d(1)}>AI agents are starting to build the maps<br />that decide <em>disaster money</em>.</h1>
    <p className="lede r" style={d(2)}>Nobody can see how they built them, so nobody can trust them.</p>
    <blockquote className="r" style={d(3)}>
      “The bottleneck is not running an agent — it is <strong>knowing whether to trust one</strong>.”
      <cite>Clay Earth Dataset Foundry, vision document</cite>
    </blockquote>
    <div className="scroll-cue r" style={d(5)} aria-hidden="true">scroll ↓</div>
  </Slide>;
}

const USES = [
  {team: 'Disaster risk finance', decision: 'How much to fund after an event', need: 'Results checkable against reliable records'},
  {team: 'Post-disaster needs (PDNA)', decision: 'How many assets were damaged, and the repair cost', need: 'Assets counted one by one, repeatably'},
  {team: 'Risk Analytics Explorer', decision: 'Where to invest in resilience (Cook Islands, Tonga, Vanuatu)', need: 'Recent data with clear licence and provenance'},
  {team: 'Project & sector teams', decision: 'Baseline and monitor funded assets', need: 'Coverage where ADB invests'},
];

export function Context() {
  return <Slide id="context">
    <p className="eyebrow r">Why it is real</p>
    <h2 className="r" style={d(1)}>Four ADB decisions run on <em>asset lists</em> nobody has.</h2>
    <div className="uses">
      {USES.map((u, i) => <article key={u.team} className="card r" style={d(2 + i)}>
        <h3>{u.team}</h3>
        <p className="decision">{u.decision}</p>
        <p className="need"><span>Needs to trust it:</span> {u.need}</p>
      </article>)}
    </div>
    <div className="stats">
      <div className="stat r" style={d(6)}><b>Data-sparse</b><span>Asia &amp; Pacific member countries with no asset registers</span></div>
      <div className="stat r" style={d(7)}><b>15.2 B</b><span>open Clay embeddings an agent can search</span></div>
      <div className="stat r" style={d(8)}><b>~99</b><span>geospatial MCP servers in Clay’s catalogue</span></div>
    </div>
    <p className="source r" style={d(9)}>Source: ADB / LGND GeoAI Evals Inception Report, Table 5 (Oct 2026); Clay hackathon technical document.</p>
  </Slide>;
}

/** Amazon "Working Backwards": start at the customer, end at what we built. Read right → left on screen. */
const BACKWARDS = [
  {k: 'Customer', v: 'An ADB analyst after a flood, with a deadline and no asset register.'},
  {k: 'Their question', v: '“Where are all the warehouses here — and can I put this list in front of a ministry?”'},
  {k: 'What earns trust', v: 'A reason for every point. Confidence that was earned, not just stated. Proof nothing was edited.'},
  {k: 'So we must capture', v: 'Every agent decision, its alternatives and evidence — sealed before anyone scores it.'},
  {k: 'So we built', v: 'Treehouse: an evaluation sandbox that observes, seals and scores agentic geospatial runs.'},
];

export function WorkingBackwards() {
  return <Slide id="backwards" className="backwards">
    <p className="eyebrow r">How we got here</p>
    <h2 className="r" style={d(1)}>We worked <em>backwards</em> from the analyst.</h2>
    <p className="press r" style={d(2)}><span>Our press-release headline, written first:</span>
      “ADB analysts can now trust — or reject — an AI-built asset map, with the evidence for every point.”</p>
    <ol className="chain">
      {BACKWARDS.map((b, i) => <li key={b.k} className="r" style={d(3 + i)}>
        <span className="step-k">{b.k}</span><span className="step-v">{b.v}</span>
      </li>)}
    </ol>
    <p className="source r" style={d(9)}>Amazon Working Backwards: start from the customer, then the press release, then the system.</p>
  </Slide>;
}

const PILLARS = [
  {n: 'Observe', icon: '◉', v: 'The agent must record a decision — why, alternatives, confidence — before the gateway lets any tool run.'},
  {n: 'Seal', icon: '▣', v: 'Each run is hash-chained and written once to S3 Object Lock. Not even an admin can rewrite it after scoring.'},
  {n: 'Score separately', icon: '◇', v: 'Reasoning, calibration and accuracy stay in separate panels. Blending them hides the failures ADB needs to see.'},
];

export function Solution() {
  return <Slide id="solution">
    <p className="eyebrow r">How we fix it</p>
    <h2 className="r" style={d(1)}>Make every agent run an <em>audit trail</em>.</h2>
    <div className="pillars">
      {PILLARS.map((p, i) => <article key={p.n} className="pillar r" style={d(2 + i)}>
        <span className="pillar-icon" aria-hidden="true">{p.icon}</span>
        <h3>{p.n}</h3><p>{p.v}</p>
      </article>)}
    </div>
    <p className="kicker r" style={d(6)}>Observe → summarize → score. The loop Clay asked for, on AWS, with the model and harness swappable by config.</p>
  </Slide>;
}

export function Impact() {
  return <Slide id="impact">
    <p className="eyebrow r">What changes</p>
    <h2 className="r" style={d(1)}>From a black box to <em>a list you can defend</em>.</h2>
    <div className="compare">
      <article className="card before r" style={d(2)}>
        <h3>Today</h3>
        <ul>
          <li>The agent says “10 warehouses”.</li>
          <li>No reasons, no evidence, an unchecked confidence.</li>
          <li>The analyst checks every point by hand, or doesn’t use it.</li>
        </ul>
      </article>
      <span className="compare-arrow r" style={d(3)} aria-hidden="true">→</span>
      <article className="card after r" style={d(4)}>
        <h3>With Treehouse</h3>
        <ul>
          <li>Each point links to the decision, tool and evidence behind it.</li>
          <li>Stated confidence is checked: unsupported claims are flagged, not hidden.</li>
          <li>The sealed record can be shown to a ministry or a partner.</li>
        </ul>
      </article>
    </div>
    <div className="impacts">
      <div className="stat r" style={d(5)}><b>Faster PDNA</b><span>Review only the flagged claims, not every point</span></div>
      <div className="stat r" style={d(6)}><b>Honest when blind</b><span>On real coarse Clay embeddings, all 4 live runs (Sonnet, Haiku) said <em>cannot assess</em> instead of guessing</span></div>
      <div className="stat r" style={d(7)}><b>&lt; $1 a run</b><span>Average recorded Bedrock cost of a live evaluated run: cheap enough to run on every agent</span></div>
    </div>
    <p className="source r" style={d(8)}>Live results: fixtures/live/real/ (4 real-data runs, 2026-11-05). Cost is the recorded Bedrock ledger, not an AWS bill.</p>
  </Slide>;
}

const ROADMAP = [
  {when: 'Now', title: 'Hackathon sandbox', items: ['ADB T1 warehouses: Nagoya, Gifu, Chattogram', 'Strands on Bedrock: Sonnet, Nova Pro, Haiku', 'AgentCore Evaluations + Lambda evaluators, S3 Object Lock']},
  {when: 'Next', title: 'ADB benchmark pilot', items: ['RODA MCP + Clay’s 99-server catalogue, discovered dynamically', 'Agent-chosen chips: Clay embeddings on demand', 'Bridges, fuel tanks, solar & wind; Manila, Port Vila, Kathmandu']},
  {when: 'Scale', title: 'Production on AWS', items: ['AgentCore Runtime + online evaluation: score every production run', 'Step Functions Distributed Map for model × area × seed matrices', 'S3 Vectors / Athena past a million embeddings; OTLP tracing to any backend']},
];

export function Future() {
  return <Slide id="future" className="future">
    <p className="eyebrow r">After release</p>
    <h2 className="r" style={d(1)}>From one sandbox to <em>every agent-built dataset</em>.</h2>
    <ol className="roadmap">
      {ROADMAP.map((p, i) => <li key={p.when} className="card r" style={d(2 + i)}>
        <span className="when">{p.when}</span><h3>{p.title}</h3>
        <ul>{p.items.map(x => <li key={x}>{x}</li>)}</ul>
      </li>)}
    </ol>
    <div className="deploy r" style={d(6)}>
      <h3>How it ships into a partner account</h3>
      <p>Two AWS CDK stacks redeploy the run store, key isolation and evaluators into any single account. Open source under Apache-2.0, like Clay’s releases.</p>
    </div>
    <p className="closing r" style={d(7)}>Clay narrows. Imagery determines. <strong>Evidence explains.</strong></p>
  </Slide>;
}
