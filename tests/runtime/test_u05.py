"""U05 automated logic, schema, local HTTP integration and acceptance."""
import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest

from rci.adapters import ReadAdapters
from rci.contracts import ContractError, validate_schema
from rci.evidence import EvidenceStore
from rci.source_manifest import Source, credential_inventory, disclosed_manifest


def source(route='https://example.org/article-50', adapter='http-read'):
    if adapter == 'google-sheets-read':
        return Source('SYSTEMS', 'https://docs.google.com/spreadsheets/d/expected', adapter, 'readonly')
    return Source('LAW', route, adapter, None)


def page(title='Article 50', body=None):
    return ('<html><title>'+title+'</title><h1>'+title+'</h1><p>'+
            (body or 'Article 50: transparency obligations. ' * 12)+'</p></html>').encode()


def run(tmp_path, handler, src=None, **kwargs):
    calls = []
    def transport(request):
        starts = list((tmp_path/'analysis/attempts').glob('*.start.json'))
        terminals = list((tmp_path/'analysis/attempts').glob('*.terminal.json'))
        assert len(starts) == len(terminals) + 1
        assert request.method == 'GET' and not request.content
        calls.append(request)
        return handler(request, len(calls))
    store = EvidenceStore(tmp_path, 'run-u05-test')
    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        reader = ReadAdapters(store, client=client, sleep=lambda _: None, sheets_access='api', **kwargs)
        events = reader.read(src or source())
    assert store.inventory() == sorted(events, key=lambda e: e['attempt']['attempt_key'])
    for event in events:
        a = event['attempt']
        validate_schema(a, 'attempt')
        assert a['date_suitability'] == 'unresolved' and not a['selected']
        if event['capture']:
            validate_schema(event['capture'], 'capture')
            raw = (tmp_path/a['local_reference']).read_bytes()
            assert a['content_hash'] == 'sha256:' + hashlib.sha256(raw).hexdigest()
    return events, calls


@pytest.mark.parametrize('status', [403, 404, 429, 500])
def test_status_and_retry_accounting(tmp_path, status):
    events, calls = run(tmp_path, lambda r, n: httpx.Response(status, content=b'failure'))
    assert len(events) == len(calls) == (2 if status in {429, 500} else 1)
    assert len({e['attempt']['id'] for e in events}) == len(events)
    assert all(e['attempt']['retrieval_status'] == 'unavailable' and e['capture'] for e in events)


def test_timeout_null_content_and_no_secret_diagnostics(tmp_path):
    def fail(r, n): raise httpx.ReadTimeout('token=SECRET')
    events, _ = run(tmp_path, fail)
    assert len(events) == 2
    for e in events:
        assert e['capture'] is e['attempt']['content_hash'] is e['attempt']['local_reference'] is None
        assert e['attempt']['retrieval_status'] == 'unavailable'
    assert 'SECRET' not in json.dumps(events)


@pytest.mark.parametrize('target', ['/document', 'https://accounts.google.com/login',
                                     'https://evil.invalid/document', '/document?token=secret'])
def test_redirects_are_separate_or_blocked(tmp_path, target):
    events, calls = run(tmp_path, lambda r, n: httpx.Response(302, headers={'Location':target}, content=b'redirect')
                        if n == 1 else httpx.Response(200, headers={'Content-Type':'text/html'}, content=page()))
    assert len(events) == (2 if target == '/document' else 1)
    assert events[0]['capture'] and events[0]['attempt']['retrieval_status'] == 'invalid'
    if len(events) == 2:
        assert events[1]['attempt']['effective_locator'] == 'https://example.org/document'
        assert events[1]['attempt']['original_locator'] == source().route
        assert events[1]['attempt']['retrieval_status'] == 'retrieved'
    assert 'secret' not in json.dumps(events)


def test_redirect_loop_is_bounded(tmp_path):
    events, _ = run(tmp_path, lambda r, n: httpx.Response(302, headers={'Location':'/loop'}, content=b'redirect'), redirects=2)
    assert len(events) == 3
    assert 'bound' in events[-1]['attempt']['recoverable_failure']


@pytest.mark.parametrize('body,mime,state,check', [
    (page(), 'text/html', 'retrieved', 'verified'),
    (page('Login'), 'text/html', 'invalid', 'mismatch'),
    (page('Article 50', '<input type="password">'), 'text/html', 'invalid', 'mismatch'),
    (page('Commission home'), 'text/html', 'unverified', 'unverified'),
    (page('Regulation 2026/999'), 'text/html', 'unverified', 'unverified'),
    (b'%PDF-unreadable', 'application/pdf', 'unverified', 'unverified'),
    (b'', None, 'unverified', 'unverified'),
])
def test_unsuitable_identity_and_formats(tmp_path, body, mime, state, check):
    events, _ = run(tmp_path, lambda r, n: httpx.Response(200, headers={} if mime is None else {'Content-Type':mime}, content=body))
    a = events[-1]['attempt']
    assert a['retrieval_status'] == state and a['identity_check'] == check
    assert a['content_hash'] is not None  # Empty response is obtained content.
    assert a['content_type_known'] == (mime is not None)


def sheet(document_id='expected', tabs=2):
    return {'spreadsheetId':document_id, 'properties':{'title':'Synthetic register'},
            'sheets':[{'properties':{'sheetId':i,'title':f'Tab {i}','sheetType':'GRID'},
                       'data':[{'rowData':[{'values':[{'formattedValue':'Synthetic'}]}]}]} for i in range(tabs)]}


@pytest.mark.parametrize('payload,state', [(sheet(),'retrieved'), (sheet('wrong'),'unverified'),
                                           (sheet(tabs=0),'unverified'), ({'sheets':[{}]},'unverified')])
def test_sheet_id_and_every_tab(tmp_path, payload, state):
    events, calls = run(tmp_path, lambda r,n: httpx.Response(200, json=payload), source(adapter='google-sheets-read'))
    a = events[-1]['attempt']
    # Wrong document is explicitly invalid; malformed/incomplete response unverified.
    expected = 'invalid' if payload.get('spreadsheetId') == 'wrong' else state
    assert a['retrieval_status'] == expected
    assert str(calls[0].url).endswith('/expected?includeGridData=true')
    assert 'ranges' not in calls[0].url.params and 'fields' not in calls[0].url.params
    if expected == 'retrieved': assert len(a['version_metadata']['returned_identity']['tabs']) == 2


def test_credential_reference_and_redirect_boundary(tmp_path, monkeypatch):
    monkeypatch.setenv('RCI_TEST_TOKEN', 'synthetic-secret')
    credential = {'owner':'Operator','principal':'Synthetic account','scopes':[
        'https://www.googleapis.com/auth/spreadsheets.readonly'], 'token_env':'RCI_TEST_TOKEN'}
    events, calls = run(tmp_path, lambda r,n: httpx.Response(302, headers={
        'Location':'https://evil.invalid'}), source(adapter='google-sheets-read'), credentials={'readonly':credential})
    assert len(calls) == 1 and calls[0].headers['Authorization'] == 'Bearer synthetic-secret'
    assert 'synthetic-secret' not in json.dumps(events)


def test_manifest_exact_routes_and_external_credential_policy(tmp_path):
    sources = disclosed_manifest()
    assert len(sources) == 10 and len({s.id for s in sources}) == 10
    text = open('interviews/interview-B-3.md').read()
    assert all(s.route in text for s in sources)
    path = tmp_path/'inventory.json'
    path.write_text(json.dumps({'ref':{'owner':'Owner','principal':'Account','token_env':'RCI_TOKEN',
        'scopes':['https://www.googleapis.com/auth/spreadsheets']}}))
    with pytest.raises(ContractError, match='read-only'): credential_inventory(path)


def test_all_core_sources_attempted_failures_retained_no_fallback(tmp_path):
    store = EvidenceStore(tmp_path, 'run-u05-test')
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(403, content=b'denied'))) as client:
        reader = ReadAdapters(store, client=client, retries=0)
        for s in disclosed_manifest(): reader.read(s)
    events = store.inventory()
    assert len(events) == 10 and {e['attempt']['source_id'] for e in events} == {s.id for s in disclosed_manifest()}
    assert all(e['capture'] and e['diagnostic'] for e in events)


def test_local_http_server(tmp_path):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/start':
                self.send_response(302)
                self.send_header('Location', '/document')
                body = b'redirect body'
            else:
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                body = page()
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *args): pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f'http://127.0.0.1:{server.server_port}'
    try:
        store = EvidenceStore(tmp_path, 'run-u05-http')
        reader = ReadAdapters(store, test_origins=[origin])
        try: events = reader.read(source(origin+'/start'))
        finally: reader.close()
        assert len(store.inventory()) == 2
        assert events[-1]['attempt']['retrieval_status'] == 'retrieved'
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_observed_timeline_title(tmp_path):
    src = Source('TIME', 'https://example.org/timeline', 'http-read', None)
    events, _ = run(tmp_path, lambda r,n: httpx.Response(200, headers={'Content-Type':'text/html'},
        content=page('Timeline for the Implementation of the EU AI Act | AI Act Service Desk')), src)
    assert events[-1]['attempt']['identity_check'] == 'verified'


def test_malformed_redirect_preserved_without_dispatch(tmp_path):
    events, calls = run(tmp_path, lambda r,n: httpx.Response(302, headers={
        'Location':'https://example.org:bad/document'}, content=b'redirect'))
    assert len(calls) == 1 and events[0]['capture']
    assert events[0]['attempt']['retrieval_status'] == 'invalid'


def test_read_adapter_integrates_frozen_stage02(tmp_path):
    from pathlib import Path
    import shutil
    from rci.contracts import parse_json
    from rci.snapshots import read_chain, write_snapshot
    fixture = Path(__file__).resolve().parents[1]/'fixtures/u02/package'
    shutil.copytree(fixture, tmp_path, dirs_exist_ok=True)
    prefix = read_chain(tmp_path, count=1)
    snapshot = parse_json((fixture/'snapshots/02-source-capture.json').read_bytes())
    class Clock:
        def now(self): return snapshot['created_at']
    store = EvidenceStore(tmp_path, snapshot['run_id'], Clock())
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=sheet()))) as client:
        reader = ReadAdapters(store, client=client, sheets_access='api')
        event, = reader.read(source(adapter='google-sheets-read'))
    a, c = event['attempt'], event['capture']
    snapshot['state']['attempts'].append(a)
    snapshot['state']['captures'].append(c)
    snapshot['state']['sources'][0]['attempt_ids'].append(a['id'])
    snapshot['produced_record_ids'].extend([a['id'], c['id']])
    (tmp_path/'snapshots/02-source-capture.json').unlink()
    write_snapshot(tmp_path, snapshot, upstream=prefix)
    assert read_chain(tmp_path, count=2)[1] == snapshot
    assert store.inventory()[0]['capture'] == c


def test_matching_title_alone_does_not_verify_landing_page(tmp_path):
    data=b'<title>Article 50</title><h1>Welcome</h1><p>'+b'Unrelated navigation. '*20+b'</p>'
    events,_ = run(tmp_path, lambda r,n: httpx.Response(200, headers={'Content-Type':'text/html'}, content=data))
    assert events[0]['attempt']['identity_check'] == 'unverified'
    assert events[0]['attempt']['retrieval_status'] == 'unverified'


def test_register_handoff_rejects_retained_unregistered_callers():
    from pathlib import Path
    from rci.adapters.readiness import register_readiness
    root = Path(__file__).resolve().parents[2]/'docs/verification/u05-live'
    report = json.loads((root/'analysis/source-access.json').read_bytes())
    result = register_readiness(EvidenceStore(root, report['run_id']))
    assert result['status'] == 'blocked'
    assert len(result['registers']) == 3
    for register in result['registers']:
        assert register['ready'] is False
        assert register['blocker'] == 'missing-caller-authentication'
        assert register['permission_status'] == 'not-established'


def test_require_registers_cli_returns_blocked_on_written_report(tmp_path, monkeypatch):
    import check_sources
    monkeypatch.setattr('sys.argv', ['check_sources.py', '--output', str(tmp_path), '--require-registers'])
    monkeypatch.setattr(check_sources, 'check_sources', lambda *a, **kw: (tmp_path, {
        'sources':[{}]*10, 'register_readiness':{'status':'blocked'}}))
    assert check_sources.main() == 3


def anonymous_page(src, tabs=(0,), revision=1, displayed=0, rows=None):
    rows = rows or [['record_id','date'], ['R-1','2026-08-20']]
    properties = [[21350203, json.dumps([0,0,str(gid),[{'1':[[0,0,f'Tab {gid}']]}],1000,26])]
                  for gid in tabs]
    changes = {'topsnapshot':properties, 'revision':revision,
               'firstchunk':[[25813757,json.dumps([[str(displayed),0,len(rows),0,len(rows[0])],[]])]]}
    bootstrap = {'changes':changes, 'gridId':displayed}
    import html
    grid = ''.join('<tr><th id="'+str(displayed)+'R'+str(i)+'">'+str(i+1)+'</th>'+''.join(
        '<td>'+html.escape(c)+'</td>' for c in row)+'</tr>' for i,row in enumerate(rows))
    return ('<meta property="og:url" content="'+src.route+'/edit">'
            '<meta property="og:title" content="Synthetic anonymous register">'
            + ''.join('<div class="docs-sheet-tab-caption">Tab '+str(gid)+'</div>' for gid in tabs)
            + '<div id="'+str(displayed)+'-grid-table-container"><table class="waffle">'+grid+'</table></div>'
            + '<script>var bootstrapData = '+json.dumps(bootstrap)+';</script>').encode()


def anonymous_read(tmp_path, *, tabs=(0,), lossy=False, revision_changed=False, truncate=False, login=False):
    src = source(adapter='google-sheets-read')
    requests = []
    page_count = 0
    def handler(request):
        nonlocal page_count
        assert 'Authorization' not in request.headers and not request.content
        requests.append(request)
        if request.url.path.endswith('/gviz/tq'):
            assert request.url.params['headers'] == '1'
            assert set(request.url.params) == {'gid','headers','tqx'}
            csv = b'record_id,date\r\nR-1,2026-08-20\r\n' if not lossy else b'record_id,\r\nR-1,2026-08-20\r\n'
            return httpx.Response(200, headers={'Content-Type':'text/csv'}, content=csv)
        if str(request.url) == src.route:
            return httpx.Response(302, headers={'Location':src.route+'/'},content=b'redirect')
        if str(request.url) == src.route+'/':
            return httpx.Response(302, headers={'Location':src.route+'/edit'},content=b'redirect')
        page_count += 1
        selected = int(request.url.params.get('gid', '0'))
        revision = 2 if revision_changed and page_count > 1 else 1
        body = page('Login') if login else anonymous_page(src,tabs,revision,selected)
        if truncate: body = body.replace(b'<td>2026-08-20</td>',b'')
        return httpx.Response(200, headers={'Content-Type':'text/html'}, content=body)
    store = EvidenceStore(tmp_path, 'run-u05-anonymous-test')
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        reader = ReadAdapters(store, client=client)
        events = reader.read(src)
    assert len(store.inventory()) == len(events)
    return events, requests, store


@pytest.mark.parametrize('dimension', [4, 5])
@pytest.mark.parametrize('bound', [None, '1000', True, 0, -1])
def test_malformed_anonymous_bounds_retained_and_all_routes_attempted(tmp_path, monkeypatch, dimension, bound):
    import check_sources
    sources = disclosed_manifest()
    bodies, calls = {}, []
    def handler(request):
        calls.append(str(request.url))
        if request.url.path.endswith('/gviz/tq'):
            return httpx.Response(200, headers={'Content-Type': 'text/csv'},
                                  content=b'record_id,date\r\nR-1,2026-08-20\r\n')
        matched = next((s for s in sources if str(request.url) == s.route), None)
        assert matched is not None
        if matched.adapter != 'google-sheets-read':
            body = b'public access blocked'
            response = httpx.Response(403, content=body)
        else:
            text = anonymous_page(matched).decode()
            prefix, suffix = text.split('var bootstrapData = ', 1)
            bootstrap, end = json.JSONDecoder().raw_decode(suffix)
            properties = json.loads(bootstrap['changes']['topsnapshot'][0][1])
            properties[dimension] = bound
            bootstrap['changes']['topsnapshot'][0][1] = json.dumps(properties)
            body = (prefix + 'var bootstrapData = ' + json.dumps(bootstrap) + suffix[end:]).encode()
            response = httpx.Response(200, headers={'Content-Type': 'text/html'}, content=body)
        bodies[matched.id] = body
        return response
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        monkeypatch.setattr(check_sources, 'ReadAdapters',
                            lambda store, **kw: ReadAdapters(store, client=client, retries=0, **kw))
        root, report = check_sources.check_sources(tmp_path)
    assert calls == [s.route for s in sources]
    assert report['register_readiness']['status'] == 'blocked'
    assert not any(r['ready'] for r in report['register_readiness']['registers'])
    events = EvidenceStore(root, report['run_id']).inventory()
    assert len(events) == len(sources)
    for event in events:
        attempt = event['attempt']
        assert event['capture'] is not None
        assert (root / attempt['local_reference']).read_bytes() == bodies[attempt['source_id']]
        if attempt['source_id'] in {'SYSTEMS', 'EVIDENCE', 'CALENDAR'}:
            assert attempt['retrieval_status'] == 'unverified'


def test_identity_parser_failure_retains_completed_body(tmp_path):
    src = source()
    store = EvidenceStore(tmp_path, 'run-u05-parser-failure')
    body = page()
    def checker(*args):
        raise TypeError('unsupported source shape')
    with httpx.Client(transport=httpx.MockTransport(lambda request:
            httpx.Response(200, headers={'Content-Type': 'text/html'}, content=body))) as client:
        events = ReadAdapters(store, client=client)._read(src, checker=checker)
    assert len(events) == 1 and store.inventory() == events
    attempt = events[0]['attempt']
    assert attempt['retrieval_status'] == 'unverified'
    assert attempt['identity_check'] == 'unverified' and not attempt['selected']
    assert (tmp_path / attempt['local_reference']).read_bytes() == body
    assert attempt['recoverable_failure']


def test_anonymous_access_captures_every_tab_and_preserves_values(tmp_path, monkeypatch):
    monkeypatch.setenv('RCI_SHEETS_ACCESS_TOKEN','must-not-be-used')
    events, requests, store = anonymous_read(tmp_path, tabs=(0,7))
    csv = [e for e in events if e['attempt']['content_type'] == 'text/csv']
    assert len(csv) == 2 and {r.url.params['gid'] for r in requests if 'gid' in r.url.params} == {'0','7'}
    assert all(e['attempt']['retrieval_status'] == 'retrieved' for e in csv)
    assert all(e['attempt']['original_locator'] == source(adapter='google-sheets-read').route for e in events)
    assert all(e['attempt']['version_metadata']['authenticated'] is False for e in events)
    assert events[-1]['attempt']['retrieval_status'] == 'retrieved'
    assert 'must-not-be-used' not in json.dumps(events)


@pytest.mark.parametrize('case', ['lossy','truncate','login','revision_changed'])
def test_anonymous_bad_representation_cannot_pass_handoff(tmp_path, case):
    from rci.adapters.readiness import register_readiness
    events, requests, store = anonymous_read(tmp_path, **{case:True})
    assert register_readiness(store)['status'] == 'blocked'
    if case == 'lossy':
        csv = next(e for e in events if e['attempt']['content_type'] == 'text/csv')
        assert csv['attempt']['retrieval_status'] == 'unverified' and csv['capture']
    elif case == 'revision_changed':
        assert events[-1]['attempt']['retrieval_status'] == 'invalid'
    else:
        assert not any('/gviz/tq' in str(r.url) for r in requests)


def test_anonymous_packed_native_grid_layout(tmp_path):
    from rci.adapters.anonymous_sheets import discover
    src=source(adapter='google-sheets-read')
    raw=anonymous_page(src)
    text=raw.decode(); prefix='var bootstrapData = '
    bootstrap,end=json.JSONDecoder().raw_decode(text.split(prefix,1)[1])
    rectangle=json.loads(bootstrap['changes']['firstchunk'][0][1])[0]
    bootstrap['changes']['firstchunk']=[[341438337,json.dumps([{'2':[{'1':rectangle}]}])]]
    changed=text.split(prefix,1)[0]+prefix+json.dumps(bootstrap)+text.split(prefix,1)[1][end:]
    assert discover(changed.encode(),src)['native_rows']['0']==[['record_id','date'],['R-1','2026-08-20']]


def test_anonymous_connection_report_requires_all_register_data(tmp_path, monkeypatch):
    import check_sources
    sources=disclosed_manifest()
    def handler(request):
        assert request.method=='GET' and 'Authorization' not in request.headers
        matched=next((s for s in sources if s.adapter=='google-sheets-read' and
                      request.url.path.startswith('/spreadsheets/d/'+s.document_id)),None)
        if matched is None: return httpx.Response(403,content=b'public access blocked')
        if request.url.path.endswith('/gviz/tq'):
            return httpx.Response(200,headers={'Content-Type':'text/csv'},content=b'record_id,date\r\nR-1,2026-08-20\r\n')
        return httpx.Response(200,headers={'Content-Type':'text/html'},content=anonymous_page(matched))
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        monkeypatch.setattr(check_sources,'ReadAdapters',lambda store,**kw: ReadAdapters(store,client=client,**kw))
        root,report=check_sources.check_sources(tmp_path)
    assert report['register_readiness']['status']=='ready'
    assert len(report['sources'])==10
    assert all(row['ready'] and row['tabs'][0]['raw_first_row']==['record_id','date']
               for row in report['register_readiness']['registers'])
    assert json.loads((root/'analysis/source-access.json').read_bytes())==report
    # A modified source capture cannot be accepted based on its old report.
    row=report['register_readiness']['registers'][0]['tabs'][0]
    (root/row['local_reference']).write_bytes(b'changed source data')
    from rci.adapters.readiness import register_readiness
    with pytest.raises(ContractError,match='hash mismatch'):
        register_readiness(EvidenceStore(root,report['run_id']))
