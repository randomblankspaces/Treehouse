/** The same per-run evaluation and evidence appear in both shell views. */
import { EVALUATIONS, type MapMarker, type RunSnapshot } from './contract.ts';

const LABELS = {reasoning_rules: 'Reasoning rules', reviewer: 'Independent model reviewer', agentcore: 'AgentCore evaluation',
  output: 'Final output quality', calibration: 'Confidence calibration', predicted_accuracy: 'Predicted accuracy'};
export const money = (value: number | null) => value === null ? 'unavailable' : `$${value.toFixed(4)}`;
export const tokenTotal = (run: RunSnapshot) => {
  const models = run.steps.flatMap(s => s.model ? [s.model] : []);
  return models.length && models.every(m => m.input_tokens !== null && m.output_tokens !== null)
    ? models.reduce((total, m) => total + m.input_tokens! + m.output_tokens!, 0).toLocaleString() : 'unavailable';
};

export function EvaluationPanels({snap}: {snap: RunSnapshot}) {
  return <section className="run-evaluation">
    <h3>Recorded rationale summary</h3>
    <p className="recorded-summary">{snap.thinking_summary?.status === 'available' ? snap.thinking_summary.text : snap.thinking_summary?.reason ?? 'No contemporaneous decision summary is available. Hidden reasoning cannot be recovered.'}</p>
    <h3>Independent evaluation</h3>
    <p>Execution: <b>{snap.mode}</b> · embeddings: {snap.provenance.embeddings} · reference: {snap.provenance.reference} · vision: {snap.provenance.vision}</p>
    <ul>{snap.provenance.limitations.map((text, i) => <li key={i}>{text}</li>)}</ul>
    {EVALUATIONS.map(name => { const e = snap.evaluation[name]; return <section key={name}>
      <h4>{LABELS[name]} · {e.status.replaceAll('_', ' ')}</h4>
      {e.reason && <p>{e.reason}</p>}
      {e.scores?.length ? <table>
        <caption>{LABELS[name]} measurements and evaluated population</caption>
        <thead><tr><th scope="col">Metric</th><th scope="col">Value</th><th scope="col">Population and basis</th></tr></thead>
        <tbody>{e.scores.map((score, i) => <tr key={i}>
          <th scope="row">{score.metric.replaceAll('_', ' ')}{score.trial_id ? ` (${score.trial_id})` : ''}</th>
          <td>{score.value === null ? 'unavailable' : `${Number(score.value.toFixed(3))}${score.unit === 'percent' ? '%' : ' raw'}`} · {score.status.replaceAll('_', ' ')}</td>
          <td>{score.numerator !== null && score.denominator !== null ? `${score.numerator} / ${score.denominator}. ` : score.denominator !== null ? `${score.denominator} observations. ` : ''}{score.basis}{score.reason ? ` ${score.reason}` : ''}</td>
        </tr>)}</tbody>
      </table> : <p>No numeric score is available for this section.</p>}
      {e.value !== null && <details><summary>Inspect raw {LABELS[name].toLowerCase()} evidence</summary><pre>{JSON.stringify(e.value, null, 2)}</pre></details>}
    </section>; })}
  </section>;
}

export function PredictionEvidence({snap, selected, onSelect}: {snap: RunSnapshot; selected: string | null; onSelect: (id: string) => void}) {
  const marker: MapMarker | undefined = snap.markers.find(m => `${m.trial_id}:${m.claim_id}` === selected) ?? snap.markers[0];
  const traceLink = (span: string) => `/dev?run=${encodeURIComponent(snap.run_id)}&step=${encodeURIComponent(span)}`;
  const decision = marker && snap.steps.find(s => s.decision_id === marker.decision_id && (!s.trial_id || s.trial_id === marker.trial_id));
  return <section className="prediction-evidence">
    <h3>Recorded predictions</h3>
    {!marker ? <p>No recorded predictions are available.</p> : <>
      <label htmlFor="prediction-select">Select a prediction</label>
      <select id="prediction-select" value={`${marker.trial_id}:${marker.claim_id}`} onChange={e => onSelect(e.target.value)}>
        {snap.markers.map(m => <option key={`${m.trial_id}:${m.claim_id}`} value={`${m.trial_id}:${m.claim_id}`}>{m.label} · {m.status} · {m.claim_id}</option>)}
      </select>
      <p>{marker.label}: <b>{marker.status}</b> at {marker.lon}, {marker.lat}. Self-reported confidence: {marker.confidence === null ? 'unavailable' : `${Math.round(marker.confidence * 100)}%`}.</p>
      <p>Claim {marker.claim_id} · trial {marker.trial_id}</p>
      <p>{decision ? <a href={traceLink(decision.span_id)}>Decision {marker.decision_id}</a> : marker.decision_id ? `Decision ${marker.decision_id}; linked trace unavailable.` : 'No contemporaneous decision is recorded.'}</p>
      {decision?.decision && <p>{decision.decision.rationale}</p>}
      <h4>Recorded support</h4>
      {marker.evidence_refs.length ? <ul>{marker.evidence_refs.map((ref, i) => {
        const step = snap.steps.find(s => s.tool?.result === ref.result_id && (!s.trial_id || s.trial_id === marker.trial_id));
        return <li key={i}>{step ? <a href={traceLink(step.span_id)}>{ref.result_id} · {ref.role}</a> : `${ref.result_id} · ${ref.role}; trace unavailable`}</li>;
      })}</ul> : <p>No evidence references were recorded for this prediction.</p>}
    </>}
  </section>;
}
