// R1 independent display acceptance: actual React report HTML and readable exports, no server/model.
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {transformWithOxc} from 'vite';
import {exportFiles, summaryMarkdown} from '../src/shell/export.ts';

const score = (metric, value, unit, numerator, denominator, basis, status='available') =>
  ({metric,value,unit,numerator,denominator,basis,status,reason:status==='method_test_only'?'Synthetic method demonstration':null});
const missing = reason => ({status:'unavailable',value:null,reason,scores:[]});
const section = scores => ({status:'method_test_only',value:{},reason:'Synthetic method demonstration only',scores});
const snapshot = {
  run_id:'r1-display',title:'Recorded evaluation',status:'complete',synthetic:true,mode:'replay',
  started_at:null,elapsed_ms:null,cost_usd:null,
  provenance:{embeddings:'synthetic_reference_derived',reference:'synthetic',vision:'not_used',limitations:['Synthetic method demonstration; no operational accuracy.']},
  evaluation:{
    reasoning_rules:{status:'available',value:{},reason:null,scores:[score('rules_pass_rate',75,'percent',3,4,'assessed workflow rule criteria; excludes not applicable')]},
    output:section([score('precision',50,'percent',1,2,'heldout flagged 160 m cells', 'method_test_only'),score('recall',25,'percent',1,4,'heldout reference assets','method_test_only')]),
    calibration:section([score('ece',12.5,'percent',null,8,'8 graded claims; expected calibration error','method_test_only'),score('brier',0.2,'raw',null,8,'8 graded claims; mean squared probability error','method_test_only')]),
    reviewer:missing('No recorded reviewer rubric or scale'),agentcore:missing('No recorded AgentCore rubric or scale'),predicted_accuracy:missing('No validated transfer model'),
  },
  thinking_summary:{status:'available',basis:'recorded_decisions',reason:null,text:'Recorded rationale summary: model recorded-model used plain_loop. It built an AEF index to explore the AOI, revised a retrieval choice after an empty result, then stopped with one present prediction. This summarizes recorded explanations, not hidden reasoning.'},
  input:{task_id:'r1',title:'Recorded evaluation',goal:'Inspect recorded evidence',aoi_bbox:null,time_window:null,tools_allowed:[],data_allowlist:[]},
  context:{model_id:'recorded-model',provider:'replay',harness:'plain_loop',system_prompt:null,items:[]},steps:[],markers:[],
};

async function reportModule() {
  const path = new URL('../src/shell/report.tsx',import.meta.url);
  const source = await readFile(path,'utf8');
  let output = (await transformWithOxc(source,path.pathname,{jsx:{runtime:'automatic'}})).code;
  output = output.replace(/from\s+(['"])([^'"]+)\1/g,(whole,quote,specifier) => {
    if(specifier.startsWith('.')) return `from ${quote}${new URL(specifier,path).href}${quote}`;
    if(specifier==='react/jsx-runtime') return `from ${quote}${import.meta.resolve('react/jsx-runtime')}${quote}`;
    return whole;
  });
  return import(`data:text/javascript;base64,${Buffer.from(output).toString('base64')}`);
}
const strip = html => html.replace(/<[^>]*>/g,' ').replace(/\s+/g,' ');

function assertReadable(text) {
  assert.match(text,/rules.pass.rate|rules pass|passed.*assessed|workflow rules/i);
  for(const [metric,percent] of [['precision','50'],['recall','25'],['ece','12.5']]) {
    assert.match(text,new RegExp(`${metric}[\\s\\S]{0,180}?${percent}(?:\\.0+)?\\s*%`,'i'),`${metric} needs a numeric percentage`);
  }
  assert.match(text,/75(?:\.0+)?\s*%/);
  assert.match(text,/3\s*\/\s*4|3\s+of\s+4|numerator[^\d]*3[\s\S]{0,40}denominator[^\d]*4/i,'display assessed criteria denominator');
  assert.match(text,/160 m cells|flagged.*cells/i);
  assert.match(text,/brier[\s\S]{0,120}?0\.2/i);
  assert.doesNotMatch(text,/brier[\s\S]{0,30}?20\s*%|80\s*%\s*(?:accuracy|accurate)/i);
  assert.match(text,/method demonstration|method test only|method_test_only/i);
  assert.match(text,/No recorded reviewer rubric or scale/);
  assert.match(text,/No recorded AgentCore rubric or scale/);
  assert.match(text,/Recorded rationale summary/);
  assert.match(text,/revised a retrieval choice after an empty result/);
  assert.match(text,/not hidden reasoning/);
}

test('R1 readable Markdown shows named percentages, denominators, raw Brier and recorded summary',()=>{
  assertReadable(summaryMarkdown(structuredClone(snapshot),[]));
});

test('R1 report React HTML renders percentages and summary outside raw JSON details',async()=>{
  const {EvaluationPanels} = await reportModule();
  const html = renderToStaticMarkup(React.createElement(EvaluationPanels,{snap:structuredClone(snapshot)}));
  // A raw JSON inspector can remain, but cannot be the only presentation of scores or rationale.
  assertReadable(strip(html.replace(/<pre\b[^>]*>[\s\S]*?<\/pre>/g,'')));
});

test('R1 export keeps named numeric metrics and recorded summary as structured evidence',()=>{
  const files=exportFiles(structuredClone(snapshot),[]);
  const run=JSON.parse(files['run.json']).run;
  assert.deepEqual(run.evaluation,snapshot.evaluation);
  assert.deepEqual(run.thinking_summary,snapshot.thinking_summary);
  assertReadable(files['README.md']);
});

test('R1 unavailable numeric evaluations do not become zero percent',async()=>{
  const blank=structuredClone(snapshot);
  blank.evaluation=Object.fromEntries(Object.keys(blank.evaluation).map(k=>[k,missing(`${k}: no assessed population or recorded scale`)]));
  blank.thinking_summary={status:'unavailable',basis:'recorded_decisions',text:'',reason:'No contemporaneous decisions were recorded.'};
  const {EvaluationPanels}=await reportModule();
  const text=strip(renderToStaticMarkup(React.createElement(EvaluationPanels,{snap:blank})))+' '+summaryMarkdown(blank,[]);
  assert.doesNotMatch(text,/\b0(?:\.0+)?\s*%/);
  assert.match(text,/No contemporaneous decisions were recorded/);
});
