'use strict';
(()=>{
const REPO='JeremyHennessy/AgentTest',API='https://api.github.com/repos/'+REPO,RAW='https://raw.githubusercontent.com/'+REPO;
const $=id=>document.getElementById(id),set=(id,value)=>{$(id).textContent=String(value);};
const isSha=value=>typeof value==='string'&&/^[0-9a-f]{40}$/.test(value);
const pos=value=>Array.isArray(value)&&value.length===2&&value.every(n=>Number.isInteger(n)&&n>=-2&&n<=2);
const same=(a,b)=>pos(a)&&pos(b)&&a[0]===b[0]&&a[1]===b[1];
const vec=value=>pos(value)?'['+value.join(', ')+']':'Unavailable';
const short=value=>isSha(value)?value.slice(0,8):'Unavailable';
let receipt=null,receiptError=null,snapshotCycle=null,lastApi=0,refreshing=false,mapLoading=false,apiError=false;
function age(value){const t=Date.parse(value),s=Math.floor((Date.now()-t)/1000);if(!Number.isFinite(t))return 'Unavailable';if(s < -60)return 'Source time ahead of device';if(s<60)return 'Less than 1 minute';if(s<3600)return Math.floor(s/60)+' minutes';if(s<86400)return Math.floor(s/3600)+' hours';return Math.floor(s/86400)+' days';}
function normalizeReceipt(value){
 if(!value||value.version!=='heartbeat-transport-v1'||!['pending','claimed','prepared','completed','failed'].includes(value.status)||!Number.isSafeInteger(value.input_cycle)||value.input_cycle<0||!isSha(value.source_sha)||!Number.isFinite(Date.parse(value.cycle_time))||!Number.isSafeInteger(value.original_run_id)||value.original_run_id<=0)throw new Error('Heartbeat receipt schema not recognized.');
 if(value.status==='completed'&&(!Number.isSafeInteger(value.result_cycle)||value.result_cycle!==value.input_cycle+1))throw new Error('Completed receipt has inconsistent cycles.');
 return value;
}
function normalizeSnapshot(value){const lab=value?.planning_lab;if(!Number.isSafeInteger(value?.cycles)||value.cycles<1||!lab||lab.bounds!==2||!pos(lab.position)||!Array.isArray(lab.transition_observations)||!Array.isArray(lab.goals)||!Array.isArray(lab.plans)||typeof lab.world_version!=='string')throw new Error('Snapshot schema not recognized.');return value;}
function errorMessage(e){return e?.name==='AbortError'?'Read timed out.':String(e?.message||'Source unavailable.');}
async function getJson(url,{large=false,onProgress=null}={}){
 const abort=new AbortController(),timer=setTimeout(()=>abort.abort(),large?120000:18000);
 try{
  const response=await fetch(url,{method:'GET',cache:'no-store',credentials:'omit',signal:abort.signal});
  if(!response.ok)throw new Error(response.status===403||response.status===429?'GitHub read limit reached.':'Source HTTP '+response.status+'.');
  if(!large)return await response.json();
  const max=115*1024*1024,declared=Number(response.headers.get('content-length'));if(declared>max)throw new Error('Snapshot exceeds 115 MiB reader limit.');
  if(!response.body)return await response.json();
  const reader=response.body.getReader(),parts=[];let total=0;
  for(;;){const {done,value}=await reader.read();if(done)break;total+=value.length;if(total>max){await reader.cancel();throw new Error('Snapshot exceeds 115 MiB reader limit.');}parts.push(value);if(onProgress)onProgress(total);}
  const bytes=new Uint8Array(total);let at=0;for(const part of parts){bytes.set(part,at);at+=part.length;}return JSON.parse(new TextDecoder().decode(bytes));
 }finally{clearTimeout(timer);}
}
function renderReceipt(){
 if(!receipt){set('overview-cycle','—');set('overview-cycle-label','Completed cycle unavailable');set('overview-heartbeat','Unavailable');set('overview-heartbeat-label','No verified source response');set('overview-live-detail','Source unavailable');set('live-cycle','—');set('live-cycle-caption','No completed result verified');set('live-status','Unavailable');set('live-warning',receiptError||'Waiting for a source response.');set('live-badge','Unavailable');$('live-badge').className='chip bad';return;}
 const done=receipt.status==='completed',time=receipt.created_at||receipt.cycle_time,elapsed=(Date.now()-Date.parse(time))/60000,stale=elapsed>5;
 const health=receiptError?'Read failed':stale?'Aging receipt':done?'Completed':receipt.status;
 set('overview-cycle',done?receipt.result_cycle.toLocaleString():'—');
 set('overview-cycle-label',done?'Verified completed cycle':'Input cycle '+receipt.input_cycle+' · no completion inferred');
 set('overview-heartbeat',health);
 set('overview-heartbeat-label',age(time)+(receiptError?' · retained last read':''));
 set('overview-live-detail',done?'Cycle '+receipt.result_cycle+' completed':'Input cycle '+receipt.input_cycle+' · '+receipt.status);
 set('live-cycle',done?receipt.result_cycle.toLocaleString():'—');
 set('live-cycle-caption',done?'Completed original-Ora cycle':'Latest input cycle '+receipt.input_cycle+' · not a completed result');
 set('live-status',receipt.status);set('live-time',new Date(time).toLocaleString());set('live-age',age(time));set('live-mode',receipt.mode==='ordinary'?'Ordinary original-Ora cycle':String(receipt.mode||'Unavailable'));set('live-source',short(receipt.source_sha));
 set('live-journal',Number.isSafeInteger(receipt.input_journal_size)&&receipt.input_journal_size>=0?(receipt.input_journal_size/1048576).toFixed(1)+' MiB at input':'Unavailable');
 set('live-badge',health);$('live-badge').className='chip '+(receiptError?'bad':stale||!done||elapsed < -1?'warn':'good');
 set('live-warning',receiptError?receiptError+' Displaying the last successful read, not current health.':stale?'Receipt older than five minutes. This alone does not prove the heartbeat stopped.':done?'Completed receipt, not proof of learning progress.':'Latest receipt is pending. A completed result is not inferred.');
 $('live-run-link').href='https://github.com/'+REPO+'/actions/runs/'+receipt.original_run_id;
 if(snapshotCycle!==null)set('world-freshness',done&&receipt.result_cycle>snapshotCycle?'A newer heartbeat exists. This map remains pinned to cycle '+snapshotCycle+'.':'Pinned snapshot, not a live animation.');
}
function renderWorkflow(value){
 if(!value||!Array.isArray(value.workflow_runs))throw new Error('Workflow response not recognized.');
 const list=$('workflow-list');list.replaceChildren();
 const runs=value.workflow_runs.filter(x=>Number.isSafeInteger(x.id)&&typeof x.name==='string'&&['completed','in_progress','queued','waiting','requested','pending'].includes(x.status)).slice(0,5);
 if(!runs.length){const p=document.createElement('p');p.className='muted';p.textContent='No eligible workflow receipts returned.';list.append(p);return;}
 for(const run of runs){const a=document.createElement('a');a.className='workflow-row';a.href='https://github.com/'+REPO+'/actions/runs/'+run.id;a.target='_blank';a.rel='noopener noreferrer';const dot=document.createElement('span');dot.className='workflow-dot '+(run.status==='completed'?(run.conclusion==='success'?'success':'failure'):'pending');dot.setAttribute('aria-hidden','true');const copy=document.createElement('span');copy.className='workflow-copy';const title=document.createElement('strong');title.textContent=run.name;const sub=document.createElement('small');sub.textContent=(run.conclusion||run.status)+' · '+(run.created_at?new Date(run.created_at).toLocaleString():'time unavailable');copy.append(title,sub);a.append(dot,copy);list.append(a);}
}
function renderPR(number,value){
 if(!value||value.number!==number||!['open','closed'].includes(value.state)||typeof value.merged!=='boolean'||!isSha(value.head?.sha))throw new Error('PR response not recognized.');
 set('pr'+number+'-status',(value.merged?'Merged':value.state+(value.draft?' · draft':''))+' · head '+short(value.head.sha)+'. Source status only; this does not establish a learning result.');
}
function renderDevelopment(value){
 if(!isSha(value?.object?.sha))throw new Error('Development branch reference not recognized.');
 set('overview-dev',short(value.object.sha));set('overview-dev-label','GitHub branch head, not pilot status');
 set('research-head',short(value.object.sha));set('research-head-note','Current Ora 2 development branch · verified GitHub ref');
}
function drawWorld(positions,current,goal){
 const board=$('world-board'),svg=$('world-trail'),visited=positions.filter(pos);board.replaceChildren();svg.replaceChildren();
 for(let y=2;y>=-2;y--)for(let x=-2;x<=2;x++){
  const cell=document.createElement('button'),p=[x,y],count=visited.filter(v=>same(v,p)).length;
  cell.type='button';cell.className='cell'+(count?' visited':'')+(same(p,current)?' active':'')+(same(p,goal)?' goal':'');
  const coord=document.createElement('span');coord.className='coord';coord.textContent=x+', '+y;cell.append(coord);
  cell.setAttribute('aria-label',vec(p)+(same(p,current)?', recorded position':'')+(same(p,goal)?', active goal':'')+', '+count+' appearances in pinned trail');
  cell.addEventListener('click',()=>set('world-cell-note',vec(p)+' · '+count+' appearances in this displayed pinned trail; not a lifetime count.'));
  board.append(cell);
 }
 if(visited.length>1){const line=document.createElementNS('http://www.w3.org/2000/svg','polyline');line.setAttribute('points',visited.map(p=>((p[0]+2)*100+50)+','+((2-p[1])*100+50)).join(' '));line.setAttribute('fill','none');line.setAttribute('stroke','currentColor');line.setAttribute('stroke-width','3');line.setAttribute('stroke-opacity','.8');svg.append(line);}
}
async function loadWorld(){
 if(mapLoading)return;mapLoading=true;$('load-world').disabled=true;
 try{
  set('world-status','Resolving one exact original-Ora state commit…');
  const ref=await getJson(API+'/git/ref/heads/autonomous/growth'),pinned=ref?.object?.sha;
  if(!isSha(pinned))throw new Error('Original state ref did not resolve to a commit.');
  const state=normalizeSnapshot(await getJson(RAW+'/'+pinned+'/state/organism.json',{large:true,onProgress:n=>set('world-status','Reading pinned state: '+(n/1048576).toFixed(1)+' MiB…')}));
  const lab=state.planning_lab,rows=lab.transition_observations.filter(r=>r?.world_version===lab.world_version&&pos(r.before)&&pos(r.after)).slice(-24);
  let trail=[];for(const row of rows){if(trail.length&&!same(trail[trail.length-1],row.before))trail=[];if(!trail.length)trail.push(row.before);trail.push(row.after);}
  if(!trail.length||!same(trail[trail.length-1],lab.position))trail=[lab.position];
  const goal=lab.goals.find(g=>g.id===lab.active_goal_id&&g.status==='active'&&pos(g.target));
  drawWorld(trail,lab.position,goal?.target);
  set('world-cycle',state.cycles.toLocaleString());set('world-position',vec(lab.position));set('world-goal',goal?vec(goal.target):'No active goal');set('world-sha',short(pinned));
  set('world-cell-note','Recorded position and '+trail.length+' displayed trail points. Select a cell to inspect.');
  snapshotCycle=state.cycles;$('world-content').hidden=false;
  set('world-status','Loaded cycle '+state.cycles+' from exact commit '+short(pinned)+'. This snapshot will not auto-refresh.');
  $('load-world').textContent='Load a fresh snapshot ↻';renderReceipt();
 }catch(e){set('world-status',errorMessage(e)+(snapshotCycle!==null?' Earlier pinned map retained; it is not current.':''));}
 finally{mapLoading=false;$('load-world').disabled=false;}
}
async function refresh({force=false}={}){
 if(refreshing||document.hidden)return;refreshing=true;$('refresh').disabled=true;
 let errors=0;const jobs=[(async()=>{
  try{receipt=normalizeReceipt(await getJson(RAW+'/autonomous/growth/state/heartbeat_operation.json'));receiptError=null;}
  catch(e){receiptError=errorMessage(e);errors++;}
  renderReceipt();
 })()];
 const now=Date.now(),apiAllowed=!lastApi||now-lastApi>=300000||(force&&now-lastApi>=30000);
 if(apiAllowed){
  lastApi=now;apiError=false;
  const calls=[
   [API+'/git/ref/heads/ora2/temporal-phase42-20261007',renderDevelopment,()=>{set('overview-dev','—');set('overview-dev-label','Branch read unavailable');set('research-head-note','Current branch read unavailable');}],
   [API+'/pulls/258',v=>renderPR(258,v),()=>set('pr258-status','Current PR status unavailable; consult source.')],
   [API+'/pulls/259',v=>renderPR(259,v),()=>set('pr259-status','Current PR status unavailable; consult source.')],
   [API+'/actions/runs?branch=main&per_page=6',renderWorkflow,()=>{const p=document.createElement('p');p.className='muted';p.textContent='Workflow feed unavailable; open GitHub Actions for evidence.';$('workflow-list').replaceChildren(p);}]
  ];
  for(const [url,render,fallback] of calls)jobs.push((async()=>{try{render(await getJson(url));}catch(e){apiError=true;errors++;fallback();}})());
 }
 try{await Promise.all(jobs);set('sync-indicator',(errors||apiError||receiptError?'Some reads unavailable · ':'Sources checked · ')+new Date().toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})+(force&&!apiAllowed?' · API throttled':''));}
 finally{refreshing=false;$('refresh').disabled=false;}
}
const tabs=['overview','live','research'];
function selectTab(name,{focus=false}={}){
 if(!tabs.includes(name))return;
 for(const tab of tabs){const selected=tab===name;$('tab-'+tab).setAttribute('aria-selected',String(selected));$('tab-'+tab).tabIndex=selected?0:-1;$('panel-'+tab).hidden=!selected;}
 set('current-section',name==='overview'?'Overview':name==='live'?'Original Ora':'Ora 2 Research');
 if(focus)$('tab-'+name).focus();
}
for(const name of tabs){
 $('tab-'+name).addEventListener('click',()=>selectTab(name));
 $('tab-'+name).addEventListener('keydown',e=>{
  if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home','End'].includes(e.key))return;
  e.preventDefault();const i=tabs.indexOf(name),next=e.key==='Home'?tabs[0]:e.key==='End'?tabs[2]:tabs[(i+(e.key==='ArrowLeft'||e.key==='ArrowUp'?2:1))%3];selectTab(next,{focus:true});
 });
}
for(const button of document.querySelectorAll('[data-go]'))button.addEventListener('click',()=>{selectTab(button.dataset.go);window.scrollTo({top:0,behavior:'auto'});});
for(const button of document.querySelectorAll('[data-filter]'))button.addEventListener('click',()=>{
 const filter=button.dataset.filter;
 for(const item of document.querySelectorAll('[data-filter]')){const selected=item===button;item.classList.toggle('selected',selected);item.setAttribute('aria-pressed',String(selected));}
 for(const item of document.querySelectorAll('.study[data-result]'))item.hidden=filter!=='all'&&item.dataset.result!==filter;
});
$('refresh').addEventListener('click',()=>refresh({force:true}));$('load-world').addEventListener('click',loadWorld);
refresh();setInterval(()=>refresh(),60000);setInterval(()=>{if(!document.hidden&&receipt)renderReceipt();},15000);document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});
window.OraObservatory=Object.freeze({normalizeReceipt,normalizeSnapshot,renderReceipt,renderDevelopment,renderPR,selectTab,age,pos});

})();
