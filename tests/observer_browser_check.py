"""Rendered Observer checks with explicitly authored API fixtures.

These are local/browser presentation checks, not a live Pages screenshot or
scientific verification. No GitHub writes or original Ora actions occur.
"""
from pathlib import Path
import json
import os
import shutil
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get('OBSERVER_EVIDENCE', str(ROOT / 'evidence')))
OUT.mkdir(parents=True, exist_ok=True)
DEV = 'a' * 40
GROWTH = 'b' * 40
RECEIPT = {
    'version': 'heartbeat-transport-v1', 'status': 'completed',
    'mode': 'ordinary', 'input_cycle': 7314, 'result_cycle': 7315,
    'input_journal_size': 3586438, 'cycle_time': '2026-10-08T20:10:37Z',
    'created_at': '2026-10-08T20:10:38Z',
    'source_sha': 'c' * 40, 'original_run_id': 37837348587,
}
SNAPSHOT = {'cycles': 7315, 'planning_lab': {
    'bounds': 2, 'world_version': 'bounded-stateful-world-v1',
    'position': [1, 0], 'active_goal_id': None, 'active_plan_id': None,
    'goals': [{'id': 'old-goal', 'status': 'completed', 'target': [2, 2]}],
    'plans': [],
    'transition_observations': [
        {'world_version': 'bounded-stateful-world-v1',
         'before': [1, 1], 'after': [1, 0]}],
}}
checks = []


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    checks.append(name)


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'),
                                headless=True, args=['--no-sandbox'])
    context = browser.new_context(viewport={'width': 1440, 'height': 1050})
    page = context.new_page()
    errors, requests = [], []
    page.on('pageerror', lambda e: errors.append(str(e)))
    failure = [False]
    pending = [False]

    def route(r):
        url = r.request.url
        requests.append({'url': url, 'method': r.request.method})
        if url.startswith('https://observer.test/'):
            name = url.rsplit('/', 1)[-1]
            r.fulfill(status=200, content_type='text/css' if name.endswith('.css') else 'text/javascript',
                      body=(ROOT / name).read_text())
            return
        if failure[0]:
            r.fulfill(status=503, body='unavailable', headers={'access-control-allow-origin': '*'})
            return
        if url.endswith('heartbeat_operation.json'):
            value = dict(RECEIPT)
            if pending[0]:
                value.pop('result_cycle')
                value['status'] = 'pending'
        elif url.endswith('/pulls/258'):
            value = {'number': 258, 'merged': True, 'draft': False, 'state': 'closed',
                     'head': {'sha': 'd' * 40}}
        elif url.endswith('/pulls/259'):
            value = {'number': 259, 'merged': False, 'draft': True, 'state': 'open',
                     'head': {'sha': 'e' * 40}}
        elif 'git/ref/heads/ora2' in url:
            value = {'object': {'sha': DEV}}
        elif 'git/ref/heads/autonomous' in url:
            value = {'object': {'sha': GROWTH}}
        elif '/actions/runs?' in url:
            value = {'workflow_runs': [
                {'id': 37837348587, 'name': 'heartbeat', 'status': 'completed',
                 'conclusion': 'success', 'created_at': '2026-10-08T20:10:00Z'},
                {'id': 37837348580, 'name': 'heartbeat controller', 'status': 'in_progress',
                 'conclusion': None, 'created_at': '2026-10-08T20:09:00Z'},
            ]}
        elif url.endswith('state/organism.json'):
            value = SNAPSHOT
        else:
            r.abort()
            return
        r.fulfill(status=200, content_type='application/json', body=json.dumps(value),
                  headers={'access-control-allow-origin': '*'})

    context.route('https://**/*', route)
    page.set_content((ROOT / 'observer.html').read_text().replace('<head>', '<head><base href="https://observer.test/">'))
    page.wait_for_function("document.getElementById('sync-indicator').textContent.includes('Sources checked')")
    check('fresh landing heading', 'Question the evidence.' in page.locator('h1').first.inner_text())
    check('real completed cycle', page.locator('#overview-cycle').inner_text() == '7,315')
    check('original receipt status separate', page.locator('#overview-heartbeat').inner_text() == 'Completed')
    check('development branch SHA', page.locator('#overview-dev').inner_text() == 'aaaaaaaa')
    check('no heavy snapshot on automatic load', not any(x['url'].endswith('organism.json') for x in requests))
    check('all remote reads GET', all(x['method'] == 'GET' for x in requests))
    check('three accessible tabs', page.locator('[role=tab]').count() == 3)
    check('original console preserved', page.locator('a[href="legacy.html"]').count() >= 1)
    page.screenshot(path=str(OUT / 'observer-new-desktop.png'), full_page=True)
    page.locator('#tab-overview').focus()
    page.keyboard.press('ArrowDown')
    check('keyboard navigation selects original', page.locator('#tab-live').get_attribute('aria-selected') == 'true')
    check('live receipt displays completed only', page.locator('#live-cycle').inner_text() == '7,315')
    check('actual workflow rows', page.locator('.workflow-row').count() == 2)
    page.screenshot(path=str(OUT / 'observer-new-live.png'), full_page=True)
    page.locator('#load-world').click()
    page.wait_for_function("document.getElementById('world-status').textContent.startsWith('Loaded cycle')")
    check('world fetched from pinned exact commit', any('/' + GROWTH + '/state/organism.json' in x['url'] for x in requests))
    check('world renders 25 cells', page.locator('#world-board button').count() == 25)
    check('completed goal not falsely active', page.locator('#world-goal').inner_text() == 'No active goal')
    page.locator('#world-board button').first.click()
    check('cell inspector scoped to trail', 'displayed pinned trail' in page.locator('#world-cell-note').inner_text())
    page.locator('#tab-research').click()
    check('positive and negative studies present', page.locator('.study').count() == 4)
    check('PR statuses do not claim pilot', 'Merged' in page.locator('#pr258-status').inner_text() and 'draft' in page.locator('#pr259-status').inner_text())
    page.locator('[data-filter=negative]').click()
    check('negative filter works', page.locator('.study:visible').count() == 2)
    page.locator('[data-filter=all]').click()
    check('filter restores four records', page.locator('.study:visible').count() == 4)
    page.screenshot(path=str(OUT / 'observer-new-research.png'), full_page=True)
    for width in (1440, 1024, 768, 620, 390, 320):
        page.set_viewport_size({'width': width, 'height': 900})
        check('no horizontal overflow at ' + str(width),
              page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
    page.set_viewport_size({'width': 390, 'height': 844})
    page.locator('#tab-overview').click()
    page.screenshot(path=str(OUT / 'observer-new-mobile.png'), full_page=True)
    check('malformed receipt rejected', page.evaluate("""() => {
      try { OraObservatory.normalizeReceipt({version:'heartbeat-transport-v1',
       status:'completed',input_cycle:1,result_cycle:99,source_sha:'a'.repeat(40),
       cycle_time:'2026-10-08T00:00:00Z',original_run_id:1}); return false; }
      catch(e) { return true; }
    }"""))
    pending[0] = True
    page.locator('#refresh').click()
    page.wait_for_function("document.getElementById('overview-heartbeat').textContent.includes('pending')")
    check('pending receipt never presented as completed', page.locator('#overview-cycle').inner_text() == '—')
    failure[0] = True
    page.locator('#refresh').click()
    page.wait_for_function("document.getElementById('live-warning').textContent.includes('last successful read')")
    check('read failure marks stale data', 'Read failed' in page.locator('#overview-heartbeat').inner_text())
    check('no browser exceptions', not errors)
    context.close()

    cold = browser.new_context(viewport={'width': 390, 'height': 844})
    other = cold.new_page()
    def cold_route(r):
        if r.request.url.startswith('https://observer.test/'):
            name = r.request.url.rsplit('/', 1)[-1]
            r.fulfill(status=200, content_type='text/css' if name.endswith('.css') else 'text/javascript',
                      body=(ROOT / name).read_text())
        else:
            r.fulfill(status=429, body='', headers={'access-control-allow-origin': '*'})
    cold.route('https://**/*', cold_route)
    other.set_content((ROOT / 'observer.html').read_text().replace('<head>', '<head><base href="https://observer.test/">'))
    other.wait_for_function("document.getElementById('sync-indicator').textContent.includes('unavailable')")
    check('cold read failure does not invent a cycle', other.locator('#overview-cycle').inner_text() == '—')
    check('cold research evidence remains readable', other.locator('#tab-research').count() == 1)
    cold.close()
    browser.close()

(OUT / 'observer-new-browser-checks.json').write_text(json.dumps({
    'passed': len(checks), 'checks': checks, 'page_errors': errors,
    'scope': 'Local rendered UI with authored fixtures; no live Pages visual verification.',
    'requests': requests,
}, indent=2) + '\n')
print(json.dumps({'passed': len(checks), 'page_errors': errors, 'scope': 'fixture-bound browser rendering'}, indent=2))
