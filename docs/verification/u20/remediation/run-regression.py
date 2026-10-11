"""One file-partitioned final regression; no test is deliberately duplicated."""
from pathlib import Path
from collections import defaultdict
from datetime import datetime,timezone
import hashlib,json,os,subprocess,sys,time
import xml.etree.ElementTree as ET
repo=Path.cwd();out=repo/'.evidence/u20-remediation'/sys.argv[1];out.mkdir(exist_ok=False)
weights=defaultdict(lambda:1.)
for node in ET.parse(repo/'.evidence/u20/suite.xml').iter('testcase'):
    path='tests/'+node.get('classname').replace('.','/')+'.py'
    if path.startswith('tests/tests/'):path=path[6:]
    weights[path]+=float(node.get('time','0'))
weights.update({'tests/runtime/test_u20_decisions.py':600.,'tests/runtime/test_feedback_remediation.py':600.,'tests/runtime/test_u20_authority_remediation.py':20.,'tests/runtime/test_u20_dependency_remediation.py':10.,'tests/runtime/test_u20_metamorphic.py':225.})
files=sorted({line.split('::')[0] for line in (repo/'.evidence/u20-remediation/collection.txt').read_text().splitlines() if line.startswith('tests/')})
parts=[[] for _ in range(3)];loads=[0.]*3
for path in sorted(files,key=lambda path:-weights[path]):
    index=min(range(3),key=lambda i:loads[i]);parts[index].append(path);loads[index]+=weights[path]
env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','TMPDIR':str(repo/'.evidence/u20-remediation/tmp')}
record={'started_at':datetime.now(timezone.utc).isoformat(),'partition_policy':'Whole test files balanced using baseline durations; disjoint files; three environment-dependent U05 tests separate.','source_hashes':{str(p.relative_to(repo)):'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest() for parent in ('regulatory-change-impact-brief','tests') for p in sorted((repo/parent).rglob('*')) if p.is_file() and p.suffix in ('.py','.md','.json')},'partitions':[]}
running=[]
for index,files in enumerate(parts,1):
    name='shard-'+str(index)
    args=[str(repo/'.evidence/u20/venv/bin/python'),'-m','pytest','-q',*sorted(files),'--basetemp='+str(out/name),'--junitxml='+str(out/(name+'.xml')),'-k','not test_local_http_server and not test_manifest_exact_routes_and and not test_require_registers_cli']
    log=(out/(name+'.log')).open('w');p=subprocess.Popen(args,stdout=log,stderr=subprocess.STDOUT,env=env)
    entry=dict(name=name,args=args,environment={k:env[k] for k in ('PYTHONDONTWRITEBYTECODE','TMPDIR')},files=sorted(files),exit_code=None)
    record['partitions'].append(entry);running.append((p,log,entry))
(out/'commands.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({'started':[p['name'] for p in record['partitions']],'file_counts':[len(p) for p in parts],'estimated_seconds':loads}),flush=True)
while running:
    for p,log,entry in list(running):
        if p.poll() is not None:
            entry.update(exit_code=p.returncode,finished_at=datetime.now(timezone.utc).isoformat());log.close();running.remove((p,log,entry))
            (out/'commands.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(entry),flush=True)
    if running:time.sleep(1)
record['finished_at']=datetime.now(timezone.utc).isoformat()
record['source_changes_during_run']=[name for name,digest in record['source_hashes'].items() if 'sha256:'+hashlib.sha256((repo/name).read_bytes()).hexdigest()!=digest]
(out/'commands.json').write_text(json.dumps(record,indent=2)+'\n')
sys.exit(any(p['exit_code'] for p in record['partitions']) or bool(record['source_changes_during_run']))
