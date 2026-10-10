"""Read-only U10 inspection resolutions in the draft export and brief."""
from copy import deepcopy
from html import unescape
from importlib import import_module

import pytest

from rci.actions import build_export_model
from rci.contracts import ContractError
from rci.snapshots import COLLECTIONS
from rci.validate import validate_artifacts
from runtime.test_u14_u16 import export_model, write_artifacts

brief = import_module('rci.renderers.brief')


def resolution_accounting(effective='complete'):
    report = dict(source_id='REPORT-EV-001', source_business_id='EV-001', system_id='學習系統',
        reference='https://example.test/report', owner='Marketing', result='captured-unverified',
        attempt_ids=['attempt-one'], capture_ids=['capture-one'], evidence_ids=['evidence-two'],
        authorized=True)
    resolved = dict(report=report, candidate_numbers=[1, 2], gap_id=None,
        resolution=dict(declaration_candidate_numbers=[3], scopes=['learner chat'],
            evidence_ids=['evidence-two'], reason='Explicit completeness declaration and supported own-report predicates'))
    ledger = dict(original_upstream_status='partial', effective_upstream_status=effective,
        resolved_diagnostic_ids=['diagnostic-report', 'diagnostic-legal'],
        unresolved_diagnostic_ids=[] if effective=='complete' else ['diagnostic-remaining'],
        report_source_ids=[report['source_id']],
        legal_assessments=[dict(source_id='AMEND', diagnostic_ids=['diagnostic-legal'],
            rule_ids=['rule-record'], evidence_ids=['evidence-one'])])
    pending = deepcopy(resolved)
    pending.update(gap_id='gap-pending')
    pending['report']['source_id']='REPORT-PENDING'
    pending.pop('resolution')
    return dict(capture_resolution=ledger, reports=[resolved, pending], candidate_reviews=[])


def export_chain(accounting):
    chain = [dict(sequence=n, state={key:[] for key in COLLECTIONS[n-1]},
        unresolved=[], decisions=[]) for n in range(1, 6)]
    chain[0].update(run_id='run-fixture')
    chain[0]['state'].update(audiences=['Legal'], systems_in_scope=['學習系統'])
    chain[2].update(predecessor={'sha256':'sha256:'+'a'*64})
    chain[2]['state']['extensions']={'u09_authority':{'value':{'candidate_reviews':[]}}}
    chain[3]['state']['extensions']={'u10_reconciliation':{'value':accounting}}
    chain[4].update(created_at='2026-08-27T15:00:00Z')
    chain[4]['state']['extensions']={'u11_impacts':{'value':{'coverage':[]}}}
    chain[1]['state']['diagnostics']=[dict(id='diagnostic-report', record_type='diagnostic',
        summary='Historical pending report inspection', evidence_ids=[], reason='Inspection required')]
    state=dict(proposed_actions=[], review_requests=[], approval_requirements=[], escalations=[],
        extensions={'u12_actions':{'value':dict(actions=[],calendar_rows=[])}})
    return chain,state


def display_model(model, effective):
    accounting=resolution_accounting(effective)
    model['source_resolution']=deepcopy(accounting['capture_resolution'])
    model['source_resolution']['report_resolutions']=[deepcopy(accounting['reports'][0])]
    model['limitations'].extend(dict(id=identity,summary='Original capture inspection remains in history',
        evidence_ids=['evidence-two'],reason='Historical inspection requirement')
        for identity in model['source_resolution']['resolved_diagnostic_ids'])
    return model


def test_export_resolution_is_exact_detached_projection_before_fingerprint():
    accounting=resolution_accounting()
    chain,state=export_chain(accounting)
    original=deepcopy(chain)
    model=build_export_model(chain,state,'complete')
    assert chain==original
    assert model['source_resolution']==dict(accounting['capture_resolution'],
        report_resolutions=[accounting['reports'][0]])
    assert model['limitations']==chain[1]['state']['diagnostics']
    assert model['source_quality']==chain[1]['state']['sources']
    changed=deepcopy(chain)
    changed[3]['state']['extensions']['u10_reconciliation']['value']['reports'][0]['resolution']['reason']='Changed assessment support'
    assert build_export_model(changed,state,'complete')['draft_version']!=model['draft_version']
    model['source_resolution']['resolved_diagnostic_ids'].clear()
    model['source_resolution']['report_resolutions'][0]['report']['capture_ids'].clear()
    assert chain==original


def test_export_legacy_without_resolution_omits_new_key():
    accounting=resolution_accounting()
    accounting.pop('capture_resolution')
    chain,state=export_chain(accounting)
    first=build_export_model(chain,state,'partial')
    assert 'source_resolution' not in first
    assert first==build_export_model(chain,state,'partial')


@pytest.mark.parametrize('effective',['complete','partial'])
def test_brief_resolution_keeps_original_diagnostics_and_all_support(export_model,tmp_path,effective):
    model=display_model(export_model,effective)
    rendered=write_artifacts(tmp_path,model)
    decoded=unescape(rendered['compliance-brief.md'].decode())
    assert 'Original upstream status: partial' in decoded
    assert 'Effective upstream status: '+effective in decoded
    assert 'Original report result: captured-unverified' in decoded
    assert 'Resolved diagnostics: diagnostic-report;diagnostic-legal' in decoded
    assert 'Rules: rule-record' in decoded and 'Evidence: evidence-one' in decoded
    for value in ('attempt-one','capture-one','evidence-two','https://example.test/report',
                  'Declaration candidates: 3','Fact candidates: 1;2','Scopes: learner chat'):
        assert value in decoded
    assert all('['+identity+']' in decoded for identity in model['source_resolution']['resolved_diagnostic_ids'])
    assert ('Unresolved diagnostics: diagnostic-remaining' if effective=='partial' else
            'Unresolved diagnostics: None recorded') in decoded
    assert validate_artifacts(tmp_path,model)
    assert write_artifacts(tmp_path,model)==rendered


def test_brief_legacy_without_ledger_retains_its_output(export_model,tmp_path):
    original=brief.render(export_model)
    enriched=display_model(deepcopy(export_model),'complete')
    enriched.pop('source_resolution')
    enriched['limitations']=deepcopy(export_model['limitations'])
    assert brief.render(enriched)==original
    assert b'## Source inspection resolution' not in original
    write_artifacts(tmp_path,export_model)
    assert validate_artifacts(tmp_path,export_model)


@pytest.mark.parametrize('mutation',['diagnostic','support','missing-section','placement','remove-history','extra-claim'])
def test_independent_brief_validator_rejects_resolution_changes(export_model,tmp_path,mutation):
    model=display_model(export_model,'complete')
    write_artifacts(tmp_path,model)
    path=tmp_path/'compliance-brief.md'
    raw=path.read_text()
    if mutation=='diagnostic':
        raw=raw.replace('Resolved diagnostics: '+brief.text('diagnostic-report;diagnostic-legal'),
            'Resolved diagnostics: fabricated')
    elif mutation=='support':
        raw=raw.replace('Captures: '+brief.text('capture-one'),'Captures: unsupported')
    elif mutation=='missing-section':
        start=raw.index('## Source inspection resolution')
        end=raw.index('## Supported observations')
        raw=raw[:start]+raw[end:]
    elif mutation=='placement':
        start=raw.index('### Report inspection ')
        end=raw.index('## Supported observations')
        moved=raw[start:end]
        raw=raw[:start]+raw[end:]
        raw=raw.replace('## Proposed actions and dates','## Proposed actions and dates\n\n'+moved)
    elif mutation=='remove-history':
        raw='\n'.join(line for line in raw.splitlines() if '['+brief.text('diagnostic-report')+']' not in line)
    else:
        raw+='\nAll sources are approved.\n'
    path.write_text(raw)
    with pytest.raises(ContractError):
        validate_artifacts(tmp_path,model)
