"""Anonymous Sheets discovery and unfiltered per-tab CSV capture. No mappings."""
import csv
from html.parser import HTMLParser
import io
import json
import re
from urllib.parse import urlsplit

from ..contracts import require
from ..source_manifest import Source


class Metadata(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.document_url = None
        self.title = None
        self.grid = None
        self.in_table = False
        self.row = None
        self.cell = None
        self.rows = {}
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'div' and re.fullmatch(r'[0-9]+-grid-table-container', attrs.get('id', '')):
            self.grid = int(attrs['id'].split('-')[0])
        if tag == 'table' and 'waffle' in attrs.get('class','').split():
            self.in_table = True
        if self.in_table and tag == 'th':
            row = re.fullmatch(r'([0-9]+)R([0-9]+)', attrs.get('id',''))
            if row:
                self.row = int(row[2])
                self.rows.setdefault(int(row[1]), {})[self.row] = []
        if self.in_table and tag == 'td' and self.row is not None: self.cell = []
        if tag == 'br' and self.cell is not None: self.cell.append('\n')
        if tag == 'meta':
            if attrs.get('property') == 'og:url': self.document_url = attrs.get('content')
            if attrs.get('property') == 'og:title': self.title = attrs.get('content')

    def handle_data(self, data):
        if self.cell is not None: self.cell.append(data)

    def handle_endtag(self, tag):
        if tag == 'td' and self.cell is not None:
            self.rows[self.grid][self.row].append(''.join(self.cell))
            self.cell = None
        if tag == 'tr': self.row = None
        if tag == 'table': self.in_table = False


def discover(data, source):
    text = data.decode('utf-8')
    meta = Metadata(text)
    require(isinstance(meta.document_url, str) and isinstance(meta.title, str) and meta.title,
            'Missing returned spreadsheet identity')
    returned = urlsplit(meta.document_url)
    require(returned.hostname == 'docs.google.com', 'Unexpected returned document host')
    match = re.fullmatch(r'/spreadsheets/d/([A-Za-z0-9_-]+)/edit', returned.path)
    require(match and match[1] == source.document_id, 'Returned spreadsheet ID mismatch')
    marker = 'var bootstrapData = '
    require(marker in text, 'Anonymous tab inventory unavailable')
    # This observed Google HTML layout is explicitly supported; never execute JS.
    bootstrap, _ = json.JSONDecoder().raw_decode(text.split(marker, 1)[1])
    changes = bootstrap['changes']
    tabs = []
    for _, encoded in changes['topsnapshot']:
        value = json.loads(encoded)
        if (isinstance(value, list) and len(value) == 6 and isinstance(value[2], str)
                and value[2].isdigit() and isinstance(value[3], list)):
            title = value[3][0]['1'][0][2]
            require(isinstance(title, str) and title, 'Unnamed spreadsheet tab')
            require(all(type(bound) is int and bound > 0 for bound in value[4:6]),
                    'Invalid spreadsheet grid bounds')
            tabs.append({'sheetId':int(value[2]), 'title':title, 'sheetType':'GRID',
                         'gridProperties':{'rowCount':value[4], 'columnCount':value[5]}})
    require(tabs and len({t['sheetId'] for t in tabs}) == len(tabs), 'Missing or ambiguous tab inventory')
    captions = re.findall(r'docs-sheet-tab-caption[^>]*>(.*?)</div>', text, re.S)
    require(len(captions) == len(tabs), 'Tab inventory incomplete or HTML layout unsupported')
    require(type(changes['revision']) is int, 'Spreadsheet revision unavailable')
    previews = {}
    for operation, encoded in changes['firstchunk']:
        if operation == 25813757:
            rectangles = [json.loads(encoded)[0]]
        elif operation == 341438337:
            rectangles = [block['1'] for block in json.loads(encoded)[0]['2']]
        else:
            continue
        for rectangle in rectangles:
            _capture_preview(rectangle, meta, previews)
    require(previews, 'No complete native grid preview')
    return {'document_id':match[1], 'title':meta.title, 'tabs':tabs,
            'revision':changes['revision'], 'native_rows':previews}


def _capture_preview(rectangle, meta, previews):
    require(len(rectangle) == 5 and str(rectangle[0]).isdigit() and
            all(type(x) is int for x in rectangle[1:]), 'Unsupported native grid range')
    gid, start_row, end_row, start_col, end_col = rectangle
    require(start_row == 0 and start_col == 0 and end_row > 0 and end_col > 0,
            'Partial or invalid native grid preview')
    gid = int(gid)
    require(str(gid) not in previews, 'Multiple native grid ranges are unsupported')
    require(gid in meta.rows, 'Native table absent')
    require(all(i in meta.rows[gid] and len(meta.rows[gid][i]) >= end_col
                for i in range(end_row)), 'Native grid preview truncated')
    previews[str(gid)] = [meta.rows[gid][i][:end_col] for i in range(end_row)]


def csv_rows(data):
    require(not data.lstrip().startswith((b'<', b'{')), 'Non-CSV response')
    rows = list(csv.reader(io.StringIO(data.decode('utf-8-sig'), newline=''), strict=True))
    require(rows and any(any(cell for cell in row) for row in rows), 'Empty tab data')
    return rows


def read_anonymous(reader, source):
    public = Source(source.id, source.route, 'http-read', None)
    original = source.route
    events = []
    discovered = {}

    def check_page(_, data, mime, effective):
        try:
            require(mime and mime.lower().startswith('text/html'), 'Not spreadsheet HTML')
            details = discover(data, source)
            discovered.update(details)
            return 'verified', 'Anonymous spreadsheet identity and tab inventory verified', details
        except (ValueError, KeyError, TypeError, IndexError, UnicodeError):
            return 'unverified', 'Unreadable anonymous spreadsheet or missing identity/tab inventory', {
                'document_id':None, 'title':None, 'tabs':None}

    page_urls = {original, original+'/', original+'/edit'}
    events.extend(reader._read(public, checker=check_page, allowed_urls=page_urls))
    if events[-1]['attempt']['retrieval_status'] != 'retrieved': return events
    basis = dict(discovered)
    identity_attempt_id = events[-1]['attempt']['id']
    for tab in basis['tabs']:
        gid = str(tab['sheetId'])
        native = basis['native_rows'].get(gid)
        if native is None:
            tab_url = original + f"/edit?gid={tab['sheetId']}"
            tab_events = reader._read(public, dispatch_url=tab_url, checker=check_page, allowed_urls={tab_url})
            events.extend(tab_events)
            if tab_events[-1]['attempt']['retrieval_status'] != 'retrieved': continue
            if discovered['revision'] != basis['revision'] or discovered['tabs'] != basis['tabs']: continue
            native = discovered['native_rows'].get(gid)
        if native is None: continue
        url = original + f"/gviz/tq?gid={tab['sheetId']}&headers=1&tqx=out:csv"

        def check_csv(_, data, mime, effective, tab=tab, native=native):
            details = {'document_id':basis['document_id'], 'title':basis['title'],
                       'tabs':[tab], 'revision':basis['revision'],
                       'identity_attempt_id':identity_attempt_id}
            try:
                require(mime and mime.split(';')[0].lower() in {'text/csv', 'application/csv'}, 'Not CSV')
                rows = csv_rows(data)
                require(rows == native, 'CSV values differ from native header/row data')
                details['native_values_verified'] = True
                details['row_count'] = len(rows)
                details['column_count'] = max(map(len, rows))
                details['headers'] = rows[0]  # Raw first row, never a field mapping.
                require(len(rows) <= tab['gridProperties']['rowCount'] and
                        max(map(len, rows)) <= tab['gridProperties']['columnCount'], 'Invalid tab bounds')
                return 'verified', 'Anonymous unfiltered tab CSV captured with raw row/cell locators', details
            except (ValueError, csv.Error, UnicodeError):
                return 'unverified', 'Unreadable or incomplete anonymous tab response', details

        events.extend(reader._read(public, dispatch_url=url, checker=check_csv, allowed_urls={url}))
    # A second fresh discovery brackets tab reads. Changes invalidate readiness.
    def check_final(_, data, mime, effective):
        checked, reason, details = check_page(_, data, mime, effective)
        if checked == 'verified' and any(details[k] != basis[k] for k in ('document_id','title','tabs','revision','native_rows')):
            return 'mismatch', 'Spreadsheet identity, revision or tab inventory changed during capture', details
        return checked, reason, details
    events.extend(reader._read(public, dispatch_url=original+'/edit', checker=check_final, allowed_urls=page_urls))
    return events
