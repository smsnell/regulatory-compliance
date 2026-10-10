#!/usr/bin/env python3
"""G3 independent specimen and coherent-tamper checks; no test helper imports.

Usage: python check-g3.py FOUR_STAGE_ROOT MIXED_AUTHORITY_ROOT
Run against synthetic acceptance specimens. This is not a legal truth engine.
"""
import hashlib
import json
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO/'regulatory-change-impact-brief/scripts'))
from rci.authority import validate_authority
from rci.contracts import ContractError
from rci.evidence import EvidenceStore
from rci.reconcile import validate_reconciliation
from rci.snapshots import read_chain

PATHS = ['snapshots/01-scope.json', 'snapshots/02-source-capture.json',
         'snapshots/03-authority-and-timing.json', 'snapshots/04-evidence-reconciliation.json']


def digest(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def load(root, path):
    return json.loads((root/path).read_bytes())


def ensure(value, reason):
    if not value:
        raise AssertionError(reason)


def inventory(root):
    return {str(p.relative_to(root)):digest(p.read_bytes()) for p in root.rglob('*') if p.is_file()}


def inspect(root, count):
    # Byte/graph/semantic inspection below does not use a producer or test helper.
    chain = [load(root, path) for path in PATHS[:count]]
    ensure(chain[0]['state']['assigned_review_date']=='2026-08-26', 'assigned date')
    records = {r['id']:r for s in chain for values in s['state'].values() if isinstance(values,list)
               for r in values if isinstance(r,dict) and 'id' in r}
    for n,snapshot in enumerate(chain):
        ensure(snapshot['run_id']==root.name and snapshot['sequence']==n+1, 'run/stage')
        if n:
            ensure(snapshot['predecessor']==dict(snapshot_id=chain[n-1]['snapshot_id'],path=PATHS[n-1],
                sha256=digest((root/PATHS[n-1]).read_bytes())), 'exact predecessor')
    for capture in chain[1]['state']['captures']:
        ensure(digest((root/capture['local_reference']).read_bytes())==capture['content_hash'], 'capture bytes')
    accounting = chain[2]['state']['extensions']['u09_authority']['value']
    pointers = accounting['interpretation']
    for pointer in pointers.values():
        ensure(digest((root/pointer['path']).read_bytes())==pointer['sha256'], 'exchange bytes')
    request,response = [load(root,pointers[name]['path']) for name in ('request','response')]
    ensure(response['packet_sha256']==pointers['request']['sha256'], 'request/response binding')
    ensure(request['run_id']==response['run_id']==root.name, 'exchange run')
    components=[];source_assessments=[]
    for candidate in accounting['candidates']:
        d=candidate['assessment'];rule=records[candidate['rule_id']]
        assessed={s['source_id']:s for s in d['sources']}
        for source in d['sources']:
            ev=records[source['evidence_id']];capture=records[ev['capture_id']];attempt=records[capture['attempt_id']]
            text=(root/ev['local_reference']).read_text()
            ensure(attempt['source_id']==source['source_id'], 'source assessment identity')
            ensure(all(source[key] in text for key in ('identity_quote','version_quote','relationship_quote')), 'source assessment quotes')
            if source['source_id'] in {'OJ','AMEND','CONSOLIDATED'}:
                ensure(all(urlsplit(attempt[key]).scheme=='https' and urlsplit(attempt[key]).hostname=='eur-lex.europa.eu'
                    for key in ('original_locator','effective_locator')), 'official authority origin')
            source_assessments.append(dict(source=source['source_id'],document=source['document_id'],version=source['version'],
                publication_date=source['publication_date'],relationship=source['relationship'],
                identity_quote=source['identity_quote'],version_quote=source['version_quote'],relationship_quote=source['relationship_quote']))
        ensure(rule['applicability']=='established' and rule['basis_type']=='binding-legal', 'rule authority')
        ensure(rule['effective_from'] <= '2026-08-26' and
            (rule['effective_until'] is None or '2026-08-26'<rule['effective_until']), 'rule timing')
        ensure(rule['version_key']==dict(basis_id=d['basis_id'],meaning_key=d['meaning_key']), 'rule identity')
        for support in d['support']:
            ev=records[support['evidence_id']];capture=records[ev['capture_id']];attempt=records[capture['attempt_id']]
            ensure(support['evidence_id']==assessed[attempt['source_id']]['evidence_id'], 'assessed version binding')
            ensure(attempt['source_id'] in {'OJ','AMEND','CONSOLIDATED'}, 'guidance cannot bind')
            ensure(support['quote'] in (root/ev['local_reference']).read_text(), 'component source quote')
            ensure(support['value'].casefold() in support['quote'].casefold(), 'component text')
            components.append(dict(component=support['component'],value=support['value'],
                quote=support['quote'],source=attempt['source_id'],path=ev['local_reference']))
    if count==3:
        ensure(chain[2]['status']=='blocked' and chain[2]['state']['authority_blockers'], 'mixed authority remains blocked')
        ensure(len(chain[2]['state']['binding_rules'])==1, 'independent supported rule retained')
        ensure([r['disposition'] for r in accounting['candidate_reviews']]==['supported-draft-rule','blocked'], 'candidate scope')
    ensure(not (root/'snapshots/05-impact-analysis.json').exists(), 'U11 must remain absent')
    return dict(root=str(root),run_id=root.name,snapshot_hashes={p:digest((root/p).read_bytes()) for p in PATHS[:count]},
        status=chain[-1]['status'],components=components,source_assessments=source_assessments,
        semantic_scope='Synthetic clauses inspected; no real legal applicability asserted')


def negative(root, case, count, mutate):
    # Mutate the last stage of each inspected prefix, leaving its predecessor
    # valid. A hash mismatch cannot explain rejection; originals remain intact.
    with TemporaryDirectory(prefix='g3-probe-') as parent:
        copy=Path(parent)/root.name;shutil.copytree(root,copy)
        snapshot=load(copy,PATHS[count-1]);mutate(snapshot)
        (copy/PATHS[count-1]).write_text(json.dumps(snapshot,indent=2)+'\n')
        read_chain(copy,count=count)  # Must still satisfy the frozen structural contract.
        try:
            (validate_authority if count==3 else validate_reconciliation)(EvidenceStore(copy,copy.name))
        except ContractError as error:
            return dict(case=case,result='PASS',observed=str(error),structurally_valid=True)
        raise AssertionError('Coherent mutation accepted: '+case)


def main():
    main_root,mixed_root=[Path(p).resolve() for p in sys.argv[1:]]
    before={str(root):inventory(root) for root in (main_root,mixed_root)}
    results=[inspect(main_root,4),inspect(mixed_root,3)]
    validate_reconciliation(EvidenceStore(main_root,main_root.name))
    validate_authority(EvidenceStore(mixed_root,mixed_root.name))
    def role(s):
        rule=s['state']['binding_rules'][0]
        rule['predicates']=[p.replace('role=deployer','role=provider') for p in rule['predicates']]
    def fact(s):
        f=next(f for f in s['state']['system_facts'] if f['predicate']=='notice_present' and f['state']=='supported')
        f['value']['resolved_value']=False
    def ledger(s):
        s['state']['extensions']['u10_reconciliation']['value']['register_rows'].pop()
    mutations=[negative(mixed_root,'invented legal role',3,role),
               negative(main_root,'changed supported notice value',4,fact),
               negative(main_root,'silently dropped raw-row accounting',4,ledger)]
    ensure(all(inventory(root)==before[str(root)] for root in (main_root,mixed_root)), 'original evidence changed')
    print(json.dumps(dict(specimens=results,adversarial=mutations,originals_unchanged=True,
        production_acceptance=False),indent=2))


if __name__=='__main__':
    main()
