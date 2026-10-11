"""Bounded representation checks; source text and legal meaning stay untouched.

Only ISO, full English calendar dates and EUR-Lex dotted day.month.year dates
are mapped. Relative commencement, abbreviated months and slash dates require
separate reviewed support. Offsets address the exact quoted string, not a
normalised copy of the capture.
"""
from datetime import date
import re

from .contracts import require

VERSION = 'rci-u20-authority-representations/1'
MONTHS = {name: number for number, name in enumerate((
    'January', 'February', 'March', 'April', 'May', 'June', 'July',
    'August', 'September', 'October', 'November', 'December'), 1)}
SPACE = r'[ \u00a0]+'
DATE = re.compile(r'(?<![\w./-])(?:'
    r'(?P<iso>[0-9]{4}-[0-9]{2}-[0-9]{2})|'
    r'(?P<day>[0-9]{1,2})' + SPACE + r'(?P<month>' + '|'.join(MONTHS) + r')' + SPACE + r'(?P<year>[0-9]{4})|'
    r'(?P<dotday>[0-9]{1,2})\.(?P<dotmonth>[0-9]{1,2})\.(?P<dotyear>[0-9]{4})'
    r')(?![\w/-]|\.[0-9])')


def date_mappings(encoded, quote):
    """Verify an ISO field against exact, unambiguous calendar representations."""
    require(isinstance(encoded, str) and re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', encoded),
            'date field requires a complete ISO calendar date')
    date.fromisoformat(encoded)
    require(not re.search(r'(?<![\w/])[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}(?!\w)', quote),
            'ambiguous slash calendar date representation')
    mappings = []
    for match in DATE.finditer(quote):
        if match['iso']:
            actual = date.fromisoformat(match['iso'])
            kind = 'iso-calendar-date'
        elif match['month']:
            actual = date(int(match['year']), MONTHS[match['month']], int(match['day']))
            kind = 'english-calendar-date'
        else:
            actual = date(int(match['dotyear']), int(match['dotmonth']), int(match['dotday']))
            kind = 'eurlex-dotted-calendar-date'
        mappings.append(dict(kind=kind, text=match.group(), start=match.start(), end=match.end(),
                             encoded=actual.isoformat()))
    date_shapes = re.compile(r'(?<!\w)(?:[0-9]{1,4}[-./][0-9]{1,2}[-./][0-9]{1,4}|'
                             r'[0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\s+[0-9]{4})(?![0-9])')
    spans = {(m['start'],m['end']) for m in mappings}
    for shaped in date_shapes.finditer(quote):
        require((shaped.start(),shaped.end()) in spans,
                'unsupported or malformed captured calendar representation')
    # Adjacent parenthesised/equated dates purport to be representations of one
    # date. Differing dates in separate clauses remain the reviewer's scope task.
    for left, right in zip(mappings, mappings[1:]):
        between = quote[left['end']:right['start']]
        if re.fullmatch(r'[ \u00a0]*(?:\(|\[|=)[ \u00a0]*', between):
            require(left['encoded'] == right['encoded'], 'contradictory calendar date representations')
    matches = [m for m in mappings if m['encoded'] == encoded]
    require(matches, 'date lacks a supported captured calendar representation')
    return matches


def literal_identity(value, text):
    return bool(re.search(r'(?<![\w:/.-])' + re.escape(value) + r'(?![\w:/.-])', text))


def selector_mapping(selector, document_id, identity_quote, version_quote):
    """Match the disclosed OJ/CELEX selectors to observed identity forms only."""
    oj = re.fullmatch(r'OJ:L_([0-9]{4})([0-9]{5})', selector or '')
    consolidated = re.fullmatch(r'CELEX:(02024R1689)-([0-9]{8})', selector or '')
    require(oj or consolidated, 'unsupported or malformed authority selector')
    if oj:
        require(int(oj[2]) > 0, 'malformed OJ document number')
        canonical = oj[1] + '/' + str(int(oj[2]))
        headers = re.findall(r'(?i)\bRegulation' + SPACE + r'\(EU\)' + SPACE + r'([0-9]{4}/[0-9]+)(?![\w/])', identity_quote)
        require(not headers or set(headers) == {canonical}, 'contradictory requested and returned act identity')
        journal_ids = re.findall(r'\bOJ' + SPACE + r'L,[ \u00a0]*([0-9]{4}/[0-9]+)(?![\w/])', version_quote)
        require(not journal_ids or set(journal_ids) == {canonical}, 'contradictory act version identity')
        require((document_id == selector and literal_identity(selector, identity_quote)) or
                (document_id == canonical and headers and set(headers) == {canonical}),
                'returned act identity does not match requested OJ selector')
        kind = 'oj-regulation-identifier'
    else:
        compact = consolidated[2]
        encoded = date(int(compact[:4]), int(compact[4:6]), int(compact[6:])).isoformat()
        canonical = consolidated[1] + '-' + compact
        identifiers = re.findall(r'(?<![\w:])(?:CELEX:)?(02024R[0-9]+-[0-9]{8})(?![\w-])', identity_quote)
        require(not identifiers or set(identifiers) == {canonical}, 'contradictory requested and returned consolidation identity')
        literal = document_id == selector and literal_identity(selector, identity_quote)
        mapped = document_id == canonical and literal_identity(canonical, identity_quote)
        require(literal or mapped, 'returned consolidation identity does not match requested CELEX selector')
        # A mapped identifier also needs the captured version header. A literal
        # selector keeps the existing synthetic contract, with any visible header
        # still checked for contradictions.
        headers = re.findall(r'\b(02024R[0-9]+)' + SPACE + r'—' + SPACE + r'EN' + SPACE + r'—' + SPACE +
                             r'([0-9]{1,2}\.[0-9]{1,2}\.[0-9]{4})' + SPACE + r'—' + SPACE + r'[0-9]{3}\.[0-9]{3}(?![\w.])', version_quote)
        require(literal or headers, 'consolidation version header unverified')
        for identifier, written_date in headers:
            require(identifier == consolidated[1], 'contradictory consolidation version identifier')
            date_mappings(encoded, written_date)
        kind = 'celex-consolidation-identifier'
    return dict(schema_version=VERSION, kind=kind, selector=selector,
                document_id=document_id, canonical_document_id=canonical,
                identity_quote=identity_quote, version_quote=version_quote)
