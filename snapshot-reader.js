'use strict';
/* Immutable Git-commit-bound original Ora snapshot adapter. GET only. */
(function(root){
const LIMIT=512*1024*1024, CHUNK=32*1024*1024, GZIP_MAX=96*1024*1024;
const SOURCE=/^https:\/\/raw\.githubusercontent\.com\/JeremyHennessy\/AgentTest\/[0-9a-f]{40}\/state$/;
const SHA=/^[0-9a-f]{64}$/, PART=/^snapshot-part-[0-9]{6}\.bin$/;
const INTEGER=v=>Number.isSafeInteger(v)&&v>=0;
const EXACT=(obj,names)=>obj&&typeof obj==='object'&&!Array.isArray(obj)&&Object.keys(obj).sort().join('|')===names.slice().sort().join('|');
function valid(condition,message){if(!condition)throw new Error('Original snapshot: '+message);}
function boundBytes(value,size,label){valid(INTEGER(value)&&value>0&&value<=size,label+' length');}
function digestHex(bytes){
  valid(root.crypto&&root.crypto.subtle,'SHA-256 verification unavailable');
  return root.crypto.subtle.digest('SHA-256',bytes).then(b=>Array.from(new Uint8Array(b),x=>x.toString(16).padStart(2,'0')).join(''));
}
async function fetchBytes(url,maxBytes){
  const abort=new AbortController(),timer=setTimeout(()=>abort.abort(),120000);
  try{
    const res=await fetch(url,{method:'GET',credentials:'omit',cache:'no-store',signal:abort.signal});
    valid(res.ok,'immutable part HTTP '+res.status);
    const declared=Number(res.headers.get('content-length'));
    if(declared>maxBytes)throw new Error('Original snapshot: part exceeds size limit');
    const bytes=new Uint8Array(await res.arrayBuffer());
    boundBytes(bytes.byteLength,maxBytes,'actual part');
    return bytes;
  }finally{clearTimeout(timer);}
}
function parseRaw(bytes,cycle){
  let value;
  try{value=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes));}
  catch(e){throw new Error('Original snapshot: reconstructed JSON invalid');}
  valid(value&&typeof value==='object'&&!Array.isArray(value)&&value.cycles===cycle,'reconstructed cycle mismatch');
  return value;
}
async function resolve(base,manifest,progress){
  valid(SOURCE.test(base),'invalid immutable source URL');
  valid(manifest&&typeof manifest==='object'&&!Array.isArray(manifest),'manifest not an object');
  if(!Object.hasOwn(manifest,'format'))return manifest;
  const cycle=manifest.cycle;
  valid(INTEGER(cycle),'declared cycle invalid');
  boundBytes(manifest.raw_bytes,LIMIT,'raw snapshot');
  valid(typeof manifest.raw_sha256==='string'&&SHA.test(manifest.raw_sha256),'invalid whole-state digest');
  let raw;
  if(manifest.format==='ora-original-raw-chunks-v1'){
    valid(EXACT(manifest,['format','raw_bytes','raw_sha256','cycle','chunk_bytes','parts']),'chunk metadata mismatch');
    valid(manifest.chunk_bytes===CHUNK,'chunk size contract mismatch');
    valid(Array.isArray(manifest.parts)&&manifest.parts.length===Math.ceil(manifest.raw_bytes/CHUNK),'missing or excess chunks');
    raw=new Uint8Array(manifest.raw_bytes);
    let written=0;
    for(let i=0;i<manifest.parts.length;i++){
      const part=manifest.parts[i],name='snapshot-part-'+String(i).padStart(6,'0')+'.bin';
      valid(EXACT(part,['name','bytes','sha256'])&&part.name===name&&PART.test(part.name),'invalid part path/order');
      const size=i+1===manifest.parts.length?manifest.raw_bytes-i*CHUNK:CHUNK;
      valid(INTEGER(part.bytes)&&part.bytes===size&&typeof part.sha256==='string'&&SHA.test(part.sha256),'invalid part length/hash');
      const bytes=await fetchBytes(base+'/'+name,CHUNK);
      valid(bytes.length===size&&await digestHex(bytes)===part.sha256,'part content hash mismatch');
      raw.set(bytes,written);written+=bytes.length;
      if(typeof progress==='function')progress(written);
    }
    valid(written===manifest.raw_bytes,'incomplete chunk generation');
  }else if(manifest.format==='ora-original-gzip-v1'){
    valid(EXACT(manifest,['format','raw_bytes','raw_sha256','gzip_bytes','gzip_sha256','gzip_file','cycle']),'gzip metadata mismatch');
    boundBytes(manifest.gzip_bytes,GZIP_MAX,'gzip');
    valid(typeof manifest.gzip_sha256==='string'&&SHA.test(manifest.gzip_sha256),'invalid gzip hash');
    const expected='snapshot-'+manifest.gzip_sha256+'.json.gz';
    valid(manifest.gzip_file===expected||manifest.gzip_file==='snapshot-current.json.gz','invalid gzip source path');
    const packed=await fetchBytes(base+'/'+manifest.gzip_file,GZIP_MAX);
    valid(packed.length===manifest.gzip_bytes&&await digestHex(packed)===manifest.gzip_sha256,'gzip identity mismatch');
    valid(typeof root.DecompressionStream==='function','gzip decompression unavailable');
    const reader=new Blob([packed]).stream().pipeThrough(new root.DecompressionStream('gzip')).getReader();
    const parts=[];let total=0;
    try{
      for(;;){const item=await reader.read();if(item.done)break;
        total+=item.value.length;
        valid(total<=manifest.raw_bytes,'gzip expands beyond declared original length');
        parts.push(item.value);
        if(typeof progress==='function')progress(total);
      }
    }catch(e){await reader.cancel().catch(()=>{});throw e;}
    valid(total===manifest.raw_bytes,'truncated gzip reconstruction');
    raw=new Uint8Array(total);let cursor=0;
    for(const item of parts){raw.set(item,cursor);cursor+=item.length;}
  }else{
    throw new Error('Original snapshot: unsupported format');
  }
  valid(raw.length===manifest.raw_bytes&&await digestHex(raw)===manifest.raw_sha256,'whole-state SHA-256 mismatch');
  return parseRaw(raw,cycle);
}
root.OraSnapshotReader=Object.freeze({resolve});
})(globalThis);
