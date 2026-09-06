import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evals.harness import isolation as i, isolated_worker as w


class IsolationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir='/private/tmp')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve() / 'prepared'
        self.manifest = i.prepare(self.root)

    def test_eight_actual_mounts_and_no_control_data(self):
        manifest = i.load_manifest(self.root)
        self.assertEqual(len(manifest['assignments']), 8)
        for a in manifest['assignments']:
            target = self.root / 'targets' / a['target']
            self.assertEqual((target / 'skill').exists(), a['condition']['skill_present'])
            self.assertEqual(i.pilot.canonical_tree_hash(target / 'workspace'), a['case']['workspace_hash'])
            self.assertFalse(list(target.rglob('*controller*')))
            self.assertFalse(list(target.rglob('*.env')))

    def test_fails_on_c0_contamination(self):
        a = next(a for a in self.manifest['assignments'] if not a['condition']['skill_present'])
        (self.root / 'targets' / a['target'] / 'skill').mkdir()
        with self.assertRaisesRegex(ValueError, 'presence'): i.load_manifest(self.root)

    def test_worker_source_and_workspace_drift(self):
        a = self.manifest['assignments'][0]
        workspace = self.root / 'targets' / a['target'] / 'workspace'
        workspace.chmod(0o755)
        (workspace / 'extra.txt').write_text('drift')
        with self.assertRaisesRegex(ValueError, 'workspace drift'): i.load_manifest(self.root)

    def test_symlinks_and_traversal_rejected(self):
        workspace = self.root / 'targets' / self.manifest['assignments'][0]['target'] / 'workspace'
        with patch.object(w, 'WORKSPACE', workspace), patch.object(w, 'SKILLS', self.root / 'none'):
            self.assertIn('import', w.read_file('verify.py'))
            for path in ('../manifest.controller.json', '/etc/passwd'):
                with self.assertRaises(ValueError): w.read_file(path)
            workspace.chmod(0o755)
            (workspace / 'link').symlink_to(self.root / 'manifest.controller.json')
            with self.assertRaises(ValueError): w.read_file('link')
            with self.assertRaises(ValueError): w.tree_hash(workspace)

    def test_shell_dispatch_never_runs_arbitrary_commands(self):
        with patch.object(w.subprocess, 'run') as run:
            for command in ('cat /etc/passwd', 'python3 verify.py; id', ['python3', 'verify.py']):
                with self.assertRaises(ValueError): w.dispatch('shell', {'command': command})
            run.assert_not_called()

    def test_worker_hash_matches_campaign_algorithm(self):
        a = self.manifest['assignments'][0]
        workspace = self.root / 'targets' / a['target'] / 'workspace'
        self.assertEqual(w.tree_hash(workspace), a['case']['workspace_hash'])

    def test_docker_boundary_and_environment(self):
        for a in self.manifest['assignments']:
            cmd = i.command(self.root, a, 'test-only')
            for option in ('--network=none', '--read-only', '--cap-drop=ALL', '--pull=never', '--user=65534:65534'):
                self.assertIn(option, cmd)
            self.assertNotIn(str(i.pilot.REPO_ROOT), ' '.join(cmd))
            self.assertNotIn('manifest.controller.json', ' '.join(cmd))
            self.assertIn(i.IMAGE, cmd)
        with patch.dict(os.environ, {'T1_API_KEY': 'test-secret'}):
            self.assertNotIn('T1_API_KEY', i.docker_env())

    def test_receipt_mismatch_rejected(self):
        a = self.manifest['assignments'][0]
        with self.assertRaises(ValueError): i.check_receipt({'receipt': {}}, a)

    def test_output_stays_outside_skill_tree(self):
        parent = self.root / 'forbidden'
        parent.mkdir(); (parent / 'SKILL.md').write_text('no')
        with self.assertRaisesRegex(ValueError, 'discovery'): i.prepare(parent / 'child')


if __name__ == '__main__': unittest.main()
