"""Inspect durable recovery packages after the final regression completes."""
from pathlib import Path
import importlib.util,json,sys
root=Path.cwd();sys.path.insert(0,str(root/'regulatory-change-impact-brief/scripts'))
from rci.contracts import SNAPSHOT_PATHS,parse_json,sha256_bytes
from rci.history import verify_archive
spec=importlib.util.spec_from_file_location('u20_check',root/'docs/verification/check-u20.py');check=importlib.util.module_from_spec(spec);spec.loader.exec_module(check)
out=root/'docs/verification/u20/remediation';records=[]
for label,shard,pattern in [('decision-recovery','shard-2','test_recovery_decision_bound_t*'),('changed-source-recovery','shard-1','test_public_run_changed_source*')]:
    parents=[p for p in (root/'.evidence/u20-remediation/regression-final'/shard).glob(pattern) if p.is_dir() and not p.is_symlink()]
    assert len(parents)==1,parents
    package=parents[0]/'out';inspection=check.inspect(package,'synthetic')
    (out/(label+'-inspection.json')).write_text(json.dumps(inspection,indent=2)+'\n')
    scope=parse_json((package/SNAPSHOT_PATHS[0]).read_bytes());previous=scope['state']['supersedes_run_id']
    archive=verify_archive(package/'history'/previous)
    recovery=next(d for d in scope['decisions'] if d['summary']=='Fresh run supersession and recovery')
    assert previous in recovery['source_basis'] and 'recovery' in recovery['chosen_behavior']
    before=parse_json((archive.root/SNAPSHOT_PATHS[1]).read_bytes());after=parse_json((package/SNAPSHOT_PATHS[1]).read_bytes())
    assert {a['attempt_key'] for a in before['state']['attempts']}.isdisjoint(a['attempt_key'] for a in after['state']['attempts'])
    damaged=(archive.root/'compliance-brief.md').read_bytes()
    assert damaged.startswith(b'Synthetic ')
    record=dict(case=label,root=str(package.relative_to(root)),run_id=scope['run_id'],supersedes_run_id=previous,decision=recovery,archived_corrupt_brief_sha256=sha256_bytes(damaged),history_manifest=archive.manifest,inspection=label+'-inspection.json',fresh_attempts=True,all_seven_snapshots=True,organizational_authorization_claimed=False)
    records.append(record);print(json.dumps({k:record[k] for k in ('case','root','run_id','supersedes_run_id','archived_corrupt_brief_sha256')}),flush=True)
(out/'recovery-results.json').write_text(json.dumps(records,indent=2)+'\n')
