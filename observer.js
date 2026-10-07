
'use strict';
(()=>{
const REPO='JeremyHennessy/AgentTest', API='https://api.github.com/repos/'+REPO, RAW='https://raw.githubusercontent.com/'+REPO;
const TEST_HEAD='58e79e4a15566d4e20c807f78e67e7709fdca192', DEV_AT_REVIEW='0e0fa11ea21f0605381a5c861b0ba22df9abc0eb';
const records=[
 {cycle:1772,owner:'phase41',position:[2,2],action:null,note:'No world transition. No experience invented.'},
 {cycle:1773,owner:'phase41',position:[2,2],note:'One recorded transition; position unchanged.'},
 {cycle:1774,owner:'phase41',position:[1,2],note:'Planner outcome recorded and learned passively.'},
 {cycle:1775,owner:'phase41',position:[1,1],note:'Planner continued its goal.'},
 {cycle:1776,owner:'ora2',position:[1,0],before:[1,1],action:'east',episode:'E005232',plan:'PP000444',step:2,note:'Learner chose east. Old plan step remained 2.'},
 {cycle:1777,owner:'phase41',position:[0,0],note:'Original planner acted again after the interruption.'},
 {cycle:1778,owner:'phase41',position:[0,-1],note:'Planner continued; no learner choice credited.'},
 {cycle:1779,owner:'ora2',position:[0,0],before:[0,-1],action:'west',episode:'E005241',plan:'PP000446',step:1,note:'Learner chose west. Old plan step remained 1.'}
];
const $=id=>document.getElementById(id), text=(id,value)=>{$(id).textContent=value;}, pos=p=>Array.isArray(p)&&p.length===2&&p.every(n=>Number.isInteger(n)&&n>=-2&&n<=2), vec=p=>pos(p)?'['+p.join(', ')+']':'Unavailable', short=s=>typeof s==='string'?s.slice(0,8):'Unavailable', isSha=s=>typeof s==='string'&&/^[a-f0-9]{40}$/.test(s);
const same=(a,b)=>pos(a)&&pos(b)&&a[0]===b[0]&&a[1]===b[1];
let receipt=null,receiptError=null,snapshotCycle=null,lastApi=0,refreshing=false,mapLoading=false,apiFailed=false;
function age(iso){const time=Date.parse(iso);if(!Number.isFinite(time))return 'Unavailable';const s=Math.floor((Date.now()-time)/1000);if(s < -60)return 'Source time is ahead of this device';if(s<60)return 'Less than a minute';if(s<3600)return Math.floor(s/60)+' minutes';return Math.floor(s/3600)+' hours';}
function normalizeReceipt(value){
 if(!value||value.version!=='heartbeat-transport-v1'||!['claimed','completed','prepared'].includes(value.status)||!Number.isSafeInteger(value.input_cycle)||value.input_cycle<0||!isSha(value.source_sha)||!Number.isFinite(Date.parse(value.cycle_time))||!Number.isSafeInteger(value.original_run_id)||value.original_run_id<=0)throw new Error('Receipt format is not recognized.');
 if(value.status==='completed'&&(!Number.isSafeInteger(value.result_cycle)||value.result_cycle!==value.input_cycle+1))throw new Error('Completed receipt has inconsistent cycle numbers.');
 return value;
}
function errorMessage(error){return error&&error.name==='AbortError'?'The read timed out.':String(error?.message||'The source could not be read.');}
async function getJson(url,{large=false,onProgress=null}={}){
 const abort=new AbortController(),timer=setTimeout(()=>abort.abort(),large?120000:18000);
 try{const response=await fetch(url,{method:'GET',cache:'no-store',credentials:'omit',signal:abort.signal});if(!response.ok)throw new Error(response.status===403||response.status===429?'GitHub read limit reached. The next automatic check will wait.':'Source returned HTTP '+response.status+'.');
 if(!large)return await response.json();
 const declared=Number(response.headers.get('content-length')),max=110*1024*1024;if(declared>max)throw new Error('Snapshot exceeds this viewer’s size limit. Use the legacy evidence links.');
 if(!response.body)return await response.json();
 const reader=response.body.getReader(),parts=[];let total=0;
 for(;;){const {done,value}=await reader.read();if(done)break;total+=value.length;if(total>max){await reader.cancel();throw new Error('Snapshot exceeds this viewer’s size limit.');}parts.push(value);if(onProgress)onProgress(total,declared);}
 const bytes=new Uint8Array(total);let offset=0;for(const part of parts){bytes.set(part,offset);offset+=part.length;}return JSON.parse(new TextDecoder().decode(bytes));
 }finally{clearTimeout(timer);}
}
function drawBoard(boardId,trailId,positions,current,{goal=null,noteId=null,scope='copied test'}={}){
 const board=$(boardId);board.replaceChildren();const visited=positions.filter(pos),ns='http://www.w3.org/2000/svg',svg=$(trailId);svg.replaceChildren();
 for(let y=2;y>=-2;y--)for(let x=-2;x<=2;x++){
  const p=[x,y],cell=document.createElement('button'),count=visited.filter(v=>same(v,p)).length;cell.type='button';cell.className='cell'+(count?' visited':'')+(same(p,current)?' active':'')+(same(p,goal)?' goal':'');
  const label=document.createElement('span');label.className='coord';label.textContent=x+', '+y;cell.append(label);
  cell.setAttribute('aria-label',vec(p)+(same(p,current)?', recorded current position':'')+(same(p,goal)?', active goal':'')+', '+count+' recorded positions in '+scope);
  cell.addEventListener('click',()=>{if(noteId)text(noteId,vec(p)+' · '+(count?count+' recorded position'+(count===1?'':'s')+' in this displayed '+scope+'.':'No visit in this displayed '+scope+'. This is not a lifetime count.'));});board.append(cell);
 }
 if(visited.length>1){const line=document.createElementNS(ns,'polyline');line.setAttribute('points',visited.map(p=>((p[0]+2)*100+50)+','+((2-p[1])*100+50)).join(' '));line.setAttribute('fill','none');line.setAttribute('stroke','currentColor');line.setAttribute('stroke-width','2');line.setAttribute('stroke-linejoin','round');line.setAttribute('stroke-opacity','.65');svg.append(line);}
}
function selectAction(cycle){
 const record=records.find(r=>r.cycle===cycle&&r.owner==='ora2');if(!record)return;
 for(const c of [1776,1779])$('pick-'+c).setAttribute('aria-pressed',String(c===cycle));
 text('map-cycle','Cycle '+cycle);text('action-choice',record.action+' · all four controls available');text('action-outcome',vec(record.before)+' → '+vec(record.position));text('action-memory',record.episode+' · learner-owned action');text('action-plan','Plan '+record.plan+' was interrupted. Its step stayed at '+record.step+'.');
 drawBoard('lab-board','lab-trail',[[2,2],...records.filter(r=>r.cycle<=cycle).map(r=>r.position)],record.position,{noteId:'lab-cell-note'});
 text('lab-cell-note','Recorded position at cycle '+cycle+'. Select a cell to inspect the displayed path.');
}
function renderTimeline(){for(const r of [...records].reverse()){const row=document.createElement('div');row.className='timeline-row';const cycle=document.createElement('span');cycle.className='timeline-cycle';cycle.textContent='C'+r.cycle;const owner=document.createElement('span');owner.className='owner'+(r.owner==='ora2'?' learner':'');owner.textContent=r.owner==='ora2'?'Ora 2 choice':r.action===null?'No action':'Phase 41';const body=document.createElement('div');body.className='timeline-body';const head=document.createElement('strong');head.textContent=vec(r.position)+' · ';body.append(head,document.createTextNode(r.note));row.append(cycle,owner,body);$('timeline').append(row);}}
function renderReceipt(){
 if(!receipt){text('live-health',receiptError?'Receipt unavailable':'Checking receipt');$('live-health').className='pill'+(receiptError?' red':'');text('live-title',receiptError?'Live status is unavailable.':'Checking original Ora.');text('live-error',receiptError||'');return;}
 const completed=receipt.status==='completed',minutes=(Date.now()-Date.parse(receipt.cycle_time))/60000,stale=minutes>5;
 text('live-cycle',completed?receipt.result_cycle.toLocaleString():'—');text('live-title',completed?'A completed cycle is recorded.':'No completed result in the latest receipt.');text('live-description',completed?'This receipt records original Ora’s cycle '+receipt.result_cycle+'. It does not describe Ora 2 or prove a learning improvement.':'The latest receipt is '+receipt.status+'. Its input cycle is '+receipt.input_cycle+'; no completed result is inferred.');
 text('live-time',new Date(receipt.cycle_time).toLocaleString());text('live-age',age(receipt.cycle_time));text('live-source',short(receipt.source_sha));text('live-mode',receipt.mode==='ordinary'?'Ordinary original-Ora cycle':String(receipt.mode||'Unavailable'));
 text('journal-size',Number.isSafeInteger(receipt.input_journal_size)&&receipt.input_journal_size>=0?(receipt.input_journal_size/1048576).toFixed(1)+' MiB at cycle input':'Unavailable');
 $('live-run').href='https://github.com/'+REPO+'/actions/runs/'+receipt.original_run_id;
 text('live-health',receiptError?'Read failed · last receipt retained':minutes < -1?'Source time ahead':stale?'Receipt aging · '+age(receipt.cycle_time):completed?'Recent completed receipt':'Receipt pending completion');
 $('live-health').className='pill '+(receiptError?'red':stale||!completed||minutes < -1?'amber':'mint');
 text('live-error',receiptError?receiptError+' The displayed value is the last successful read.':stale?'The receipt is older than five minutes. This alone does not prove the heartbeat has stopped.':'');
 if(snapshotCycle!==null)text('snapshot-freshness',completed&&receipt.result_cycle>snapshotCycle?'A newer heartbeat exists. The map remains pinned to cycle '+snapshotCycle+' until explicitly reloaded.':'The map is a separately pinned state snapshot, not a running animation.');
}
function renderPR(pr){
 if(!pr||pr.number!==245||!isSha(pr.head?.sha)||!['open','closed'].includes(pr.state)||typeof pr.merged!=='boolean')throw new Error('Pull-request response is incomplete.');
 const changed=pr.head.sha!==TEST_HEAD;
 text('pr-status','GitHub: #245 '+(pr.merged?'merged':pr.state+(pr.draft?' · draft':''))+' · head '+short(pr.head.sha)+'.'+(changed?' The displayed test is for an earlier commit.':''));
 if(pr.merged){text('correction-step','GitHub now reports this pull request merged. Consult the current handoff for corrected-head verification.');text('hold-title','Repository status has advanced.');text('hold-text','PR #245 is now merged. The map below remains a historical test receipt; consult the current handoff for subsequent verification and limitations.');}
 else if(changed){text('correction-step','A newer candidate is published. Its corrected-head verification must be checked separately.');text('hold-title','A newer candidate is under review.');text('hold-text','The pull-request head has changed. Do not use the old passing result below to verify the newer code or assume the goal-arrival correction is resolved.');}
 else{text('correction-step','Publication blocked at the recorded review. Keep the integration unmerged until the correction passes.');text('hold-title','Integration is on hold.');text('hold-text','The initial test passed, but a goal-arrival correction is not published. A passing old test does not verify the correction.');}
}
async function refresh({force=false}={}){
 if(refreshing||document.hidden)return;refreshing=true;$('refresh').disabled=true;
 try{
  const jobs=[(async()=>{try{receipt=normalizeReceipt(await getJson(RAW+'/autonomous/growth/state/heartbeat_operation.json'));receiptError=null;}catch(error){receiptError=errorMessage(error);}renderReceipt();})()];
  if(!lastApi||Date.now()-lastApi>=300000){lastApi=Date.now();apiFailed=false;jobs.push((async()=>{try{const pr=await getJson(API+'/pulls/245');renderPR(pr);}catch(error){apiFailed=true;text('pr-status','Current pull-request status unavailable. Recorded evidence remains visible; current status is unconfirmed. '+errorMessage(error));}})());jobs.push((async()=>{try{const value=await getJson(API+'/git/ref/heads/ora2/temporal-phase42-20261007');if(!isSha(value.object?.sha))throw new Error('Invalid branch reference.');const changed=value.object.sha!==DEV_AT_REVIEW;text('dev-status','Development head: '+short(value.object.sha)+'. '+(changed?'Code has advanced since the displayed plan was recorded; read the current handoff.':'The correction is not yet integrated in this development checkpoint.'));}catch(error){apiFailed=true;text('dev-status','Development-head check unavailable. '+errorMessage(error));}})());}
  await Promise.all(jobs);text('checked',(receiptError||apiFailed?'Some reads unavailable · checked ':'Sources checked ')+new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})+(force&&Date.now()-lastApi<300000?' · API checks limited to every 5 min':''));
 }finally{refreshing=false;$('refresh').disabled=false;}
}
function normalizeSnapshot(value){const lab=value?.planning_lab;if(!Number.isSafeInteger(value?.cycles)||value.cycles<=0||!lab||lab.bounds!==2||!pos(lab.position)||typeof lab.world_version!=='string'||!Array.isArray(lab.transition_observations)||!Array.isArray(lab.goals)||!Array.isArray(lab.plans))throw new Error('Snapshot does not contain a valid bounded-world view.');return value;}
async function loadMap(){
 if(mapLoading)return;mapLoading=true;$('load-live-map').disabled=true;let pinned;
 try{text('live-map-status','Resolving original Ora’s state to one commit…');const reference=await getJson(API+'/git/ref/heads/autonomous/growth');pinned=reference.object?.sha;if(!isSha(pinned))throw new Error('State branch did not resolve to a commit.');
 const state=normalizeSnapshot(await getJson(RAW+'/'+pinned+'/state/organism.json',{large:true,onProgress:n=>text('live-map-status','Reading pinned snapshot: '+(n/1048576).toFixed(1)+' MiB…')})),lab=state.planning_lab;
 const rows=lab.transition_observations.filter(r=>r.world_version===lab.world_version&&pos(r.before)&&pos(r.after)).slice(-20);let chain=[];
 for(const r of rows){if(chain.length&&!same(chain[chain.length-1],r.before))chain=[];if(!chain.length)chain.push(r.before);chain.push(r.after);}
 if(!chain.length||!same(chain[chain.length-1],lab.position))chain=[lab.position];
 const goal=lab.goals.find(g=>g.id===lab.active_goal_id&&g.status==='active'),plan=lab.plans.find(p=>p.id===lab.active_plan_id&&p.status==='active');
 drawBoard('live-board','live-trail',chain,lab.position,{goal:goal?.target,noteId:'live-cell-note',scope:'snapshot trail'});
 text('live-cell-note','Original Ora · position recorded in this pinned snapshot.');text('snapshot-cycle',state.cycles.toLocaleString());text('snapshot-position',vec(lab.position));text('snapshot-goal',goal?vec(goal.target):'No active goal');text('snapshot-sha',short(pinned));
 const i=plan?.next_step_index,next=Number.isSafeInteger(i)&&i>=0&&Array.isArray(plan.actions)?plan.actions[i]:null;
 text('live-plan',goal?(next?'The active plan records '+String(next)+' as its next command toward '+vec(goal.target)+'.':'A goal at '+vec(goal.target)+' is recorded, but there is no pending command in an active plan.'):'No active goal is recorded. A completed historical goal is not shown as current.');
 snapshotCycle=state.cycles;$('live-map-content').hidden=false;text('live-map-status','Loaded cycle '+state.cycles+' from commit '+short(pinned)+'. The map will not refresh automatically.');$('live-map-status').classList.remove('error');$('load-live-map').textContent='Reload a fresh pinned snapshot';renderReceipt();
 }catch(error){text('live-map-status',errorMessage(error)+(snapshotCycle!==null?' The earlier map is retained and is not current.':''));$('live-map-status').classList.add('error');}
 finally{mapLoading=false;$('load-live-map').disabled=false;}
}
function tab(name,{focus=false}={}){for(const n of ['lab','live']){const on=n===name;$('tab-'+n).setAttribute('aria-selected',String(on));$('tab-'+n).tabIndex=on?0:-1;$('panel-'+n).hidden=!on;}if(focus)$('tab-'+name).focus();}
for(const name of ['lab','live']){$('tab-'+name).addEventListener('click',()=>tab(name));$('tab-'+name).addEventListener('keydown',e=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){e.preventDefault();tab(e.key==='Home'?'lab':e.key==='End'?'live':name==='lab'?'live':'lab',{focus:true});}});}
for(const n of [1776,1779])$('pick-'+n).addEventListener('click',()=>selectAction(n));
$('refresh').addEventListener('click',()=>refresh({force:true}));$('load-live-map').addEventListener('click',loadMap);
renderTimeline();selectAction(1779);refresh();setInterval(()=>refresh(),60000);setInterval(()=>{if(!document.hidden)renderReceipt();},15000);document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});
window.OraObserver=Object.freeze({normalizeReceipt,normalizeSnapshot,renderPR,selectAction,records:JSON.parse(JSON.stringify(records)),pos,age});
})();
