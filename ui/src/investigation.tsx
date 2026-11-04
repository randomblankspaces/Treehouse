import { useEffect, useRef } from 'react';
import {
  decodeDatabase, decodeInvestigation, type Bundle, type InvestigationDecision,
  type InvestigationReport, type Prediction, type TypedNumber,
} from './api.ts';
import { Badge, Link, Metric, State, useResource } from './components.tsx';
import { geographicPoints, runUrl, selection, type Route } from './state.ts';

type ChangeSelection = (changes: Record<string, string | null>) => void;

export function Investigation({route, bundle, update}: {route: Route; bundle: Bundle; update: ChangeSelection}) {
  const base = `/api/runs/${encodeURIComponent(route.runId!)}`;
  const report = useResource(base + '/investigation', decodeInvestigation);
  const database = useResource(base + '/database', decodeDatabase);
  const selected = route.params.get('decision');
  const activeDecision = useRef<HTMLElement>(null);
  const focusDecision = route.params.get('focus') === 'decision';
  useEffect(() => {
    if (selected && focusDecision && activeDecision.current) {
      activeDecision.current.focus();
      activeDecision.current.scrollIntoView({block: 'nearest', behavior: 'instant'});
    }
  }, [selected, focusDecision, report.data]);
  if (report.error) return <State title="Investigation report unavailable" error retry={report.retry}>{report.error} No decision pathway was inferred from the tool trace.</State>;
  if (!report.data) return <State title="Reading the sealed investigation">Decision explanations and action bindings are read separately from MCP trace activity.</State>;
  const data = report.data;
  if (data.run_id !== route.runId || data.manifest_ref !== bundle.manifest_ref) {
    return <State title="Investigation identity does not match this report" error>No records are displayed. Ask the operator to verify the sealed run.</State>;
  }
  const decisions = [...data.decisions].sort((a, b) => a.sequence - b.sequence || a.decision_id.localeCompare(b.decision_id));
  const decisionIds = new Set(decisions.map(d => d.decision_id));
  return <section className="investigation-view" aria-labelledby="investigation-title">
    <div className="section-heading"><div><h3 id="investigation-title">Investigation strategy &amp; decisions</h3><p>{data.summary}</p></div><Badge>{data.synthetic ? 'SYNTHETIC observations' : 'Sealed observations'}</Badge></div>
    <p className="notice">Rationale, alternatives and decision confidence are agent self-reports, not proof of hidden internal computation. This view evaluates observable decisions and final predictions separately from the MCP Trace.</p>
    {!decisions.length ? <State title="Decision explanations unavailable">This legacy run did not record contemporaneous investigation decisions. The trace remains available; no rationale, alternatives or pathway has been invented.</State> : <>
      <h4>Recorded decision pathway</h4>
      <ol className="pathway-list" aria-label="Recorded decision pathway">{data.pathways.map((path, index) => <li key={`${path.decision_id}:${index}`}>
        {path.parent_id ? <><span>From </span>{decisionIds.has(path.parent_id) ? <DecisionLink id={path.parent_id} route={route}/> : <span>{path.parent_id} (unresolved parent)</span>}<span> → </span></> : <span>Root → </span>}
        <DecisionLink id={path.decision_id} route={route}/><span> · action {path.action_id ?? 'not linked'} · result {path.result_id ?? 'not linked'}</span>
      </li>)}</ol>
      <ol className="decision-records" aria-label="Chronological investigation decisions">{decisions.map(d => <li key={d.decision_id}>
        <article ref={d.decision_id === selected ? activeDecision : undefined} tabIndex={-1} id={`decision-${encodeURIComponent(d.decision_id)}`} className={`decision-record${selected === d.decision_id ? ' selected-decision' : ''}${d.parent_id ? ' child-decision' : ''}`} data-decision-id={d.decision_id}>
          <div className="section-heading"><div><h4><DecisionLink id={d.decision_id} route={route}/></h4><p className="mono">Sequence {d.sequence} · {d.trial_id ?? 'Trial not supplied'} · action {d.action_id}</p></div><Badge>{d.action?.status ?? 'No linked action'}</Badge></div>
          <dl><dt>Chosen tool</dt><dd>{d.tool}</dd><dt>Rationale (agent self-report)</dt><dd>{d.rationale}</dd><dt>Decision confidence</dt><dd>{d.confidence} · agent self-reported; not a calibrated probability</dd><dt>Prior evidence references</dt><dd>{d.evidence_refs.length ? d.evidence_refs.map(ref => <EvidenceLink key={ref} resultId={ref} trialId={d.trial_id} route={route} bundle={bundle}/>) : 'No prior evidence cited.'}</dd><dt>Parent / revision link</dt><dd>{d.parent_id ? (decisionIds.has(d.parent_id) ? <DecisionLink id={d.parent_id} route={route}/> : `${d.parent_id} (unresolved)`) : 'Root decision; no parent recorded.'}</dd><dt>Actual action outcome</dt><dd>{d.action ? `${d.action.status} · ${d.action.tool} · result ${d.action.result_id ?? 'not returned'} · span ${d.action.span_id}` : 'No matching executed action was established.'}</dd><dt>Decision flags</dt><dd>{d.flags.length ? d.flags.join('; ') : 'No linkage flags reported. This does not grade semantic reasoning quality.'}</dd></dl>
          <h5>Alternatives actually recorded</h5>{d.alternatives.length ? <ul>{d.alternatives.map((a, index) => <li key={index}><strong>{a.option}</strong>: {a.reason}</li>)}</ul> : <p>No alternatives were recorded; none have been inferred.</p>}
          <details><summary>Recorded tool parameters</summary><p>Only explicitly recorded parameters are shown. An absent model ID or region is not inferred.</p><pre>{JSON.stringify(d.parameters, null, 2)}</pre><p className="mono">Decision source span: {d.span_id}</p></details>
        </article>
      </li>)}</ol>
    </>}
    <ObservedModels bundle={bundle}/>
    <p className="notice">Semantic reasoning quality: Not assessed. No stored independent rubric review is loaded in this view. Decision counts, linkage checks and fluent explanations do not establish logical or semantic quality.</p>
    <div className="investigation-assessments">
      <Assessment title="Observable process diagnostics" numbers={data.process.numbers}/>
      <section className="evaluation-panel"><h4>Coverage, failures &amp; assessment limits</h4><ul>{data.process.limitations.map((limit, i) => <li key={i}>{limit}</li>)}</ul><p>Tool counts are context, not a measure of reasoning quality. No human baseline or composite score is invented.</p></section>
      <Assessment title="Final database catalogue matching" numbers={data.output.numbers} reason={data.output.no_grade_reason}/>
      <Assessment title="Confidence calibration" numbers={data.confidence.numbers} reason={data.confidence.no_grade_reason}/>
      {data.cost ? <Assessment title="Cost &amp; speed of the investigation" numbers={data.cost.numbers} reason={data.cost.no_grade_reason}/> : <State title="Investigation cost accounting not supplied">Inspect the existing Cost, Speed &amp; Data panel. Unavailable costs are not treated as zero.</State>}
    </div>
    {data.output.reference && <details><summary>Grading reference provenance and scope</summary><p>Reference features and held-out labels are not returned to this page. Catalogue matching does not establish image-model accuracy or a complete real-world inventory.</p><pre>{JSON.stringify(data.output.reference, null, 2)}</pre>{data.output.unmatched_to_adjudicate != null && <p>Unmatched predictions to adjudicate: {data.output.unmatched_to_adjudicate}.</p>}</details>}
    {database.error ? <State title="Prediction database unavailable" error retry={database.retry}>{database.error}</State> : !database.data ? <State title="Reading the prediction database"/> : <PredictionView features={database.data.features} report={data} route={route} update={update} bundle={bundle}/>}
  </section>;
}

function DecisionLink({id, route}: {id: string; route: Route}) {
  return <Link href={runUrl(route.runId!, 'atlas', selection(route.params, {pane: 'investigation', decision: id, focus: 'decision'}))}>{id}</Link>;
}
function EvidenceLink({resultId, trialId, route, bundle}: {resultId: string; trialId?: string; route: Route; bundle: Bundle}) {
  const available = bundle.evidence.some(e => e.result_id === resultId);
  return available ? <Link href={runUrl(route.runId!, 'atlas', selection(route.params, {pane: 'evidence', evidence: resultId, trial: trialId ?? null}))}>{resultId} (imagery metadata)</Link> : <span className="evidence-reference">{resultId} · prior tool result; imagery metadata not available in this bundle</span>;
}
function Assessment({title, numbers, reason}: {title: string; numbers: Record<string, TypedNumber>; reason?: string | null}) {
  return <section className="evaluation-panel"><h4>{title}</h4>{reason && <p className="notice">Not assessed / limited: {reason}</p>}{Object.values(numbers).map(number => <Metric key={number.metric} number={number}/>)}{!Object.keys(numbers).length && !reason && <p>Not assessed. No measurement was issued.</p>}</section>;
}
function PredictionView({features, report, route, update, bundle}: {features: Prediction[]; report: InvestigationReport; route: Route; update: ChangeSelection; bundle: Bundle}) {
  const points = geographicPoints(features.map(f => ({center: f.geometry})));
  const selected = features.find(f => f.properties.claim_id === route.params.get('claim') && (!route.params.get('trial') || f.properties.trial_id === route.params.get('trial')));
  const choose = (f: Prediction) => update({claim: f.properties.claim_id, trial: f.properties.trial_id, decision: f.properties.decision_id, focus: null, evidence: f.properties.evidence_refs[0]?.result_id ?? null});
  const actualDecision: InvestigationDecision | undefined = report.decisions.find(d => d.decision_id === selected?.properties.decision_id);
  return <section className="prediction-database" aria-labelledby="prediction-title"><div className="section-heading"><div><h3 id="prediction-title">Final geographic prediction database</h3><p>Red markers are positive agent predictions, not confirmed truth. Clay candidate stars are a separate layer with no invented nearest-cell join.</p></div><Badge>Geographic · EPSG:4326 lon/lat</Badge></div>
    {!features.length ? <State title="No positive predictions">The verified database has no present, intact, damaged or destroyed claims. Absence of predictions does not establish absence of real features.</State> : <>
      <div className="prediction-map"><svg viewBox="0 0 800 420" role="group" aria-label="Geographic map of positive agent predictions"><defs><pattern id="prediction-grid" width="80" height="70" patternUnits="userSpaceOnUse"><path d="M80 0H0V70" fill="none" stroke="#365169"/></pattern></defs><rect width="800" height="420" fill="url(#prediction-grid)"/>{features.map((f, index) => {const p = f.properties; const position = points[index]; const active = selected === f; return <g key={`${p.trial_id}:${p.claim_id}`} role="button" tabIndex={0} aria-label={`Prediction marker ${p.claim_id}, trial ${p.trial_id}, ${p.cls}, ${p.status}, agent self-reported confidence ${p.agent_confidence}, longitude ${f.geometry.coordinates[0]}, latitude ${f.geometry.coordinates[1]}`} aria-pressed={active} onClick={() => choose(f)} onKeyDown={e => {if (e.key === 'Enter' || e.key === ' ') {e.preventDefault(); choose(f);}}}><circle cx={position.x} cy={position.y} r="22" fill="transparent"/><path d={`M${position.x} ${position.y - 10}l8 8-8 12-8-12z`} fill="#ff655c" stroke={active ? '#fff' : '#ffaaa4'} strokeWidth={active ? 3 : 1.5}/><text x={position.x + 14} y={position.y - 12} fill="#f4f6fa" fontSize="12">{p.claim_id}</text></g>;})}<text x="20" y="400" fill="#c3d1e0" fontSize="12">Longitude → · Latitude ↑ · geographic extent fitted to predictions</text></svg></div>
      <div className="table-scroll"><table><caption>Positive prediction database; coordinates are copied from sealed claims. Confidence is the agent's self-report.</caption><thead><tr><th scope="col">Claim / trial</th><th scope="col">Class / predicted status</th><th scope="col">Longitude / latitude</th><th scope="col">Agent confidence</th><th scope="col">Decision / evidence</th></tr></thead><tbody>{features.map(f => {const p = f.properties; return <tr key={`${p.trial_id}:${p.claim_id}`} className={selected === f ? 'selected-row' : ''}><th scope="row"><button className="text-button" onClick={() => choose(f)} aria-pressed={selected === f}>{p.claim_id}</button><span className="cell-detail">{p.trial_id}{p.synthetic ? ' · SYNTHETIC' : ''}</span></th><td>{p.cls} / {p.status}</td><td>{f.geometry.coordinates.join(', ')}</td><td>{p.agent_confidence} · self-reported</td><td>{p.decision_id ? <DecisionLink id={p.decision_id} route={route}/> : 'No decision association recorded.'}{p.evidence_refs.map((ref, i) => <EvidenceLink key={i} resultId={ref.result_id} trialId={p.trial_id} route={route} bundle={bundle}/>)}</td></tr>;})}</tbody></table></div>
    </>}
    {selected && <aside className="selection-detail" aria-label="Selected prediction"><h4>Selected claim {selected.properties.claim_id}</h4><p>Trial {selected.properties.trial_id}; {selected.properties.cls}; predicted {selected.properties.status}; coordinate {selected.geometry.coordinates.join(', ')}.</p><p>Agent self-reported confidence: {selected.properties.agent_confidence}. This is not a keyed accuracy or calibrated probability.</p><p>Linked decision: {actualDecision ? <DecisionLink id={actualDecision.decision_id} route={route}/> : selected.properties.decision_id ? `${selected.properties.decision_id} (not resolved in this report)` : 'No verified decision association recorded.'}</p>{actualDecision && <p>Decision rationale (agent self-report): {actualDecision.rationale}</p>}</aside>}
  </section>;
}

function ObservedModels({bundle}: {bundle: Bundle}) {
  const rows = bundle.trace_rows.filter(span => span.attributes['gen_ai.request.model'] || span.attributes['gen_ai.response.model'] || span.attributes['treehouse.classifier.model_id']);
  return <section className="recorded-models"><h4>Observed model calls &amp; execution settings</h4><p>Values below come from recorded span metadata. Missing settings or region are not inferred from a planned action or installed SDK.</p>{rows.length ? <div className="table-scroll"><table><caption>Recorded models and source spans</caption><thead><tr><th scope="col">Model / provider</th><th scope="col">Settings / region</th><th scope="col">Source span</th></tr></thead><tbody>{rows.map(span => <tr key={span.span_id}><td>{String(span.attributes['treehouse.classifier.model_id'] ?? span.attributes['gen_ai.response.model'] ?? span.attributes['gen_ai.request.model'])}<span className="cell-detail">{String(span.attributes['gen_ai.provider.name'] ?? 'Provider not recorded')}</span></td><td>Max tokens: {String(span.attributes['gen_ai.request.max_tokens'] ?? 'not recorded')}; temperature: {String(span.attributes['gen_ai.request.temperature'] ?? 'not recorded')}<span className="cell-detail">Region: {String(span.attributes['cloud.region'] ?? span.attributes['aws.region'] ?? 'not recorded')}</span></td><td className="mono">{span.span_id}</td></tr>)}</tbody></table></div> : <p>No model ID, settings or region metadata was recorded in the public trace.</p>}</section>;
}
