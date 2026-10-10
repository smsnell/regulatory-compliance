"""U09 synthetic law only: no fixture asserts real legal obligations or dates."""
from copy import deepcopy
import os
from pathlib import Path
import shutil
import subprocess
import sys
from unittest.mock import patch

import httpx
import pytest
from jsonschema import Draft202012Validator

from rci.authority import (SOURCES, create_authority_request, freeze_authority,
    project_legal, submit_authority, validate_authority)
from rci.contracts import ContractError, SNAPSHOT_PATHS, json_bytes, parse_json, sha256_bytes, validate_schema
from rci.evidence import EvidenceStore
from rci.runner import capture_slice, validate_slice
from rci.runtime import SKILL, Providers
from rci.snapshots import accept_package, read_chain
from runtime.test_u07 import CONFIG, Replay

OBLIGATION = 'Deployers disclose synthetic AI output.'
PREDICATE = 'synthetic public output'
EXCEPTION = 'except synthetic editorial review'
TIMING = 'Synthetic rule applies from 2026-08-02 until 2027-01-01 exclusively.'
SOURCE_TEXT = {
    'LAW': ('Article 50', 'LAW-v1 2026-07-01', 'Reproduction of regulation 2024/1689'),
    'OJ': ('2024/1689', 'OJ-v1 2026-07-01', 'Base regulation 2024/1689'),
    'AMEND': ('OJ:L_202601744', 'AMEND-v1 2026-07-01', 'Unrelated synthetic agricultural instrument'),
    'CONSOLIDATED': ('CELEX:02024R1689-20260727', 'CONSOLIDATED-v1 2026-07-27', 'Consolidates regulation 2024/1689'),
    'TIME': ('Implementation timeline', 'TIME-v1 2026-07-01', 'Explanatory context only'),
    'FAQ': ('Transparency obligations under Article 50', 'FAQ-v1 2026-07-01', 'Explanatory context only'),
}


class LegalReplay(Replay):
    def handler(self, request):
        source = next((s['id'] for s in CONFIG['sources'] if s['route'] == str(request.url) and s['id'] in SOURCES), None)
        if source:
            self.calls.append(str(request.url))
            title = {'LAW':'Article 50','OJ':'Regulation 2024/1689','TIME':'Implementation timeline',
                'FAQ':'Transparency obligations under Article 50'}.get(source,source)
            paragraphs = [*SOURCE_TEXT[source], 'SYNTHETIC TEST ONLY, NOT LEGISLATION.',
                OBLIGATION, PREDICATE, EXCEPTION, TIMING]
            raw = ('<html><title>' + title + '</title><h1>' + title + '</h1>' +
                ''.join('<p>' + p + '</p>' for p in paragraphs) + '</html>').encode()
            return httpx.Response(200,content=raw,headers={'Content-Type':'text/html'})
        return super().handler(request)


@pytest.fixture(scope='module')
def captured(tmp_path_factory):
    parent = tmp_path_factory.mktemp('u09')
    config = deepcopy(CONFIG); config['output_root']='out'
    path=parent/'config.json'; path.write_bytes(json_bytes(config))
    # Capture only through Stage 02 here; explicit seam avoids any model call.
    from rci.runner import run_stages
    original=run_stages
    def with_legal(*args,**kwargs):
        return original(*args,**{**kwargs,'legal_extracts':True})
    with patch('rci.runtime.REPO',parent), patch('rci.runner.run_stages',side_effect=with_legal):
        outcome=capture_slice(path,reader_factory=LegalReplay,linked_reports=True)
    assert outcome['capture_slice_complete'],outcome
    return parent/outcome['candidate']


def clone(captured,tmp_path):
    root=tmp_path/captured.name
    shutil.copytree(captured,root)
    return root


def packet(root):
    second=read_chain(root,count=2)[1]
    ids=[e['id'] for e in second['state']['evidence'] if e['assertion'].startswith('Captured legal/context page body')]
    for name,path in [('policy','references/authority-policy.md'),('schema','references/schemas/authority-basis.schema.json')]:
        (root/('analysis/'+name+'.txt')).write_bytes((SKILL/path).read_bytes())
    metadata=dict(host_version=None,requested_model='synthetic-test',requested_effort='test-only',
        reported_model=None,reported_effort=None,usage=None,
        instruction_versions=[dict(path='analysis/policy.txt',sha256=sha256_bytes((root/'analysis/policy.txt').read_bytes()))],
        reference_versions=[dict(path='analysis/schema.txt',sha256=sha256_bytes((root/'analysis/schema.txt').read_bytes()))])
    request=create_authority_request(root,ids,metadata)
    return request


def proposal(request):
    ids={e['locator']['value'].split('body of ')[1].split(';')[0]:e['evidence_id'] for e in request['extracts']}
    relations=dict(LAW='reproduction',OJ='base',AMEND='unrelated',CONSOLIDATED='consolidates',TIME='context',FAQ='context')
    sources=[]; citations=[]
    for name in SOURCES:
        identity,version,relationship=SOURCE_TEXT[name]
        for quote in (identity,version,relationship):citations.append(dict(evidence_id=ids[name],quote=quote))
        sources.append(dict(source_id=name,evidence_id=ids[name],document_id=identity,version=version.split()[0],
            publication_date=version.split()[1],effective_from=None,identity_quote=identity,version_quote=version,
            relationship_quote=relationship,relationship=relations[name],assessment='consistent'))
    support=[]
    for component,value,quote in [('obligation',OBLIGATION,OBLIGATION),('predicate',PREDICATE,PREDICATE),
        ('role','deployer',OBLIGATION),('exception-scope',EXCEPTION,EXCEPTION),('exception',EXCEPTION,EXCEPTION),('timing',TIMING,TIMING)]:
        support.append(dict(component=component,value=value,evidence_id=ids['OJ'],quote=quote))
        citation=dict(evidence_id=ids['OJ'],quote=quote)
        if citation not in citations:citations.append(citation)
    descriptor=dict(schema_version='rci-u09-authority-basis/1',basis_id='synthetic-article50-output',
        meaning_key='synthetic-public-output-deployer-editorial-exception/v1',supersedes_rule_version_id=None,
        exception_scope=EXCEPTION,sources=sources,support=support,
        timing=dict(basis=TIMING,precision='date',boundary_timezone=None,effective_from='2026-08-02',
            effective_until='2027-01-01',until_exclusive=True))
    candidate=dict(summary=OBLIGATION,basis_type='binding-legal',citations=citations,
        conditions=[PREDICATE],role='deployer',timing_candidates=[json_bytes(descriptor).decode()],
        exception_candidates=[EXCEPTION],uncertainty=None,system_ids=['AI-001'])
    return dict(disposition='proposed',diagnostic=None,candidates=[candidate])


def descriptor(value):return parse_json(value['candidates'][0]['timing_candidates'][0].encode())
def set_descriptor(value,d):value['candidates'][0]['timing_candidates']=[json_bytes(d).decode()]


def freeze(root,value):
    result=submit_authority(root,json_bytes(value))
    third=freeze_authority(EvidenceStore(root,root.name))
    return result,third


def test_supported_draft_exact_versions_quotes_and_predecessor(captured,tmp_path):
    root=clone(captured,tmp_path); request=packet(root)
    before={p:p.read_bytes() for p in (root/'sources').glob('*')}
    before.update({p:p.read_bytes() for p in (root/'snapshots').glob('*')})
    result,third=freeze(root,proposal(request))
    assert result['disposition']=='proposed',result
    assert not third['state']['authority_blockers']
    rule,=third['state']['binding_rules']; timing,=third['state']['timing_rules']
    assert rule['basis_type']=='binding-legal' and rule['applicability']=='established'
    assert rule['obligation']==OBLIGATION
    assert rule['predicates']==[PREDICATE,'role=deployer','exception scope: '+EXCEPTION,'exception: '+EXCEPTION]
    assert timing['rule_id']==rule['id'] and timing['effective_from']=='2026-08-02'
    assert 'existing_due_date' not in rule and 'proposed_due_date' not in rule
    assert third['predecessor']['sha256']==sha256_bytes((root/SNAPSHOT_PATHS[1]).read_bytes())
    assert third['status']=='partial'  # unrelated company/report capture gaps remain visible
    assert all(p.read_bytes()==raw for p,raw in before.items())
    assert read_chain(root,count=3)[0]['state']['assigned_review_date']=='2026-08-26'
    validate_schema(third); validate_authority(EvidenceStore(root,root.name))
    assert not list((root/'snapshots').glob('04*'))
    with pytest.raises((ContractError,OSError)):accept_package(root)


@pytest.mark.parametrize('case',['faq-binding','time-binding','future-rule','future-version','unrelated-oj',
    'conflicting-timing','missing-identity','missing-version','missing-source','missing-predicate','unknown-role',
    'instant','unknown-precision','invented-date','invented-obligation','unknown-exceptions','uncertain','duplicate-chain',
    'nonlegal','amend-wrong-selector','consolidation-wrong-selector','unknown-publication','exception-approval'])
def test_unsupported_formal_conclusions_impossible(captured,tmp_path,case):
    root=clone(captured,tmp_path); request=packet(root); value=proposal(request); d=descriptor(value)
    c=value['candidates'][0]
    if case in {'faq-binding','time-binding'}:
        eid=next(s['evidence_id'] for s in d['sources'] if s['source_id']==('FAQ' if case=='faq-binding' else 'TIME'))
        for support in d['support']:
            support['evidence_id']=eid
            c['citations'].append(dict(evidence_id=eid,quote=support['quote']))
    elif case=='future-rule':d['timing']['effective_from']='2027-01-01'
    elif case=='future-version':d['sources'][1]['publication_date']='2027-01-01'
    elif case=='unrelated-oj':d['sources'][1]['document_id']='agricultural'
    elif case=='conflicting-timing':d['sources'][4]['assessment']='conflicting'
    elif case=='missing-identity':d['sources'][0]['identity_quote']='invented'
    elif case=='missing-version':d['sources'][1]['version']='imaginary'
    elif case=='missing-source':d['sources'].pop()
    elif case=='missing-predicate':d['support']=[s for s in d['support'] if s['component']!='predicate']
    elif case=='unknown-role':c['role']='unknown'
    elif case=='instant':d['timing'].update(precision='instant',boundary_timezone=None)
    elif case=='unknown-precision':d['timing']['precision']='unknown'
    elif case=='invented-date':d['timing']['effective_from']='2026-08-03'
    elif case=='invented-obligation':
        c['summary']='All systems are legally compliant.'
        d['support'][0]['value']=c['summary']
    elif case=='unknown-exceptions':d['exception_scope']='No exceptions ever apply'
    elif case=='uncertain':c['uncertainty']='Legal interpretation remains ambiguous'
    elif case=='duplicate-chain':value['candidates'].append(deepcopy(c))
    elif case=='nonlegal':c['basis_type']='internal-control'
    elif case=='amend-wrong-selector':d['sources'][2]['document_id']='2024/1689'
    elif case=='consolidation-wrong-selector':d['sources'][3]['document_id']='2024/1689'
    elif case=='unknown-publication':d['sources'][1]['publication_date']=None
    else:
        c['exception_candidates']=['Legal approved exemption']
        d['support'][-2]['value']='Legal approved exemption'
    set_descriptor(value,d)
    result,third=freeze(root,value)
    assert result['disposition']=='unresolved'
    assert third['status']=='blocked' and not third['state']['binding_rules'] and not third['state']['timing_rules']
    assert third['state']['authority_blockers']
    assert all(b['owner']=='Legal' and b['source_basis'] and b['resolution_need'] for b in third['state']['authority_blockers'])


@pytest.mark.parametrize('disposition',['refused','truncated','unsupported','ambiguous'])
def test_interpretation_failure_preserved_for_legal(captured,tmp_path,disposition):
    root=clone(captured,tmp_path); packet(root)
    raw=json_bytes(dict(disposition=disposition,diagnostic='Cannot interpret captured authority',candidates=[]))
    result=submit_authority(root,raw)
    third=freeze_authority(EvidenceStore(root,root.name))
    assert result['disposition']=='unresolved' and third['status']=='blocked'
    assert next((root/'analysis/authority/exchanges').glob('*/proposal.json')).read_bytes()==raw


def test_helper_cli_and_independent_projection_tamper(captured,tmp_path):
    root=clone(captured,tmp_path); request=packet(root); proposal_path=root/'analysis/authority/agent-proposal.json'
    proposal_path.write_bytes(json_bytes(proposal(request)))
    env={**os.environ,'RCI_CHILD_RUN':root.name,'PYTHONDONTWRITEBYTECODE':'1'}
    process=subprocess.run([sys.executable,str(SKILL/'scripts/stage.py'),'submit-authority','--root',str(root),'--proposal',str(proposal_path)],
        env=env,capture_output=True,text=True)
    assert process.returncode==0,process.stdout+process.stderr
    assert parse_json(process.stdout.encode())['disposition']=='proposed'
    freeze_authority(EvidenceStore(root,root.name))
    third=parse_json((root/SNAPSHOT_PATHS[2]).read_bytes())
    third['state']['binding_rules'][0]['obligation']='All eight systems comply'
    (root/SNAPSHOT_PATHS[2]).write_bytes(json_bytes(third))
    read_chain(root,count=3)  # structural validity is deliberately insufficient
    with pytest.raises(ContractError,match='Stage 03 differs'):validate_authority(EvidenceStore(root,root.name))


@pytest.mark.parametrize('body',[b'{broken',b'[]',b'{"disposition":"proposed","diagnostic":null,"candidates":[]}'])
def test_parse_failure_or_empty_support_retained(captured,tmp_path,body):
    root=clone(captured,tmp_path); packet(root)
    if body.startswith(b'{"'):
        assert submit_authority(root,body)['disposition']=='unresolved'
    else:
        with pytest.raises(ContractError):submit_authority(root,body)
    assert next((root/'analysis/authority/exchanges').glob('*/proposal.json')).read_bytes()==body
    assert next((root/'analysis/authority/exchanges').glob('*/validation.json')).is_file()


def test_source_failure_propagates_to_stage03_without_host_or_fallback(tmp_path):
    class MissingLawReplay(Replay):
        def handler(self,request):
            if str(request.url)==next(s['route'] for s in CONFIG['sources'] if s['id']=='OJ'):
                raise httpx.ConnectError('synthetic required law unavailable')
            return super().handler(request)
    config=deepcopy(CONFIG);config['output_root']='out';path=tmp_path/'config.json';path.write_bytes(json_bytes(config))
    with patch('rci.runtime.REPO',tmp_path),patch('rci.authority.preflight',side_effect=AssertionError('missing authority must not invoke host')):
        outcome=capture_slice(path,reader_factory=MissingLawReplay,authority=True)
    root=tmp_path/outcome['candidate']
    third=validate_authority(EvidenceStore(root,root.name))
    assert outcome['authority_stage_complete'] and outcome['authority_status']=='blocked'
    assert third['state']['authority_blockers'] and not third['state']['binding_rules']
    assert any('OJ' in b['reason'] for b in third['state']['authority_blockers'])
    attempts=[a for a in read_chain(root,count=2)[1]['state']['attempts'] if a['source_id']=='OJ']
    assert attempts and all(a['content'] is a['content_hash'] is a['local_reference'] is None for a in attempts)
    assert 'u08_reports' in read_chain(root,count=2)[1]['state']['extensions']
    assert outcome['missing_snapshots']==list(SNAPSHOT_PATHS[3:])
    assert not outcome['production_package'] and not outcome['package_acceptance']


@pytest.mark.parametrize('target',['sources','analysis','packet','run'])
def test_corrupt_bindings_technical_failure(captured,tmp_path,target):
    root=clone(captured,tmp_path);request=packet(root);value=proposal(request)
    if target=='sources':(root/request['extracts'][0]['path']).write_bytes(b'altered')
    elif target=='analysis':(root/'analysis/policy.txt').write_bytes(b'altered')
    elif target=='packet':
        request['extracts'][0]['text']='invented'
        (root/'analysis/authority/request.json').write_bytes(json_bytes(request))
    else:
        request['run_id']='run-other'
        (root/'analysis/authority/request.json').write_bytes(json_bytes(request))
    with pytest.raises(ContractError):submit_authority(root,json_bytes(value))
    diagnostic=parse_json(next((root/'analysis/authority/exchanges').glob('*/validation.json')).read_bytes())
    assert diagnostic['status']=='failed'
    assert not (root/SNAPSHOT_PATHS[2]).exists()


def test_additive_schema_and_frozen_contract_fingerprints():
    Draft202012Validator.check_schema(parse_json((SKILL/'references/schemas/authority-basis.schema.json').read_bytes()))
    assert sha256_bytes((SKILL.parent/'snapshot.schema.json').read_bytes())=='sha256:8de9874ded18fa97294e83012796e4c386aa60ccfd30f8eca89cabdf2a267ac3'
    assert sha256_bytes((SKILL/'references/schemas/contracts.schema.json').read_bytes())=='sha256:946d7fa46c18373f01313e1c2aab7b48b25b296527cbae0cf138f31f9c8915ec'
    # Owner-approved U19 bounded status amendment; baseline and authorization
    # are retained in docs/verification/report-resolution-proposal.md.
    assert sha256_bytes((SKILL/'scripts/rci/snapshots.py').read_bytes())=='sha256:a9b14e8ebed869dbdc4cc0952ed36eba1468bb28246559f09be7e28f2b7ff2e0'


@pytest.mark.parametrize('same_basis',[False,True])
def test_independent_supported_rule_survives_another_candidate_blocker(captured,tmp_path,same_basis):
    root=clone(captured,tmp_path); request=packet(root); value=proposal(request)
    blocked=deepcopy(value['candidates'][0])
    assessment=parse_json(blocked['timing_candidates'][0].encode())
    if not same_basis:assessment['basis_id']='different-synthetic-rule'
    assessment['timing']['precision']='unknown'
    blocked['timing_candidates']=[json_bytes(assessment).decode()]
    value['candidates'].append(blocked)
    result,third=freeze(root,value)
    assert result['disposition']=='unresolved' and third['status']=='blocked'
    assert len(third['state']['binding_rules'])==(0 if same_basis else 1)
    if not same_basis:
        assert third['state']['binding_rules'][0]['version_key']['basis_id']=='synthetic-article50-output'
    assert [r['disposition'] for r in third['state']['extensions']['u09_authority']['value']['candidate_reviews']]==[
        'blocked' if same_basis else 'supported-draft-rule','blocked']
    validate_authority(EvidenceStore(root,root.name))


def test_components_cannot_borrow_an_unassessed_capture_version(captured):
    # Exercise the prerequisite checker after the envelope's quote validation:
    # another successful OJ capture can have valid quotes but unreviewed history.
    from rci.authority import _assessment
    chain=read_chain(captured,count=2)
    evidence=[e for e in chain[1]['state']['evidence'] if e['assertion'].startswith('Captured legal/context')]
    request={'extracts':[dict(evidence_id=e['id'],locator=e['locator']) for e in evidence]}
    value=proposal(request); c=value['candidates'][0]; d=descriptor(value)
    original=next(e for e in evidence if 'body of OJ;' in e['locator']['value'])
    extra=deepcopy(original);extra['id']=original['id']+'-other-version'
    capture=deepcopy(next(r for r in chain[1]['state']['captures'] if r['id']==original['capture_id']))
    attempt=deepcopy(next(r for r in chain[1]['state']['attempts'] if r['id']==capture['attempt_id']))
    attempt['id']+='-other-version';capture['id']+='-other-version'
    capture['attempt_id']=attempt['id'];extra['capture_id']=capture['id']
    chain[1]['state']['attempts'].append(attempt);chain[1]['state']['captures'].append(capture);chain[1]['state']['evidence'].append(extra)
    d['support'][0]['evidence_id']=extra['id']
    c['citations'].append(dict(evidence_id=extra['id'],quote=d['support'][0]['quote']))
    set_descriptor(value,d)
    with pytest.raises(ContractError,match='assessed source capture'):_assessment(c,chain)


def test_authority_host_without_submission_is_technical_failure(captured,tmp_path):
    from rci.authority import interpret_authority
    root=clone(captured,tmp_path)
    def silent_host(command,prompt,root,timeout):
        (root/'analysis/host-events.jsonl').write_bytes(b'')
        (root/'analysis/host-stderr.txt').write_bytes(b'')
    with patch('rci.authority.preflight',return_value=('synthetic-host','test-v1')), \
         patch('rci.authority.invoke_host',side_effect=silent_host):
        with pytest.raises(ContractError,match='host did not submit authority'):
            interpret_authority(EvidenceStore(root,root.name),CONFIG)
    assert not (root/SNAPSHOT_PATHS[2]).exists()
    assert (root/'analysis/authority/request.json').exists()


def test_shared_source_conflict_still_withholds_all_dependent_rules(captured,tmp_path):
    root=clone(captured,tmp_path);request=packet(root);value=proposal(request)
    disputed=deepcopy(value['candidates'][0]);d=parse_json(disputed['timing_candidates'][0].encode())
    d['basis_id']='different-synthetic-rule'
    next(s for s in d['sources'] if s['source_id']=='OJ')['assessment']='conflicting'
    disputed['timing_candidates']=[json_bytes(d).decode()];value['candidates'].append(disputed)
    _,third=freeze(root,value)
    assert third['status']=='blocked' and third['state']['authority_blockers']
    assert not third['state']['binding_rules'] and not third['state']['timing_rules']
