"""Retained U20 representations plus synthetic support; no legal determination."""
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from rci.authority import _assessment, _representation_accounting, evaluate, freeze_authority, submit_authority
from rci.authority_representations import date_mappings, literal_identity, selector_mapping
from rci.contracts import ContractError, json_bytes, parse_json, sha256_bytes
from rci.evidence import EvidenceStore
from rci.snapshots import read_chain
from runtime.test_u09 import captured, descriptor, packet, proposal, set_descriptor, LegalReplay
from runtime.test_u07 import CONFIG

REPO = Path(__file__).resolve().parents[2]


def retained(source):
    request = parse_json((REPO/'deliverables/analysis/authority/request.json').read_bytes())
    extract, = [e for e in request['extracts'] if e['locator']['value'].startswith('whole visible body of '+source+';')]
    # This fixture checks exact retained bytes, rather than retyping source claims.
    assert sha256_bytes((REPO/'deliverables'/extract['path']).read_bytes()) == extract['sha256']
    assert sha256_bytes(extract['text'].encode()) == extract['text_sha256']
    return extract


def test_observed_dates_pass_existing_assessment_without_rewriting_support(captured):
    """Synthetic semantics; the encoding witness is copied from actual U20 text."""
    chain = deepcopy(read_chain(captured, count=2))
    evidence = [e for e in chain[1]['state']['evidence'] if e['assertion'].startswith('Captured legal/context')]
    packet = {'extracts':[dict(evidence_id=e['id'],locator=e['locator']) for e in evidence]}
    value = proposal(packet); candidate = value['candidates'][0]; d = descriptor(value)
    oj_text = retained('OJ')['text']
    timing = next(line for line in oj_text.splitlines() if line == 'It shall apply from 2\xa0August 2026.')
    publication = next(line for line in oj_text.splitlines() if line.startswith('OJ L, 2024/1689,'))
    source = next(s for s in d['sources'] if s['source_id']=='OJ')
    source.update(version='12.7.2024', version_quote=publication, publication_date='2024-07-12')
    d['timing'].update(basis=timing, effective_until=None)
    component = next(s for s in d['support'] if s['component']=='timing')
    component.update(value=timing,quote=timing)
    candidate['citations'] += [dict(evidence_id=source['evidence_id'],quote=publication),
                               dict(evidence_id=source['evidence_id'],quote=timing)]
    set_descriptor(value,d)
    before = deepcopy(candidate)
    accepted = _assessment(candidate,chain)
    assert accepted['timing']['effective_from']=='2026-08-02'
    assert accepted['sources'][1]['publication_date']=='2024-07-12'
    assert candidate==before
    mapped = _representation_accounting(accepted,chain)
    assert {m['field'] for m in mapped} == {'publication_date','timing.effective_from'}
    for record in mapped:
        assert record['source_version']=='12.7.2024'
        assert record['evidence_id']==source['evidence_id'] and record['capture_id']
        assert record['original_locator']==record['effective_locator']=='https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng'
        for mapping in record['mappings']:
            assert record['quoted_support'][mapping['start']:mapping['end']]==mapping['text']


def test_retained_ambiguous_proposal_stays_unresolved_after_mapping():
    root=REPO/'deliverables'
    raw=parse_json((root/'analysis/authority/exchanges/918b277a6439493294bcd1df1633ae77/proposal.json').read_bytes())
    assert raw['disposition']=='ambiguous'
    # No representation conversion changes the host's disposition or history assessment.
    assert 'historical' in raw['diagnostic']
    exchange=root/'analysis/authority/exchanges/918b277a6439493294bcd1df1633ae77'
    checked=evaluate(root,(exchange/'request.json').read_bytes(),(exchange/'response.json').read_bytes())
    assert checked['exchange'].disposition=='unresolved' and not checked['rules']
    assert checked['exchange'].response['disposition']=='ambiguous'
    assert checked['problems']


def test_representation_witness_is_quote_validated_and_emits_provenance(tmp_path):
    """A new synthetic capture exercises the public exchange/freeze path."""
    from rci.runner import capture_slice, run_stages
    oj=retained('OJ')['text']
    publication=next(line for line in oj.splitlines() if line.startswith('OJ L, 2024/1689,'))
    timing=next(line for line in oj.splitlines() if line=='It shall apply from 2\xa0August 2026.')
    route=next(s['route'] for s in CONFIG['sources'] if s['id']=='OJ')
    class RepresentationReplay(LegalReplay):
        def handler(self,request):
            response=super().handler(request)
            if str(request.url)==route:
                witness=('<p>'+publication+'</p><p>'+timing+'</p>').encode()
                return httpx.Response(200,content=response.content.replace(b'</html>',witness+b'</html>'),
                                      headers={'Content-Type':'text/html'})
            return response
    config=deepcopy(CONFIG); config['output_root']='out'
    path=tmp_path/'config.json';path.write_bytes(json_bytes(config))
    def legal(*args,**kwargs):return run_stages(*args,**{**kwargs,'legal_extracts':True})
    with patch('rci.runtime.REPO',tmp_path),patch('rci.runner.run_stages',side_effect=legal):
        outcome=capture_slice(path,reader_factory=RepresentationReplay,linked_reports=True)
    root=tmp_path/outcome['candidate']
    before={p:p.read_bytes() for directory in ('sources','snapshots') for p in (root/directory).glob('*') if p.is_file()}
    request=packet(root);value=proposal(request);c=value['candidates'][0];d=descriptor(value)
    source=next(s for s in d['sources'] if s['source_id']=='OJ')
    source.update(version='12.7.2024',version_quote=publication,publication_date='2024-07-12')
    d['timing'].update(basis=timing,effective_until=None)
    next(s for s in d['support'] if s['component']=='timing').update(value=timing,quote=timing)
    c['citations'] += [dict(evidence_id=source['evidence_id'],quote=q) for q in (publication,timing)]
    set_descriptor(value,d)
    submitted=submit_authority(root,json_bytes(value))
    assert submitted['disposition']=='proposed',submitted
    third=freeze_authority(EvidenceStore(root,root.name))
    assert len(third['state']['binding_rules'])==1
    accounting=third['state']['extensions']['u09_authority']['value']
    mappings=accounting['representation_mappings']
    assert {m['encoded_value'] for m in mappings}=={'2024-07-12','2026-08-02'}
    assert {m['quoted_support'] for m in mappings}=={publication,timing}
    assert all(p.read_bytes()==raw for p,raw in before.items())
    assert third['state']['binding_rules'][0]['source_publication_date']=='2024-07-12'
    assert third['state']['binding_rules'][0]['effective_from']=='2026-08-02'


@pytest.mark.parametrize('source,encoded,needle',[
    ('OJ','2024-07-12','12.7.2024'),
    ('OJ','2026-08-02','2\xa0August 2026'),
    ('AMEND','2026-07-24','24.7.2026'),
    ('AMEND','2026-12-02','2\xa0December 2026'),
    ('CONSOLIDATED','2026-07-27','27.07.2026'),
    ('CONSOLIDATED','2026-08-02','2 August 2026'),
    ('FAQ','2026-07-24','24 July 2026'),
])
def test_calendar_mapping_exact_retained_bytes(source,encoded,needle):
    extract=retained(source)
    quote=next(line for line in extract['text'].splitlines() if needle in line)
    mappings=date_mappings(encoded,quote)
    assert any(m['text']==needle for m in mappings)
    assert all(m['encoded']==encoded and quote[m['start']:m['end']]==m['text'] for m in mappings)


@pytest.mark.parametrize('quote',[
    '02/08/2026','08/02/2026','2 Aug 2026','August 2, 2026','2nd August 2026',
    '2 august 2026','2\u2009August 2026','2\tAugust 2026','2\u200bAugust 2026',
    '2026-8-02','2026-08-2','x2026-08-02','2026-08-02T00:00:00Z',
    '31 February 2026','31.2.2026','2026-02-31','32 August 2026',
    'the third day following publication','2 August','August 2026','2026',
    '2 August 2026 (2026-08-03)','2 August 2026 = 3.8.2026',
    '2 August 2026 and 2026-02-31','2 August 2026 and 02/08/2026',
    '2 August 2026 and 2026-8-02','2 August 2026 and 2 Aug 2026',
])
def test_unsupported_ambiguous_and_malformed_dates_fail_closed(quote):
    with pytest.raises((ContractError,ValueError)):
        date_mappings('2026-08-02',quote)


def test_date_encoding_checks_target_and_preserves_supported_interval():
    quote='Synthetic rule applies from 2026-08-02 until 2027-01-01 exclusively.'
    assert date_mappings('2026-08-02',quote)
    assert date_mappings('2027-01-01',quote)
    with pytest.raises(ContractError):date_mappings('2026-08-03',quote)
    with pytest.raises(ContractError):date_mappings('20260802',quote)


def test_actual_amendment_and_consolidation_identifier_mapping():
    amend=retained('AMEND')['text']
    identity=next(line for line in amend.splitlines() if line.startswith('Regulation (EU) 2026/1744 of'))
    version=next(line for line in amend.splitlines() if line.startswith('OJ L, 2026/1744,'))
    mapped=selector_mapping('OJ:L_202601744','2026/1744',identity,version)
    assert mapped['canonical_document_id']=='2026/1744' and mapped['identity_quote']==identity
    text=retained('CONSOLIDATED')['text']
    identity=next(line for line in text.splitlines() if line=='Document\xa002024R1689-20260727')
    version=next(line for line in text.splitlines() if line.startswith('02024R1689 — EN —'))
    mapped=selector_mapping('CELEX:02024R1689-20260727','02024R1689-20260727',identity,version)
    assert mapped['canonical_document_id']=='02024R1689-20260727'
    assert mapped['identity_quote']==identity and mapped['version_quote']==version


@pytest.mark.parametrize('selector,document,identity,version',[
    ('OJ:L_202601744','2024/1689','Regulation (EU) 2024/1689','24.7.2026'),
    ('OJ:L_202601744','2026/17440','Regulation (EU) 2026/17440','24.7.2026'),
    ('OJ:L_202601744','2026/1744','See 2026/1744','24.7.2026'),
    ('OJ:L_202601744','2026/1744','Regulations (EU) 2026/1744','24.7.2026'),
    ('OJ:L_202601744','2026/1744','Regulation (EU) 2026/1744; Regulation (EU) 2024/1689','24.7.2026'),
    ('OJ:L_20261744','2026/1744','Regulation (EU) 2026/1744','24.7.2026'),
    ('OJ:L_202600000','2026/0','Regulation (EU) 2026/0','24.7.2026'),
    ('OJ:L_202601744','2026/1744','Regulation (EU) 2026/1744','OJ L, 2026/1745, 24.7.2026'),
    ('CELEX:02024R1689-20260727','02024R1689-20260728','Document 02024R1689-20260728','27.07.2026'),
    ('CELEX:02024R1689-20260727','02024R1689-20260727','Document 02024R1689-20260727','02024R1689 — EN — 28.07.2026 — 001.001'),
    ('CELEX:02024R1689-20260727','02024R1689-20260727','Document 02024R1689-20260727','02024R1690 — EN — 27.07.2026 — 001.001'),
    ('CELEX:02024R1689-20260727','02024R1689-20260727','Document 02024R1689-20260727','27.07.2026'),
    ('CELEX:02024R1689-20260231','02024R1689-20260231','Document 02024R1689-20260231','02024R1689 — EN — 31.02.2026 — 001.001'),
    ('CELEX:32024R1689','2024/1689','Regulation (EU) 2024/1689','27.07.2026'),
])
def test_selector_mismatch_unsupported_and_contradictory_representations_fail_closed(selector,document,identity,version):
    with pytest.raises((ContractError,ValueError)):
        selector_mapping(selector,document,identity,version)


@pytest.mark.parametrize('quote',['2024/16890','12024/1689','2024/1689-20260727','CELEX:2024/1689'])
def test_partial_document_identifier_is_not_literal_support(quote):
    assert not literal_identity('2024/1689',quote)
