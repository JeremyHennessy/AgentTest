// Run with node --test tests/test_observer.js. No network or live state needed.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const page = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const transport = page.match(/<script id="observerTransport">([\s\S]*?)<\/script>/)[1];
const shaA = 'a'.repeat(40), shaB = 'b'.repeat(40);
const response = (data, status = 200) => ({ok: status >= 200 && status < 300, status, json: async () => data});
const state = generation => ({generation, updated_at: '2026-10-05T12:00:00Z', schema_version:25, agenda:{started_cycle:1,decisions:[],threads:[]}});
function setup(custom) {
  const box = {}; vm.createContext(box); vm.runInContext(transport, box);
  const calls = [], published = [], statuses = [];
  let time = 1, sha = shaA, generation = 12, fail = false;
  const fetch = async url => {
    calls.push(url);
    if (custom) return custom(url);
    if (fail) throw new Error('offline');
    if (url.startsWith('ref')) return response({object:{sha}});
    if (url.endsWith('/organism.json')) return response(state(generation));
    if (url.endsWith('/last_interaction.json')) return response({response_text:'persisted reply'});
    return response({diagnostic_version:'phase42-resumption-opportunities-v2'});
  };
  const loader=box.createObserverLoader({fetch,refUrl:'ref',rawBase:'raw',pollMs:75,now:()=>time,publish:x=>published.push(x),status:x=>statuses.push(x)});
  return {loader,calls,published,statuses,advance:x=>time+=x,setSha:x=>sha=x,setGeneration:x=>generation=x,setFail:x=>fail=x};
}
test('manual and periodic refresh overlap share one in-flight snapshot download', async () => {
  let release; const wait = new Promise(r=>release=r);
  const h=setup(async url=>{await wait;return url.startsWith('ref')?response({object:{sha:shaA}}):response(url.endsWith('/organism.json')?state(12):{});});
  const first=h.loader.refresh();
  assert.equal(first,h.loader.refresh({force:true}));
  assert.equal(first,h.loader.refresh());
  release(); await first;
  assert.equal(h.calls.length,4);assert.equal(h.published.length,1);
  assert.ok(h.calls.slice(1).every(x=>x.includes('/'+shaA+'/state/')));
});
test('same SHA never redownloads 71MB organism; manual refresh checks ref immediately', async () => {
  const h=setup();await h.loader.refresh();await h.loader.refresh();assert.equal(h.calls.length,4);
  await h.loader.refresh({force:true});assert.equal(h.calls.length,5);assert.equal(h.published.length,1);
  h.advance(80);await h.loader.refresh();assert.equal(h.calls.length,6);
});
test('new SHA publishes only after coherent organism, interaction and diagnostic complete', async()=>{
  const h=setup();await h.loader.refresh();h.setSha(shaB);h.setGeneration(13);await h.loader.refresh({force:true});
  assert.equal(h.published.length,2);assert.equal(h.published[1].sha,shaB);
  assert.ok(h.calls.slice(5).every(x=>x.includes('/'+shaB+'/state/')));
});
test('ref error retains last good data and reports failed freshness check; retry recovers',async()=>{
  const h=setup();await h.loader.refresh();h.setFail(true);await h.loader.refresh({force:true});
  assert.equal(h.published.length,1);assert.equal(h.statuses.at(-1).kind,'error');
  assert.equal(h.statuses.at(-1).snapshot.organism.generation,12);
  h.setFail(false);await h.loader.refresh({force:true});assert.equal(h.statuses.at(-1).kind,'ready');
});
test('periodic refresh after an error must recheck the ref, never relabel a failed check as fresh',async()=>{
  const h=setup();await h.loader.refresh();h.setFail(true);await h.loader.refresh({force:true});
  const count=h.calls.length;await h.loader.refresh();
  assert.equal(h.calls.length,count+1);assert.equal(h.statuses.at(-1).kind,'error');
});
test('failed changed-source data retains all of the previous coherent snapshot',async()=>{
  let current=shaA;
  const h=setup(async url=>url.startsWith('ref')?response({object:{sha:current}}):response(url.endsWith('/organism.json')?state(current===shaA?12:13):{},current===shaB&&url.endsWith('/last_interaction.json')?503:200));
  await h.loader.refresh();current=shaB;await h.loader.refresh({force:true});
  assert.equal(h.published.length,1);assert.equal(h.statuses.at(-1).snapshot.sha,shaA);
});
test('late abandoned ref cannot overwrite newer source',async()=>{
  let release;const slow=new Promise(r=>release=r);let refs=0;
  const h=setup(async url=>{
    if(url.startsWith('ref')){if(++refs===1){await slow;return response({object:{sha:shaA}});}return response({object:{sha:shaB}});}
    return response(url.endsWith('/organism.json')?state(13):{});
  });
  const old=h.loader.refresh();h.loader.invalidate();await h.loader.refresh({force:true});release();await old;
  assert.deepEqual(h.published.map(x=>x.sha),[shaB]);
});
test('late abandoned snapshot responses cannot replace newer generation',async()=>{
  let release;const slow=new Promise(r=>release=r);let refs=0;
  const h=setup(async url=>{
    if(url.startsWith('ref'))return response({object:{sha:++refs===1?shaA:shaB}});
    if(url.includes(shaA)){await slow;return response(url.endsWith('/organism.json')?state(12):{});}
    return response(url.endsWith('/organism.json')?state(13):{});
  });
  const old=h.loader.refresh();await Promise.resolve();await Promise.resolve();await Promise.resolve();
  h.loader.invalidate();await h.loader.refresh({force:true});release();await old;
  assert.deepEqual(h.published.map(x=>x.sha),[shaB]);
});
for (const filename of ['organism.json','last_interaction.json','phase42_resumption_opportunities.json']) {
  test(filename+' server error does not publish partial data',async()=>{
    const h=setup(async url=>url.startsWith('ref')?response({object:{sha:shaA}}):response(url.endsWith('organism.json')?state(12):{},url.endsWith(filename)?503:200));
    await h.loader.refresh();assert.equal(h.published.length,0);assert.equal(h.statuses.at(-1).kind,'error');
  });
}
test('missing optional diagnostic displays unavailable, not invented zero counts',async()=>{
  const h=setup(async url=>url.startsWith('ref')?response({object:{sha:shaA}}):response(url.endsWith('organism.json')?state(12):{},url.endsWith('opportunities.json')?404:200));
  await h.loader.refresh();assert.equal(h.published[0].diagnostic,null);assert.equal(h.statuses.at(-1).kind,'ready');
});
test('generation rollback fails closed and keeps last good snapshot',async()=>{
  const h=setup();await h.loader.refresh();h.setSha(shaB);h.setGeneration(11);await h.loader.refresh({force:true});
  assert.equal(h.published.length,1);assert.equal(h.statuses.at(-1).kind,'error');
});
test('malformed SHA and JSON fail without publishing',async()=>{
  for(const fetch of [async()=>response({object:{sha:'bad'}}),async()=>({ok:true,status:200,json:async()=>{throw Error('malformed JSON')}})]) {
    const h=setup(fetch);await h.loader.refresh();assert.equal(h.published.length,0);assert.equal(h.statuses.at(-1).kind,'error');
  }
});
function view() {
  const ids=[...page.matchAll(/\bid="([^"]+)"/g)].map(x=>x[1]);assert.equal(new Set(ids).size,ids.length,'unique DOM ids');
  const nodes=Object.fromEntries(ids.map(id=>[id,{textContent:'',innerHTML:'',value:'',style:{},listeners:{},attrs:{},addEventListener(event,fn){this.listeners[event]=fn},setAttribute(k,v){this.attrs[k]=v}}]));
  const opened=[],stored=[],intervals=[];
  const box={document:{getElementById:id=>{assert.ok(nodes[id],id+' exists');return nodes[id]}},fetch:async()=>response({object:{sha:shaA}}),setInterval:(fn,ms)=>intervals.push({fn,ms}),URLSearchParams,localStorage:{setItem:(...args)=>stored.push(args)},window:{open:(...args)=>opened.push(args)}};
  vm.createContext(box);vm.runInContext(transport,box);vm.runInContext(page.match(/<script>\s*(const ORGANISM_SOURCE[\s\S]*?)<\/script>/)[1],box);
  return {box,nodes,opened,stored,intervals};
}
test('whole Observer script compiles and renders map, plan, inquiry and zero-resumption evidence',()=>{
  const h=view();h.box.render(state(12),{response_text:'hello'},null);
  assert.match(h.nodes.nowStory.textContent,/Ora|ora/);
  assert.match(h.nodes.worldGrid.attrs['aria-label'],/Ora at/);
  assert.match(h.nodes.worldGrid.innerHTML,/cell/);
  assert.match(h.nodes.agendaCoverage.textContent,/absent/);
  assert.match(h.nodes.demonstratedSummary.textContent,/Zero resumptions alone is not a failure/);
  h.box.renderAgendaOpportunityDiagnostic({diagnostic_version:'phase42-resumption-opportunities-v2',retained_decision_count:128,telemetry_decision_count:127,pre_telemetry_decision_count:1,opportunity_count:127,lower_priority_opportunity_count:127,handoff_or_selection_mismatch_count:0});
  assert.match(h.nodes.agendaCoverage.textContent,/127 measured \/ 128 retained/);
  assert.match(h.nodes.agendaOpportunityStatus.textContent,/lower priority/);
  assert.match(h.nodes.agendaResumptionLabel.textContent,/retained-window/);
  h.box.render({...state(13),agenda:{started_cycle:1,threads:[],decisions:[],genuine_resumption_count:0,next_decision_index:850}}, {}, null);
  assert.match(h.nodes.agendaResumptionLabel.textContent,/lifetime/);
  assert.equal(h.nodes.milestoneTests.textContent,'849');
});
test('owner interaction preserves explicit GitHub handoff, escaping and pending persistence',()=>{
  const h=view();h.nodes.message.value='';h.nodes.send.listeners.click();assert.equal(h.opened.length,0);
  h.nodes.message.value='a & b / <test>';h.nodes.send.listeners.click();
  assert.equal(h.stored[0][1],'a & b / <test>');assert.equal(h.opened[0][2],'noopener');
  assert.equal(new URL(h.opened[0][0]).searchParams.get('body'),'/agent a & b / <test>');
  assert.equal(vm.runInContext('esc(\'<img onerror="x">\')',h.box),'&lt;img onerror=&quot;x&quot;&gt;');
  assert.equal(h.intervals.find(x=>x.ms===15000).fn.name,'load');assert.ok(h.nodes.refresh.listeners.click);
});
test('active plan and learned outcome survive technical rendering in the final now/map view',()=>{
  const h=view(),o=state(13);
  o.questions=[{id:'Q1',text:'Will east move me?'}];
  o.agenda={started_cycle:1,foreground_thread_id:'AT1',threads:[{id:'AT1',question_id:'Q1',status:'foreground'}],decisions:[],genuine_resumption_count:0,next_decision_index:42};
  o.planning_lab={version:'persistent-planning-lab-v10',bootstrapped_cycle:1,position:[0,0],bounds:2,status:'executing_plan',active_goal_id:'G1',active_plan_id:'P1',visit_counts:{'0,0':1},goals:[{id:'G1',target:[1,0],status:'active'}],plans:[{id:'P1',goal_id:'G1',actions:['east'],predicted_states:[[1,0]],next_step_index:0}],executions:[],objective_realizations:[{id:'R1',cycle:12,action:'east',before:[0,0],predicted_after:[1,0],after:[0,0],blocked:true,interpretation:'hypothesis_refuted',realized_information_gain:1}]};
  h.box.render(o,{},null);
  assert.equal(h.nodes.actionCount.textContent,'Phase 42');
  assert.match(h.nodes.nowPlan.textContent,/east/);assert.equal(h.nodes.nowQuestion.textContent,'Will east move me?');
  assert.match(h.nodes.nowLearning.textContent,/hypothesis was refuted/);
  assert.match(h.nodes.latestDelta.textContent,/east/);assert.equal(h.nodes.latestBlocked.textContent,'1');
  assert.ok(h.nodes.plannedPath.attrs.points.length>0);assert.match(h.nodes.worldGrid.innerHTML,/active/);
});
test('layout and accessibility contracts retain viewport, mobile rules, labelled controls and focus navigation',()=>{
  assert.match(page,/width=device-width,initial-scale=1/);
  assert.match(page,/@media\(max-width:720px\)/);
  assert.match(page,/\.world-layout\{display:block\}/);
  assert.match(page,/\.roadmap,\.capability-levels\{grid-template-columns:1fr\}/);
  assert.match(page,/aria-live="polite"/);assert.match(page,/<label for="message">/);
  assert.match(page,/:focus-visible/);assert.match(page,/class="skip-link"/);
  assert.ok(page.indexOf('Where Ora is exploring')<page.indexOf('Evidence and future plans'));
  assert.ok(page.indexOf('id="futurePlans"')<page.indexOf('id="inquiryFocusCard"'));
});
