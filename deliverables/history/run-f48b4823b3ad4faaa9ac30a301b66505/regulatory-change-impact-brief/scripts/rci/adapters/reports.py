"""U08 direct report reads. Register URLs authorize one GET, never a crawl.

Labels, unsupported URLs, binary formats and unreadable representations remain
unresolved. HTML text is a derived representation; images/PDF need a separately
verified extraction workflow and are retained without invented OCR.
"""
from copy import deepcopy
import re
from urllib.parse import urlsplit

from .reads import Page
from ..contracts import json_bytes, package_path, require, sha256_bytes, validate_schema
from ..evidence import _write
from ..ids import new_record_id
from ..source_manifest import Source


def supported_route(value):
    try:
        u = urlsplit(value)
        return (u.scheme == 'https' and u.port in {None, 443} and not
                (u.username or u.password or u.query or u.fragment) and
                bool(re.fullmatch(r'(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}', u.hostname or '')) and
                not u.hostname.lower().endswith(('.local', '.localhost', '.internal')))
    except ValueError:
        return False


def declarations(normalized):
    result = []
    for row in normalized['normalized_rows']:
        if row['source_id'] != 'EVIDENCE':
            continue
        values = row['values']
        fields = values['fields']
        ref = fields.get('evidence_ref')
        locator = values['field_locators'].get('evidence_ref')
        result.append(dict(source_id='REPORT-' + row['source_business_id'] + '-' +
            sha256_bytes(json_bytes(locator))[-12:],
            source_business_id=row['source_business_id'], system_id=row['system_id'],
            owner=fields.get('owner'), reference=ref,
            locator=locator,
            authorized=values['validation_status'] == 'valid' and supported_route(ref or '')))
    require(len({d['source_id'] for d in result}) == len(result), 'ambiguous linked report identity')
    return result


def report_identity(source, data, mime, effective):
    # A URL in a row authorizes reading, but establishes neither returned identity
    # nor historical suitability. Detect known access pages, leave the rest open.
    title = None
    if mime and mime.split(';')[0].strip().lower() == 'text/html':
        title = Page(data).title.strip() or None
    mismatch = title and re.search(r'\b(login|sign in|access denied|not found|captcha)\b', title, re.I)
    return ('mismatch' if mismatch else 'unverified',
            'Access page is not the requested report' if mismatch else 'Report identity/version require inspection',
            {'title': title, 'document_id': None, 'tabs': None})


def read_reports(store, reader, normalized):
    specs = declarations(normalized)
    for spec in specs:
        if spec['authorized']:
            source = Source(spec['source_id'], spec['reference'], 'http-read', None)
            # Exact target only: redirects are retained but not followed. No
            # embedded link, asset, script or source instruction can dispatch.
            reader._read(source, checker=report_identity, allowed_urls={source.route})
    return specs


def text_representation(store, event):
    attempt, capture = event['attempt'], event['capture']
    if capture is None or attempt['outcome'] != 'HTTP 200' or attempt['identity_check'] == 'mismatch':
        return None
    mime = capture['content_type'].split(';')[0].strip().lower()
    if mime not in {'text/plain', 'text/csv', 'text/html'}:
        return None
    raw = package_path(store.root, capture['local_reference']).read_bytes()
    try:
        text = raw.decode('utf-8')
    except UnicodeError:
        return None
    if mime == 'text/html':
        page = Page(raw)
        text = '\n'.join(t.strip() for t in page.text if t.strip())
    return text if text.strip() else None


def project_reports(store, specs, *, persist=False, retained_captures=()):
    """Construct/recheck supplemental report provenance against the exact journal."""
    events = store.inventory()
    captures, evidence, diagnostics, accounting = [], [], [], []
    for spec in specs:
        reads = [e for e in events if e['attempt']['source_id'] == spec['source_id']]
        require(bool(reads) == spec['authorized'], 'linked report dispatch coverage differs')
        for event in reads:
            require(event['attempt']['original_locator'] == spec['reference'] and
                    event['attempt']['effective_locator'] == spec['reference'] and
                    event['attempt']['adapter'] == 'http-read', 'unauthorized linked report route')
        item = dict(spec, attempt_ids=[e['attempt']['id'] for e in reads],
                    capture_ids=[], evidence_ids=[], result='unresolved')
        for event in reads:
            text = text_representation(store, event)
            if text is None:
                continue
            parent = event['capture']
            capture = parent
            if parent['content_type'].split(';')[0].strip().lower() == 'text/html':
                path = 'sources/' + event['attempt']['attempt_key'] + '.visible.txt'
                if persist:
                    _write(store.root, path, text.encode('utf-8'))
                    capture = dict(id=new_record_id(store.run_id, 2, 'capture'), record_type='capture',
                        summary='Derived visible HTML report text; layout and image meaning not established', evidence_ids=[],
                        attempt_id=parent['attempt_id'], representation='extract', local_reference=path,
                        content_hash=sha256_bytes(text.encode('utf-8')), content_type='text/plain',
                        derived_from_capture_id=parent['id'],
                        derivation={'method':'HTMLParser visible text (no scripts/styles)', 'processed_at':store.providers.now()},
                        representation_metadata={'method':'HTMLParser visible text (no scripts/styles)',
                            'locator':'whole HTML body text', 'permission':'Interview-authorized linked report retention'})
                else:
                    matches = [c for c in retained_captures if c.get('derived_from_capture_id') == parent['id']]
                    require(len(matches) == 1, 'missing or duplicated report text derivation')
                    capture = deepcopy(matches[0])
                    require(capture['local_reference'] == path and capture['content_hash'] == sha256_bytes(text.encode('utf-8')) and
                            capture['content_type'] == 'text/plain' and
                            capture['derivation']['method'] == 'HTMLParser visible text (no scripts/styles)',
                            'derived report text differs from original')
                    require(package_path(store.root, path).read_bytes() == text.encode('utf-8'), 'derived report bytes changed')
                validate_schema(capture, 'capture')
                captures.append(capture)
            claim = dict(id=new_record_id(store.run_id, 2, 'evidence'), record_type='evidence',
                summary='Unverified report content for ' + spec['source_business_id'], evidence_ids=[],
                capture_id=capture['id'], local_reference=capture['local_reference'], content_hash=capture['content_hash'],
                locator={'kind':'extract', 'value':'whole report text for ' + spec['source_business_id']},
                assertion='Unverified report content for ' + spec['source_business_id'], quoted_support=text)
            validate_schema(claim, 'evidence')
            evidence.append(claim)
            item['capture_ids'].append(capture['id'])
            item['evidence_ids'].append(claim['id'])
            item['result'] = 'captured-unverified'
        reason = ('Report reference is a label or unsupported route; no report URL invented' if not reads else
                  'Report bytes retained; identity, date, meaning and contradictions require inspection' if item['evidence_ids'] else
                  'Report unavailable, access page, or unsupported representation; source owner must supply readable evidence')
        diagnostics.append(dict(id=new_record_id(store.run_id, 2, 'diagnostic'), record_type='diagnostic',
            summary=reason, evidence_ids=[], source_basis=[spec['source_business_id'], spec['reference'] or 'missing reference'],
            reason=reason, owner=spec['owner'], resolution_need='System owner and Legal must verify report content and resolve contradictions; source status is not compliance.'))
        accounting.append(item)
    return dict(captures=captures, evidence=evidence, diagnostics=diagnostics, reports=accounting)
