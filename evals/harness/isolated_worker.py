#!/usr/bin/env python3
"""Container-only, credential-free tool worker for the two T1 shakedown cases."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

WORKSPACE = Path('/workspace')
SKILLS = Path('/skills')
MAX_READ_BYTES = 32768
TOOLS = ['read', 'shell']
PROFILE = 't1-small-read-shell-v1'


def tree_hash(root):
    digest = hashlib.sha256()
    files = []
    for path in sorted(root.rglob('*')):
        if path.is_symlink() or (not path.is_file() and not path.is_dir()):
            raise ValueError('non-regular tree entry')
        if path.is_file():
            files.append(path)
    if not files:
        raise ValueError('empty tree')
    for path in files:
        name = path.relative_to(root).as_posix().encode()
        data = path.read_bytes()
        digest.update(len(name).to_bytes(4, 'big') + name)
        digest.update(len(data).to_bytes(8, 'big') + data)
    return 'sha256:' + digest.hexdigest()


def read_file(value):
    if not isinstance(value, str):
        raise ValueError('path must be a string')
    path = Path(value)
    if not path.is_absolute():
        path = WORKSPACE / path
    if '..' in path.parts:
        raise ValueError('path traversal rejected')
    root = next((r for r in (WORKSPACE, SKILLS) if r in path.parents), None)
    if root is None or any(p.is_symlink() for p in [path, *path.parents]):
        raise ValueError('path outside allowed regular files')
    if not path.is_file() or path.stat().st_size > MAX_READ_BYTES:
        raise ValueError('file absent or read budget exceeded')
    return path.read_text(encoding='utf-8')


def receipt():
    present = (SKILLS / 'SKILL.md').is_file()
    if SKILLS.exists() and not present:
        raise ValueError('malformed skill mount')
    return {'skill_present': present,
            'bundle_hash': tree_hash(SKILLS) if present else None,
            'workspace_hash': tree_hash(WORKSPACE),
            'allowed_tools': TOOLS, 'budget_profile': PROFILE}


def evidence():
    # Observation from the process namespace, independently of condition labels.
    ro = False
    try:
        (WORKSPACE / '.write-probe').write_text('probe')
    except OSError:
        ro = True
    else:
        (WORKSPACE / '.write-probe').unlink()
    forbidden = [Path('/controller'), Path('/var/run/docker.sock'), Path('/root/.agents'),
                 Path('/root/.codex'), Path('/workspace/SKILL.md')]
    def unavailable(path):
        try:
            return not path.exists()
        except PermissionError:
            return True
    env_keys = sorted(os.environ)
    return {'uid': os.getuid(), 'active_interfaces': sorted(p.name for p in Path('/sys/class/net').iterdir()
                if (p / 'flags').is_file() and int((p / 'flags').read_text(), 16) & 1),
            'ipv4_route_count': len(Path('/proc/net/route').read_text().strip().splitlines()) - 1,
            'workspace_read_only': ro,
            'forbidden_paths_unavailable': all(unavailable(p) for p in forbidden),
            'environment_keys': env_keys,
            'credential_env_absent': not any('KEY' in k or 'TOKEN' in k for k in env_keys),
            'skill_files': sorted(str(p.relative_to(SKILLS)) for p in SKILLS.rglob('*') if p.is_file()),
            'workspace_files': sorted(str(p.relative_to(WORKSPACE)) for p in WORKSPACE.rglob('*') if p.is_file())}


def dispatch(name, args):
    if not isinstance(args, dict):
        raise ValueError('arguments must be an object')
    if name == 'read' and set(args) == {'path'}:
        return {'content': read_file(args['path'])}
    if name == 'shell' and args == {'command': 'python3 verify.py'}:
        result = subprocess.run(['/usr/local/bin/python3', '-I', '-B', 'verify.py'],
                                cwd=WORKSPACE, env={'PATH': '/usr/local/bin:/usr/bin:/bin',
                                'HOME': '/nonexistent'}, capture_output=True, timeout=5)
        if len(result.stdout) + len(result.stderr) > MAX_READ_BYTES:
            raise ValueError('shell output budget exceeded')
        return {'exit_code': result.returncode, 'stdout': result.stdout.decode(),
                'stderr': result.stderr.decode()}
    raise ValueError('unsupported tool or arguments')


def main():
    try:
        request = json.loads(sys.stdin.buffer.read(4097))
        before = receipt()
        if request == {'operation': 'inspect'}:
            result = {'receipt': before, 'runtime': evidence()}
        elif set(request) == {'name', 'arguments'}:
            result = dispatch(request['name'], request['arguments'])
        else:
            raise ValueError('unsupported operation')
        if receipt() != before:
            raise ValueError('mounted tree changed')
        print(json.dumps(result))
        return 0
    except (ValueError, OSError, subprocess.SubprocessError):
        print(json.dumps({'error': 'tool rejected or execution failed'}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
