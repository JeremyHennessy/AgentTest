"""Read-only browser checks. Network replies are captured or explicitly authored fixtures.
No live AgentTest action, repository write, or learning experiment is performed.
"""
from pathlib import Path
import json
import os
import shutil
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get('OBSERVER_EVIDENCE', str(ROOT / 'evidence')))
OUT.mkdir(exist_ok=True)
TEST_HEAD = '58e79e4a15566d4e20c807f78e67e7709fdca192'
DEV = '7652ce2439a90d6c4f01e6f0b3537b3f13875905'
GROWTH = '6d943636c4b524dfe626db5769d2b8c8a2361624'
# Captured fields from the immutable real receipt read via the GitHub connector.
RECEIPT = {
 'version':'heartbeat-transport-v1','status':'completed','mode':'ordinary',
 'input_cycle':6702,'result_cycle':6703,'input_journal_size':93778836,
 'cycle_time':'2026-10-07T23:23:52.214765+00:00',
 'source_sha':'2d9ac236d7bc4e487df13efffe964a081ad8f3c9','original_run_id':37701996330
}
# Authored schema fixture only, never presented as a captured live-world state.
SNAPSHOT = {'cycles':6703,'planning_lab':{'bounds':2,'world_version':'bounded-stateful-world-v1',
 'position':[1,0],'active_goal_id':None,'active_plan_id':None,
 'goals':[{'id':'old-goal','status':'completed','target':[2,2]}],'plans':[],
 'transition_observations':[{'world_version':'bounded-stateful-world-v1','before':[1,1],'after':[1,0]}]}}

checks=[]
def check(name, condition):
 if not condition: raise AssertionError(name)
 checks.append(name)

with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'),headless=True,args=['--no-sandbox'])
 context=browser.new_context(viewport={'width':1440,'height':1150},device_scale_factor=1)
 page=context.new_page()
 errors=[]; requests=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 fail=[False]
 def route(r):
  requests.append({'url':r.request.url,'method':r.request.method})
  if fail[0]:
   r.fulfill(status=503,body='unavailable',headers={'access-control-allow-origin':'*'});return
  url=r.request.url
  if url.startswith('https://observer.test/'):
   name=url.rsplit('/',1)[-1]
   r.fulfill(status=200,content_type='text/css' if name.endswith('.css') else 'text/javascript',body=(ROOT/name).read_text(),headers={'access-control-allow-origin':'*'});return
  if url.endswith('heartbeat_operation.json'): value=RECEIPT
  elif url.endswith('/pulls/245'): value={'number':245,'merged':True,'draft':False,'state':'closed','head':{'sha':'273fd9edf7daf0cdf9809267e6de4e574e5fdecf'}}
  elif 'ref/heads/ora2' in url: value={'object':{'sha':DEV}}
  elif 'ref/heads/autonomous' in url: value={'object':{'sha':GROWTH}}
  elif url.endswith('/state/organism.json'): value=SNAPSHOT
  else:
   r.abort();return
  r.fulfill(status=200,content_type='application/json',body=json.dumps(value),headers={'access-control-allow-origin':'*'})
 context.route('https://**/*',route)
 page.set_content((ROOT/'observer.html').read_text().replace('<head>','<head><base href="https://observer.test/">'))
 page.wait_for_function("document.getElementById('checked').textContent.includes('Sources checked')")
 check('25 copied-world cell buttons',page.locator('#lab-board button').count()==25)
 check('resolved code hold distinct from pilot status',page.locator('#hold-title').inner_text()=='Repository status has advanced.')
 check('negative timing result remains visible after code merge','Pilot screen not met.' in page.locator('#timing-result').inner_text())
 check('one-of-four timing result is separate from selector result','1 / 4' in page.locator('#timing-result').inner_text() and '13 / 16' in page.locator('#panel-lab').inner_text())
 check('empty shared commitment cohort not hidden','no initially active goals' in page.locator('#timing-result').inner_text())
 check('two selected copied actions not described as live',page.locator('#panel-lab').inner_text().count('not a live')>=1)
 check('no large snapshot automatically requested',not any(r['url'].endswith('organism.json') for r in requests))
 check('all automatic reads are GET',all(r['method']=='GET' for r in requests))
 check('all eight timeline records visible',page.locator('#timeline .timeline-row').count()==8)
 check('learner ownership separated',page.locator('#timeline .owner.learner').count()==2)
 page.locator('#pick-1776').click()
 check('action inspector selects actual recorded movement',page.locator('#action-outcome').inner_text()=='[1, 1] → [1, 0]')
 check('inspector preserves old plan attribution','stayed at 2' in page.locator('#action-plan').inner_text())
 page.locator('#lab-board button').first.click()
 check('cell inspection uses displayed-run counts','displayed' in page.locator('#lab-cell-note').inner_text())
 page.locator('#pick-1779').click()
 for width in (1440,1024,768,620,390,320):
  page.set_viewport_size({'width':width,'height':950})
  check('no horizontal body overflow '+str(width),page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
 page.set_viewport_size({'width':1440,'height':1150})
 page.screenshot(path=str(OUT/'observer-desktop.png'),full_page=True)
 page.set_viewport_size({'width':390,'height':844})
 page.screenshot(path=str(OUT/'observer-mobile.png'),full_page=True)
 page.set_viewport_size({'width':1440,'height':1050})
 page.locator('#tab-lab').focus();page.keyboard.press('ArrowRight')
 check('keyboard tab selection',page.locator('#tab-live').get_attribute('aria-selected')=='true')
 check('live receipt uses captured result cycle',page.locator('#live-cycle').inner_text()=='6,703')
 check('source version shown separately',page.locator('#live-source').inner_text()=='2d9ac236')
 page.screenshot(path=str(OUT/'observer-live-receipt.png'),full_page=True)
 page.locator('#load-live-map').click()
 page.wait_for_function("document.getElementById('live-map-status').textContent.startsWith('Loaded cycle')")
 check('live snapshot requested by exact commit',any('/'+GROWTH+'/state/organism.json' in r['url'] for r in requests))
 check('absent active goal does not revive a completed goal',page.locator('#snapshot-goal').inner_text()=='No active goal')
 check('loaded authored-schema snapshot has 25 cells',page.locator('#live-board button').count()==25)
 for width in (390,320):
  page.set_viewport_size({'width':width,'height':844})
  check('live view no horizontal overflow '+str(width),page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
 invalid=page.evaluate("""()=>{let n=0;for(const r of [null,{}, {version:'heartbeat-transport-v1',status:'completed',input_cycle:2,result_cycle:20,source_sha:'a'.repeat(40),cycle_time:'2026-10-07T00:00:00Z',original_run_id:1}]){try{OraObserver.normalizeReceipt(r)}catch(e){n++}}return n;}""")
 check('missing and inconsistent receipts rejected',invalid==3)
 page.evaluate("OraObserver.renderPR({number:245,merged:false,draft:true,state:'open',head:{sha:'b'.repeat(40)}})")
 check('newer head does not inherit old verification','newer candidate' in page.locator('#hold-title').inner_text())
 check('old test remains pinned',page.locator('#map-cycle').inner_text()=='Cycle 1779')
 page.evaluate("OraObserver.renderPR({number:245,merged:true,draft:false,state:'closed',head:{sha:'b'.repeat(40)}})")
 check('merged PR distinguished without new test claim','historical test receipt' in page.locator('#hold-text').inner_text())
 # Normalizing a future clock is explicit rather than claiming fresh/healthy.
 check('future timestamps not silently fresh',page.evaluate("OraObserver.age('2099-01-01T00:00:00Z')").startswith('Source time'))
 fail[0]=True
 page.locator('#refresh').click();page.wait_for_function("document.getElementById('live-error').textContent.includes('last successful')")
 check('read failure retains data with warning',page.locator('#live-cycle').inner_text()=='6,703' and 'Read failed' in page.locator('#live-health').inner_text())
 check('unavailable source not shown as current healthy receipt','red' in page.locator('#live-health').get_attribute('class'))
 check('no page exceptions',not errors)
 context.close()
 # Independent first-load failures: no false zeros or bootstrapped live state.
 context=browser.new_context(viewport={'width':390,'height':844});page=context.new_page()
 context.route('https://**/*',lambda r:r.fulfill(status=200,content_type='text/css' if r.request.url.endswith('.css') else 'text/javascript',body=(ROOT/r.request.url.rsplit('/',1)[-1]).read_text()) if r.request.url.startswith('https://observer.test/') else r.fulfill(status=429,body='',headers={'access-control-allow-origin':'*'}))
 page.set_content((ROOT/'observer.html').read_text().replace('<head>','<head><base href="https://observer.test/">'));page.wait_for_function("document.getElementById('checked').textContent.includes('unavailable')")
 check('cold error shows unavailable not cycle zero',page.locator('#live-cycle').inner_text()=='—')
 check('historical test usable offline',page.locator('#lab-board button').count()==25)
 check('cold error explains public read limit','read limit' in page.locator('#pr-status').inner_text())
 context.close();browser.close()

(OUT/'browser-checks.json').write_text(json.dumps({'passed':len(checks),'checks':checks,'page_errors':errors,
 'browser':'system Chromium via Playwright','scope':'Local rendered page; captured heartbeat/PR fields and authored schema/error fixtures. No live-site visual verification.','requests':requests},indent=2)+'\n')
print(json.dumps({'passed':len(checks),'page_errors':errors,'scope':'local rendered UI; fixture-bound network'},indent=2))
