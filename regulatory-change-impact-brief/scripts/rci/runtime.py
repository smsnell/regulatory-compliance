"""U03 supervisor boundary. No source adapters, publication or recovery yet."""
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import importlib.metadata
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
from uuid import uuid4
from urllib.parse import parse_qsl, urlsplit

from jsonschema import Draft202012Validator, FormatChecker
from .contracts import ContractError, json_bytes, package_path, parse_json, require, sha256_bytes
from .snapshots import accept_package

SKILL = Path(__file__).resolve().parents[2]
REPO = SKILL.parent


class Providers:
    def now(self):
        return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

    def run_id(self):
        return 'run-' + uuid4().hex


def validate_config(config):
    schema = parse_json((SKILL / 'references/schemas/runtime-config.schema.json').read_bytes())
    errors = list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(config))
    require(not errors, 'invalid runtime configuration')  # Validation diagnostics omit supplied values.
    require({s['id'] for s in config['sources']} ==
            {'LAW','OJ','AMEND','CONSOLIDATED','TIME','FAQ','POLICY','SYSTEMS','EVIDENCE','CALENDAR'},
            'required source inventory must be distinct and complete')
    for source in config['sources']:
        url = urlsplit(source['route'])
        require(url.scheme == 'https' and url.hostname and not url.username and not url.password,
                'source route must be credential-free HTTPS')
        require(not url.fragment, 'source route fragments are unsupported; credentials belong outside configuration')
        if url.query:
            # Only the disclosed EUR-Lex document selector needs a query in U03.
            # Decode keys/values, then allow the supported shape instead of
            # guessing every spelling or encoding of a credential parameter.
            try:
                query = parse_qsl(url.query, strict_parsing=True, errors='strict')
            except ValueError:
                raise ContractError('unsupported source route query') from None
            require(url.hostname == 'eur-lex.europa.eu' and url.path == '/legal-content/EN/TXT/'
                    and len(query) == 1 and query[0][0] == 'uri'
                    and re.fullmatch(r'(?:OJ:[A-Z]_[0-9]+|CELEX:[0-9][0-9A-Z()/\-]*)', query[0][1]),
                    'unsupported source route query; credentials belong outside configuration')
    require(not Path(config['output_root']).is_absolute() and
            '..' not in Path(config['output_root']).parts, 'output must be repository-relative')
    output_directory(config['output_root'])
    return config


def output_directory(value, config_path=None):
    repo = REPO.resolve()
    root = (repo / value).resolve()
    require(root.is_relative_to(repo) and root != repo, 'unsafe output root')
    protected = [SKILL.resolve(), *(repo / name for name in (
        SKILL.name, 'config', 'docs', 'interviews', 'references', 'tests',
        '.git', '.agents', '.codex', '.entire'))]
    if config_path is not None:
        protected.append(config_path.resolve())
    require(not any(root.is_relative_to(path.resolve()) or path.resolve().is_relative_to(root)
                    for path in protected), 'output root overlaps implementation or inputs')
    require(not root.exists() or root.is_dir(), 'output root must be a directory')
    return root


def preflight(config):
    require(not os.environ.get('RCI_CHILD_RUN'), 'recursive supervisor launch rejected')
    require(sys.version_info >= (3,12), 'Python 3.12 or later required')
    for name in ('httpx','jsonschema','icalendar'):
        importlib.metadata.version(name)
    host = shutil.which('codex')
    require(host is not None, 'Codex host unavailable')
    try:
        version = subprocess.run([host,'--version'], capture_output=True, text=True, timeout=15)
        require(version.returncode == 0 and version.stdout.strip() == 'codex-cli 0.161.0',
                'unsupported host version; review capability profile')
        auth = subprocess.run([host,'login','status'], capture_output=True, timeout=15)
        require(auth.returncode == 0, 'host authentication unavailable')
    except subprocess.TimeoutExpired as error:
        raise ContractError('host preflight timed out') from error
    return host, version.stdout.strip()


@contextmanager
def writer_lock(root):
    root.mkdir(parents=True, exist_ok=True)
    require(not (root / '.writer.lock').is_symlink(), 'unsafe lock path')
    with (root / '.writer.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ContractError('another writer owns output root') from error
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def host_command(host, workspace, model, effort):
    # Ignore inherited MCP/plugins/hooks, approval rules and broad user profiles.
    return [host,'exec','--ignore-user-config','--ignore-rules','--ephemeral',
            '--skip-git-repo-check','--sandbox','workspace-write','--json',
            '-C',str(workspace),'-m',model,'-c',f'model_reasoning_effort="{effort}"',
            '-c','approval_policy="never"','-c','sandbox_workspace_write.network_access=false',
            '-c','features.multi_agent=false','-c','features.web_search=false','-']


def invoke_host(command, prompt, workspace, timeout, *, analysis_directory='analysis'):
    env = {k:v for k,v in os.environ.items() if not k.startswith('CODEX_THREAD')}
    env['RCI_CHILD_RUN'] = workspace.name
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    log_root = package_path(workspace, analysis_directory + '/host-events.jsonl').parent
    log_root.mkdir(parents=True, exist_ok=True)
    with (log_root/'host-events.jsonl').open('wb') as out, \
            (log_root/'host-stderr.txt').open('wb') as err:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=out, stderr=err,
                                   env=env, start_new_session=True)
        try:
            process.communicate(prompt.encode(), timeout=timeout)
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            raise ContractError('host interrupted or timed out; candidate retained')
        require(process.returncode == 0, 'host failed; inspect retained host diagnostics')


def verify_final(root, run_id, started_at):
    chain = accept_package(root)
    require(chain[0]['run_id'] == run_id, 'old or foreign package rejected')
    instant=lambda value: datetime.fromisoformat(value.replace('Z','+00:00'))
    require(instant(chain[0]['created_at']) >= instant(started_at), 'package predates invocation')
    attempts = chain[1]['state']['attempts']
    require(attempts and all(instant(a['started_at']) >= instant(started_at) for a in attempts), 'missing fresh attempts')
    require({s['source_id'] for s in chain[1]['state']['sources']} >=
            {'LAW','OJ','AMEND','CONSOLIDATED','TIME','FAQ','POLICY','SYSTEMS','EVIDENCE','CALENDAR'},
            'missing required source attempts')
    require(all(s['attempt_ids'] for s in chain[1]['state']['sources']), 'source has no attempt')
    from .contracts import reduce_states
    require(chain[-1]['status'] == reduce_states(s['status'] for s in chain),
            'final outcome conceals earlier stage outcome')
    return chain[-1]['status']


def prepare_workspace(root):
    (root/'analysis').mkdir()
    shutil.copytree(SKILL,root/SKILL.name,ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copyfile(REPO/'snapshot.schema.json',root/'snapshot.schema.json')
    directory=root/'.agents/skills'
    directory.mkdir(parents=True)
    (directory/SKILL.name).symlink_to('../../'+SKILL.name,target_is_directory=True)


def file_inventory(root):
    return {p.relative_to(root).as_posix():sha256_bytes(p.read_bytes())
            for p in root.rglob('*') if p.is_file() and not p.is_symlink()}


def verify_inventory(root, inventory):
    for path,digest in inventory.items():
        require(sha256_bytes((root/path).read_bytes())==digest,'host altered immutable input: '+path)


def visible_usage(root, *, analysis_directory='analysis'):
    usage=[]
    for line in package_path(root, analysis_directory + '/host-events.jsonl').read_bytes().splitlines():
        try:
            event=parse_json(line)
        except ContractError:
            continue
        if event.get('type')=='turn.completed':
            usage.append(event.get('usage'))
    return usage or None


def production(config_path):
    config = validate_config(parse_json(config_path.read_bytes()))
    root = output_directory(config['output_root'], config_path)
    host,version=preflight(config)
    providers=Providers()
    with writer_lock(root):
        staging=root/'.staging'
        require(not staging.is_symlink(), 'unsafe staging root')
        run_id=providers.run_id()
        candidate=staging/run_id
        candidate.mkdir(parents=True,exist_ok=False)
        prepare_workspace(candidate)
        context={'run_id':run_id,'mode':'production-skeleton','started_at':providers.now(),
                 'config_sha256':sha256_bytes(config_path.read_bytes()),
                 'host_version':version,'requested_model':config['host']['model'],
                 'requested_effort':config['host']['effort'],'reported_model':None,
                 'reported_effort':None,'credential_ref':config['host']['credential_ref'],
                 'host_owner':config['host']['owner']}
        (candidate/'analysis/run-context.json').write_bytes(json_bytes(context))
        immutable=file_inventory(candidate)
        helper=candidate/SKILL.name/'scripts/stage.py'
        prompt=(f'Use $regulatory-change-impact-brief. Read {candidate/SKILL.name}/SKILL.md. '
                f'This is the production skeleton branch for root {candidate}. '
                f'Helper command: {sys.executable} {helper} block --root {candidate}. '
                'Report the actual blocked helper outcome. Stage engines are not implemented.')
        command=host_command(host,candidate,config['host']['model'],config['host']['effort'])
        (candidate/'analysis/host-prompt.txt').write_text(prompt)
        (candidate/'analysis/host-command.json').write_bytes(json_bytes({'argv':command}))
        try:
            invoke_host(command,prompt,candidate,180)
            verify_inventory(candidate,immutable)
            diagnostic=parse_json((candidate/'analysis/stage-outcome.json').read_bytes())
            require(diagnostic=={'run_id':run_id,'status':'blocked',
                                'reason':'U03 skeleton: live stage engines are not implemented'},
                    'missing or invalid stage outcome')
            outcome={**diagnostic,'production_package':False}
        except (ValueError,OSError) as error:
            outcome={'run_id':run_id,'status':'failed','reason':str(error),'production_package':False}
        outcome['visible_usage']=visible_usage(candidate) if (candidate/'analysis/host-events.jsonl').exists() else None
        (candidate/'analysis/outcome.json').write_bytes(json_bytes(outcome))
        return outcome
