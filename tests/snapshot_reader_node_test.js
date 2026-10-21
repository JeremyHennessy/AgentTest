const fs=require('node:fs');
const assert=require('node:assert/strict');
const {createHash,webcrypto}=require('node:crypto');
const {gzipSync}=require('node:zlib');
globalThis.crypto=webcrypto;
require('./snapshot-reader.js');
const sha=b=>createHash('sha256').update(b).digest('hex');
const source='https://raw.githubusercontent.com/JeremyHennessy/AgentTest/'+'b'.repeat(40)+'/state';
const original=Buffer.from(JSON.stringify({cycles:9904,planning_lab:{bounds:2},history:[1,2,3]}));
const chunks={'snapshot-part-000000.bin':original};
const requests=[];
globalThis.fetch=async (url,options)=>{
  requests.push({url,options});
  const name=url.slice(url.lastIndexOf('/')+1);
  if(!Object.hasOwn(chunks,name))return new Response(null,{status:404});
  return new Response(chunks[name],{status:200,headers:{'content-length':String(chunks[name].length)}});
};
(async()=>{
 const reader=globalThis.OraSnapshotReader;
 const plain={cycles:9904};
 assert.equal(await reader.resolve(source,plain),plain);
 assert.equal(requests.length,0);
 const manifest={format:'ora-original-raw-chunks-v1',raw_bytes:original.length,raw_sha256:sha(original),
  cycle:9904,chunk_bytes:33554432,parts:[{name:'snapshot-part-000000.bin',bytes:original.length,sha256:sha(original)}]};
 let progress=0;
 assert.equal((await reader.resolve(source,manifest,n=>progress=n)).cycles,9904);
 assert.equal(progress,original.length);
 assert.equal(requests[0].options.method,'GET');
 assert.equal(requests[0].options.credentials,'omit');
 await assert.rejects(reader.resolve(source,{...manifest,raw_sha256:'0'.repeat(64)}),/whole-state SHA-256 mismatch/);
 await assert.rejects(reader.resolve(source,{...manifest,parts:[{...manifest.parts[0],name:'../outside'}]}),/part path/);
 await assert.rejects(reader.resolve(source,{...manifest,parts:[]}),/missing or excess/);
 await assert.rejects(reader.resolve('https://example.com/state',manifest),/source URL/);
 const zipped=gzipSync(original,{mtime:0}),packedName='snapshot-current.json.gz';
 chunks[packedName]=zipped;
 const gz={format:'ora-original-gzip-v1',raw_bytes:original.length,raw_sha256:sha(original),cycle:9904,
  gzip_bytes:zipped.length,gzip_sha256:sha(zipped),gzip_file:packedName};
 assert.equal((await reader.resolve(source,gz)).cycles,9904);
 await assert.rejects(reader.resolve(source,{...gz,gzip_sha256:'0'.repeat(64)}),/gzip identity/);
 await assert.rejects(reader.resolve(source,{...manifest,format:'alien-format'}),/unsupported format/);
 console.log('observer immutable raw/gzip/chunk loader tests passed');
})().catch(e=>{console.error(e);process.exitCode=1});
