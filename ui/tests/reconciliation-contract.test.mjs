// Independent acceptance authored/frozen before source repair. Node >=22.12; no network.
import {test, afterEach} from 'node:test';
import assert from 'node:assert/strict';
import {httpClient} from '../src/shell/http.ts';
import {exportFiles, summaryMarkdown} from '../src/shell/export.ts';

const sections = ['reasoning_rules', 'reviewer', 'agentcore', 'output', 'calibration', 'predicted_accuracy'];
const unavailable = reason => ({status: 'unavailable', value: null, reason});
const evaluation = Object.fromEntries(sections.map(k => [k, unavailable(`No recorded ${k} result`)]));
evaluation.reasoning_rules = {status:'available', value:{rules_version:'independent-1', passed_rules:['RV4']}, reason:null};
evaluation.output = {status:'method_test_only', value:{precision:0.5, unit:'160 m cells'}, reason:'Reference-derived synthetic embeddings demonstrate the method; no operational accuracy claim.'};
evaluation.reviewer = {status:'available', value:{source:'recorded-reviewer', verdict:'limited evidence'}, reason:null};
const reference = {
  run_id:'saved-method', title:'Saved method test', status:'complete', synthetic:false, mode:'replay',
  started_at:null, elapsed_ms:null, cost_usd:null,
  provenance:{embeddings:'synthetic_reference_derived', reference:'synthetic', vision:'not_used',
    limitations:['Reference-derived synthetic embeddings; method demonstration only.', 'No vision model was used.']},
  evaluation,
  input:{task_id:'task-one', title:'Saved method test', goal:'Find warehouses', aoi_bbox:[136.82,35.05,136.92,35.12], time_window:['2024-01-01','2024-12-31'], tools_allowed:['record_claim'], data_allowlist:[]},
  context:{model_id:'recorded-model', provider:'replay', harness:'plain_loop', system_prompt:null, items:[]},
  steps:[],
  markers:[{lon:136.85,lat:35.08,label:'warehouse',confidence:0.8,status:'present',at_ms:null,
    claim_id:'claim-1',trial_id:'t-0',evidence_refs:[{result_id:'result-7',role:'existence'}],decision_id:'decision-1'}],
};
const run = {run_id:'saved-method',title:'Saved method test',task_id:'task-one',mode:'replay',synthetic:false,status:'report_ready'};
const claim = {claim_id:'claim-1',run_id:run.run_id,trial_id:'t-0',step_id:'inventory',geometry:{type:'Point',coordinates:[136.85,35.08]},cls:'warehouse',status:'present',confidence:0.8,reason:'Recorded synthetic prediction',evidence_refs:reference.markers[0].evidence_refs,span_id:'claim-span',grounded:true,contaminated:false,synthetic:false,unresolved_refs:[]};
const panel = name => ({name,version:'independent-1',numbers:{},evidence_span_ids:{},no_grade_reason:'No independent grade'});
const bundle = {schema_version:'treehouse.bundle/1',manifest_ref:'sha256:fixture',card_ref:'task-one@sha256:fixture',summary:'Synthetic method fixture',synthetic:false,
  manifest_summary:{run_id:run.run_id,mode:'replay',task_ref:'task-one@sha256:fixture',backends:{worker:'replay'},key_isolation_statement:'local test',license_floor:'CC-BY-4.0',license_obligations:[],nc_notice:null},
  card_summary:{id:'task-one',version:'1',title:run.title,goal:'Find warehouses',synthetic_notice:null,license_floor:'CC-BY-4.0',license_obligations:[],known_limits:['Synthetic fixture'],steps:[]},
  scorecard:Object.fromEntries(['process','understanding','output','cost'].map(x=>[x,panel(x)]).concat([['versions',{}]])),
  passports:[],claims:[claim],evidence:[],ledgers:[],facts:{},trace_rows:[{trace_id:'trace',span_id:'chat',parent_span_id:null,name:'Model response',op:'chat',start_ns:1,end_ns:2,status:'ok',error:null,events:[],attributes:{'gen_ai.request.model':'recorded-model'}}]};
const investigation = {schema_version:'treehouse.investigation-report/1',run_id:run.run_id,manifest_ref:'sha256:fixture',decisions:[{decision_id:'decision-1',action_id:'action-1',tool:'record_claim',parameters:{},rationale:'Recorded support',alternatives:[],confidence:0.8,parent_id:null,evidence_refs:['result-7'],sequence:1,span_id:'decision-span',flags:[],trial_id:'t-0',action:{span_id:'claim-span',result_id:'result-8',status:'success',tool:'record_claim'}}],pathways:[],process:{numbers:{},limitations:['Synthetic fixture']},output:{numbers:{},no_grade_reason:'No reference'},confidence:{numbers:{},no_grade_reason:'No valid population'},summary:'Method fixture',synthetic:false};
const tasks = {tasks:[{preset_id:'preset-one',title:'Pinned one',goal:'Find warehouses',task_id:'task-one',task_ref:'task-one@sha256:fixture',mode:'replay',synthetic:false,tools:[],model_id:'model-one',harness:'plain_loop',tracers:[],budget:{},config:{}}]};
const originalFetch = globalThis.fetch;
afterEach(()=> {globalThis.fetch = originalFetch;});

function mockFetch({pending=false}={}) {
  const calls=[];
  globalThis.fetch = async (url, options={}) => {
    calls.push([String(url),options.method??'GET',options.body]);
    const path=String(url);
    const snapshot = pending ? {...reference,status:'running',steps:[],markers:[],evaluation:Object.fromEntries(sections.map(k=>[k,unavailable('Run is not sealed yet')]))} : reference;
    const routes = {
      '/api/tasks':tasks,
      '/api/runs':{runs:[run]},
      '/api/runs/saved-method':pending?{...run,status:'running'}:run,
      '/api/runs/saved-method/snapshot':snapshot,
      '/api/runs/saved-method/bundle':bundle,
      '/api/runs/saved-method/investigation':investigation,
      '/api/runs/saved-method/database':{type:'FeatureCollection',features:[{type:'Feature',geometry:claim.geometry,properties:{claim_id:claim.claim_id,trial_id:'t-0',cls:'warehouse',status:'present',agent_confidence:0.8,evidence_refs:claim.evidence_refs,decision_id:'decision-1',synthetic:false}}]},
    };
    if (path==='/api/runs' && options.method==='POST') return Response.json({run_id:'new-run',status:'queued'},{status:202});
    assert.ok(path in routes,`unexpected network request: ${path}`);
    return Response.json(routes[path]);
  };
  return calls;
}

test('HTTP adaptation preserves predicted presence rather than inventing confirmed truth',async()=>{
  mockFetch();
  const snapshot=await httpClient.snapshot('saved-method');
  assert.equal(snapshot.markers[0].status,'present');
});

test('selected prediction retains claim identity, recorded evidence and decision links',async()=>{
  mockFetch();
  const snapshot=await httpClient.snapshot('saved-method');
  for(const key of ['claim_id','trial_id','evidence_refs','decision_id']) assert.deepEqual(snapshot.markers[0][key],reference.markers[0][key],`lost ${key}`);
});

test('opening a saved run preserves replay provenance and all independent evaluation sections',async()=>{
  const calls=mockFetch();
  const saved=await httpClient.listRuns();
  const snapshot=await httpClient.snapshot(saved[0].run_id);
  assert.equal(snapshot.mode,'replay');
  assert.deepEqual(snapshot.provenance,reference.provenance);
  assert.deepEqual(snapshot.evaluation,reference.evaluation);
  assert.ok(calls.every(([,method])=>method==='GET'),'opening recorded history never starts a run');
});

test('missing cost and tokens are unavailable instead of fabricated zeros',async()=>{
  mockFetch();
  const snapshot=await httpClient.snapshot('saved-method');
  assert.equal(snapshot.cost_usd,null);
  for(const step of snapshot.steps.filter(x=>x.model)) {
    assert.equal(step.model.cost_usd,null);
    assert.equal(step.model.input_tokens,null);
    assert.equal(step.model.output_tokens,null);
  }
});

test('pending recorded replay stays partial with explicit evaluation availability',async()=>{
  mockFetch({pending:true});
  const snapshot=await httpClient.snapshot('saved-method');
  assert.equal(snapshot.status,'running');
  assert.equal(snapshot.cost_usd,null);
  assert.equal(snapshot.elapsed_ms,null);
  assert.deepEqual(snapshot.steps,[]);
  assert.deepEqual(snapshot.markers,[]);
  for(const name of sections) assert.deepEqual(snapshot.evaluation[name],unavailable('Run is not sealed yet'));
});

test('pinned preset rejects an edited goal before sending a different task',async()=>{
  const calls=mockFetch();
  await assert.rejects(()=>httpClient.startRun({place_id:'task-one',agent_id:'model-one|plain_loop',goal:'Find bridges instead'}),/preset|goal|read.only|configur/i);
  assert.ok(calls.every(([,method])=>method==='GET'),'edited goal must not silently launch old preset');
});

test('unchanged pinned preset can still launch its explicitly selected model and harness',async()=>{
  const calls=mockFetch();
  assert.equal(await httpClient.startRun({place_id:'task-one',agent_id:'model-one|plain_loop',goal:'Find warehouses'}),'new-run');
  assert.deepEqual(JSON.parse(calls.find(([,method])=>method==='POST')[2]),{preset_id:'preset-one'});
});

test('readable export labels method demonstrations and separates unavailable evaluations',()=>{
  const text=summaryMarkdown(structuredClone(reference),[]);
  assert.match(text,/replay/i);
  assert.match(text,/synthetic|method demonstration/i);
  assert.match(text,/vision.*not.*used|No vision model was used/i);
  for(const name of ['reasoning','reviewer','agentcore','calibration','predicted']) assert.match(text,new RegExp(name,'i'));
  assert.doesNotMatch(text,/\bconfirmed\b/i,'predicted presence is not a confirmed warehouse');
});

test('exported geometry keeps identity, status, evidence and decision links',()=>{
  const files=exportFiles({...structuredClone(reference),elapsed_ms:1000,cost_usd:0.25},[]);
  const feature=JSON.parse(files['markers.geojson']).features[0];
  assert.equal(feature.properties.status,'present');
  for(const key of ['claim_id','trial_id','evidence_refs','decision_id']) assert.deepEqual(feature.properties[key],reference.markers[0][key],`export lost ${key}`);
  const exported=JSON.parse(files['run.json']).run;
  assert.deepEqual(exported.evaluation,reference.evaluation);
  assert.deepEqual(exported.provenance,reference.provenance);
});


test('readable summary distinguishes absent and unassessable claims from found predictions',()=>{
  const snapshot={...structuredClone(reference),elapsed_ms:1000,cost_usd:0.25};
  snapshot.markers.push({...snapshot.markers[0],claim_id:'claim-absent',status:'absent'},
    {...snapshot.markers[0],claim_id:'claim-unknown',status:'cannot_assess'});
  const text=summaryMarkdown(snapshot,[]);
  assert.match(text,/present|predicted/i);
  assert.match(text,/absent/i);
  assert.match(text,/cannot.assess|unassessable/i);
  assert.doesNotMatch(text,/\bconfirmed\b/i);
});
