from pathlib import Path
import importlib.util,json
root=Path.cwd();out=root/'docs/verification/u20/remediation'
spec=importlib.util.spec_from_file_location('u20_check',root/'docs/verification/check-u20.py');checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)
packages=[('complete',Path('.evidence/u20-remediation/e04/retained/complete'),'synthetic'),('partial',Path('.evidence/u20-remediation/e04/retained/partial'),'synthetic'),('blocked',Path('.evidence/u20-remediation/e04/retained/blocked'),'synthetic'),('legacy-live',Path('deliverables'),'live'),('legacy-host',Path('.evidence/u20/clean-host/deliverables'),'synthetic')]
replay=json.loads((out/'replay-results.json').read_text())
print('replay keys',list(replay),flush=True)
for kind,folder in [('conditional','same'),('changed-date','date'),('changed-content','content')]:
    packages.append((kind,Path('.evidence/u20-remediation/e07/replay-runs')/('e07-'+folder)/'out','synthetic'))
packages.append(('rejection',Path('.evidence/u20-remediation/e07/rejection-run/out'),'synthetic'))
results=[]
for name,path,basis in packages:
    value=checker.inspect(path,basis)
    (out/(name+'-inspection.json')).write_text(json.dumps(value,indent=2)+'\n')
    results.append({k:value[k] for k in ('run_id','basis','publication_status','csv_rows','calendar_events','decision_counts','mechanical_validation')})
    results[-1]['case']=name
    print(json.dumps(results[-1]),flush=True)
(out/'consolidated-inspection.json').write_text(json.dumps(results,indent=2)+'\n')
