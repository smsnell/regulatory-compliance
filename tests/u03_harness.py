"""Explicit test-only replay/host harness; never imported by production."""
from pathlib import Path
import shutil
import sys
from rci.contracts import (json_bytes, parse_json, require, sha256_bytes,
                           validate_interpretation)
from rci.runtime import SKILL, REPO, Providers, host_command, invoke_host, preflight, visible_usage
from rci.snapshots import read_chain, write_snapshot

FIXTURE = REPO/'tests/fixtures/u02/package'


class FakeProviders(Providers):
    def __init__(self):
        self.counter = 0

    def now(self):
        return '2026-10-08T04:00:00Z'

    def run_id(self):
        self.counter += 1
        return f'run-u03-fake-{self.counter}'


def prepare(parent, providers=None, host_version=None):
    providers = providers or Providers()
    run_id = providers.run_id()
    root = parent/run_id
    root.mkdir()
    (root/'analysis').mkdir()
    (root/'sources').mkdir()
    shutil.copytree(SKILL,root/SKILL.name,ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copyfile(REPO/'snapshot.schema.json',root/'snapshot.schema.json')
    # Discovery registration scoped to this test session, without installing globally.
    directory=root/'.agents/skills'
    directory.mkdir(parents=True)
    (directory/SKILL.name).symlink_to('../../'+SKILL.name, target_is_directory=True)
    text = (FIXTURE/'sources/systems.txt').read_bytes() + (
        b'Synthetic mapping: SYNTHETIC-SYS-01 is the learner-facing assistant. '
        b'The stated notice requirement is an internal control for this system only. '
        b'Its exact required notice text is: You are interacting with an AI assistant. '
        b'The notice appears visibly before the first assistant interaction. '
        b'This synthetic control has no exceptions or additional conditions.\n')
    (root/'sources/systems.txt').write_bytes(text)
    old_hash=sha256_bytes((FIXTURE/'sources/systems.txt').read_bytes())
    source_hash=sha256_bytes(text)
    (root/'analysis/instructions.txt').write_bytes((SKILL/'SKILL.md').read_bytes())
    (root/'analysis/reference.txt').write_bytes((SKILL/'references/contracts.md').read_bytes())
    prefix=[]
    for i,path in enumerate(('snapshots/01-scope.json','snapshots/02-source-capture.json')):
        raw=(FIXTURE/path).read_text().replace('run-u02-synthetic',run_id).replace(old_hash,source_hash)
        snapshot=parse_json(raw.encode())
        snapshot['snapshot_id']=f'snapshot-{run_id}-{i+1}'
        if prefix:
            snapshot['predecessor']={'snapshot_id':prefix[-1]['snapshot_id'],
                                    'path':'snapshots/01-scope.json',
                                    'sha256':sha256_bytes((root/'snapshots/01-scope.json').read_bytes())}
        write_snapshot(root,snapshot,upstream=prefix)
        prefix.append(snapshot)
    request=parse_json((FIXTURE/'analysis/request.json').read_text().replace('run-u02-synthetic',run_id).encode())
    request['extracts'][0].update(text=text.decode(),sha256=source_hash,text_sha256=source_hash)
    request['packet_id']='packet-'+run_id
    request['created_at']=providers.now()
    request['upstream']=[{'snapshot_id':s['snapshot_id'],'sequence':s['sequence'],
                          'path':f'snapshots/{s["sequence"]:02d}-{s["stage"]}.json',
                          'sha256':sha256_bytes((root/f'snapshots/{s["sequence"]:02d}-{s["stage"]}.json').read_bytes())}
                         for s in prefix]
    request['metadata'].update(host_version=host_version,requested_model='gpt-6.1-sol',requested_effort='high')
    for group in ('instruction_versions','reference_versions'):
        for pointer in request['metadata'][group]:
            pointer['sha256']=sha256_bytes((root/pointer['path']).read_bytes())
    (root/'analysis/request.json').write_bytes(json_bytes(request))
    immutable={p.relative_to(root).as_posix():sha256_bytes(p.read_bytes()) for p in root.rglob('*')
               if p.is_file() and not p.is_symlink()}
    return root, immutable


def verify_exchange(root, immutable):
    for path,digest in immutable.items():
        require(sha256_bytes((root/path).read_bytes())==digest,'host altered immutable input: '+path)
    request=(root/'analysis/request.json').read_bytes()
    response=(root/'analysis/response.json').read_bytes()
    result=validate_interpretation(request,response,root=root,run_id=root.name,
                                  stage='authority-and-timing',upstream=read_chain(root,count=2))
    require(result.disposition=='proposed','synthetic interpretation remains unresolved')
    return result


def run_live(parent, timeout=180):
    host,version=preflight({})
    root,immutable=prepare(parent,host_version=version)
    helper=root/SKILL.name/'scripts/stage.py'
    command=host_command(host,root,'gpt-6.1-sol','high')
    prompt=(f'Use $regulatory-change-impact-brief. This is the U03 synthetic host test. '
            f'Read {root/SKILL.name}/SKILL.md and follow its synthetic branch. '
            f'Run root: {root}. Python interpreter: {sys.executable}. '
            f'Helper command: {sys.executable} {helper} submit --root {root} '
            f'--proposal {root}/analysis/agent-proposal.json. '
            'Interpret only the explicit synthetic internal notice control for SYNTHETIC-SYS-01. '
            'Legal applicability, effective dates and provider/deployer classification are outside this test task. '
            'Retain uncertainty where the stated control itself is ambiguous. '
            'After one submission, finish and report its actual disposition. '
            'An unresolved result stays unresolved; never remove uncertainty to obtain acceptance. '
            'No production artifacts are expected.')
    (root/'analysis/host-prompt.txt').write_text(prompt)
    (root/'analysis/host-invocation.json').write_bytes(json_bytes({
        'command':command,'started_at':Providers().now(),'host_version':version,
        'requested_model':'gpt-6.1-sol','requested_effort':'high',
        'reported_model':None,'reported_effort':None,'usage':None,
        'synthetic':True,'production_package':False}))
    try:
        invoke_host(command,prompt,root,timeout)
        result=verify_exchange(root,immutable)
        status='complete'
        reason='bounded synthetic host exchange verified; not a production package'
    except (ValueError,OSError) as error:
        status='failed';reason=str(error)
    outcome={'run_id':root.name,'status':status,'reason':reason,'production_package':False,
             'visible_usage':visible_usage(root)}
    (root/'analysis/outcome.json').write_bytes(json_bytes(outcome))
    return root,outcome
