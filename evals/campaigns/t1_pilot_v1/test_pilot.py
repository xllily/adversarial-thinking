from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SOURCE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("t1_pilot", SOURCE / "pilot.py")
assert SPEC is not None and SPEC.loader is not None
pilot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pilot)


class T1PilotTest(unittest.TestCase):
    def test_frozen_source_verifies_without_model_calls(self) -> None:
        result = pilot.verify_source(SOURCE)
        self.assertEqual(result["cases"], 12)
        self.assertEqual(result["conditions"], 4)
        self.assertEqual(result["model_calls"], 0)

    def test_workspace_tampering_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="t1-pilot-test-") as temp_name:
            copied = Path(temp_name) / "source"
            shutil.copytree(SOURCE, copied)
            target = copied / "workspaces" / "dual-write-06" / "rehearsal.json"
            target.write_text(target.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            with self.assertRaisesRegex(pilot.PilotError, "workspace hash mismatch"):
                pilot.verify_source(copied)

    def test_candidate_hash_tampering_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="t1-pilot-test-") as temp_name:
            copied = Path(temp_name) / "source"
            shutil.copytree(SOURCE, copied)
            conditions_path = copied / "conditions.json"
            conditions = json.loads(conditions_path.read_text(encoding="utf-8"))
            conditions[1]["bundle_hash"] = "sha256:wrong"
            conditions_path.write_text(
                json.dumps(conditions, indent=2) + "\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(pilot.PilotError, "bundle hashes"):
                pilot.verify_source(copied)

    def test_bundle_path_traversal_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="t1-pilot-test-") as temp_name:
            copied = Path(temp_name) / "source"
            shutil.copytree(SOURCE, copied)
            spec_path = copied / "bundle-spec.json"
            bundle_spec = json.loads(spec_path.read_text(encoding="utf-8"))
            bundle_spec["paths"][0] = "../SKILL.md"
            spec_path.write_text(
                json.dumps(bundle_spec, indent=2) + "\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(pilot.PilotError, "must stay inside"):
                pilot.verify_source(copied)

    def test_c2_is_label_only_and_c3_preserves_step_order(self) -> None:
        with tempfile.TemporaryDirectory(prefix="t1-pilot-test-") as temp_name:
            root = Path(temp_name)
            c1 = root / "c1"
            c2 = root / "c2"
            c3 = root / "c3"
            pilot.build_bundle(SOURCE, "c1-current-0.1.1", c1)
            pilot.build_bundle(SOURCE, "c2-discriminate-label", c2)
            pilot.build_bundle(SOURCE, "c3-operational-discriminator", c3)

            paths = json.loads(
                (SOURCE / "bundle-spec.json").read_text(encoding="utf-8")
            )["paths"]
            for relative in paths:
                if relative != "SKILL.md":
                    self.assertEqual((c1 / relative).read_bytes(), (c2 / relative).read_bytes())
                    self.assertEqual((c1 / relative).read_bytes(), (c3 / relative).read_bytes())

            c1_skill = (c1 / "SKILL.md").read_text(encoding="utf-8")
            c2_skill = (c2 / "SKILL.md").read_text(encoding="utf-8")
            self.assertEqual(
                c1_skill.replace("Disconfirm before commitment", "Discriminate before commitment"),
                c2_skill,
            )
            c3_skill = (c3 / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("A proposed check is not an observation.", c3_skill)
            self.assertLess(
                c3_skill.index("1. **Frame:**"),
                c3_skill.index("2. **Countermodel:**"),
            )
            self.assertLess(
                c3_skill.index("2. **Countermodel:**"),
                c3_skill.index("3. **Discriminate:**"),
            )
            self.assertLess(
                c3_skill.index("3. **Discriminate:**"),
                c3_skill.index("4. **Integrate:**"),
            )

    def test_materialization_binds_exact_profile_and_remains_offline(self) -> None:
        with tempfile.TemporaryDirectory(prefix="t1-pilot-test-") as temp_name:
            output = Path(temp_name) / "materialized"
            pilot.materialize(
                argparse.Namespace(
                    source=SOURCE,
                    output=output,
                    model_name="test-model",
                    model_version="test-model-2026-09-04",
                    model_config_json='{"temperature": 0, "tool_budget": "frozen"}',
                )
            )
            campaign = json.loads(
                (output / "campaign" / "campaign.json").read_text(encoding="utf-8")
            )
            self.assertEqual(campaign["execution_profile"]["model"]["name"], "test-model")
            self.assertEqual(
                campaign["execution_profile"]["model"]["version"],
                "test-model-2026-09-04",
            )
            self.assertEqual(
                campaign["execution_profile"]["model"]["config"][
                    pilot.PROFILE_HASH_FIELD
                ],
                pilot.file_hash(SOURCE / "budget-profiles.json"),
            )
            receipt = json.loads(
                (output / "materialization.controller.json").read_text(encoding="utf-8")
            )
            self.assertEqual(receipt["model_calls"], 0)
            self.assertEqual(receipt["model"], campaign["execution_profile"]["model"])
            self.assertFalse((output / "bundles" / "c0-skill-absent").exists())
            self.assertTrue(
                (output / "bundles" / "c3-operational-discriminator" / "SKILL.md").is_file()
            )

    def test_materialization_rejects_output_under_skill_repository(self) -> None:
        output = SOURCE / "nested-target-output"
        with self.assertRaisesRegex(pilot.PilotError, "outside the skill repository"):
            pilot.materialize(
                argparse.Namespace(
                    source=SOURCE,
                    output=output,
                    model_name="test-model",
                    model_version="test-model-2026-09-04",
                    model_config_json='{"temperature": 0}',
                )
            )
        self.assertFalse(output.exists())

    def test_public_case_metadata_does_not_reveal_outcome_labels(self) -> None:
        forbidden = {
            "correct",
            "wrong",
            "supported",
            "misleading",
            "unavailable",
            "failure",
            "negative",
            "noise",
            "exhausted",
            "conflict",
            "correlated",
            "verifier",
        }
        cases = json.loads((SOURCE / "cases.public.json").read_text(encoding="utf-8"))
        for case in cases:
            metadata = f"{case['id']} {case['stratum']}".lower()
            for token in forbidden:
                self.assertNotIn(token, metadata, case["id"])

    def test_parser_verifier_rejects_broken_implementation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="t1-parser-mutation-") as directory:
            workspace = Path(directory) / "workspace"
            shutil.copytree(SOURCE / "workspaces" / "parser-fix-10", workspace)
            parser_path = workspace / "parser.py"
            parser_path.write_text(
                parser_path.read_text().replace(
                    "raise ParseError('non-finite number')", "pass"
                )
            )
            result = subprocess.run(
                [sys.executable, "-B", "verify.py"], cwd=workspace,
                capture_output=True, text=True, check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("FAIL accepted non-finite number", result.stdout + result.stderr)

    def test_fixture_verifiers_match_frozen_oracles(self) -> None:
        expected = {
            "migration-compat-01": (1, "FAIL incompatible deployed workers"),
            "dual-write-06": (0, "PASS complete mixed-version rehearsal"),
            "callback-config-09": (1, "FAIL production callback_url"),
            "parser-fix-10": (0, "PASS finite/non-finite parser matrix"),
        }
        for case_id, (returncode, marker) in expected.items():
            workspace = SOURCE / "workspaces" / case_id
            result = subprocess.run(
                [sys.executable, "-B", "verify.py"],
                cwd=workspace,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, returncode, case_id)
            self.assertIn(marker, result.stdout, case_id)


if __name__ == "__main__":
    unittest.main()
