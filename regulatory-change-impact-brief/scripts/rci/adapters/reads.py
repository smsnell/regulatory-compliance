"""Bounded GET-only transport and conservative source identity checks."""
import json
import os
import re
import time
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, parse_qs

import httpx

from ..contracts import require


class Page(HTMLParser):
    def __init__(self, raw):
        super().__init__()
        self.title = ''
        self.text = []
        self.headings = []
        self.heading = None
        self.in_title = False
        self.hidden = 0
        self.feed(raw.decode('utf-8', errors='replace'))

    def handle_starttag(self, tag, attrs):
        if tag == 'title': self.in_title = True
        if tag in {'h1', 'h2', 'h3'}: self.heading = []
        if tag in {'script', 'style'}: self.hidden += 1

    def handle_endtag(self, tag):
        if tag == 'title': self.in_title = False
        if tag in {'h1', 'h2', 'h3'} and self.heading is not None:
            self.headings.append(' '.join(self.heading))
            self.heading = None
        if tag in {'script', 'style'}: self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if self.in_title: self.title += data
        if not self.hidden and not self.in_title:
            self.text.append(data)
            if self.heading is not None: self.heading.append(data)


def identity(source, data, mime, effective):
    """Identity is separate from historical suitability and legal relevance."""
    details = {'title': None, 'document_id': None, 'tabs': None}
    if not data:
        return 'unverified', 'Empty response has no readable identity', details
    if source.adapter == 'google-sheets-read':
        try:
            sheet = json.loads(data)
            details['document_id'] = sheet.get('spreadsheetId')
            details['title'] = sheet.get('properties', {}).get('title')
            tabs = sheet.get('sheets')
            require(isinstance(tabs, list) and bool(tabs), 'tab inventory absent')
            details['tabs'] = [tab['properties'] for tab in tabs]
            ids = [tab['sheetId'] for tab in details['tabs']]
            require(len(set(ids)) == len(ids) and all(isinstance(i, int) and not isinstance(i, bool) for i in ids),
                    'ambiguous tab identities')
            require(all(isinstance(t.get('title'), str) and t['title'] and t.get('sheetType') == 'GRID'
                        for t in details['tabs']), 'unsupported or unnamed tab')
            require(isinstance(details['title'], str) and details['title'], 'spreadsheet title absent')
            if details['document_id'] != source.document_id:
                return 'mismatch', 'Returned spreadsheet ID differs from requested ID', details
            # No ranges or fields filter is sent: includeGridData requests every tab.
            # Empty grid data may be omitted by Google; tab metadata remains explicit.
            return 'verified', 'Requested spreadsheet ID and complete tab inventory returned', details
        except (ValueError, TypeError, KeyError, AttributeError):
            return 'unverified', 'Unreadable Sheets response or incomplete tab inventory', details
    if not mime or mime.split(';')[0].strip().lower() != 'text/html':
        return 'unverified', 'Unsupported representation; content retained for inspection', details
    page = Page(data)
    title = ' '.join(page.title.split())
    text = ' '.join(' '.join(page.text).split())
    details['title'] = title or None
    if (re.search(r'\b(sign in|log in|login|access denied|page not found|just a moment|captcha)\b', title, re.I)
            or urlsplit(effective).hostname in {'accounts.google.com', 'login.microsoftonline.com'}
            or re.search(r'<input[^>]+type=["\']password', data.decode('utf-8', errors='replace'), re.I)):
        return 'mismatch', 'Login, challenge or error page is not the requested document', details
    if source.id == 'OJ':
        details['document_id'] = '2024/1689' if re.search(r'2024/1689', title) else None
        matched = bool(details['document_id'] and re.search(r'REGULATION.*2024/1689', text, re.I))
    elif source.id in {'AMEND', 'CONSOLIDATED'}:
        selector = parse_qs(urlsplit(source.route).query)['uri'][0]
        details['document_id'] = selector if selector in text else None
        # The disclosed amendment's relationship is unknown; do not infer it.
        return 'unverified', 'Act identity/version and relevance require source inspection', details
    else:
        patterns = {'LAW': r'article\s+50', 'TIME': r'(implementation\s+timeline|ai act.*timeline|timeline.*implementation.*ai act)',
                    'FAQ': r'transparency obligations.*article\s+50',
                    'POLICY': r'Project.?2.*Regulatory.*Compliance.*Current.*Internal.*Policies'}
        matched = bool(re.search(patterns.get(source.id, r'(?!)'), title, re.I)
                       and any(re.search(patterns.get(source.id, r'(?!)'), heading, re.I)
                               for heading in page.headings) and len(text) > 200)
    if not matched:
        return 'unverified', 'Missing document title/content identity; possible landing page', details
    return 'verified', 'Returned title and visible document content match requested source', details


class ReadAdapters:
    def __init__(self, store, *, client=None, credentials=None, retries=1,
                 redirects=3, timeout=20, sleep=time.sleep, test_origins=(), sheets_access='anonymous'):
        require(type(retries) is int and 0 <= retries <= 2, 'retry bound must be 0..2')
        require(type(redirects) is int and 0 <= redirects <= 5, 'redirect bound must be 0..5')
        require(0 < timeout <= 60, 'timeout must be bounded')
        require(sheets_access in {'anonymous', 'api'}, 'unsupported Sheets access mode')
        self.sheets_access = sheets_access
        self.store = store
        self.client = client or httpx.Client(follow_redirects=False, trust_env=False)
        self.owns_client = client is None
        self.credentials = credentials or {}
        self.retries, self.redirects, self.timeout = retries, redirects, timeout
        self.sleep = sleep
        # Test injection never appears in the production command/configuration.
        self.test_origins = set(test_origins)

    def close(self):
        if self.owns_client: self.client.close()

    def _allowed(self, url, source, origin):
        try:
            u = urlsplit(url)
            port = u.port
        except ValueError:
            return False
        if u.scheme == 'http' and (u.scheme + '://' + u.netloc) in self.test_origins:
            return not u.query and not u.fragment and not u.username
        if u.scheme != 'https' or u.username or u.password or u.fragment or port not in {None, 443}:
            return False
        allowed_host = 'sheets.googleapis.com' if source.adapter == 'google-sheets-read' else urlsplit(origin).hostname
        if u.hostname != allowed_host: return False
        if source.adapter == 'google-sheets-read':
            return url == origin  # Credentials never leave the exact API endpoint.
        if u.query:
            q = parse_qs(u.query, keep_blank_values=True)
            return (u.hostname == 'eur-lex.europa.eu' and u.path == '/legal-content/EN/TXT/'
                    and set(q) == {'uri'} and len(q['uri']) == 1
                    and re.fullmatch(r'(?:OJ:[A-Z]_[0-9]+|CELEX:[0-9][0-9A-Z()/\-]*)', q['uri'][0]) is not None)
        return True

    def read(self, source):
        if source.adapter == 'google-sheets-read' and self.sheets_access == 'anonymous':
            from .anonymous_sheets import read_anonymous
            return read_anonymous(self, source)
        return self._read(source)

    def _read(self, source, *, dispatch_url=None, checker=identity, allowed_urls=None):
        require(source.adapter in {'http-read', 'google-sheets-read'}, 'unsupported adapter')
        original = source.route
        url = dispatch_url or original
        headers = {'Accept': 'application/json' if source.adapter == 'google-sheets-read' else 'text/html'}
        credential = None
        if source.adapter == 'google-sheets-read':
            url = f'https://sheets.googleapis.com/v4/spreadsheets/{source.document_id}?includeGridData=true'
            credential = self.credentials.get(source.credential_ref)
            if credential:
                require(set(credential) == {'owner', 'principal', 'scopes', 'token_env'},
                        'credential values must stay outside adapter metadata')
                require(credential['scopes'] == ['https://www.googleapis.com/auth/spreadsheets.readonly'],
                        'read-only credential scope required')
                token = os.environ.get(credential['token_env'])
                if token: headers['Authorization'] = 'Bearer ' + token
        origin = url
        allowed = (lambda target: target in allowed_urls) if allowed_urls is not None else (
            lambda target: self._allowed(target, source, origin))
        require(allowed(url), 'unsupported dispatch route')
        events, hops, retry_count = [], 0, 0
        while True:
            key = self.store.start(source.id, original, source.adapter)
            obtained = []
            def retain_response(response):
                # httpx may reject malformed Location while preparing its next
                # request even with redirects disabled. Capture the completed
                # response before that step, so its body is not lost.
                response.read()
                obtained.append(response)
            self.client.event_hooks['response'].append(retain_response)
            transport_error = None
            try:
                response = self.client.get(url, headers=headers, timeout=self.timeout, follow_redirects=False)
            except (httpx.HTTPError, OSError) as error:
                if obtained:
                    response = obtained[-1]
                else:
                    transport_error = type(error).__name__
            except (KeyboardInterrupt, SystemExit):
                self.store.finish(key, effective_locator=url, outcome='Interrupted',
                    recoverable_failure='Read interrupted', selection_reason='No complete response')
                raise
            finally:
                self.client.event_hooks['response'].remove(retain_response)
            if transport_error:
                event = self.store.finish(key, effective_locator=url, outcome=transport_error,
                    retrieval_status='unavailable',
                    recoverable_failure='Transport failed; no complete response obtained',
                    selection_reason='No response; no fallback', version_metadata={'version': None})
                events.append(event)
                if retry_count < self.retries:
                    retry_count += 1
                    self.sleep(min(retry_count, 2))
                    continue
                break
            data = response.content
            status = response.status_code
            mime = response.headers.get('content-type')
            try:
                checked, reason, details = checker(source, data, mime, url)
            except (ValueError, TypeError, KeyError, IndexError, AttributeError):
                # A source parser failure does not erase a completed response.
                # Preserve it with an unverified identity and no selection.
                checked, reason, details = ('unverified',
                    'Unsupported source representation; identity parsing failed',
                    {'title': None, 'document_id': None, 'tabs': None})
            version = {'version': ({'kind':'observed-google-html-revision', 'value':details['revision']}
                                    if allowed_urls is not None and 'revision' in details else None), 'etag': response.headers.get('etag'),
                       'last_modified': response.headers.get('last-modified'),
                       'returned_identity': details, 'identity_reason': reason,
                       'date_reason': 'Historical applicability not established by retrieval; assigned date unchanged',
                       'credential_ref': source.credential_ref,
                       'credential_inventory': credential,
                       'authenticated': 'Authorization' in headers,
                       'access_mode': 'anonymous' if allowed_urls is not None else 'api' if source.adapter == 'google-sheets-read' else 'public-http'}
            redirect = status in {301, 302, 303, 307, 308}
            try:
                next_url = urljoin(url, response.headers.get('location', '')) if redirect else None
            except ValueError:
                next_url = None
            allowed_redirect = (redirect and next_url is not None and bool(response.headers.get('location')) and hops < self.redirects
                                and allowed(next_url))
            if redirect:
                retrieval, checked = 'invalid', 'unverified'
                reason = 'Redirect response retained; next GET separately journaled' if allowed_redirect else 'Redirect blocked by route policy or hop bound'
            elif status != 200:
                retrieval = 'unavailable' if status in {401, 403, 404, 429} or status >= 500 else 'invalid'
                checked, reason = 'unverified', f'HTTP {status}; requested content unavailable'
            else:
                retrieval = 'retrieved' if checked == 'verified' else 'invalid' if checked == 'mismatch' else 'unverified'
            version['identity_reason'] = reason
            event = self.store.finish(key, data=data, effective_locator=url, outcome=f'HTTP {status}',
                content_type=mime, version_metadata=version, identity_check=checked,
                date_suitability='unresolved', retrieval_status=retrieval, selected=False,
                selection_reason='Retained for identity/access review; downstream selection deferred',
                recoverable_failure=None if retrieval == 'retrieved' else reason,
                representation_metadata={'method': 'HTTP GET decoded response body',
                    'permission': 'Authorized source route read and local evidence retention',
                    'content_encoding': response.headers.get('content-encoding'),
                    'requested_locator': url, 'redirect_target': next_url if allowed_redirect else None})
            events.append(event)
            if allowed_redirect:
                hops += 1
                url = next_url
                continue
            if status in {429, 500, 502, 503, 504} and retry_count < self.retries:
                retry_count += 1
                self.sleep(min(retry_count, 2))  # Ignore unbounded server Retry-After.
                continue
            break
        return events
