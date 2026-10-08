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
// INSERT SECOND HALF
})();
