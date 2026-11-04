'use strict';
const $ = (id) => document.getElementById(id);
const names = ['Know Your Stuff', 'Gateway Builder', 'Ship It'];
let configured = false;
let refreshTimer;
let lastReceiptCapture;
function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}
function pairs(target, data) {
  target.replaceChildren();
  for (const [key, value] of Object.entries(data)) {
    target.append(el('dt', key.replaceAll('_', ' ')), el('dd', String(value ?? 'Not returned')));
  }
}
function render(data) {
  clearTimeout(refreshTimer);
  // This polls in-memory server status only. It never submits another paid request.
  if (data.busy) refreshTimer = setTimeout(load, 1500);
  configured = data.configured;
  const r = data.receipt;
  if (r && !$('error').hidden && r.captured_at !== lastReceiptCapture && !data.busy) {
    $('error').hidden = true;
    $('announcement').textContent = 'Answer and evidence received. A completed request was recovered without another invocation.';
  }
  if (r) lastReceiptCapture = r.captured_at;
  const source = r ? ({live: 'Live AWS response', recorded: 'Recorded AWS receipt', sample: 'Sample · unverified'}[r.source]) : 'No evidence yet';
  $('mode').textContent = source;
  $('setup').hidden = configured;
  $('submit').disabled = !configured || data.busy;
  $('request-note').textContent = configured ? 'One Runtime invocation per submit.' : 'Live questions need server configuration.';
  $('proofs').replaceChildren();
  const proofs = data.proofs.length ? data.proofs : names.map(name => ({name, state: 'pending', detail: 'Awaiting an invocation receipt.'}));
  for (const proof of proofs) {
    const row = el('li'); const title = el('div', undefined, 'proof-title');
    title.append(el('h3', proof.name), el('span', proof.state[0].toUpperCase() + proof.state.slice(1), `state ${proof.state}`));
    row.append(title, el('p', proof.detail)); $('proofs').append(row);
  }
  const count = proofs.filter(p => p.state === 'observed').length;
  $('proof-count').textContent = `${count} / 3 observed live`;
  if (data.resources) {
    const {schema_version, ...resources} = data.resources;
    pairs($('resources'), resources);
  }
  if (!r) return;
  $('empty-answer').hidden = true; $('answer-content').hidden = false; $('export').hidden = false;
  $('answer-source').textContent = `${source} · ${data.elapsed_seconds ?? '—'} s`;
  $('answer-text').textContent = r.answer || 'The Runtime returned no answer.';
  $('recorded-warning').hidden = r.source === 'live' && !data.stale;
  $('recorded-warning').textContent = (r.source === 'sample' ? 'Synthetic sample. This demonstrates the interface only; none of its contents verify AWS challenges.' : r.source === 'recorded' ? 'Recorded evidence only. No live request was made by this page; provenance is operator supplied.' : '') + (data.stale ? ' This receipt is older than 24 hours.' : '');
  $('citations').replaceChildren(); $('no-citations').hidden = !!r.citations.length;
  r.citations.forEach(c => {
    const li = el('li');
    // Never inject receipt HTML. Only HTTP(S) citations become links; S3 stays text.
    if (/^https?:\/\//i.test(c.uri)) {
      const link = el('a', c.title || c.uri); link.href = c.uri; link.target = '_blank'; link.rel = 'noopener noreferrer'; li.append(link);
    } else li.append(el('strong', c.title || 'Source document'));
    li.append(el('code', c.uri)); if (c.quote) li.append(el('p', c.quote)); $('citations').append(li);
  });
  $('tool-count').textContent = `${r.tool_calls.length} calls`;
  $('tool-trace').replaceChildren(el('h3', 'Gateway catalog'), el('p', r.gateway_tools.join(', ') || 'No catalog returned.'));
  r.tool_calls.forEach((call, index) => {
    $('tool-trace').append(el('h3', `${index + 1}. ${call.name} · ${call.is_error ? 'Error' : 'Returned'}`), el('pre', JSON.stringify({arguments: call.arguments, result: call.result, request_id: call.request_id}, null, 2)));
  });
  pairs($('runtime-trace'), {source: r.source, captured_at: r.captured_at, request_id: r.request_id, session_id: r.session_id, runtime_arn: r.runtime_arn, model_id: r.model_id, knowledge_base_id: r.knowledge_base_id, gateway_id: r.gateway_id});
}
async function load() {
  try { const response = await fetch('api/status'); if (!response.ok) throw Error(); render(await response.json()); }
  catch { $('mode').textContent = 'Unavailable'; $('error').hidden = false; $('error').textContent = 'The workbench server is unavailable. Reload after the operator restarts it.'; }
}
$('ask-form').addEventListener('submit', async event => {
  event.preventDefault(); if (!configured) return;
  $('error').hidden = true; $('submit').disabled = true; $('submit').textContent = 'Asking…';
  $('answer-pane').setAttribute('aria-busy', 'true'); $('announcement').textContent = 'Request sent. Waiting for the agent and its evidence…';
  const start = Date.now(); const timer = setInterval(() => { $('request-note').textContent = `Waiting · ${Math.floor((Date.now() - start) / 1000)} s`; }, 1000);
  try {
    const response = await fetch('api/invoke', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({prompt: $('question').value})});
    const data = await response.json(); if (!response.ok) throw Error(data.detail || 'Request failed.');
    render(data); $('announcement').textContent = 'Answer and evidence received. Review the sources and challenge evidence below.';
  } catch (error) {
    $('error').textContent = `${error.message} Any answer still shown is from the previous receipt.`; $('error').hidden = false; $('announcement').textContent = 'The request did not produce a new receipt.';
  } finally {
    clearInterval(timer); $('submit').textContent = 'Ask agent'; $('answer-pane').setAttribute('aria-busy', 'false');
    // Reads are local only; this also preserves the busy state after an SDK timeout.
    await load();
  }
});
load();

window.addEventListener('pagehide', () => clearTimeout(refreshTimer));
