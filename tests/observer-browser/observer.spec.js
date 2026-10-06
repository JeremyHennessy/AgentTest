const {test:base,expect}=require('@playwright/test');
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const {execFileSync}=require('node:child_process');
const fixture=require('./fixture.json');
const root=path.resolve(__dirname,'../..');
const html=fs.readFileSync(path.join(root,'index.html'),'utf8');
const shaA='a'.repeat(40),shaB='b'.repeat(40),shaC='c'.repeat(40);
const origin='https://observer-ui.invalid/';
const digest=value=>crypto.createHash('sha256').update(value).digest('hex');
const clone=value=>structuredClone(value);
const cors={'access-control-allow-origin':'*','access-control-allow-methods':'GET, OPTIONS','access-control-allow-headers':'*'};

function snapshot(generation=4599){
  const result=clone(fixture);
  result.organism.generation=generation;
  if(generation>4599)result.organism.updated_at='2026-10-05T12:09:30Z';
  result.interaction.response_text='Synthetic fixture generation '+generation+'; no live Ora state.';
  return result;
}
async function createHarness(page,context){
  const states=new Map([[shaA,snapshot()]]),holds=new Map(),errors=[],requests=[],unexpected=[];
  let head=shaA,refStatus=200;
  await page.clock.install({time:new Date('2026-10-05T12:10:00Z')});
  await page.clock.pauseAt(new Date('2026-10-05T12:10:01Z'));
  await page.addInitScript(()=>{
    window.__fixtureHandoffs=[];
    window.open=(...args)=>{window.__fixtureHandoffs.push(args);return null};
  });
  page.on('pageerror',error=>errors.push(error.message));
  await context.route('**/*',async route=>{
    const request=route.request(),url=new URL(request.url()),method=request.method();
    const log={url:request.url(),method};requests.push(log);
    if(method!=='GET'&&method!=='OPTIONS'){unexpected.push(log);return route.abort()}
    if(url.origin==='https://observer-ui.invalid'&&url.pathname==='/'){
      log.kind='page';return route.fulfill({contentType:'text/html',body:html});
    }
    if(url.origin==='https://observer-ui.invalid'&&url.pathname==='/favicon.ico'){
      log.kind='favicon';return route.fulfill({status:404,body:''});
    }
    if(url.hostname==='api.github.com'&&url.pathname==='/repos/JeremyHennessy/AgentTest/git/ref/heads/autonomous/growth'){
      log.kind='ref';log.sha=head;
      const capturedHead=head,status=refStatus;
      if(method==='OPTIONS')return route.fulfill({status:204,headers:cors});
      if(holds.has('ref'))await holds.get('ref').promise;
      return route.fulfill({status,headers:cors,json:{object:{sha:capturedHead}}});
    }
    const match=url.hostname==='raw.githubusercontent.com'&&url.pathname.match(/^\/JeremyHennessy\/AgentTest\/([a-f0-9]{40})\/state\/(organism|last_interaction|phase42_resumption_opportunities)\.json$/);
    if(match){
      log.kind='state';log.sha=match[1];log.file=match[2]+'.json';
      if(method==='OPTIONS')return route.fulfill({status:204,headers:cors});
      const stored=states.get(log.sha),key=match[2]==='organism'?'organism':match[2]==='last_interaction'?'interaction':'diagnostic';
      if(!stored){unexpected.push(log);return route.abort()}
      const data=clone(stored[key]),status=stored.http?.[log.file]||200,hold=holds.get(log.sha+'/'+log.file);
      if(hold)await hold.promise;
      return route.fulfill({status,headers:cors,json:data});
    }
    unexpected.push(log);return route.abort();
  });
  return {
    page,context,requests,unexpected,errors,
    publish(sha,data){states.set(sha,clone(data));head=sha},
    refError(status){refStatus=status},
    hold(key){let release;const promise=new Promise(resolve=>release=resolve);holds.set(key,{promise,release});return ()=>{release();holds.delete(key)}},
    releaseAll(){for(const held of holds.values())held.release();holds.clear()},
    count(kind,sha,file){return requests.filter(r=>r.method==='GET'&&r.kind===kind&&(!sha||r.sha===sha)&&(!file||r.file===file)).length},
    async boot(ready=true){await page.goto(origin);if(ready)await expect(page.locator('#generation')).toHaveText('4599')},
    async refresh(){await page.getByRole('button',{name:'Refresh now',exact:true}).click()},
    async settled(){await expect(page.locator('#refresh')).toHaveAttribute('aria-busy','false')},
    async data(){return page.evaluate(()=>Object.fromEntries([...document.querySelectorAll('[id]')].filter(node=>!['liveStatus','refresh','refreshFoot'].includes(node.id)).map(node=>[node.id,{html:node.innerHTML,attributes:[...node.attributes].map(a=>[a.name,a.value])}])))}
  };
}

const test=base.extend({
  harness:async({page,context,browser},use,testInfo)=>{
    const harness=await createHarness(page,context);
    try{await use(harness)}finally{
      harness.releaseAll();
      const manifest={
        head:execFileSync('git',['rev-parse','HEAD'],{cwd:root,encoding:'utf8'}).trim(),
        expectedHead:process.env.OBSERVER_EXPECTED_HEAD_SHA||null,
        originalHtmlSha256:digest(html),fixtureSha256:digest(JSON.stringify(fixture)),fixtureOnly:true,
        project:testInfo.project.name,viewport:testInfo.project.use.viewport,test:testInfo.title,status:testInfo.status,
        browser:browser.version(),playwright:require('@playwright/test/package.json').version,
        requests:harness.requests,blockedUnexpected:harness.unexpected,pageErrors:harness.errors
      };
      const file=testInfo.outputPath('manifest.json');fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,JSON.stringify(manifest,null,2));
      await testInfo.attach('exact-head synthetic fixture manifest',{path:file,contentType:'application/json'});
      expect(harness.unexpected,'all browser traffic must stay within intercepted fixtures').toEqual([]);
      expect(harness.errors,'no uncaught browser script errors').toEqual([]);
    }
  }
});
async function screenshot(page,testInfo,name,fullPage=false){
  const file=testInfo.outputPath(name+'.png');
  await page.screenshot({path:file,fullPage,animations:'disabled'});
  await testInfo.attach(name,{path:file,contentType:'image/png'});
}
async function expectNoOverflow(page){
  const sizes=await page.evaluate(()=>({viewport:innerWidth,document:document.documentElement.scrollWidth}));
  expect(sizes.document).toBeLessThanOrEqual(sizes.viewport);
  const map=await page.locator('#worldGrid').boundingBox();
  expect(map.width).toBeGreaterThan(100);expect(map.x).toBeGreaterThanOrEqual(0);expect(map.x+map.width).toBeLessThanOrEqual(sizes.viewport+1);
}

test('layout, useful map and expandable evidence render without viewport overflow',async({harness:h},testInfo)=>{
  await h.boot();await expectNoOverflow(h.page);
  await expect(h.page.locator('#nowPlan')).toContainText('east');
  await expect(h.page.locator('#nowQuestion')).toHaveText('Will east still move me from the boundary?');
  await expect(h.page.locator('#nowLearning')).toContainText('the hypothesis was refuted');
  await expect(h.page.locator('#plannedPath')).not.toHaveAttribute('points','');
  await expect(h.page.getByRole('img',{name:/Bounded world map: Ora at/})).toHaveCount(1);
  await screenshot(h.page,testInfo,'main-top');await screenshot(h.page,testInfo,'main-full',true);
  await h.page.locator('#researchFrontierCard > summary').click();
  await h.page.locator('.evidence-drawer > summary').first().click();
  await expect(h.page.locator('#researchFrontierCard')).toHaveAttribute('open','');
  await expect(h.page.locator('.evidence-drawer').first()).toHaveAttribute('open','');
  await expect(h.page.locator('#agendaOpportunityStatus')).toHaveText('127 retained-window qualifying opportunities were recognized but remained lower priority.');
  await expectNoOverflow(h.page);
  await h.page.locator('#futurePlans').scrollIntoViewIfNeeded();await screenshot(h.page,testInfo,'roadmap-expanded');
  await screenshot(h.page,testInfo,'evidence-expanded-full',true);
});

test('keyboard skip, focus, disclosure and owner handoff remain accessible without live interaction',async({harness:h},testInfo)=>{
  await h.boot();await h.page.keyboard.press('Tab');await expect(h.page.locator('.skip-link')).toBeFocused();
  const outline=await h.page.locator('.skip-link').evaluate(node=>getComputedStyle(node).outlineStyle);expect(outline).not.toBe('none');
  await screenshot(h.page,testInfo,'keyboard-focus');
  await h.page.keyboard.press('Enter');await expect(h.page.locator('#nowStory')).toBeFocused();
  await h.page.keyboard.press('Tab');await expect(h.page.locator('.capability-history > summary')).toBeFocused();
  await h.page.keyboard.press('Enter');await expect(h.page.locator('.capability-history')).toHaveAttribute('open','');
  const owner=h.page.locator('details').filter({has:h.page.locator('#message')});
  await owner.locator(':scope > summary').focus();await h.page.keyboard.press('Enter');await expect(owner).toHaveAttribute('open','');
  await expect(h.page.getByLabel('Message for Ora')).toBeVisible();await h.page.getByLabel('Message for Ora').fill('Synthetic UI handoff & <fixture>');
  await h.page.getByRole('button',{name:'Open secure GitHub handoff',exact:true}).click();
  const handoffs=await h.page.evaluate(()=>window.__fixtureHandoffs);expect(handoffs).toHaveLength(1);
  expect(handoffs[0][2]).toBe('noopener');expect(new URL(handoffs[0][0]).searchParams.get('body')).toBe('/agent Synthetic UI handoff & <fixture>');
  expect(h.context.pages()).toHaveLength(1);await expect(h.page.getByRole('status')).toHaveAttribute('aria-live','polite');
});

test('manual and periodic refresh overlap shares one immutable download; unchanged source avoids redownload',async({harness:h},testInfo)=>{
  await h.boot();expect(h.count('state',shaA,'organism.json')).toBe(1);
  await h.refresh();await h.settled();expect(h.count('ref')).toBe(2);expect(h.count('state',shaA)).toBe(3);
  h.publish(shaB,snapshot(4600));const release=h.hold(shaB+'/organism.json');
  await h.refresh();await expect.poll(()=>h.count('state',shaB,'organism.json')).toBe(1);
  await h.refresh();await h.page.clock.runFor(15000);
  expect(h.count('ref')).toBe(3);expect(h.count('state',shaB)).toBe(3);
  await expect(h.page.locator('#generation')).toHaveText('4599');await expect(h.page.locator('#sourceCommit')).toContainText('aaaaaaaaaa');
  release();await expect(h.page.locator('#generation')).toHaveText('4600');await expect(h.page.locator('#sourceCommit')).toContainText('bbbbbbbbbb');
  await h.refresh();await h.settled();expect(h.count('state',shaB,'organism.json')).toBe(1);
  await screenshot(h.page,testInfo,'overlap-coherent-result');
});

test('abandoned slow responses cannot overwrite a newer accepted generation and source',async({harness:h},testInfo)=>{
  await h.boot();h.publish(shaB,snapshot(4600));const release=h.hold(shaB+'/organism.json');
  await h.page.evaluate(()=>{window.__abandoned=loader.refresh({force:true})});await expect.poll(()=>h.count('state',shaB)).toBe(3);
  h.publish(shaC,snapshot(4601));await h.page.evaluate(()=>{loader.invalidate();window.__winner=loader.refresh({force:true})});
  await expect(h.page.locator('#generation')).toHaveText('4601');await expect(h.page.locator('#sourceCommit')).toContainText('cccccccccc');
  release();await h.page.evaluate(()=>window.__abandoned);await h.page.evaluate(()=>window.__winner);
  await expect(h.page.locator('#generation')).toHaveText('4601');await expect(h.page.locator('#sourceCommit')).toContainText('cccccccccc');
  await expect(h.page.getByRole('status')).toContainText('generation 4601');await screenshot(h.page,testInfo,'out-of-order-newest-source');
});

test('ref and immutable-file errors retain last good data and recover coherently',async({harness:h},testInfo)=>{
  await h.boot();const accepted=await h.data();h.refError(503);await h.refresh();await h.settled();
  await expect(h.page.getByRole('status')).toHaveText('Refresh failed · last good snapshot');expect(await h.data()).toEqual(accepted);
  h.refError(200);const next=snapshot(4600);next.http={'last_interaction.json':503};h.publish(shaB,next);await h.refresh();await h.settled();
  await expect(h.page.getByRole('status')).toHaveText('Refresh failed · last good snapshot');expect(await h.data()).toEqual(accepted);
  await screenshot(h.page,testInfo,'last-good-http-error');
  h.publish(shaB,snapshot(4600));await h.refresh();await expect(h.page.locator('#generation')).toHaveText('4600');
  await expect(h.page.locator('#sourceCommit')).toContainText('bbbbbbbbbb');await expect(h.page.getByRole('status')).toContainText('generation 4600');
  await screenshot(h.page,testInfo,'http-error-recovery');
});

test('malformed nested state preserves the whole render, source and later age tick before recovery',async({harness:h},testInfo)=>{
  await h.boot();const accepted=await h.data(),bad=snapshot(4600);bad.organism.agenda.threads={invalid:true};
  h.publish(shaB,bad);await h.refresh();await h.settled();
  await expect(h.page.getByRole('status')).toHaveText('Refresh failed · last good snapshot');expect(await h.data()).toEqual(accepted);
  expect(await h.page.evaluate(()=>organism.generation)).toBe(4599);await h.page.clock.runFor(1000);
  await expect(h.page.locator('#stateAge')).toHaveText('10m');await expect(h.page.locator('#generation')).toHaveText('4599');
  await expect(h.page.locator('#sourceCommit')).toContainText('aaaaaaaaaa');await screenshot(h.page,testInfo,'malformed-state-last-good');
  h.publish(shaB,snapshot(4600));await h.refresh();await expect(h.page.locator('#generation')).toHaveText('4600');
  await expect(h.page.locator('#sourceCommit')).toContainText('bbbbbbbbbb');expect(await h.page.evaluate(()=>organism.generation)).toBe(4600);
  await screenshot(h.page,testInfo,'malformed-state-recovery');
});

test('late renderer failure preserves all panels and global state, then recovers',async({harness:h},testInfo)=>{
  await h.boot();const accepted=await h.data();
  await h.page.evaluate(()=>{window.__originalTimeline=renderTimeline;renderTimeline=()=>{throw Error('Synthetic late renderer failure')}});
  h.publish(shaB,snapshot(4600));await h.refresh();await h.settled();expect(await h.data()).toEqual(accepted);
  await expect(h.page.locator('#refreshFoot')).toContainText('Synthetic late renderer failure');expect(await h.page.evaluate(()=>organism.generation)).toBe(4599);
  await h.page.evaluate(()=>{renderTimeline=window.__originalTimeline});await h.refresh();await expect(h.page.locator('#generation')).toHaveText('4600');
  await expect(h.page.locator('#sourceCommit')).toContainText('bbbbbbbbbb');await screenshot(h.page,testInfo,'late-render-recovery');
});

test('first-load render failure remains unavailable and can recover without invented data',async({harness:h},testInfo)=>{
  const bad=snapshot();bad.organism.agenda.threads='invalid';h.publish(shaA,bad);await h.boot(false);await h.settled();
  await expect(h.page.getByRole('status')).toHaveText('State unavailable');await expect(h.page.locator('#generation')).toHaveText('—');
  await expect(h.page.locator('#sourceCommit')).toHaveText('Displayed source pending');expect(await h.page.evaluate(()=>organism)).toBeNull();
  await screenshot(h.page,testInfo,'first-load-unavailable');h.publish(shaA,snapshot());await h.refresh();await expect(h.page.locator('#generation')).toHaveText('4599');
  await expect(h.page.locator('#sourceCommit')).toContainText('aaaaaaaaaa');
});
