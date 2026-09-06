#!/usr/bin/env python3
"""Prepare and rehearse eight isolated T1 mounts. No provider imports or calls."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import uuid

if __package__:
    from evals.campaigns.t1_pilot_v1 import pilot
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from evals.campaigns.t1_pilot_v1 import pilot

IMAGE = 'python@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254'
WORKER = Path(__file__).with_name('isolated_worker.py')
CASES = ('migration-compat-01', 'dual-write-06')


def write_json(path, value):
    with path.open('x', encoding='utf-8') as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write('\n')


def prepare(output):
    output = output.absolute()
    if output.exists() or output.is_symlink():
        raise ValueError('output already exists')
    if not output.parent.is_dir() or output.parent.resolve() != output.parent:
        raise ValueError('output parent must be an existing canonical path')
    if any((p / 'SKILL.md').exists() or (p / '.agents').exists() or
           (p / '.codex').exists() for p in output.parents):
        raise ValueError('output must be outside skill discovery trees')
    pilot.verify_source(pilot.SOURCE_ROOT)
    cases = {c['id']: c for c in pilot.load_json(pilot.SOURCE_ROOT / 'cases.public.json')}
    conditions = pilot.load_json(pilot.SOURCE_ROOT / 'conditions.json')
    output.mkdir(mode=0o700)
    runtime = output / 'runtime'
    runtime.mkdir()
    shutil.copyfile(WORKER, runtime / 'worker.py')
    (runtime / 'worker.py').chmod(0o444)
    targets = output / 'targets'
    targets.mkdir()
    assignments = []
    for case_id in CASES:
        for condition in conditions:
            blind_id = 'target-' + uuid.uuid4().hex[:12]
            target = targets / blind_id
            target.mkdir()
            shutil.copytree(pilot.SOURCE_ROOT / 'workspaces' / case_id, target / 'workspace')
            if condition['skill_present']:
                pilot.build_bundle(pilot.SOURCE_ROOT, condition['condition_id'], target / 'skill')
            for file in target.rglob('*'):
                if file.is_file(): file.chmod(0o444)
                elif file.is_dir(): file.chmod(0o555)
            assignments.append({'target': blind_id, 'case': cases[case_id], 'condition': condition})
    manifest = {'schema': 1, 'purpose': 'offline isolation rehearsal; no evaluation records',
                'image': IMAGE, 'worker_sha256': hashlib.sha256(WORKER.read_bytes()).hexdigest(),
                'budget_profiles_sha256': pilot.file_hash(pilot.SOURCE_ROOT / 'budget-profiles.json'),
                'assignments': assignments}
    write_json(output / 'manifest.controller.json', manifest)
    return manifest


def load_manifest(root):
    if root.resolve() != root.absolute():
        raise ValueError('root must be canonical')
    manifest = pilot.load_json(root / 'manifest.controller.json')
    if manifest['image'] != IMAGE or len(manifest['assignments']) != 8:
        raise ValueError('invalid isolation plan')
    if manifest['worker_sha256'] != hashlib.sha256(WORKER.read_bytes()).hexdigest():
        raise ValueError('worker source drift')
    if (root / 'runtime/worker.py').read_bytes() != WORKER.read_bytes():
        raise ValueError('mounted worker drift')
    expected = {(c, condition) for c in CASES for condition in pilot.EXPECTED_CONDITIONS}
    if {(a['case']['id'], a['condition']['condition_id']) for a in manifest['assignments']} != expected:
        raise ValueError('assignments differ from eight-case matrix')
    if len({a['target'] for a in manifest['assignments']}) != 8:
        raise ValueError('duplicate target')
    source_cases = {c['id']: c for c in pilot.load_json(pilot.SOURCE_ROOT / 'cases.public.json')}
    source_conditions = {c['condition_id']: c for c in pilot.load_json(pilot.SOURCE_ROOT / 'conditions.json')}
    if manifest['budget_profiles_sha256'] != pilot.file_hash(pilot.SOURCE_ROOT / 'budget-profiles.json'):
        raise ValueError('budget profile drift')
    for a in manifest['assignments']:
        if not re.fullmatch(r'target-[a-f0-9]{12}', a['target']):
            raise ValueError('invalid target directory')
        if a['case'] != source_cases[a['case']['id']] or a['condition'] != source_conditions[a['condition']['condition_id']]:
            raise ValueError('assignment/source drift')
        verify_mounts(root, a)
    return manifest


def verify_mounts(root, assignment):
    target = root / 'targets' / assignment['target']
    if target.is_symlink() or (root / 'targets').is_symlink() or (root / 'runtime').is_symlink():
        raise ValueError('symlink target rejected')
    workspace, skill = target / 'workspace', target / 'skill'
    if workspace.is_symlink() or pilot.canonical_tree_hash(workspace) != assignment['case']['workspace_hash']:
        raise ValueError('workspace drift')
    condition = assignment['condition']
    if skill.is_symlink() or skill.exists() != condition['skill_present']:
        raise ValueError('skill presence drift')
    if skill.exists() and pilot.canonical_tree_hash(skill) != condition['bundle_hash']:
        raise ValueError('skill hash drift')


def docker_env():
    # No provider variables are inherited by the Docker client or tool process.
    return {k: os.environ[k] for k in ('PATH', 'HOME', 'DOCKER_HOST', 'DOCKER_CONTEXT') if k in os.environ}


def command(root, assignment, name):
    target = root / 'targets' / assignment['target']
    argv = ['docker', 'run', '--rm', '--pull=never', '--name', name, '-i',
            '--network=none', '--read-only', '--cap-drop=ALL',
            '--security-opt=no-new-privileges:true', '--pids-limit=32',
            '--memory=128m', '--cpus=1', '--user=65534:65534',
            '--workdir=/workspace', '--env=HOME=/nonexistent',
            '--entrypoint=/usr/bin/env']
    for src, dst in [(target / 'workspace', '/workspace'), (root / 'runtime', '/runner')]:
        if ',' in str(src): raise ValueError('comma in mount path')
        argv += ['--mount', f'type=bind,src={src},dst={dst},readonly']
    if assignment['condition']['skill_present']:
        argv += ['--mount', f'type=bind,src={target / "skill"},dst=/skills,readonly']
    return argv + [IMAGE, '-i', 'PATH=/usr/local/bin:/usr/bin:/bin', 'HOME=/nonexistent',
                   '/usr/local/bin/python3', '-I', '-B', '/runner/worker.py']


def invoke(root, assignment, request):
    verify_mounts(root, assignment)
    name = 't1-isolation-' + uuid.uuid4().hex
    try:
        result = subprocess.run(command(root, assignment, name), input=json.dumps(request),
                                text=True, capture_output=True, timeout=20, env=docker_env())
        if result.returncode not in (0, 2) or len(result.stdout.encode()) > 131072:
            raise ValueError('container failed or output limit exceeded')
        response = json.loads(result.stdout)
        verify_mounts(root, assignment)
        return response
    finally:
        # Remove only this invocation's randomly named container, including interruption.
        subprocess.run(['docker', 'rm', '-f', name], capture_output=True, timeout=10, env=docker_env())


def check_receipt(observed, assignment):
    case, condition = assignment['case'], assignment['condition']
    expected = {'skill_present': condition['skill_present'], 'bundle_hash': condition['bundle_hash'],
                'workspace_hash': case['workspace_hash'], 'allowed_tools': case['allowed_tools'],
                'budget_profile': case['budget_profile']}
    if observed.get('receipt') != expected:
        raise ValueError('effective mount receipt mismatch')
    runtime = observed['runtime']
    if not (runtime['uid'] == 65534 and runtime['active_interfaces'] == ['lo'] and runtime['ipv4_route_count'] == 0 and
            runtime['workspace_read_only'] and runtime['forbidden_paths_unavailable'] and
            runtime['credential_env_absent']):
        raise ValueError('runtime isolation checks failed')
    if (len(runtime['skill_files']) > 0) != condition['skill_present']:
        raise ValueError('effective skill discovery mismatch')


def rehearse(root):
    manifest = load_manifest(root)
    evidence_dir = root / 'offline-evidence'
    evidence_dir.mkdir()
    for a in manifest['assignments']:
        observed = invoke(root, a, {'operation': 'inspect'})
        check_receipt(observed, a)
        read = invoke(root, a, {'name': 'read', 'arguments': {'path': 'verify.py'}})
        if 'content' not in read: raise ValueError('read tool failed')
        shell = invoke(root, a, {'name': 'shell', 'arguments': {'command': 'python3 verify.py'}})
        if shell.get('exit_code') not in (0, 1): raise ValueError('fixture verifier failed to execute')
        # Exercise denial through the same dispatch interface future model tools will use.
        denied = [invoke(root, a, req) for req in [
            {'name': 'read', 'arguments': {'path': '/controller/gold.controller.json'}},
            {'name': 'read', 'arguments': {'path': '../manifest.controller.json'}},
            {'name': 'shell', 'arguments': {'command': 'cat /etc/passwd'}}]]
        if any('error' not in response for response in denied):
            raise ValueError('tool restriction failed')
        observed.update({'target': a['target'], 'case_id': a['case']['id'],
                         'condition_id': a['condition']['condition_id'], 'verifier': shell,
                         'denial_checks_passed': 3, 'model_calls': 0, 'evaluation_record': False})
        write_json(evidence_dir / (a['target'] + '.json'), observed)
        print('offline isolation passed: ' + a['target'], flush=True)
    summary = {'isolated_workspaces_checked': 8, 'model_calls': 0, 'evaluation_record': False,
               'image': IMAGE, 'runtime_boundary': 'Docker namespace plus fixed read/shell dispatch'}
    write_json(evidence_dir / 'summary.json', summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'rehearse'])
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = prepare(args.root) if args.command == 'prepare' else rehearse(args.root)
        print(json.dumps({'root': str(args.root), 'model_calls': 0,
                          'targets': len(result['assignments']) if 'assignments' in result else 8}))
        return 0
    except (ValueError, OSError, subprocess.SubprocessError, pilot.PilotError):
        print('isolation operation failed; inspect local state before repeating', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
