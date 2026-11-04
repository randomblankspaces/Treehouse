/** Public-view contract; Python validates authoritative records before projecting this JSON. */
export type Json = null | boolean | number | string | Json[] | {[key:string]:Json};
export type Capability = {id:string;label:string;status:'available'|'offline_demo'|'not_configured'|'unsupported';reason:string};
export type Capabilities = {schema_version:'treehouse.ui/1';execution:'offline';capabilities:Capability[];limits:{max_parallel_runs:number};judge_url:string|null};
export type Run = {run_id:string;title:string;task_id:string;mode:string;synthetic:boolean;status:'report_ready'|'sealed'|'running'|'queued'|'failed';message?:string};
export type Task = {preset_id:string;title:string;goal:string;task_id:string;task_ref:string;mode:'replay';synthetic:boolean;tools:string[];model_id:string;harness:string;tracers:string[];budget:Record<string,Json>;config:Record<string,Json>};
export type Point = {type:'Point';coordinates:[number,number]};
export type TypedNumber = {metric:string;value:number|null;type:string;tier:'KEYED'|'GOLD-ANCHORED'|'CALIBRATED-TRANSFER'|'MODEL-ESTIMATED'|'ABSTAINED'|'MEASURED';panel:string;n:number|null;n_gold?:number|null;n_verified?:number|null;abstention_rate?:number|null;interval:{lo:number;hi:number;level:number;method:string}|null;estimator_version:string;manifest_ref:string;reasons:string[];synthetic:boolean;replayed:boolean;detail:Record<string,Json>};
export type Panel = {name:string;version:string;numbers:Record<string,TypedNumber>;evidence_span_ids:Record<string,string[]>;no_grade_reason:string|null};
export type Claim = {claim_id:string;run_id:string;trial_id:string;step_id:string;geometry:Point;cls:string;status:string;confidence:number;reason:string;evidence_refs:{result_id:string;role:string}[];span_id:string;grounded:boolean;contaminated:boolean;synthetic:boolean;unresolved_refs:string[]};
export type Evidence = {result_id:string;source_id:string;scene_id:string;scene_datetime:string;bbox_requested:number[];bbox_read:number[];footprint_coverage_fraction:number;nominal_gsd_m:number;pixel_spacing_m:number;effective_gsd_m:number;bytes_read:number;requests:number;scene_cloud_pct:number;reader:string;license:string;synthetic:boolean;detail:Record<string,Json>;obscuration:{bright_lowvar_fraction:number;nodata_fraction:number;method:string};pixel_sha256:string;out_shape:number[];phase:string|null};
export type Span = {trace_id:string;span_id:string;parent_span_id:string|null;name:string;op:string;start_ns:number;end_ns:number;status:string;error:{source:string;type:string;message:string}|null;attributes:Record<string,Json>;events:Json[]};
export type Passport = {headline:TypedNumber;gate:'Rely'|'Spot-check'|'Do not rely';gate_reasons:string[];estimator_version:string;beat_baseline:string;sample_design_id:string;manifest_ref:string;alternatives:TypedNumber[];n_gold_cannot_assess:number;controls:Record<string,Json>;synthetic:boolean};
export type Bundle = {schema_version:'treehouse.bundle/1';manifest_ref:string;manifest_summary:{run_id:string;mode:string;task_ref:string;backends:Record<string,string>;key_isolation_statement:string;license_floor:string;license_obligations:string[];nc_notice:string|null};card_ref:string;card_summary:{id:string;version:string;title:string;goal:string;synthetic_notice:string|null;license_floor:string;license_obligations:string[];known_limits:string[];steps:{step_id:string;question_id:string;keying_mode:string;completeness_caveat:string|null}[]};scorecard:{process:Panel;understanding:Panel;output:Panel;cost:Panel;versions:Record<string,string>};passports:Passport[];claims:Claim[];evidence:Evidence[];ledgers:{claim_id:string;resolved:string;resolved_by:string|null;results:Json[]}[];trace_rows:Span[];facts:Record<string,TypedNumber>;summary:string;synthetic:boolean};
export type Cell = {cell_id:string;center:Point;similarity:number};
export type Coverage = {source:string;cell_m:number;date_range:string[];predates_event:boolean;aoi_cells_expected:number;aoi_cells_present:number;smallest_resolvable_m:number;synthetic:boolean};
export type Search = {search_id:string;trial_id:string;span_id:string;result_id:string;trace_ref:string;result:{cells:Cell[];coverage:Coverage}};
export type Searches = {searches:Search[];unavailable_reason?:string};
export type Event = {event_id:string;run_id:string;sequence:number;trial_id:string;span_id:string;time_ns:number;type:string;name:string;status:string;tool_name?:string};
export type Events = {events:Event[];next_cursor:number;source:'recorded_trace';complete:boolean};
export type Verification = {ok:boolean;scope:'sealed_run_and_evaluation_ledger';manifest_ref:string|null;ledger_head:string;problems:string[];bundle_source:'reconstructed_from_verified_records'};

function fail():never {throw new Error('The server returned an unsupported or malformed record. No results were displayed.');}
function obj(v:unknown):Record<string,unknown>{if(!v||typeof v!=='object'||Array.isArray(v))fail();return v as Record<string,unknown>;}
function str(v:unknown):asserts v is string{if(typeof v!=='string')fail();}
function num(v:unknown):asserts v is number{if(typeof v!=='number'||!Number.isFinite(v))fail();}
function bool(v:unknown):asserts v is boolean{if(typeof v!=='boolean')fail();}
function arr(v:unknown,check:(v:unknown)=>void):asserts v is unknown[]{if(!Array.isArray(v))fail();v.forEach(check);}
function strings(v:unknown){arr(v,str);}
function fields(v:unknown,keys:string[],check:(v:unknown)=>void){const r=obj(v);keys.forEach(k=>check(r[k]));return r;}
function choice(v:unknown,options:string[]){if(!options.includes(String(v)))fail();}
function nullable(v:unknown,check:(v:unknown)=>void){if(v!==null&&v!==undefined)check(v);}
function point(v:unknown){const p=obj(v);if(p.type!=='Point')fail();arr(p.coordinates,num);if(p.coordinates.length!==2)fail();}
function typed(v:unknown){const r=fields(v,['metric','type','panel','estimator_version','manifest_ref'],str);nullable(r.value,num);if(r.value===undefined)fail();choice(r.tier,['KEYED','GOLD-ANCHORED','CALIBRATED-TRANSFER','MODEL-ESTIMATED','ABSTAINED','MEASURED']);nullable(r.n,num);nullable(r.n_gold,num);nullable(r.n_verified,num);nullable(r.abstention_rate,num);strings(r.reasons);bool(r.synthetic);bool(r.replayed);obj(r.detail);if(r.interval){const i=fields(r.interval,['lo','hi','level'],num);str(i.method);}}
function panel(v:unknown){const r=fields(v,['name','version'],str);Object.values(obj(r.numbers)).forEach(typed);nullable(r.no_grade_reason,str);obj(r.evidence_span_ids);}
function claim(v:unknown){const r=fields(v,['claim_id','run_id','trial_id','step_id','cls','status','reason','span_id'],str);point(r.geometry);num(r.confidence);['grounded','contaminated','synthetic'].forEach(k=>bool(r[k]));strings(r.unresolved_refs);arr(r.evidence_refs,x=>fields(x,['result_id','role'],str));}
function evidence(v:unknown){const r=fields(v,['result_id','source_id','scene_id','scene_datetime','reader','license','pixel_sha256'],str);fields(r,['footprint_coverage_fraction','nominal_gsd_m','pixel_spacing_m','effective_gsd_m','bytes_read','requests','scene_cloud_pct'],num);arr(r.bbox_requested,num);arr(r.bbox_read,num);arr(r.out_shape,num);bool(r.synthetic);obj(r.detail);fields(r.obscuration,['bright_lowvar_fraction','nodata_fraction'],num);}
function span(v:unknown){const r=fields(v,['trace_id','span_id','name','op','status'],str);fields(r,['start_ns','end_ns'],num);nullable(r.parent_span_id,str);obj(r.attributes);arr(r.events,()=>{});if(r.error)fields(r.error,['source','type','message'],str);}
function passport(v:unknown){const r=fields(v,['gate','estimator_version','beat_baseline','sample_design_id','manifest_ref'],str);choice(r.gate,['Rely','Spot-check','Do not rely']);typed(r.headline);strings(r.gate_reasons);arr(r.alternatives,typed);num(r.n_gold_cannot_assess);obj(r.controls);bool(r.synthetic);}
function run(v:unknown){const r=fields(v,['run_id','title','task_id','mode'],str);choice(r.status,['report_ready','sealed','running','queued','failed']);bool(r.synthetic);nullable(r.message,str);}
export function decodeBundle(v:unknown):Bundle{const b=obj(v);if(b.schema_version!=='treehouse.bundle/1')fail();fields(b,['manifest_ref','card_ref','summary'],str);const m=fields(b.manifest_summary,['run_id','mode','task_ref','key_isolation_statement','license_floor'],str);Object.values(obj(m.backends)).forEach(str);strings(m.license_obligations);nullable(m.nc_notice,str);const c=fields(b.card_summary,['id','version','title','goal','license_floor'],str);strings(c.known_limits);strings(c.license_obligations);nullable(c.synthetic_notice,str);arr(c.steps,x=>{const r=fields(x,['step_id','question_id','keying_mode'],str);nullable(r.completeness_caveat,str);});const sc=obj(b.scorecard);['process','understanding','output','cost'].forEach(k=>panel(sc[k]));obj(sc.versions);arr(b.passports,passport);arr(b.claims,claim);arr(b.evidence,evidence);arr(b.trace_rows,span);arr(b.ledgers,x=>{const r=fields(x,['claim_id','resolved'],str);nullable(r.resolved_by,str);arr(r.results,()=>{});});Object.values(obj(b.facts)).forEach(typed);bool(b.synthetic);return b as unknown as Bundle;}
export function decodeSearches(v:unknown):Searches{const r=obj(v);arr(r.searches,x=>{const s=fields(x,['search_id','trial_id','span_id','result_id','trace_ref'],str);const result=obj(s.result);arr(result.cells,x=>{const c=fields(x,['cell_id'],str);point(c.center);num(c.similarity);});const c=fields(result.coverage,['source'],str);fields(c,['cell_m','aoi_cells_expected','aoi_cells_present','smallest_resolvable_m'],num);strings(c.date_range);bool(c.predates_event);bool(c.synthetic);});nullable(r.unavailable_reason,str);return r as unknown as Searches;}
export function decodeCapabilities(v:unknown):Capabilities{const r=obj(v);if(r.schema_version!=='treehouse.ui/1'||r.execution!=='offline')fail();arr(r.capabilities,x=>{const c=fields(x,['id','label','reason'],str);choice(c.status,['available','offline_demo','not_configured','unsupported']);});num(obj(r.limits).max_parallel_runs);if(r.judge_url!==null&&r.judge_url!=='/judge'&&r.judge_url!=='/judge/')fail();return r as unknown as Capabilities;}
export function decodeRuns(v:unknown):{runs:Run[]}{const r=obj(v);arr(r.runs,run);return r as unknown as {runs:Run[]};}
export function decodeRun(v:unknown):Run{run(v);return v as Run;}
export function decodeTasks(v:unknown):{tasks:Task[]}{const r=obj(v);arr(r.tasks,x=>{const t=fields(x,['preset_id','title','goal','task_id','task_ref','model_id','harness'],str);if(t.mode!=='replay')fail();bool(t.synthetic);strings(t.tools);strings(t.tracers);obj(t.budget);obj(t.config);});return r as unknown as {tasks:Task[]};}
export function decodeVerify(v:unknown):Verification{const r=obj(v);bool(r.ok);if(r.scope!=='sealed_run_and_evaluation_ledger'||r.bundle_source!=='reconstructed_from_verified_records')fail();nullable(r.manifest_ref,str);str(r.ledger_head);strings(r.problems);return r as unknown as Verification;}
export function decodeEvents(v:unknown):Events{const r=obj(v);if(r.source!=='recorded_trace')fail();num(r.next_cursor);bool(r.complete);arr(r.events,x=>{const e=fields(x,['event_id','run_id','trial_id','span_id','type','name','status'],str);num(e.sequence);num(e.time_ns);nullable(e.tool_name,str);});return r as unknown as Events;}
export function decodeStarted(v:unknown):{run_id:string;status:string}{const r=fields(v,['run_id','status'],str);choice(r.status,['queued','running']);return r as {run_id:string;status:string};}
export async function request<T>(url:string,decode:(data:unknown)=>T,signal?:AbortSignal,body?:unknown):Promise<T>{const response=await fetch(url,{signal,method:body?'POST':'GET',headers:body?{'Content-Type':'application/json'}:undefined,body:body?JSON.stringify(body):undefined});const data:unknown=await response.json();if(!response.ok){const detail=obj(data).detail;throw new Error(typeof detail==='string'?detail:'The request could not be completed.');}return decode(data);}

export type InvestigationDecision = {
  decision_id: string; action_id: string; tool: string; parameters: Record<string, Json>;
  rationale: string; alternatives: {option: string; reason: string}[]; confidence: number;
  parent_id: string | null; evidence_refs: string[]; sequence: number; span_id: string;
  flags: string[]; trial_id?: string;
  action: {span_id: string; result_id: string | null; status: string; tool: string} | null;
};
export type InvestigationReport = {
  schema_version: 'treehouse.investigation-report/1'; run_id: string; manifest_ref: string;
  decisions: InvestigationDecision[];
  pathways: {decision_id: string; parent_id: string | null; action_id: string | null; result_id: string | null}[];
  process: {numbers: Record<string, TypedNumber>; limitations: string[]};
  output: {numbers: Record<string, TypedNumber>; no_grade_reason: string | null; reference?: Record<string, Json> | null; unmatched_to_adjudicate?: number | null};
  confidence: {numbers: Record<string, TypedNumber>; no_grade_reason: string | null};
  cost?: {numbers: Record<string, TypedNumber>; no_grade_reason: string | null};
  summary: string; synthetic: boolean;
};
export type Prediction = {
  type: 'Feature'; geometry: Point;
  properties: {claim_id: string; trial_id: string; cls: string; status: string; agent_confidence: number;
    evidence_refs: {result_id: string; role: string}[]; decision_id: string | null; synthetic: boolean};
};
export type PredictionDatabase = {type: 'FeatureCollection'; features: Prediction[]};
function jsonValue(v: unknown): void {
  if (v === null || typeof v === 'string' || typeof v === 'boolean') return;
  if (typeof v === 'number') return num(v);
  if (Array.isArray(v)) return v.forEach(jsonValue);
  Object.values(obj(v)).forEach(jsonValue);
}
export function decodeInvestigation(v: unknown): InvestigationReport {
  const r = fields(v, ['run_id', 'manifest_ref', 'summary'], str);
  if (r.schema_version !== 'treehouse.investigation-report/1') fail();
  bool(r.synthetic);
  arr(r.decisions, item => {
    const d = fields(item, ['decision_id', 'action_id', 'tool', 'rationale', 'span_id'], str);
    Object.values(obj(d.parameters)).forEach(jsonValue);
    num(d.confidence); if (d.confidence < 0 || d.confidence > 1) fail();
    num(d.sequence); if (!Number.isSafeInteger(d.sequence) || d.sequence < 0) fail();
    if (d.parent_id !== null) str(d.parent_id);
    strings(d.evidence_refs); strings(d.flags); nullable(d.trial_id, str);
    arr(d.alternatives, a => fields(a, ['option', 'reason'], str));
    if (d.action !== null) {
      const a = fields(d.action, ['span_id', 'status', 'tool'], str);
      if (a.result_id !== null) str(a.result_id);
    }
  });
  arr(r.pathways, item => {
    const p = fields(item, ['decision_id'], str);
    ['parent_id', 'action_id', 'result_id'].forEach(key => { if (p[key] !== null) str(p[key]); });
  });
  const process = obj(r.process); Object.values(obj(process.numbers)).forEach(typed); strings(process.limitations);
  for (const key of ['output', 'confidence', ...(r.cost === undefined ? [] : ['cost'])]) {
    const panel = obj(r[key]); Object.values(obj(panel.numbers)).forEach(typed);
    if (panel.no_grade_reason !== null) str(panel.no_grade_reason);
  }
  return r as unknown as InvestigationReport;
}
export function decodeDatabase(v: unknown): PredictionDatabase {
  const db = obj(v); if (db.type !== 'FeatureCollection') fail();
  const ids = new Set<string>();
  arr(db.features, item => {
    const f = obj(item); if (f.type !== 'Feature') fail(); point(f.geometry);
    const coordinates = obj(f.geometry).coordinates as number[];
    if (Math.abs(coordinates[0]) > 180 || Math.abs(coordinates[1]) > 90) fail();
    const p = fields(f.properties, ['claim_id', 'trial_id', 'cls', 'status'], str);
    choice(p.status, ['present', 'intact', 'damaged', 'destroyed']);
    num(p.agent_confidence); if (p.agent_confidence < 0 || p.agent_confidence > 1) fail();
    if (p.decision_id !== null) str(p.decision_id); bool(p.synthetic);
    arr(p.evidence_refs, ref => fields(ref, ['result_id', 'role'], str));
    const id = `${p.trial_id}\u0000${p.claim_id}`; if (ids.has(id)) fail(); ids.add(id);
  });
  return db as unknown as PredictionDatabase;
}
