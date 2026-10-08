"""U02 A/S/I/R regressions. All inputs are synthetic; no live acceptance claim."""
from copy import deepcopy
import base64
from dataclasses import asdict
import csv
import hashlib
from itertools import product
import json
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'regulatory-change-impact-brief/scripts'))
from jsonschema import Draft202012Validator, FormatChecker
from rci.contracts import (ApprovalState, ContractError, ImpactState, PublicationState,
                           RetrievalState, RunState, SNAPSHOT_PATHS, STAGES, PUBLIC_SCHEMA_HASH,
                           json_bytes, package_path, parse_json, reduce_states, sha256_bytes,
                           validate_interpretation, validate_schema)
from rci.ids import (BusinessKey, IdentityConflict, IdentityRegistry, calendar_uid,
                     new_record_id, new_run_id, new_snapshot_id, rule_version_id, stable_business_id,
                     action_rule_basis)
from rci.snapshots import (COMPLETION_MARKER, INCOMPLETE_MARKER, accept_package, read_chain,
                           stage_records, validate_marker, validate_snapshot, write_snapshot)

FIXTURE = ROOT / 'tests/fixtures/u02/package'
CHAIN = [parse_json((FIXTURE / path).read_bytes()) for path in SNAPSHOT_PATHS]


class IdentityAndState(unittest.TestCase):
    def test_action_basis_set_is_order_independent_and_preserves_members(self):
        self.assertEqual(action_rule_basis(['rule-A']), 'rule-A')
        self.assertEqual(action_rule_basis(['rule-B','rule-A','rule-A']),action_rule_basis(['rule-A','rule-B']))
        self.assertNotEqual(action_rule_basis(['rule-A','rule-B']), action_rule_basis(['rule-A','rule-C']))
        key=BusinessKey('SYS',action_rule_basis(['rule-A','rule-B']),'verify','learner-chat')
        reordered=BusinessKey('SYS',action_rule_basis(['rule-B','rule-A']),'verify','learner-chat')
        self.assertEqual(calendar_uid(stable_business_id('action',key)),calendar_uid(stable_business_id('action',reordered)))
        with self.assertRaises(ValueError):action_rule_basis([])

    def test_stable_ids_ignore_row_order_wording_and_dates(self):
        rows = [dict(system_id=f'SYS-{i}', rule_basis='rule:v1:test', kind='notice',
                     distinguishing_scope='learner-chat', row=i, date='2026-08-26', wording='old')
                for i in range(8)]
        def identities(values):
            return {r['system_id']: tuple(stable_business_id(ns, BusinessKey(**{
                k: r[k] for k in ('system_id','rule_basis','kind','distinguishing_scope')}))
                for ns in ('impact','action')) for r in values}
        changed = [{**r, 'date':'2027-10-01','wording':'rewritten','row':100-i}
                   for i,r in enumerate(reversed(rows))]
        self.assertEqual(identities(rows), identities(changed))
        actions = [v[1] for v in identities(rows).values()]
        self.assertEqual({k:calendar_uid(v[1]) for k,v in identities(rows).items()},
                         {k:calendar_uid(v[1]) for k,v in identities(changed).items()})
        self.assertEqual(len(set(actions)), 8)

    def test_distinguishing_components_change_identity(self):
        key = BusinessKey('SYS', 'RULE-1', 'notice', 'learners')
        for field in ('system_id','rule_basis','kind','distinguishing_scope'):
            other = BusinessKey(**{**asdict(key),field:'changed'})
            self.assertNotEqual(stable_business_id('impact',key),stable_business_id('impact',other))
        self.assertNotEqual(rule_version_id('policy','meaning-v1'),rule_version_id('policy','meaning-v2'))
        with self.assertRaises(ValueError): BusinessKey('SYS','RULE','notice','scope',version='v2').canonical_bytes()
        with self.assertRaises(ValueError): calendar_uid('source-native-action')

    def test_fresh_and_run_bound_ids(self):
        self.assertEqual(len({new_run_id() for _ in range(30)}),30)
        self.assertEqual(len({new_snapshot_id() for _ in range(30)}),30)
        a,b=new_run_id(),new_run_id()
        self.assertNotEqual(new_record_id(a,1,'gap'),new_record_id(b,1,'gap'))
        fixture=deepcopy(CHAIN[3]);fixture['state']['system_facts'][0]['id']=new_record_id(b,4,'fact')
        fixture['produced_record_ids']=[fixture['state']['system_facts'][0]['id']]
        with self.assertRaises(IdentityConflict): validate_snapshot(fixture,root=FIXTURE,upstream=CHAIN[:3])

    def test_collision_detection_preserves_source_ids(self):
        registry=IdentityRegistry();key=BusinessKey('SYS','RULE','notice','chat')
        self.assertEqual(registry.operational('SYSTEMS',' Original-ID '),' Original-ID ')
        with self.assertRaises(IdentityConflict): registry.operational('SYSTEMS',' Original-ID ')
        self.assertEqual(registry.operational('CALENDAR',' Original-ID '),' Original-ID ')
        identity=registry.business('impact',key)
        self.assertEqual(registry.business('impact',key),identity)
        with patch('rci.ids.stable_business_id',return_value=identity):
            with self.assertRaises(IdentityConflict): registry.business('impact',BusinessKey('other','RULE','notice','chat'))

    def test_full_reducer_truth_table(self):
        priority={'complete':0,'partial':1,'blocked':2,'failed':3}
        for size in (1,2,3,4):
            for values in product(priority,repeat=size):
                self.assertEqual(reduce_states(values),max(values,key=priority.get))
        with self.assertRaises(ContractError): reduce_states([])
        with self.assertRaises(ValueError): reduce_states(['approved'])

    def test_exact_independent_enums(self):
        expected=[(RunState,['complete','partial','blocked','failed']),
                  (RetrievalState,['retrieved','unavailable','invalid','unverified','stale']),
                  (ImpactState,['supported-impact','supported-no-impact','conflicting','unresolved']),
                  (ApprovalState,['pending','approved','rejected','not-required']),
                  (PublicationState,['validated','blocked','failed'])]
        for cls,values in expected:self.assertEqual([v.value for v in cls],values)
        schema=json.loads((ROOT/'regulatory-change-impact-brief/references/schemas/contracts.schema.json').read_bytes())['$defs']
        for cls,definition,field in [(RunState,'snapshot','status'),(RetrievalState,'attempt','retrieval_status'),
                                      (ImpactState,'impact','state'),(ApprovalState,'approval','status')]:
            self.assertEqual(schema[definition]['properties'][field]['enum'],[v.value for v in cls])
        for native in ['complete','planned','open','blocked','scheduled','closed']:
            with self.assertRaises(ValueError): ApprovalState(native)


class SnapshotContracts(unittest.TestCase):
    def copy_run(self, root, run_id):
        shutil.copytree(FIXTURE,root)
        replacements={CHAIN[0]['run_id']:run_id}
        for snapshot in CHAIN:
            replacements[snapshot['snapshot_id']]=new_snapshot_id()
            for record in stage_records(snapshot):
                replacements[record['id']]=new_record_id(run_id,snapshot['sequence'],record['record_type'])
        def remap(value):
            if isinstance(value,str):return replacements.get(value,value)
            if isinstance(value,list):return [remap(v) for v in value]
            if isinstance(value,dict):return {k:remap(v) for k,v in value.items()}
            return value
        chain=remap(deepcopy(CHAIN))
        for i,s in enumerate(chain):
            if i:s['predecessor']['sha256']=sha256_bytes((root/SNAPSHOT_PATHS[i-1]).read_bytes())
            (root/SNAPSHOT_PATHS[i]).write_bytes(json_bytes(s))
        marker=parse_json((root/COMPLETION_MARKER).read_bytes())
        marker.update(run_id=run_id,stage07={'snapshot_id':chain[6]['snapshot_id'],'path':SNAPSHOT_PATHS[6],
                      'sha256':sha256_bytes((root/SNAPSHOT_PATHS[6]).read_bytes())})
        (root/COMPLETION_MARKER).write_bytes(json_bytes(marker))
        return chain

    def test_policy_control_ids_survive_fresh_runs(self):
        identities=[]
        for number in (1,2,3):
            root=Path(self.temp.name)/f'policy-{number}';chain=self.copy_run(root,new_run_id())
            evidence=chain[1]['state']['evidence'][0]['id'];system=chain[0]['state']['systems_in_scope'][0]
            key={'basis_id':'SYNTHETIC-NOTICE-CONTROL','meaning_key':'notice-before-interaction/v1' if number<3 else 'notice-before-interaction/v2'}
            control={'id':new_record_id(chain[0]['run_id'],4,'policy-control'),'record_type':'policy-control',
                     'summary':f'Synthetic control wording variant {number}.','evidence_ids':[evidence],
                     'basis_type':'internal-control','control':'Require notice before interaction.', 'system_ids':[system],
                     'version_key':key,'rule_version_id':rule_version_id(**key),'supersedes_rule_version_id':None}
            chain[3]['state']['policy_controls']=[control];chain[3]['produced_record_ids'].append(control['id'])
            impact=chain[4]['state']['impacts'][0];chain[4]['consumed_record_ids'].remove(impact['rule_id'])
            chain[4]['consumed_record_ids'].append(control['id']);impact['rule_id']=control['id']
            impact['identity_key']['rule_basis']=control['rule_version_id']
            impact['impact_id']=stable_business_id('impact',BusinessKey(**impact['identity_key']))
            action=chain[5]['state']['proposed_actions'][0];action['identity_key']['rule_basis']=control['rule_version_id']
            action['action_id']=stable_business_id('action',BusinessKey(**action['identity_key']))
            for i,s in enumerate(chain):
                if i:s['predecessor']['sha256']=sha256_bytes((root/SNAPSHOT_PATHS[i-1]).read_bytes())
                validate_snapshot(s,root=root,upstream=chain[:i]);(root/SNAPSHOT_PATHS[i]).write_bytes(json_bytes(s))
            self.assertEqual(read_chain(root),chain)
            identities.append((impact['impact_id'],action['action_id'],calendar_uid(action['action_id'])))
            for field in ('version_key','rule_version_id'):
                bad=deepcopy(chain[3]);bad['state']['policy_controls'][0].pop(field)
                with self.assertRaises(ContractError):validate_snapshot(bad,root=root,upstream=chain[:3])
            bad=deepcopy(chain[3]);bad['state']['policy_controls'][0]['version_key']['meaning_key']='fabricated'
            with self.assertRaises(ContractError):validate_snapshot(bad,root=root,upstream=chain[:3])
        self.assertEqual(identities[0],identities[1]);self.assertNotEqual(identities[1],identities[2])

    def check_current_package(self, stage06):
        (self.root/SNAPSHOT_PATHS[5]).write_bytes(json_bytes(stage06))
        final=deepcopy(CHAIN[6]);final['predecessor']['sha256']=sha256_bytes(json_bytes(stage06))
        (self.root/SNAPSHOT_PATHS[6]).write_bytes(json_bytes(final))
        marker=parse_json((self.root/COMPLETION_MARKER).read_bytes())
        marker['stage07']['sha256']=sha256_bytes(json_bytes(final))
        (self.root/COMPLETION_MARKER).write_bytes(json_bytes(marker))
        return accept_package(self.root)

    def check_rehashed_package(self, chain):
        """Exercise disk acceptance without hiding semantic failures behind old hashes."""
        for i, snapshot in enumerate(chain):
            if i:
                snapshot['predecessor']['sha256'] = sha256_bytes(
                    (self.root / SNAPSHOT_PATHS[i - 1]).read_bytes())
            (self.root / SNAPSHOT_PATHS[i]).write_bytes(json_bytes(snapshot))
        marker = parse_json((self.root / COMPLETION_MARKER).read_bytes())
        marker['stage07']['sha256'] = sha256_bytes((self.root / SNAPSHOT_PATHS[-1]).read_bytes())
        (self.root / COMPLETION_MARKER).write_bytes(json_bytes(marker))
        return accept_package(self.root)

    def test_g1_action_states_agree_with_requirements(self):
        for status in ('not-required', 'rejected'):
            chain = deepcopy(CHAIN)
            chain[5]['state']['proposed_actions'][0]['approval_status'] = status
            with self.subTest(status=status), self.assertRaises(ContractError):
                self.check_rehashed_package(chain)
        chain = deepcopy(CHAIN)
        chain[5]['state']['proposed_actions'][0]['approval_status'] = 'not-required'
        chain[5]['state']['approval_requirements'][0]['status'] = 'not-required'
        self.assertEqual(self.check_rehashed_package(chain)[5]['state']['proposed_actions'][0]['approval_status'],
                         'not-required')
        approval = chain[5]['state']['approval_requirements'].pop()
        chain[5]['produced_record_ids'].remove(approval['id'])
        with self.assertRaises(ContractError):
            self.check_rehashed_package(chain)

    def test_g1_rejection_requires_authenticated_matching_rejection(self):
        chain = deepcopy(CHAIN)
        stage = chain[5]
        stage['state']['proposed_actions'][0]['approval_status'] = 'rejected'
        approval = stage['state']['approval_requirements'][0]
        approval['status'] = 'rejected'
        with self.assertRaisesRegex(ContractError, 'rejection lacks authenticated matching feedback'):
            self.check_rehashed_package(chain)
        feedback = self.current_feedback(stage)
        feedback['outcome'] = 'rejected'
        stage['state']['feedback'] = [feedback]
        stage['produced_record_ids'].append(feedback['id'])
        approval['feedback_ids'] = [feedback['id']]
        self.assertEqual(self.check_rehashed_package(chain)[5]['state']['approval_requirements'][0]['status'],
                         'rejected')
        for field, value in [('authentication', 'unverified'), ('outcome', 'approved'),
                             ('outcome', 'conditional'), ('outcome', 'unresolved'),
                             ('claimed_request_id', 'wrong-request'), ('responder_role', 'Legal')]:
            bad = deepcopy(chain)
            bad[5]['state']['feedback'][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ContractError):
                self.check_rehashed_package(bad)
        bad = deepcopy(chain)
        bad[5]['state']['proposed_actions'][0]['approval_status'] = 'not-required'
        with self.assertRaises(ContractError):
            self.check_rehashed_package(bad)

    def test_g1_discovery_must_finish_before_scope_freezes(self):
        for timestamp, accepted in [('2026-10-07T15:02:00Z', False),
                                    ('2026-10-07T15:01:00Z', True),
                                    ('2026-10-07T17:00:00+02:00', True)]:
            chain = deepcopy(CHAIN)
            chain[0]['state']['scope_basis'][0]['retrieved_at'] = timestamp
            chain[1]['state']['attempts'][0]['retrieved_at'] = timestamp
            chain[1]['state']['sources'][0]['retrieved_at'] = timestamp
            with self.subTest(timestamp=timestamp):
                if accepted:
                    self.assertEqual(len(self.check_rehashed_package(chain)), 7)
                else:
                    with self.assertRaisesRegex(ContractError, 'scope discovery finishes after scope creation'):
                        self.check_rehashed_package(chain)

    def test_retained_feedback_does_not_reapply_older_history(self):
        s=deepcopy(CHAIN[5]);feedback=self.current_feedback(s)
        s['state']['feedback']=[feedback];s['produced_record_ids'].append(feedback['id'])
        s['state']['approval_requirements'][0].update(status='approved',feedback_ids=[feedback['id']])
        s['state']['proposed_actions'][0]['approval_status']='approved'
        archive=self.root/feedback['reviewed_draft']['root']
        old6=parse_json((archive/SNAPSHOT_PATHS[5]).read_bytes())
        request=old6['state']['review_requests'][0]
        historical=deepcopy(feedback)
        historical.update(id=new_record_id(old6['run_id'],6,'feedback'),request_id=request['request_id'],
                          subject_ids=request['subject_ids'][:],evidence_ids=request['evidence_ids'][:],
                          claimed_run_id='run-older-unavailable')
        historical['reviewed_draft']['root']='history/run-older-unavailable'
        old6['state']['feedback']=[historical];old6['produced_record_ids'].append(historical['id'])
        # The older feedback is retained context, not authority for the new
        # approval. Its local graph must still be valid; its archive is not read.
        self.assertFalse((archive/'history/run-older-unavailable').exists())
        (archive/SNAPSHOT_PATHS[5]).write_bytes(json_bytes(old6))
        old7=parse_json((archive/SNAPSHOT_PATHS[6]).read_bytes())
        old7['predecessor']['sha256']=sha256_bytes(json_bytes(old6))
        (archive/SNAPSHOT_PATHS[6]).write_bytes(json_bytes(old7))
        for seq in (6,7):
            feedback['reviewed_draft'][f'stage{seq:02d}']['sha256']=sha256_bytes((archive/SNAPSHOT_PATHS[seq-1]).read_bytes())
        feedback['revalidation']['reviewed_stage07_sha256']=feedback['reviewed_draft']['stage07']['sha256']
        self.assertEqual(self.check_current_package(s)[5]['state']['proposed_actions'][0]['approval_status'],'approved')

    def test_retained_review_rejects_broken_stage06_and_stage07_graphs(self):
        s=deepcopy(CHAIN[5]);feedback=self.current_feedback(s)
        s['state']['feedback']=[feedback];s['produced_record_ids'].append(feedback['id'])
        s['state']['approval_requirements'][0].update(status='approved',feedback_ids=[feedback['id']])
        s['state']['proposed_actions'][0]['approval_status']='approved'
        archive=self.root/feedback['reviewed_draft']['root']
        originals=[parse_json((archive/path).read_bytes()) for path in SNAPSHOT_PATHS]
        mutations=[
            (5,lambda x:x['state']['review_requests'][0].__setitem__('evidence_ids',[x['state']['proposed_actions'][0]['id']])),
            (5,lambda x:x['state']['review_requests'][0].__setitem__('subject_ids',['missing'])),
            (5,lambda x:x['consumed_record_ids'].remove(x['state']['review_requests'][0]['evidence_ids'][0])),
            (5,lambda x:x['state']['approval_requirements'][0].__setitem__('subject_ids',[x['state']['approval_requirements'][0]['id']])),
            (5,lambda x:(x['state']['approval_requirements'][0].__setitem__('subject_ids',[x['state']['review_requests'][0]['id']]),
                         x['state']['review_requests'][0].__setitem__('subject_ids',[x['state']['approval_requirements'][0]['id']]))),
            (6,lambda x:x['state']['validation_checks'][0].__setitem__('subject_ids',['missing']))]
        for seq,mutate in mutations:
            with self.subTest(stage=seq+1,mutation=mutate):
                chain=deepcopy(originals);mutate(chain[seq])
                for i in (5,6):
                    if i==6:chain[i]['predecessor']['sha256']=sha256_bytes((archive/SNAPSHOT_PATHS[5]).read_bytes())
                    (archive/SNAPSHOT_PATHS[i]).write_bytes(json_bytes(chain[i]))
                    feedback['reviewed_draft'][f'stage{i+1:02d}']['sha256']=sha256_bytes(json_bytes(chain[i]))
                feedback['revalidation']['reviewed_stage07_sha256']=feedback['reviewed_draft']['stage07']['sha256']
                with self.assertRaises(ContractError):validate_snapshot(s,root=self.root,upstream=CHAIN[:5])
                with self.assertRaises(ContractError):self.check_current_package(s)
        for i in (5,6):
            (archive/SNAPSHOT_PATHS[i]).write_bytes(json_bytes(originals[i]))
            feedback['reviewed_draft'][f'stage{i+1:02d}']['sha256']=sha256_bytes(json_bytes(originals[i]))
        feedback['revalidation']['reviewed_stage07_sha256']=feedback['reviewed_draft']['stage07']['sha256']
        validate_snapshot(s,root=self.root,upstream=CHAIN[:5])

    def test_approval_requirements_cannot_contradict_or_duplicate(self):
        s=deepcopy(CHAIN[5]);feedback=self.current_feedback(s)
        s['state']['feedback']=[feedback];s['produced_record_ids'].append(feedback['id'])
        approval=s['state']['approval_requirements'][0]
        approval.update(status='approved',feedback_ids=[feedback['id']])
        s['state']['proposed_actions'][0]['approval_status']='approved'
        validate_snapshot(s,root=self.root,upstream=CHAIN[:5])
        for status in ('approved','pending','rejected','not-required'):
            bad=deepcopy(s);other=deepcopy(approval)
            other.update(id=new_record_id(s['run_id'],6,'approval'),status=status)
            bad['state']['approval_requirements'].append(other);bad['produced_record_ids'].append(other['id'])
            with self.subTest(status=status),self.assertRaises(ContractError):
                validate_snapshot(bad,root=self.root,upstream=CHAIN[:5])
            with self.assertRaises(ContractError):self.check_current_package(bad)
        # A distinct required role remains a separate decision, but an approved
        # action cannot hide its pending/rejected requirement.
        for status in ('pending','rejected','not-required'):
            bad=deepcopy(s);other=deepcopy(approval)
            other.update(id=new_record_id(s['run_id'],6,'approval'),required_reviewer='Legal',
                         request_id=None,status=status,feedback_ids=[])
            bad['state']['approval_requirements'].append(other);bad['produced_record_ids'].append(other['id'])
            if status=='not-required':validate_snapshot(bad,root=self.root,upstream=CHAIN[:5])
            else:
                with self.assertRaises(ContractError):validate_snapshot(bad,root=self.root,upstream=CHAIN[:5])
                bad['state']['proposed_actions'][0]['approval_status']='pending'
                if status == 'rejected':
                    # Pending action does not legitimize an invented reviewer rejection.
                    with self.assertRaisesRegex(ContractError, 'rejection lacks authenticated matching feedback'):
                        validate_snapshot(bad,root=self.root,upstream=CHAIN[:5])
                else:
                    validate_snapshot(bad,root=self.root,upstream=CHAIN[:5])

    def test_upstream_boolean_number_substitution_rejected(self):
        for value in (0,0.0):
            upstream=deepcopy(CHAIN[:4]);upstream[3]['state']['system_facts'][0]['value']=value
            with self.assertRaisesRegex(ContractError,'upstream object differs'):
                validate_snapshot(deepcopy(CHAIN[4]),root=self.root,upstream=upstream)
        validate_snapshot(deepcopy(CHAIN[4]),root=self.root,upstream=deepcopy(CHAIN[:4]))

    def test_approved_outcome_cannot_bypass_explicit_conditions(self):
        s=deepcopy(CHAIN[5]);feedback=self.current_feedback(s)
        feedback['conditions']=['Verify the notice before this approval takes effect.']
        s['state']['feedback']=[feedback];s['produced_record_ids'].append(feedback['id'])
        approval=s['state']['approval_requirements'][0];approval.update(status='approved',feedback_ids=[feedback['id']])
        s['state']['proposed_actions'][0]['approval_status']='approved'
        with self.assertRaises(ContractError):validate_snapshot(s,root=self.root,upstream=CHAIN[:5])
        approval.update(conditions_satisfied=True,condition_evidence_ids=feedback['evidence_ids'])
        validate_snapshot(s,root=self.root,upstream=CHAIN[:5])
        for changes in ({'conditions_satisfied':False},{'condition_evidence_ids':[]}):
            bad=deepcopy(s);bad['state']['approval_requirements'][0].update(changes)
            with self.assertRaises(ContractError):validate_snapshot(bad,root=self.root,upstream=CHAIN[:5])

    def test_overflow_and_nonfinite_values_fail_closed(self):
        for raw in (b'{"value":1e999}',b'{"nested":[-1e999]}',b'{"nested":{"v":NaN}}'):
            with self.assertRaises(ContractError):parse_json(raw)
        for value in (float('inf'),float('-inf'),float('nan')):
            self.reject(4,lambda s,v=value:s['state']['system_facts'][0].__setitem__('value',{'nested':[v]}),'non-finite')
        self.assertEqual(parse_json(b'{"value":1e100}')['value'],1e100)
        path=self.root/SNAPSHOT_PATHS[3]
        path.write_bytes(path.read_bytes().replace(b'"value": false',b'"value": 1e999'))
        with self.assertRaisesRegex(ContractError,'non-finite'):read_chain(self.root,count=4)
        for i in range(4,7):
            snapshot=deepcopy(CHAIN[i])
            snapshot['predecessor']['sha256']=sha256_bytes((self.root/SNAPSHOT_PATHS[i-1]).read_bytes())
            (self.root/SNAPSHOT_PATHS[i]).write_bytes(json_bytes(snapshot))
        marker=parse_json((self.root/COMPLETION_MARKER).read_bytes())
        marker['stage07']['sha256']=sha256_bytes((self.root/SNAPSHOT_PATHS[6]).read_bytes())
        (self.root/COMPLETION_MARKER).write_bytes(json_bytes(marker))
        with self.assertRaisesRegex(ContractError,'non-finite'):accept_package(self.root)

    def current_feedback(self, snapshot):
        request=snapshot['state']['review_requests'][0]
        relative='history/run-u02-reviewed';archive=self.root/relative
        if not archive.exists():
            chain=self.copy_run(archive,'run-u02-reviewed')
            for prior in chain:
                prior['created_at']=prior['created_at'].replace('2026-10-07','2026-10-06')
            for record in chain[0]['state']['scope_basis']+chain[1]['state']['attempts']+chain[1]['state']['sources']:
                for field in ('retrieved_at','started_at'):
                    if field in record:record[field]=record[field].replace('2026-10-07','2026-10-06')
            old_request=chain[5]['state']['review_requests'][0]
            old_request['request_id']='request-reviewed-date'
            chain[5]['state']['approval_requirements'][0]['request_id']=old_request['request_id']
            chain[6]['state']['review_bindings'][0]['request_id']=old_request['request_id']
            for i,prior in enumerate(chain):
                if i:prior['predecessor']['sha256']=sha256_bytes((archive/SNAPSHOT_PATHS[i-1]).read_bytes())
                (archive/SNAPSHOT_PATHS[i]).write_bytes(json_bytes(prior))
            marker=parse_json((archive/COMPLETION_MARKER).read_bytes())
            marker['completed_at']=marker['completed_at'].replace('2026-10-07','2026-10-06')
            marker['stage07']['sha256']=sha256_bytes((archive/SNAPSHOT_PATHS[6]).read_bytes())
            (archive/COMPLETION_MARKER).write_bytes(json_bytes(marker))
        chain=accept_package(archive)
        old_request=chain[5]['state']['review_requests'][0]
        reference={'root':relative,**{f'stage{seq:02d}':{'snapshot_id':chain[seq-1]['snapshot_id'],
                    'path':SNAPSHOT_PATHS[seq-1],'sha256':sha256_bytes((archive/SNAPSHOT_PATHS[seq-1]).read_bytes())} for seq in (6,7)}}
        evidence=request['evidence_ids']
        report={'current_run_id':snapshot['run_id'],'current_request_id':request['request_id'],
                'current_draft_version':request['draft_version'],'current_source_versions':request['source_versions'][:],
                'reviewed_stage07_sha256':reference['stage07']['sha256'],
                'upstream':[{'snapshot_id':s['snapshot_id'],'path':SNAPSHOT_PATHS[i],
                            'sha256':sha256_bytes((self.root/SNAPSHOT_PATHS[i]).read_bytes())} for i,s in enumerate(CHAIN[:5])],
                'subject_bindings':[{'reviewed_id':old_request['subject_ids'][0],'current_id':request['subject_ids'][0]}],
                'checks':{k:{'result':'passed','evidence_ids':evidence[:],
                             'reason':f'Synthetic {k} revalidation report; actual authority checking remains U13.'}
                          for k in ('facts','source_versions','scope','conditions')}}
        return {'id':new_record_id(snapshot['run_id'],6,'feedback'),'record_type':'feedback',
                'summary':'Synthetic prior reviewed response, separately revalidated for the current draft.',
                'evidence_ids':evidence[:],'responder_identity':'synthetic-reviewer','responder_role':request['required_reviewer'],
                'claimed_subject_ids':old_request['subject_ids'][:],'claimed_request_id':old_request['request_id'],
                'claimed_run_id':old_request['run_id'],'claimed_draft_version':old_request['draft_version'],
                'claimed_source_versions':old_request['source_versions'][:],
                'claimed_artifacts':deepcopy(chain[6]['state']['review_bindings'][0]['artifacts']),
                'subject_ids':request['subject_ids'][:],'request_id':request['request_id'],
                'match_status':'matched','reviewer_response_at':'2026-10-07T15:06:00Z',
                'outcome':'approved','reasons':['Revalidated synthetic current action may proceed.'],'conditions':[],
                'authentication':'verified','authentication_basis':'Synthetic trusted-channel test evidence',
                'reviewed_draft':reference,'revalidation':report}

    def test_retained_review_binding_and_revalidation(self):
        s=deepcopy(CHAIN[5]);feedback=self.current_feedback(s)
        s['state']['feedback']=[feedback];s['produced_record_ids'].append(feedback['id'])
        s['state']['approval_requirements'][0].update(status='approved',feedback_ids=[feedback['id']])
        s['state']['proposed_actions'][0]['approval_status']='approved'
        validate_snapshot(s,root=self.root,upstream=CHAIN[:5])
        original_claims={k:deepcopy(v) for k,v in feedback.items() if k.startswith('claimed_')}
        for mutate in [lambda r:r.pop('reviewed_draft'),lambda r:r.pop('revalidation'),
                       lambda r:r.__setitem__('claimed_artifacts',[]),
                       lambda r:r['reviewed_draft'].__setitem__('root','../outside'),
                       lambda r:r['reviewed_draft']['stage06'].__setitem__('sha256',sha256_bytes(b'wrong')),
                       lambda r:r['reviewed_draft']['stage07'].__setitem__('snapshot_id','wrong'),
                       lambda r:r['revalidation'].__setitem__('current_run_id','wrong'),
                       lambda r:r['revalidation'].__setitem__('current_draft_version','wrong'),
                       lambda r:r['revalidation'].__setitem__('current_source_versions',['wrong']),
                       lambda r:r['revalidation']['upstream'][3].__setitem__('sha256',sha256_bytes(b'wrong')),
                       lambda r:r['revalidation']['subject_bindings'][0].__setitem__('reviewed_id','wrong'),
                       lambda r:r['revalidation']['checks']['facts'].__setitem__('evidence_ids',[]),
                       lambda r:r['revalidation']['checks']['scope'].__setitem__('evidence_ids',['missing']),
                       lambda r:r['revalidation']['checks']['conditions'].__setitem__('result','unresolved')]:
            bad=deepcopy(s);mutate(bad['state']['feedback'][0])
            with self.assertRaises(ContractError):validate_snapshot(bad,root=self.root,upstream=CHAIN[:5])
        for name in ('facts','source_versions','scope','conditions'):
            bad=deepcopy(s);bad['state']['feedback'][0]['revalidation']['checks'][name]['result']='failed'
            with self.assertRaises(ContractError):validate_snapshot(bad,root=self.root,upstream=CHAIN[:5])
        bad=deepcopy(s);action=bad['state']['proposed_actions'][0]
        action['action_kind']='activate-policy';action['identity_key']['kind']=action['action_kind']
        action['action_id']=stable_business_id('action',BusinessKey(**action['identity_key']))
        with self.assertRaisesRegex(ContractError,'semantic subject'):validate_snapshot(bad,root=self.root,upstream=CHAIN[:5])
        archive=self.root/feedback['reviewed_draft']['root']
        retained=archive/'compliance-brief.md';raw=retained.read_bytes();retained.write_bytes(raw+b'tampered')
        with self.assertRaisesRegex(ContractError,'hash mismatch'):validate_snapshot(s,root=self.root,upstream=CHAIN[:5])
        retained.write_bytes(raw)
        (archive/INCOMPLETE_MARKER).write_bytes(b'interrupted')
        with self.assertRaisesRegex(ContractError,'incomplete reviewed'):validate_snapshot(s,root=self.root,upstream=CHAIN[:5])
        (archive/INCOMPLETE_MARKER).unlink()
        self.assertEqual({k:v for k,v in feedback.items() if k.startswith('claimed_')},original_claims)
        # Publication does not change the prior reviewed artifact claims. Current
        # Stage07 binds the new request to the new draft independently.
        (self.root/SNAPSHOT_PATHS[5]).write_bytes(json_bytes(s))
        final=deepcopy(CHAIN[6]);final['predecessor']['sha256']=sha256_bytes(json_bytes(s))
        (self.root/SNAPSHOT_PATHS[6]).write_bytes(json_bytes(final))
        marker=parse_json((self.root/COMPLETION_MARKER).read_bytes());marker['stage07']['sha256']=sha256_bytes(json_bytes(final))
        (self.root/COMPLETION_MARKER).write_bytes(json_bytes(marker))
        self.assertEqual(accept_package(self.root)[5]['state']['feedback'][0]['claimed_artifacts'],original_claims['claimed_artifacts'])

    def test_approval_requires_exact_request_subject_role_and_versions(self):
        s=deepcopy(CHAIN[5]);feedback=self.current_feedback(s)
        s['state']['feedback']=[feedback];s['produced_record_ids'].append(feedback['id'])
        approval=s['state']['approval_requirements'][0]
        approval.update(status='approved',feedback_ids=[feedback['id']])
        validate_snapshot(s,root=self.root,upstream=CHAIN[:5])
        changes=[('claimed_request_id','old-request'),('request_id','missing-request'),
                 ('claimed_run_id','old-run'),('claimed_draft_version','old-draft'),
                 ('claimed_source_versions',['old-source']),('claimed_subject_ids',['old-subject']),
                 ('subject_ids',[CHAIN[4]['state']['impacts'][0]['id']]),('responder_role','Legal'),
                 ('claimed_artifacts',[{'path':'compliance-brief.md','sha256':sha256_bytes(b'old')}])]
        for field,value in changes:
            with self.subTest(field=field):
                bad=deepcopy(s);bad['state']['feedback'][0][field]=value
                with self.assertRaises(ContractError):validate_snapshot(bad,root=self.root,upstream=CHAIN[:5])
        for field,value in [('required_reviewer','Legal'),('request_id','missing-request'),
                            ('subject_ids',[CHAIN[4]['state']['impacts'][0]['id']])]:
            bad=deepcopy(s);bad['state']['approval_requirements'][0][field]=value
            with self.assertRaises(ContractError):validate_snapshot(bad,root=self.root,upstream=CHAIN[:5])
        # A second valid request cannot authorize the first request's approval.
        bad=deepcopy(s);other=deepcopy(bad['state']['review_requests'][0])
        other.update(id=new_record_id(s['run_id'],6,'review-request'),request_id='request-other')
        bad['state']['review_requests'].append(other);bad['produced_record_ids'].append(other['id'])
        bad['state']['feedback'][0].update(request_id=other['request_id'],claimed_request_id=other['request_id'])
        with self.assertRaises(ContractError):validate_snapshot(bad,root=self.root,upstream=CHAIN[:5])

    def test_graph_preserves_system_and_authority_basis(self):
        def other_system(s, collection, namespace):
            r=s['state'][collection][0];r['system_id']='SYNTHETIC-SYS-02'
            r['identity_key']['system_id']=r['system_id']
            r[namespace+'_id']=stable_business_id(namespace,BusinessKey(**r['identity_key']))
        self.reject(5,lambda s:other_system(s,'impacts','impact'))
        self.reject(5,lambda s:s['state']['impacts'][0].__setitem__('basis_type','binding-legal'))
        self.reject(6,lambda s:other_system(s,'proposed_actions','action'))
        def invented_basis(s):
            r=s['state']['proposed_actions'][0];r['identity_key']['rule_basis']='invented-rule'
            r['action_id']=stable_business_id('action',BusinessKey(**r['identity_key']))
        self.reject(6,invented_basis)

    def test_multi_basis_action_binds_all_originating_impacts(self):
        upstream=deepcopy(CHAIN[:5]);rule=deepcopy(upstream[2]['state']['binding_rules'][0])
        rule.update(id=new_record_id(upstream[2]['run_id'],3,'rule'),basis_type='binding-legal',
                    source_versions=['synthetic-legal/1'],
                    summary='Synthetic second legal-typed basis tests graph consistency; no legal authority is asserted.')
        rule['version_key']={'basis_id':'synthetic-legal','meaning_key':'notice-before-interaction'}
        rule['rule_version_id']=rule_version_id(**rule['version_key'])
        upstream[2]['state']['binding_rules'].append(rule);upstream[2]['produced_record_ids'].append(rule['id'])
        impact=deepcopy(upstream[4]['state']['impacts'][0])
        impact.update(id=new_record_id(upstream[4]['run_id'],5,'impact'),rule_id=rule['id'],basis_type='binding-legal',
                      summary='Synthetic distinct second basis for the same system and absent-notice observation.')
        impact['identity_key']['rule_basis']=rule['rule_version_id']
        impact['impact_id']=stable_business_id('impact',BusinessKey(**impact['identity_key']))
        upstream[4]['state']['impacts'].append(impact);upstream[4]['produced_record_ids'].append(impact['id'])
        upstream[4]['consumed_record_ids'].append(rule['id'])
        for i,prior in enumerate(upstream):
            if i:prior['predecessor']['sha256']=sha256_bytes((self.root/SNAPSHOT_PATHS[i-1]).read_bytes())
            validate_snapshot(prior,root=self.root,upstream=upstream[:i])
            (self.root/SNAPSHOT_PATHS[i]).write_bytes(json_bytes(prior))
        s=deepcopy(CHAIN[5]);s['predecessor']['sha256']=sha256_bytes((self.root/SNAPSHOT_PATHS[4]).read_bytes())
        action=s['state']['proposed_actions'][0];action['impact_ids'].append(impact['id']);s['consumed_record_ids'].append(impact['id'])
        with self.assertRaisesRegex(ContractError,'originating rule bases'):validate_snapshot(s,root=self.root,upstream=upstream)
        action['identity_key']['rule_basis']=action_rule_basis([i['identity_key']['rule_basis'] for i in upstream[4]['state']['impacts']])
        action['action_id']=stable_business_id('action',BusinessKey(**action['identity_key']))
        validate_snapshot(s,root=self.root,upstream=upstream)
        action_id=action['action_id'];action['impact_ids'].reverse()
        validate_snapshot(s,root=self.root,upstream=upstream)
        self.assertEqual(action['action_id'],action_id)

    def test_downstream_values_and_required_record_fields(self):
        self.assertEqual(CHAIN[3]['state']['system_facts'][0]['value'],False)
        self.assertEqual(CHAIN[4]['state']['impacts'][0]['basis_type'],'internal-control')
        action=CHAIN[5]['state']['proposed_actions'][0]
        self.assertEqual(action['existing_due_date'],'2026-09-01');self.assertIsNone(action['proposed_due_date'])
        self.assertEqual(CHAIN[5]['state']['review_requests'][0]['required_reviewer'],'Operations')
        for sequence,snapshot in enumerate(CHAIN,1):
            for record in stage_records(snapshot):
                for field in ('id','summary','evidence_ids'):
                    bad=deepcopy(snapshot)
                    target=next(r for r in stage_records(bad) if r['id']==record['id']);target.pop(field)
                    with self.assertRaises(ContractError):validate_snapshot(bad,root=self.root,upstream=CHAIN[:sequence-1])
        for seq,collection,fields in [(3,'binding_rules',('obligation','predicates','rule_version_id')),
                                     (4,'system_facts',('system_id','predicate','value')),
                                     (5,'impacts',('rule_id','fact_ids','basis_type','reason','owner')),
                                     (6,'proposed_actions',('impact_ids','owner','date_basis','existing_due_date','proposed_due_date')),
                                     (6,'review_requests',('question','required_reviewer','draft_version','source_versions'))]:
            for field in fields:self.reject(seq,lambda s,c=collection,f=field:s['state'][c][0].pop(f))

    def test_capture_mime_cannot_bypass_text_support(self):
        self.reject(2,lambda s:(s['state']['captures'][0].__setitem__('content_type','application/octet-stream'),
                               s['state']['evidence'][0].__setitem__('quoted_support','Invented claim')))
        self.reject(2,lambda s:s['state']['captures'][0].__setitem__('content_type','image/png'))
        def differently_cased_text(s):
            for collection in ('attempts','sources','captures'):
                s['state'][collection][0]['content_type']='Text/Plain; charset=UTF-8'
            s['state']['evidence'][0]['quoted_support']='Invented claim'
        self.reject(2,differently_cased_text,'quotation absent')

    def test_derived_capture_retains_one_acquisition_and_packet_lineage(self):
        s=deepcopy(CHAIN[1]);attempt=deepcopy(s['state']['attempts'][0]);attempt.pop('scope_basis_id')
        # Valid one-pixel PNG; the synthetic derived text is a provenance test,
        # not an assertion that OCR recovered meaningful text from this image.
        image=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j3ioAAAAASUVORK5CYII=')
        (self.root/'sources/screenshot.png').write_bytes(image)
        attempt.update(id=new_record_id(s['run_id'],2,'attempt'),attempt_key='screenshot-acquisition',
                       source_id='REPORT',local_reference='sources/screenshot.png',content_hash=sha256_bytes(image),content_type='image/png',
                       original_locator='fixture://REPORT',effective_locator='fixture://REPORT',
                       summary='One synthetic image acquisition; derived text does not add a retrieval.')
        primary=deepcopy(s['state']['captures'][0]);primary.update(id=new_record_id(s['run_id'],2,'capture'),
                       attempt_id=attempt['id'],local_reference=attempt['local_reference'],content_hash=attempt['content_hash'],
                       content_type='image/png',representation_metadata={'method':'synthetic retained image fixture'},
                       summary='Synthetic original retained image capture.')
        text=b'Synthetic screenshot notice requires owner review.'
        (self.root/'sources/ocr.txt').write_bytes(text)
        derived=deepcopy(primary);derived.update(id=new_record_id(s['run_id'],2,'capture'),representation='extract',
                       local_reference='sources/ocr.txt',content_hash=sha256_bytes(text),content_type='text/plain',
                       derived_from_capture_id=primary['id'],derivation={'method':'synthetic OCR fixture; no OCR executed',
                       'processed_at':'2026-10-07T15:00:30Z'},representation_metadata={'encoding':'utf-8'},
                       summary='Synthetic separate derived-text capture linked to the original image.')
        source=deepcopy(s['state']['sources'][0]);source.update(id=new_record_id(s['run_id'],2,'source'),
                       source_id='REPORT',attempt_ids=[attempt['id']],local_reference=attempt['local_reference'],
                       content_hash=attempt['content_hash'],content_type='image/png',
                       summary='Synthetic REPORT declaration with one image acquisition.')
        evidence=deepcopy(s['state']['evidence'][0]);evidence.update(id=new_record_id(s['run_id'],2,'evidence'),
                       capture_id=derived['id'],local_reference=derived['local_reference'],content_hash=derived['content_hash'],
                       quoted_support=text.decode(),assertion='Synthetic notice needs review.',
                       summary='Synthetic derived-text quotation retains the original image lineage.')
        for collection,records in [('attempts',[attempt]),('captures',[primary,derived]),('sources',[source]),('evidence',[evidence])]:
            s['state'][collection].extend(records);s['produced_record_ids'].extend(r['id'] for r in records)
        validate_snapshot(s,root=self.root,upstream=CHAIN[:1])
        self.assertEqual(len(s['state']['attempts']),2)  # scope read + screenshot acquisition; OCR is not a retrieval
        for change in [lambda r:r.pop('derivation'),lambda r:r.__setitem__('attempt_id',CHAIN[1]['state']['attempts'][0]['id']),
                       lambda r:r.__setitem__('content_hash',sha256_bytes(b'invented')),
                       lambda r:r['derivation'].__setitem__('processed_at','2026-10-07T14:00:00Z'),
                       lambda r:r['derivation'].__setitem__('processed_at','not-a-timestamp'),
                       lambda r:r['derivation'].__setitem__('method',''),
                       lambda r:r.__setitem__('derived_from_capture_id','missing-capture')]:
            bad=deepcopy(s);change(bad['state']['captures'][-1])
            with self.assertRaises(ContractError):validate_snapshot(bad,root=self.root,upstream=CHAIN[:1])
        bad=deepcopy(s);bad['state']['captures'][1]['derivation']={'method':'invented primary derivation','processed_at':'2026-10-07T15:00:30Z'}
        with self.assertRaises(ContractError):validate_snapshot(bad,root=self.root,upstream=CHAIN[:1])
        bad=deepcopy(s);bad['state']['captures'].remove(bad['state']['captures'][1]);bad['produced_record_ids'].remove(primary['id'])
        with self.assertRaises(ContractError):validate_snapshot(bad,root=self.root,upstream=CHAIN[:1])
        bad=deepcopy(s);other=deepcopy(primary);other['id']=new_record_id(s['run_id'],2,'capture')
        bad['state']['captures'].append(other);bad['produced_record_ids'].append(other['id'])
        with self.assertRaisesRegex(ContractError,'exactly one primary'):validate_snapshot(bad,root=self.root,upstream=CHAIN[:1])
        (self.root/SNAPSHOT_PATHS[1]).write_bytes(json_bytes(s))
        request=parse_json((self.root/'analysis/request.json').read_bytes())
        response=parse_json((self.root/'analysis/response.json').read_bytes())
        request['upstream'][1]['sha256']=sha256_bytes(json_bytes(s))
        extract=request['extracts'][0];extract.update(evidence_id=evidence['id'],capture_id=derived['id'],
                path=derived['local_reference'],sha256=derived['content_hash'],text=text.decode(),text_sha256=sha256_bytes(text),locator=evidence['locator'])
        response['packet_sha256']=sha256_bytes(json_bytes(request))
        response['candidates'][0]['citations']=[{'evidence_id':evidence['id'],'quote':text.decode()}]
        self.assertEqual(validate_interpretation(json_bytes(request),json_bytes(response),root=self.root,
                         run_id=s['run_id'],stage=STAGES[2],upstream=[CHAIN[0],s]).disposition,'proposed')

    def test_intraday_timezone_must_be_known_and_precision_explicit(self):
        s=deepcopy(CHAIN[2]);rule=s['state']['binding_rules'][0]
        timing={'id':new_record_id(s['run_id'],3,'timing-rule'),'record_type':'timing-rule',
                'summary':'Synthetic explicit intraday boundary.', 'evidence_ids':rule['evidence_ids'],
                'rule_id':rule['id'],'timing_basis':'Synthetic source boundary',
                'precision':'instant','boundary_timezone':'UTC','applicability':'established'}
        s['state']['timing_rules']=[timing];s['produced_record_ids'].append(timing['id'])
        for timezone in ['UTC','+02:30','America/New_York']:
            timing['boundary_timezone']=timezone;validate_snapshot(s,root=self.root,upstream=CHAIN[:2])
        for timezone in [None,'unknown','Mars/Base','+24:00','-00:00']:
            timing['boundary_timezone']=timezone
            with self.assertRaises(ContractError):validate_snapshot(s,root=self.root,upstream=CHAIN[:2])
            timing['applicability']='unresolved';validate_snapshot(s,root=self.root,upstream=CHAIN[:2])
            timing['applicability']='established'
        timing.update(precision='unknown',boundary_timezone='UTC')
        with self.assertRaises(ContractError):validate_snapshot(s,root=self.root,upstream=CHAIN[:2])
        timing.update(precision='date',boundary_timezone=None);validate_snapshot(s,root=self.root,upstream=CHAIN[:2])

    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'package';shutil.copytree(FIXTURE,self.root)

    def reject(self, seq, mutate, pattern=None):
        s=deepcopy(CHAIN[seq-1]);mutate(s)
        with self.assertRaises((ContractError,IdentityConflict)) as caught:
            validate_snapshot(s,root=self.root,upstream=CHAIN[:seq-1])
        if pattern:self.assertIn(pattern,str(caught.exception))

    def test_seven_schema_and_graph_valid_snapshots(self):
        self.assertEqual(read_chain(self.root),CHAIN)
        public=json.loads((ROOT/'snapshot.schema.json').read_bytes())
        validator=Draft202012Validator(public,format_checker=FormatChecker())
        for snapshot in CHAIN:
            self.assertEqual(list(validator.iter_errors(snapshot)),[])
            validate_schema(snapshot)
        internal=json.loads((ROOT/'regulatory-change-impact-brief/references/schemas/contracts.schema.json').read_bytes())
        Draft202012Validator.check_schema(internal)
        self.assertEqual(sha256_bytes((ROOT/'snapshot.schema.json').read_bytes()),PUBLIC_SCHEMA_HASH)

    def test_all_seven_minimal_allowed_snapshots(self):
        root=Path(self.temp.name)/'minimal';shutil.copytree(self.root/'sources',root/'sources')
        chain=[];pred=None
        for seq,original in enumerate(CHAIN,1):
            s=deepcopy(original);s['predecessor']=pred
            for collection in list(s['state']):
                if collection in ('binding_rules','timing_rules','guidance_context','authority_blockers',
                                  'system_facts','policy_controls','incident_evidence','conflicts','evidence_gaps',
                                  'impacts','unaffected_items','unresolved_items','proposed_actions',
                                  'approval_requirements','escalations','review_requests','feedback','artifacts',
                                  'validation_checks','review_bindings','evidence'):
                    s['state'][collection]=[]
            s['produced_record_ids']=[r['id'] for r in stage_records(s)]
            if seq>1:s['consumed_record_ids']=[CHAIN[0]['produced_record_ids'][0]]
            if seq==7:s['status']='blocked';s['state']['publication_status']='blocked'
            pred=write_snapshot(root,s,upstream=chain);chain.append(s)
        self.assertEqual(read_chain(root),chain)

    def test_permitted_empty_collections_and_required_nonempty(self):
        s=deepcopy(CHAIN[2]);s['state']['binding_rules']=[];s['produced_record_ids']=[]
        validate_snapshot(s,root=self.root,upstream=CHAIN[:2])
        for field in ['systems_in_scope','audiences','approval_gates','scope_basis']:
            self.reject(1,lambda s,f=field:s['state'].__setitem__(f,[]))
        self.reject(2,lambda s:s['state'].__setitem__('sources',[]))

    def test_enum_and_date_format_rejections(self):
        for seq,mutate in [(1,lambda s:s.__setitem__('status','approved')),
                           (2,lambda s:s['state']['attempts'][0].__setitem__('retrieval_status','complete')),
                           (5,lambda s:s['state']['impacts'][0].__setitem__('state','complete')),
                           (6,lambda s:s['state']['approval_requirements'][0].__setitem__('status','closed')),
                           (7,lambda s:s['state'].__setitem__('publication_status','complete')),
                           (1,lambda s:s.__setitem__('created_at','2026-10-07')),
                           (1,lambda s:s.__setitem__('created_at','2026-13-07T00:00:00Z')),
                           (4,lambda s:s['state']['system_facts'][0].__setitem__('observed_at','2026-08-26T09:00:00')),
                           (6,lambda s:s['state']['proposed_actions'][0].__setitem__('proposed_due_date','2026-02-30'))]:
            with self.subTest(seq=seq,mutate=mutate):self.reject(seq,mutate)
        for field in ('retrieved_at','source_revision_at','effective_from'):
            seq,collection=(2,'attempts') if field=='retrieved_at' else (4,'system_facts')
            self.reject(seq,lambda s,f=field,c=collection:s['state'][c][0].__setitem__(f,'not-a-date'))

    def test_stage_sequence_and_predecessors(self):
        self.reject(2,lambda s:s.__setitem__('sequence',3))
        for field,value in [('snapshot_id','unknown'),('path',SNAPSHOT_PATHS[2]),('sha256','sha256:'+'0'*64)]:
            self.reject(2,lambda s,f=field,v=value:s['predecessor'].__setitem__(f,v),'predecessor')
        self.reject(1,lambda s:s.__setitem__('predecessor',CHAIN[1]['predecessor']))
        self.reject(2,lambda s:s.__setitem__('run_id','other-run'),'cross-run')
        self.reject(2,lambda s:s.__setitem__('snapshot_id',CHAIN[0]['snapshot_id']),'duplicate snapshot')

    def test_dangling_current_stage_wrong_type_and_run_links(self):
        self.reject(2,lambda s:s['consumed_record_ids'].append('dangling'),'consumed')
        self.reject(2,lambda s:s['consumed_record_ids'].append(s['state']['evidence'][0]['id']),'consumed')
        self.reject(3,lambda s:s['state']['binding_rules'][0].__setitem__('evidence_ids',[CHAIN[0]['produced_record_ids'][0]]),'link type')
        self.reject(3,lambda s:s.__setitem__('consumed_record_ids',[CHAIN[1]['state']['sources'][0]['id']]),'missing from consumption')
        self.reject(2,lambda s:s['state']['evidence'][0].__setitem__('capture_id','dangling'),'dangling')
        self.reject(2,lambda s:s['state']['captures'][0].__setitem__('attempt_id',s['state']['evidence'][0]['id']),'link type')

    def test_produced_and_business_identity_collisions(self):
        self.reject(4,lambda s:s['state']['system_facts'].append(deepcopy(s['state']['system_facts'][0])),'duplicate produced')
        self.reject(4,lambda s:s.__setitem__('produced_record_ids',[]),'enumerate')
        def duplicate_impact(s):
            r=deepcopy(s['state']['impacts'][0]);r['id']=new_record_id(s['run_id'],5,'impact')
            s['state']['impacts'].append(r);s['produced_record_ids'].append(r['id'])
        self.reject(5,duplicate_impact,'colliding business')
        self.reject(5,lambda s:s['state']['impacts'][0]['identity_key'].__setitem__('rule_basis','other'),'identity mismatch')
        self.reject(3,lambda s:s['state']['binding_rules'][0]['version_key'].__setitem__('meaning_key','changed'),'meaning/version')

    def test_no_fabricated_or_null_content_hashes(self):
        self.reject(2,lambda s:(s['state']['attempts'][0].__setitem__('content_hash','sha256:'+'0'*64),s['state']['sources'][0].__setitem__('content_hash','sha256:'+'0'*64)),'hash mismatch')
        self.reject(2,lambda s:s['state']['attempts'][0].__setitem__('content',None),'null mismatch')
        self.reject(2,lambda s:s['state']['attempts'][0].__setitem__('local_reference',None),'null mismatch')
        self.reject(2,lambda s:s['state']['evidence'][0].__setitem__('local_reference','sources/absent.txt'),'missing retained')
        self.reject(2,lambda s:s['state']['attempts'][0].__setitem__('content_type_known',False),'unknown MIME')

    def test_zero_bytes_vs_no_obtained_content(self):
        s=deepcopy(CHAIN[1]);a=s['state']['attempts'][0];c=s['state']['captures'][0];source=s['state']['sources'][0]
        s['state']['evidence']=[];s['produced_record_ids'].remove(CHAIN[1]['state']['evidence'][0]['id'])
        # A separate new attempt keeps the discovery import unchanged.
        extra=deepcopy(a);extra['id']=new_record_id(s['run_id'],2,'attempt');extra['attempt_key']='zero-byte'
        extra.pop('scope_basis_id');extra['local_reference']='sources/empty.txt';extra['content_hash']=sha256_bytes(b'')
        (self.root/'sources/empty.txt').write_bytes(b'')
        cap=deepcopy(c);cap['id']=new_record_id(s['run_id'],2,'capture');cap['attempt_id']=extra['id']
        cap['local_reference']=extra['local_reference'];cap['content_hash']=extra['content_hash']
        s['state']['attempts'].append(extra);s['state']['captures'].append(cap)
        source['attempt_ids'].append(extra['id']);s['produced_record_ids'] += [extra['id'],cap['id']]
        validate_snapshot(s,root=self.root,upstream=CHAIN[:1])
        extra.update(content=None,content_hash=None,local_reference=None,retrieval_status='unavailable',recoverable_failure='No response')
        s['state']['captures'].remove(cap);s['produced_record_ids'].remove(cap['id'])
        validate_snapshot(s,root=self.root,upstream=CHAIN[:1])

    def test_scope_import_preserves_original_attempt(self):
        self.assertLess(CHAIN[1]['state']['attempts'][0]['retrieved_at'],CHAIN[0]['created_at'])
        for field,value in [('retrieved_at','2026-10-07T15:02:00Z'),('attempt_key','new-fake-attempt'),('scope_basis_id','unknown')]:
            self.reject(2,lambda s,f=field,v=value:s['state']['attempts'][0].__setitem__(f,v))
        self.reject(1,lambda s:s['state']['scope_basis'][0].__setitem__('evidence_ids',[CHAIN[1]['state']['evidence'][0]['id']]),'dangling')
        self.reject(1,lambda s:s['state']['scope_basis'][0].__setitem__('system_ids',['TBD']))
        def repeat(s):
            a=deepcopy(s['state']['attempts'][0]);a['id']=new_record_id(s['run_id'],2,'attempt')
            s['state']['attempts'].append(a);s['produced_record_ids'].append(a['id'])
        self.reject(2,repeat,'duplicate imported')

    def test_date_precision_and_newer_values(self):
        s=deepcopy(CHAIN[3]);r=s['state']['system_facts'][0]
        r.update(retrieved_at='2027-01-01T08:00:00-05:00',source_revision_at='2026-12-31T13:00:00Z',
                 observed_on='2026-08-26',observation_precision='date',source_revision_date='2026-12-31',
                 effective_from='2026-08-01',effective_until='2027-08-01')
        validate_snapshot(s,root=self.root,upstream=CHAIN[:3])
        for status in ('complete','partial','blocked'):
            s=deepcopy(CHAIN[0]);s['status']=status;validate_snapshot(s,root=self.root,upstream=[])
            self.assertEqual(s['state']['assigned_review_date'],'2026-08-26')
        self.reject(1,lambda s:s['state'].__setitem__('assigned_review_date','2026-10-07'))
        self.reject(1,lambda s:s['state'].__setitem__('as_of_precision','instant'))
        self.reject(1,lambda s:s['state'].__setitem__('as_of','2026-08-26T00:00:00-04:00'))

    def test_useful_fields_and_uncertainty(self):
        self.reject(4,lambda s:s['state']['system_facts'][0].pop('value'))
        self.reject(4,lambda s:s['state']['system_facts'][0].__setitem__('summary','   '))
        self.reject(4,lambda s:s['state']['system_facts'][0].__setitem__('summary','TBD'))
        self.reject(4,lambda s:s['state']['system_facts'][0].__setitem__('evidence_ids',[]),'lacks claim evidence')
        self.reject(5,lambda s:s['state']['impacts'][0].__setitem__('fact_ids',[]),'affirmative')
        def unresolved(s):
            r=s['state']['impacts'].pop();r.update(state='unresolved',evidence_ids=[],resolution_need='Owner must provide historical notice evidence.')
            s['state']['unresolved_items']=[r]
        s=deepcopy(CHAIN[4]);unresolved(s);validate_snapshot(s,root=self.root,upstream=CHAIN[:4])
        self.reject(5,lambda s:(unresolved(s),s['state']['unresolved_items'][0].__setitem__('evidence_ids',CHAIN[4]['state']['impacts'][0]['evidence_ids']),s['state']['unresolved_items'][0].__setitem__('resolution_need',None)),'resolution need')
        s=deepcopy(CHAIN[4]);s['state']['impacts'][0]['state']='supported-no-impact'
        s['state']['unaffected_items']=s['state']['impacts'];s['state']['impacts']=[]
        validate_snapshot(s,root=self.root,upstream=CHAIN[:4])

    def test_exact_byte_two_stage_write_reread_and_mutation(self):
        root=Path(self.temp.name)/'new';shutil.copytree(self.root/'sources',root/'sources')
        first,second=deepcopy(CHAIN[:2]);binding=write_snapshot(root,first,upstream=[])
        self.assertEqual(binding['sha256'],'sha256:'+hashlib.sha256((root/SNAPSHOT_PATHS[0]).read_bytes()).hexdigest())
        second['predecessor']=binding;write_snapshot(root,second,upstream=[first])
        self.assertEqual(read_chain(root,count=2),[first,second])
        with self.assertRaises(FileExistsError):write_snapshot(root,first,upstream=[])
        prior=root/SNAPSHOT_PATHS[0];prior.write_bytes(prior.read_bytes()+b' ')
        with self.assertRaisesRegex(ContractError,'predecessor'):read_chain(root,count=2)

    def test_path_traversal_symlink_and_archive_resolution(self):
        for path in ['../sources/systems.txt','/etc/passwd','sources/../systems.txt','sources\\systems.txt','https://invalid','sources//systems.txt']:
            with self.assertRaises(ContractError):package_path(self.root,path)
        (self.root/'sources/escape').symlink_to(Path(self.temp.name))
        with self.assertRaises(ContractError):package_path(self.root,'sources/escape/outside')
        archive=Path(self.temp.name)/'archive';shutil.copytree(FIXTURE,archive)
        (self.root/'sources/systems.txt').write_bytes(b'changed current')
        self.assertEqual(read_chain(archive),CHAIN)
        with self.assertRaises(ContractError):read_chain(self.root)

    def test_incomplete_marker_wins_over_completion(self):
        self.assertEqual(accept_package(self.root),CHAIN)
        (self.root/INCOMPLETE_MARKER).write_bytes(b'interrupted marker write')
        with self.assertRaisesRegex(ContractError,'incomplete'):accept_package(self.root)
        with self.assertRaisesRegex(ContractError,'incomplete'):read_chain(self.root)

    def test_marker_contracts_and_final_identity(self):
        marker={'schema_version':'rci-incomplete-replacement/1','old_run_id':'run-old','new_run_id':'run-new',
                'created_at':'2026-10-07T15:00:00Z','archive':{'root':'history/run-old','inventory_sha256':sha256_bytes(b'inventory'),'verified':True},
                'candidate':{'root':'.staging/run-new','stage07_sha256':CHAIN[6]['predecessor']['sha256'],'verified':True}}
        validate_marker(marker,'incomplete-marker',self.root)
        for mutate in [lambda m:m.__setitem__('archive',None),lambda m:m['candidate'].__setitem__('verified',False),
                       lambda m:m['archive'].__setitem__('root','history/wrong'),lambda m:m.__setitem__('new_run_id','run-old')]:
            bad=deepcopy(marker);mutate(bad)
            with self.assertRaises(ContractError):validate_marker(bad,'incomplete-marker',self.root)
        marker['old_run_id']=None;marker['archive']=None;validate_marker(marker,'incomplete-marker',self.root)
        completion=parse_json((self.root/COMPLETION_MARKER).read_bytes());completion['run_id']='other-run'
        (self.root/COMPLETION_MARKER).write_bytes(json_bytes(completion))
        with self.assertRaisesRegex(ContractError,'identity'):accept_package(self.root)

    def test_publication_and_detached_bindings(self):
        self.reject(7,lambda s:s['state'].__setitem__('artifacts',[]))
        self.reject(7,lambda s:s['state'].__setitem__('review_bindings',[]),'unbound')
        self.reject(7,lambda s:s['state']['review_bindings'][0].__setitem__('draft_version','other'),'version')
        self.reject(7,lambda s:s['state']['review_bindings'][0]['artifacts'][0].__setitem__('sha256','sha256:'+'0'*64),'hash mismatch')
        self.reject(7,lambda s:s['state']['artifacts'][0].__setitem__('validation_status','not-produced'))
        self.reject(6,lambda s:s['state']['review_requests'][0].__setitem__('delivery_status','sent'),'delivery evidence')
        (self.root/'impact-register.csv').write_bytes(b'tampered')
        with self.assertRaisesRegex(ContractError,'hash mismatch'):accept_package(self.root)

    def test_failed_missing_artifact_has_no_fabricated_hash(self):
        s=deepcopy(CHAIN[6]);missing=s['state']['artifacts'].pop(0);s['produced_record_ids'].remove(missing['id'])
        (self.root/missing['path']).unlink();s['state']['publication_status']='failed';s['status']='failed'
        s['state']['missing_artifacts']=[{'path':missing['path'],'reason':'Synthetic write failure'}]
        s['state']['review_bindings']=[];check=s['state']['validation_checks'][0]
        check.update(result='failed',observed='Only two files were retained.',subject_ids=[])
        validate_snapshot(s,root=self.root,upstream=CHAIN[:6])

    def test_unmatched_feedback_retained_without_approval(self):
        s=deepcopy(CHAIN[5]);evidence=CHAIN[1]['state']['evidence'][0]['id']
        feedback={'id':new_record_id(s['run_id'],6,'feedback'),'record_type':'feedback',
                  'summary':'Actual synthetic feedback claims an old draft; retained unresolved.',
                  'evidence_ids':[evidence],'responder_identity':'synthetic-reviewer','responder_role':'Operations',
                  'claimed_subject_ids':['old-run-action'],'claimed_request_id':'unknown-old-request',
                  'claimed_run_id':'old-run','claimed_draft_version':'old-draft/1','claimed_source_versions':['old-source/1'],
                  'claimed_artifacts':[],'subject_ids':[],'request_id':None,'match_status':'unresolved',
                  'reviewer_response_at':'2026-10-07T14:00:00Z','outcome':'approved','reasons':['Synthetic old draft response'],
                  'conditions':[],'authentication':'unverified','authentication_basis':None}
        s['state']['feedback']=[feedback];s['produced_record_ids'].append(feedback['id'])
        validate_snapshot(s,root=self.root,upstream=CHAIN[:5])
        approval=s['state']['approval_requirements'][0];approval.update(status='approved',feedback_ids=[feedback['id']])
        with self.assertRaises(ContractError):validate_snapshot(s,root=self.root,upstream=CHAIN[:5])
        feedback.update(authentication='verified',authentication_basis='Synthetic trusted-channel fixture',
                        match_status='matched',request_id=s['state']['review_requests'][0]['request_id'],
                        subject_ids=[s['state']['proposed_actions'][0]['id']],outcome='conditional',
                        conditions=['Verify the current notice capture before approval.'])
        approval.update(conditions_satisfied=True,condition_evidence_ids=[evidence])
        with self.assertRaisesRegex(ContractError,'retained reviewed draft'):validate_snapshot(s,root=self.root,upstream=CHAIN[:5])
        # Retain the unmatchable old response unchanged and unresolved. A separate
        # verified response with retained review context and current revalidation
        # supplies conditional approval without rewriting its historical claims.
        feedback.update(authentication='unverified',authentication_basis=None,match_status='unresolved',
                        request_id=None,subject_ids=[],outcome='approved',conditions=[])
        current=self.current_feedback(s)
        current.update(outcome='conditional',conditions=['Verify the current notice capture before approval.'])
        s['state']['feedback'].append(current);s['produced_record_ids'].append(current['id'])
        approval['feedback_ids']=[current['id']]
        approval.pop('conditions_satisfied');approval.pop('condition_evidence_ids')
        with self.assertRaisesRegex(ContractError,'authenticated matching'):validate_snapshot(s,root=self.root,upstream=CHAIN[:5])
        approval.update(conditions_satisfied=True,condition_evidence_ids=[evidence])
        validate_snapshot(s,root=self.root,upstream=CHAIN[:5])
        self.reject(6,lambda s:s['state']['proposed_actions'][0].__setitem__('approval_status','approved'),'explicit approval')
        self.reject(6,lambda s:s['state']['approval_requirements'][0].__setitem__('status','approved'),'authenticated matching')

    def test_required_authority_and_upstream_outcomes_fail_closed(self):
        s=deepcopy(CHAIN[2]);blocker={'id':new_record_id(s['run_id'],3,'blocker'),'record_type':'blocker',
            'summary':'Required synthetic legal authority remains unverified.','evidence_ids':[],
            'source_basis':['AMEND declaration'],'reason':'No verified authority content','owner':'Legal',
            'resolution_need':'Verify applicable amendment content before dependent conclusions.'}
        s['state']['authority_blockers']=[blocker];s['produced_record_ids'].append(blocker['id'])
        with self.assertRaisesRegex(ContractError,'fail open'):validate_snapshot(s,root=self.root,upstream=CHAIN[:2])
        s['status']='blocked';validate_snapshot(s,root=self.root,upstream=CHAIN[:2])
        upstream=deepcopy(CHAIN[:6]);upstream[-1]['status']='blocked'
        (self.root/SNAPSHOT_PATHS[5]).write_bytes(json_bytes(upstream[-1]))
        final=deepcopy(CHAIN[6]);final['predecessor']['sha256']=sha256_bytes(json_bytes(upstream[-1]))
        with self.assertRaisesRegex(ContractError,'upstream run outcome'):validate_snapshot(final,root=self.root,upstream=upstream)

    def test_decision_and_gap_fields_are_complete(self):
        s=deepcopy(CHAIN[2]);gap={'id':new_record_id(s['run_id'],3,'gap'),'record_type':'gap',
            'summary':'Synthetic amendment identity cannot be established from available bytes.',
            'evidence_ids':[],'source_basis':['AMEND declared route'],'reason':'No suitable response',
            'owner':'Legal','resolution_need':'Obtain and verify the returned amendment identity.',
            'subject_ids':[],'state':'unresolved'}
        decision={'id':new_record_id(s['run_id'],3,'decision'),'record_type':'decision',
            'summary':'Keep dependent legal conclusions unresolved pending amendment verification.',
            'evidence_ids':[],'concern':'Unknown required authority identity','options_considered':['Guess identity','Withhold finding'],
            'source_basis':['D001','D007'],'chosen_behavior':'Withhold dependent legal conclusions',
            'rationale':'A source declaration does not establish applicable authority.',
            'tradeoffs':['Legal review remains necessary.'],'downstream_effect':'Dependent findings remain unresolved.',
            'decision_basis':'references/decision-log.md#D001','status':'provisional-engineering'}
        s['unresolved']=[gap];s['decisions']=[decision];s['produced_record_ids'] += [gap['id'],decision['id']]
        validate_snapshot(s,root=self.root,upstream=CHAIN[:2])
        for field in ('concern','options_considered','source_basis','chosen_behavior','rationale','tradeoffs','downstream_effect'):
            bad=deepcopy(s);del bad['decisions'][0][field]
            with self.assertRaises(ContractError):validate_snapshot(bad,root=self.root,upstream=CHAIN[:2])
        for field in ('source_basis','reason','owner','resolution_need'):
            bad=deepcopy(s);del bad['unresolved'][0][field]
            with self.assertRaises(ContractError):validate_snapshot(bad,root=self.root,upstream=CHAIN[:2])

    def test_broken_incomplete_marker_symlink_still_rejects(self):
        (self.root/INCOMPLETE_MARKER).symlink_to(self.root/'missing-marker-target')
        with self.assertRaisesRegex(ContractError,'incomplete'):accept_package(self.root)

    def test_current_stage_cycles_and_intraday_uncertainty(self):
        s=deepcopy(CHAIN[5]);a=s['state']['approval_requirements'][0]
        b=deepcopy(a);b['id']=new_record_id(s['run_id'],6,'approval')
        a['subject_ids']=[b['id']];b['subject_ids']=[a['id']]
        s['state']['approval_requirements'].append(b);s['produced_record_ids'].append(b['id'])
        with self.assertRaisesRegex(ContractError,'cyclic'):validate_snapshot(s,root=self.root,upstream=CHAIN[:5])
        s=deepcopy(CHAIN[2]);rule=s['state']['binding_rules'][0]
        timing={'id':new_record_id(s['run_id'],3,'timing-rule'),'record_type':'timing-rule',
                'summary':'Synthetic intraday applicability boundary remains unknown.',
                'evidence_ids':rule['evidence_ids'],'rule_id':rule['id'],'timing_basis':'Synthetic text',
                'precision':'instant','boundary_timezone':None,'applicability':'unresolved'}
        s['state']['timing_rules']=[timing];s['produced_record_ids'].append(timing['id'])
        validate_snapshot(s,root=self.root,upstream=CHAIN[:2])
        timing['applicability']='established'
        with self.assertRaisesRegex(ContractError,'intraday'):validate_snapshot(s,root=self.root,upstream=CHAIN[:2])

    def test_claim_support_must_exist_in_retained_text(self):
        self.reject(2,lambda s:s['state']['evidence'][0].__setitem__('quoted_support','Invented claim quotation'),
                    'quotation absent')

    def test_rfc3339_offsets_and_leap_second_format(self):
        for timestamp in ('2026-10-07t15:00:00z','2026-10-07T15:00:00+05:30','2016-12-31T23:59:60Z'):
            s=deepcopy(CHAIN[0]);s['created_at']=timestamp;validate_schema(s)
        for timestamp in ('2026-10-07T24:00:00Z','2026-10-07T15:00:61Z','2026-10-07T15:00:00+24:00'):
            self.reject(1,lambda s,t=timestamp:s.__setitem__('created_at',t))

    def test_duplicate_json_and_nonfinite_values(self):
        for raw in [b'{"run_id":"a","run_id":"b"}',b'{"x":NaN}',b'\xff',b'{']:
            with self.assertRaises(ContractError):parse_json(raw)


class InterpretationContracts(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'package';shutil.copytree(FIXTURE,self.root)
        self.request=parse_json((self.root/'analysis/request.json').read_bytes())
        self.response=parse_json((self.root/'analysis/response.json').read_bytes())

    def evaluate(self,request=None,response=None):
        return validate_interpretation(json_bytes(request or self.request),json_bytes(response or self.response),
                                      root=self.root,run_id=CHAIN[0]['run_id'],stage=STAGES[2],upstream=CHAIN[:2])

    def test_valid_exchange_and_accepted_stage_binding(self):
        self.assertEqual(self.evaluate().disposition,'proposed')
        s=deepcopy(CHAIN[2]);s['interpretation_bindings']=[{k:{'path':f'analysis/{k}.json','sha256':sha256_bytes((self.root/f'analysis/{k}.json').read_bytes())} for k in ('request','response')}]
        validate_snapshot(s,root=self.root,upstream=CHAIN[:2])

    def test_interpretation_rejects_nested_boolean_number_substitution(self):
        for replacement in (1,1.0):
            upstream=deepcopy(CHAIN[:2])
            upstream[1]['state']['attempts'][0]['content_type_known']=replacement
            with self.assertRaisesRegex(ContractError,'invalid interpretation upstream chain'):
                validate_interpretation(json_bytes(self.request),json_bytes(self.response),root=self.root,
                                        run_id=CHAIN[0]['run_id'],stage=STAGES[2],upstream=upstream)
        self.assertEqual(self.evaluate().disposition,'proposed')

    def test_technical_exchange_violations(self):
        for mutate in [lambda r:r.__setitem__('run_id','other-run'),lambda r:r.__setitem__('stage',STAGES[3]),
                       lambda r:r.__setitem__('packet_id','other'),lambda r:r.__setitem__('packet_sha256','sha256:'+'0'*64),
                       lambda r:r.pop('metadata'),lambda r:r['metadata'].__setitem__('requested_effort','changed')]:
            r=deepcopy(self.response);mutate(r)
            with self.assertRaises(ContractError):self.evaluate(response=r)
        for mutate in [lambda r:r['upstream'][0].__setitem__('sha256','sha256:'+'0'*64),
                       lambda r:r['extracts'][0].__setitem__('sha256','sha256:'+'0'*64),
                       lambda r:r['extracts'][0].__setitem__('text_sha256','sha256:'+'0'*64),
                       lambda r:r['extracts'][0].__setitem__('locator',{'kind':'paragraph','value':'invented'}),
                       lambda r:r['field_dictionary'].__setitem__('sha256','sha256:'+'0'*64)]:
            request=deepcopy(self.request);mutate(request)
            response=deepcopy(self.response);response['packet_sha256']=sha256_bytes(json_bytes(request))
            with self.assertRaises(ContractError):self.evaluate(request,response)
        (self.root/SNAPSHOT_PATHS[0]).write_bytes((self.root/SNAPSHOT_PATHS[0]).read_bytes()+b' ')
        with self.assertRaises(ContractError):self.evaluate()

    def test_semantic_unsupported_and_refusal_are_unresolved(self):
        for disposition in ('refused','truncated','unsupported','ambiguous'):
            r=deepcopy(self.response);r.update(disposition=disposition,candidates=[],diagnostic='Synthetic bounded failure')
            self.assertEqual(self.evaluate(response=r).disposition,'unresolved')
        for mutate in [lambda r:r['candidates'][0]['citations'][0].__setitem__('evidence_id','invented'),
                       lambda r:r['candidates'][0]['citations'][0].__setitem__('quote','unsupported quote'),
                       lambda r:r['candidates'][0].__setitem__('citations',[]),lambda r:r['candidates'][0].pop('citations'),
                       lambda r:r['candidates'][0].__setitem__('uncertainty','Legal must interpret'),
                       lambda r:r['candidates'][0].__setitem__('system_ids',['OUTSIDE']),lambda r:r.__setitem__('candidates',[])]:
            r=deepcopy(self.response);mutate(r)
            self.assertEqual(self.evaluate(response=r).disposition,'unresolved')


# Independently reviewed assertion-to-leaf bindings. This catalog states the
# bounded behavior each test actually proves; the evidence CSV is checked against
# it and the referenced behavioral tests must run successfully.
EVIDENCE_GROUPS = [
    ('R1', (1,2,4), 'SnapshotContracts.test_seven_schema_and_graph_valid_snapshots',
     'Seven synthetic stage snapshots satisfy both schemas and their retained graph.'),
    ('R1', (3,8,9), 'SnapshotContracts.test_stage_sequence_and_predecessors',
     'Cross-run, out-of-order and wrong immediate predecessor bindings are rejected.'),
    ('R1', (5,13), 'SnapshotContracts.test_useful_fields_and_uncertainty',
     'Empty or placeholder summaries are rejected; supported and unresolved records remain distinct.'),
    ('R1', (6,11,14,15), 'SnapshotContracts.test_downstream_values_and_required_record_fields',
     'Typed values distinguish policy, absent-notice fact, impact, existing date and unknown proposal; deleting required record fields fails.'),
    ('R1', (7,16), 'SnapshotContracts.test_dangling_current_stage_wrong_type_and_run_links',
     'Dangling, wrong-type, missing-consumption and current-stage consumed references are rejected.'),
    ('R1', (10,), 'SnapshotContracts.test_exact_byte_two_stage_write_reread_and_mutation',
     'Written predecessor SHA matches independent hashing; appended bytes invalidate reread.'),
    ('R1', (12,17), 'SnapshotContracts.test_produced_and_business_identity_collisions',
     'Produced identities exactly enumerate current records; duplicate identities fail.'),
    ('R3', tuple(range(1,22)), 'IdentityAndState.test_exact_independent_enums',
     'Code and schema contain the exact separate run/retrieval/impact/approval literals; native labels do not become approval.'),
    ('R3', (22,), 'SnapshotContracts.test_permitted_empty_collections_and_required_nonempty',
     'Permitted typed collections accept empty lists while explicitly nonempty collections reject them.'),
    ('R3', (23,24,25), '',
     'Persistence across evidence changes and actual authorized resolution require later reconciliation/review/rerun acceptance.'),
    ('R3', tuple(range(26,31)), 'SnapshotContracts.test_decision_and_gap_fields_are_complete',
     'Unresolved gap basis, reason, owner and resolution need are retained; deletion of each field fails.'),
    ('R3', (31,32), 'SnapshotContracts.test_date_precision_and_newer_values',
     'Retrieval/revision/observation/effective fields coexist; assigned date and date precision cannot change.'),
]
REQUIREMENT_EVIDENCE = {f'{prefix}-{number:03d}': (check, assertion)
                        for prefix, numbers, check, assertion in EVIDENCE_GROUPS for number in numbers}


def check_requirement_evidence(rows, leaves, *, execute=False):
    columns = {'requirement_id','contract_check','contract_assertion','status','expected','observed','u02_boundary'}
    if any(set(row) != columns for row in rows):
        raise AssertionError('malformed evidence columns')
    if len(rows) != len(leaves) or {r['requirement_id'] for r in rows} != set(leaves):
        raise AssertionError('missing or duplicate R1/R3 evidence leaves')
    checks = set()
    for row in rows:
        check, assertion = REQUIREMENT_EVIDENCE[row['requirement_id']]
        status = 'scoped-contract-demonstrated' if check else 'deferred'
        observed = 'passed' if check else 'not-demonstrated'
        if (row['contract_check'], row['contract_assertion'], row['status'], row['observed'], row['expected']) != (
                check, assertion, status, observed, leaves[row['requirement_id']]):
            raise AssertionError('unsupported evidence association/status: ' + row['requirement_id'])
        if not row['u02_boundary']:
            raise AssertionError('missing acceptance boundary')
        if check:
            checks.add(check)
    if execute:
        classes = {c.__name__:c for c in (SnapshotContracts, IdentityAndState, InterpretationContracts)}
        cases = [classes[c](m) for c,m in (name.split('.') for name in sorted(checks))]
        result = unittest.TestResult(); unittest.TestSuite(cases).run(result)
        if result.testsRun != len(checks) or not result.wasSuccessful():
            raise AssertionError('referenced requirement behavior failed: ' + str(result.failures + result.errors))


class RequirementAcceptance(unittest.TestCase):
    def setUp(self):
        with (ROOT/'docs/requirements-traceability.csv').open(newline='') as f:
            self.leaves={r['requirement_id']:r['source_text'] for r in csv.DictReader(f)
                         if r['requirement_id'].startswith(('R1-','R3-'))}
        with (ROOT/'docs/verification/u02-requirement-evidence.csv').open(newline='') as f:
            self.evidence=list(csv.DictReader(f))

    def test_R1_R3_leaves_have_explicit_contract_evidence(self):
        check_requirement_evidence(self.evidence,self.leaves,execute=True)

    def test_unrelated_tests_and_deferred_pass_claims_are_rejected(self):
        rows=deepcopy(self.evidence)
        for row in rows:row['contract_check']='IdentityAndState.test_exact_independent_enums'
        with self.assertRaises(AssertionError):check_requirement_evidence(rows,self.leaves)
        for leaf in ('R3-023','R3-024','R3-025'):
            rows=deepcopy(self.evidence);row=next(r for r in rows if r['requirement_id']==leaf)
            row.update(status='scoped-contract-demonstrated',observed='passed')
            with self.assertRaises(AssertionError):check_requirement_evidence(rows,self.leaves)

    def test_evidence_requires_successful_behavior_execution(self):
        with patch.object(SnapshotContracts,'test_exact_byte_two_stage_write_reread_and_mutation',
                          side_effect=AssertionError('synthetic behavioral failure')):
            with self.assertRaisesRegex(AssertionError,'behavior failed'):
                check_requirement_evidence(self.evidence,self.leaves,execute=True)


if __name__ == '__main__':unittest.main(verbosity=2)
