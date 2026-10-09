"""Real temporary Git indexes and scanner: never stage synthetic secrets here."""
from pathlib import Path
import os
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / 'scripts/secret_guard.py'
KEY = b'AIza' + b'0123456789AbCdEfGhIjKlMnOpQrStUvWxYz_'  # Synthetic, assembled only in memory.


@pytest.fixture
def repo(tmp_path):
    if not shutil.which('gitleaks'):
        pytest.fail('Gitleaks required for security regression tests; see docs/secret-safety.md')
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    def git(*args):
        return subprocess.run(['git', *args], cwd=tmp_path, env=env,
                              check=True, capture_output=True)
    git('init', '-q')
    git('config', 'user.name', 'Guard test')
    git('config', 'user.email', 'guard@example.invalid')
    git('config', 'commit.gpgsign', 'false')
    def stage(name, body):
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(body)
        git('add', '--', name)
    def check(*args):
        return subprocess.run(['python3', str(GUARD), *args], cwd=tmp_path,
                              env=env, capture_output=True)
    return tmp_path, git, stage, check


@pytest.mark.parametrize('name,body', [
    ('capture.bin', b'\x00\xff' + KEY + b'\x00'),
    ('odd name\nwith newline.txt', KEY),
    ('capture.txt', KEY + b' # gitleaks:allow'),
    ('id.pem', b'-----BEGIN ' + b'RSA PRIVATE KEY-----\nabc\n'),
    ('token.txt', b'ghp_' + b'AbcDefGhiJklMnoPqrStuVwxYz012345678901'),
])
def test_secret_rejected_without_value_output(repo, name, body):
    _, _, stage, check = repo
    stage(name, body)
    result = check()
    assert result.returncode == 1
    assert KEY not in result.stdout + result.stderr
    assert b'possible secret' in result.stderr


def test_partial_staging_scans_index_not_worktree(repo):
    root, _, stage, check = repo
    stage('data.bin', KEY)
    (root / 'data.bin').write_bytes(b'clean unstaged edit')
    assert check().returncode == 1
    stage('data.bin', b'clean staged bytes')
    (root / 'data.bin').write_bytes(KEY)
    assert check().returncode == 0


@pytest.mark.parametrize('path', ['u07-verification/data.bin', 'other/.staging/data.bin',
                                 'docs/verification/u05-anonymous-live/data.bin', '.env', '.aws/credentials'])
def test_raw_and_credential_paths_rejected_even_without_secret(repo, path):
    _, _, stage, check = repo
    stage(path, b'no secrets')
    assert check().returncode == 1


def test_rename_deletion_and_full_index(repo):
    _, git, stage, check = repo
    stage('old.bin', KEY)
    git('commit', '-qm', 'synthetic test baseline')
    assert check().returncode == 0
    assert check('--all').returncode == 1
    git('mv', 'old.bin', 'new.bin')
    assert check().returncode == 1
    git('rm', '-f', 'new.bin')
    assert check().returncode == 0


def test_hook_blocks_actual_commit(repo):
    root, git, stage, _ = repo
    shutil.copytree(ROOT / 'scripts', root / 'scripts')
    shutil.copyfile(ROOT / '.gitleaks.toml', root / '.gitleaks.toml')
    subprocess.run(['sh', 'scripts/install-secret-hook.sh'], cwd=root, check=True, capture_output=True)
    stage('response.bin', b'\x00' + KEY)
    with pytest.raises(subprocess.CalledProcessError):
        git('commit', '-qm', 'must be blocked')


def test_attempt_filename_exception_does_not_hide_other_keys(repo):
    _, _, stage, check = repo
    stage('journal.json', b'{"attempt_key": "0123456789abcdef0123456789abcdef"}')
    assert check().returncode == 0
    stage('journal.json', b'{"attempt_key": "' + KEY + b'"}')
    assert check().returncode == 1


def test_missing_scanner_blocks_commit(tmp_path):
    result = subprocess.run([sys.executable, str(GUARD)], cwd=tmp_path,
                            env={'PATH': str(tmp_path)}, capture_output=True)
    assert result.returncode != 0
    assert b'install Gitleaks' in result.stderr
