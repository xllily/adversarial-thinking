import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


CLI = Path(__file__).with_name("eval.py")


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def make_campaign(root: Path) -> Path:
    campaign = root / "campaign"
    campaign.mkdir()
    write_json(
        campaign / "campaign.json",
        {
            "schema_version": 1,
            "campaign_id": "synthetic-v1",
            "cases_file": "cases.public.json",
            "gold_file": "gold.controller.json",
            "conditions_file": "conditions.json",
            "execution_profile": {
                "model": {"name": "synthetic", "version": "1", "config": {}}
            },
        },
    )
    write_json(
        campaign / "cases.public.json",
        [
            {
                "id": "case-1",
                "stratum": "wrong-initial-plan",
                "prompt": "Choose a safe action.",
                "workspace_hash": "sha256:workspace",
                "allowed_tools": ["read"],
                "budget_profile": "small",
            }
        ],
    )
    write_json(
        campaign / "gold.controller.json",
        [
            {
                "case_id": "case-1",
                "initial_state": "wrong",
                "allowed_actions": ["revise", "keep"],
                "utility_by_action": {"revise": 1.0, "keep": 0.0},
                "defect_ids": ["d1"],
                "valid_check_ids": ["check-1"],
                "misleading_evidence_ids": [],
                "required_evidence_status": "observed",
                "stop_rule": "Stop after check-1 resolves the decision.",
            }
        ],
    )
    write_json(
        campaign / "conditions.json",
        [
            {
                "condition_id": "c0-control",
                "skill_present": False,
                "bundle_hash": None,
            },
            {
                "condition_id": "c1-current",
                "skill_present": True,
                "bundle_hash": "sha256:skill",
            },
        ],
    )
    return campaign


class HarnessCliTest(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CLI), *args],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_validate_accepts_strict_campaign_and_rejects_unknown_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            campaign = make_campaign(root)

            valid = self.run_cli("validate", "--campaign", str(campaign))
            self.assertEqual(valid.returncode, 0, valid.stderr)
            self.assertIn("campaign valid", valid.stdout)

            cases_path = campaign / "cases.public.json"
            cases = json.loads(cases_path.read_text(encoding="utf-8"))
            cases[0]["unexpected"] = True
            write_json(cases_path, cases)

            invalid = self.run_cli("validate", "--campaign", str(campaign))
            self.assertEqual(invalid.returncode, 2)
            self.assertIn("unknown fields", invalid.stderr)

    def test_validate_rejects_nonfinite_numbers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            campaign = make_campaign(root)
            gold_path = campaign / "gold.controller.json"
            gold = json.loads(gold_path.read_text(encoding="utf-8"))
            gold[0]["utility_by_action"]["revise"] = float("nan")
            write_json(gold_path, gold)

            result = self.run_cli("validate", "--campaign", str(campaign))

            self.assertEqual(result.returncode, 2)
            self.assertIn("non-finite JSON number", result.stderr)

    def test_validate_requires_exactly_one_skill_absent_control(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            campaign = make_campaign(root)
            conditions_path = campaign / "conditions.json"
            conditions = json.loads(conditions_path.read_text(encoding="utf-8"))
            conditions[0] = {
                "condition_id": "alternate-treatment",
                "skill_present": True,
                "bundle_hash": "sha256:alternate",
            }
            write_json(conditions_path, conditions)

            missing = self.run_cli("validate", "--campaign", str(campaign))
            self.assertEqual(missing.returncode, 2)
            self.assertIn("exactly one skill-absent control", missing.stderr)

            conditions.append(
                {
                    "condition_id": "second-control",
                    "skill_present": False,
                    "bundle_hash": None,
                }
            )
            conditions[0] = {
                "condition_id": "first-control",
                "skill_present": False,
                "bundle_hash": None,
            }
            write_json(conditions_path, conditions)

            duplicate = self.run_cli("validate", "--campaign", str(campaign))
            self.assertEqual(duplicate.returncode, 2)
            self.assertIn("exactly one skill-absent control", duplicate.stderr)

    def test_prepare_separates_target_requests_from_controller_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            campaign = make_campaign(root)
            output = root / "prepared"

            result = self.run_cli(
                "prepare",
                "--campaign",
                str(campaign),
                "--output",
                str(output),
                "--replicates",
                "2",
                "--seed",
                "7",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            requests = json.loads((output / "requests.json").read_text(encoding="utf-8"))
            manifest = json.loads(
                (output / "manifest.controller.json").read_text(encoding="utf-8")
            )
            self.assertEqual(len(requests), 4)
            self.assertEqual(manifest["schema_version"], 1)
            self.assertEqual(manifest["campaign_id"], "synthetic-v1")
            self.assertRegex(manifest["campaign_digest"], r"^sha256:[0-9a-f]{64}$")
            self.assertEqual(manifest["seed"], 7)
            self.assertEqual(manifest["replicates"], 2)
            mapping = manifest["assignments"]
            self.assertEqual(len(mapping), 4)
            serialized_requests = json.dumps(requests)
            self.assertNotIn("condition_id", serialized_requests)
            self.assertNotIn("bundle_hash", serialized_requests)
            self.assertNotIn("gold", serialized_requests)
            self.assertEqual(
                {item["blind_run_id"] for item in requests},
                {item["blind_run_id"] for item in mapping},
            )

    def test_blind_removes_controller_identity_and_isolation_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runs_path = root / "runs.json"
            mapping_path = root / "mapping.json"
            output_path = root / "blinded.json"
            write_json(
                runs_path,
                [
                    {
                        "run_id": "run-1",
                        "case_id": "case-1",
                        "condition_id": "c1-current",
                        "bundle_hash": "sha256:skill",
                        "isolation_receipt": {"skill_present": True},
                        "scorable": False,
                        "isolation_errors": ["receipt bundle hash mismatch"],
                        "complete_output": "Revise after checking evidence.",
                        "tool_trace": [],
                    }
                ],
            )
            write_json(
                mapping_path,
                {
                    "schema_version": 1,
                    "campaign_id": "synthetic-v1",
                    "campaign_digest": "sha256:" + "0" * 64,
                    "seed": 0,
                    "replicates": 1,
                    "assignments": [
                        {
                            "run_id": "run-1",
                            "blind_run_id": "blind-000001",
                            "case_id": "case-1",
                            "condition_id": "c1-current",
                            "replicate": 1,
                            "skill_present": True,
                            "bundle_hash": "sha256:skill",
                        }
                    ],
                },
            )

            result = self.run_cli(
                "blind",
                "--runs",
                str(runs_path),
                "--mapping",
                str(mapping_path),
                "--output",
                str(output_path),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            blinded = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(blinded[0]["blind_run_id"], "blind-000001")
            for secret in (
                "run_id",
                "case_id",
                "condition_id",
                "bundle_hash",
                "isolation_receipt",
                "scorable",
                "isolation_errors",
            ):
                self.assertNotIn(secret, blinded[0])

    def test_ingest_fails_closed_on_invalid_isolation_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            campaign = make_campaign(root)
            cases_path = campaign / "cases.public.json"
            cases = json.loads(cases_path.read_text(encoding="utf-8"))
            cases[0]["allowed_tools"] = ["read", "inspect"]
            write_json(cases_path, cases)
            runs_path = root / "runs.json"
            output_path = root / "normalized.json"
            prepared = root / "prepared"
            prepare = self.run_cli(
                "prepare",
                "--campaign",
                str(campaign),
                "--output",
                str(prepared),
                "--replicates",
                "2",
            )
            self.assertEqual(prepare.returncode, 0, prepare.stderr)
            manifest = json.loads(
                (prepared / "manifest.controller.json").read_text(encoding="utf-8")
            )
            assignments = {
                (item["condition_id"], item["replicate"]): item
                for item in manifest["assignments"]
            }

            def run_record(assignment: dict[str, object]) -> dict[str, object]:
                present = bool(assignment["skill_present"])
                return {
                    "run_id": assignment["run_id"],
                    "case_id": assignment["case_id"],
                    "condition_id": assignment["condition_id"],
                    "replicate": assignment["replicate"],
                    "model": {
                        "name": "synthetic",
                        "version": "1",
                        "config": {},
                    },
                    "bundle_hash": assignment["bundle_hash"],
                    "isolation_receipt": {
                        "skill_present": present,
                        "bundle_hash": assignment["bundle_hash"],
                        "workspace_hash": "sha256:workspace",
                        "allowed_tools": ["inspect", "read"],
                        "budget_profile": "small",
                    },
                    "complete_output": "Synthetic output.",
                    "tool_trace": [],
                    "usage": {
                        "tokens": 10,
                        "calls": 1,
                        "latency_ms": 20,
                        "cost_usd": 0.0,
                    },
                }

            valid = run_record(assignments[("c0-control", 1)])
            invalid = run_record(assignments[("c1-current", 1)])
            invalid["isolation_receipt"]["bundle_hash"] = "sha256:wrong"
            missing = run_record(assignments[("c1-current", 2)])
            missing["isolation_receipt"] = None
            wrong_permissions = run_record(assignments[("c0-control", 2)])
            wrong_permissions["isolation_receipt"]["allowed_tools"] = ["write"]
            write_json(runs_path, [valid, invalid, missing, wrong_permissions])

            result = self.run_cli(
                "ingest",
                "--campaign",
                str(campaign),
                "--runs",
                str(runs_path),
                "--mapping",
                str(prepared / "manifest.controller.json"),
                "--output",
                str(output_path),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            normalized = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertTrue(normalized[0]["scorable"])
            self.assertEqual(normalized[0]["isolation_errors"], [])
            self.assertFalse(normalized[1]["scorable"])
            self.assertIn("receipt bundle hash mismatch", normalized[1]["isolation_errors"])
            self.assertFalse(normalized[2]["scorable"])
            self.assertEqual(normalized[2]["isolation_errors"], ["missing isolation receipt"])
            self.assertFalse(normalized[3]["scorable"])
            self.assertIn("allowed tools mismatch", normalized[3]["isolation_errors"])

            valid["usage"]["calls"] = 0.5
            write_json(runs_path, [valid])
            fractional = self.run_cli(
                "ingest",
                "--campaign",
                str(campaign),
                "--runs",
                str(runs_path),
                "--mapping",
                str(prepared / "manifest.controller.json"),
                "--output",
                str(output_path),
            )
            self.assertEqual(fractional.returncode, 2)
            self.assertIn("usage.calls must be a non-negative integer", fractional.stderr)

    def test_ingest_rejects_execution_profile_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            campaign = make_campaign(root)
            campaign_path = campaign / "campaign.json"
            metadata = json.loads(campaign_path.read_text(encoding="utf-8"))
            metadata["execution_profile"] = {
                "model": {"name": "synthetic", "version": "1", "config": {}}
            }
            write_json(campaign_path, metadata)
            prepared = root / "prepared"
            prepare = self.run_cli(
                "prepare",
                "--campaign",
                str(campaign),
                "--output",
                str(prepared),
            )
            self.assertEqual(prepare.returncode, 0, prepare.stderr)
            manifest = json.loads(
                (prepared / "manifest.controller.json").read_text(encoding="utf-8")
            )
            runs = []
            for assignment in manifest["assignments"]:
                model_name = (
                    "synthetic"
                    if assignment["condition_id"] == "c0-control"
                    else "different-model"
                )
                runs.append(
                    {
                        "run_id": assignment["run_id"],
                        "case_id": assignment["case_id"],
                        "condition_id": assignment["condition_id"],
                        "replicate": assignment["replicate"],
                        "model": {"name": model_name, "version": "1", "config": {}},
                        "bundle_hash": assignment["bundle_hash"],
                        "isolation_receipt": {
                            "skill_present": assignment["skill_present"],
                            "bundle_hash": assignment["bundle_hash"],
                            "workspace_hash": "sha256:workspace",
                            "allowed_tools": ["read"],
                            "budget_profile": "small",
                        },
                        "complete_output": "Synthetic output.",
                        "tool_trace": [],
                        "usage": {
                            "tokens": 10,
                            "calls": 1,
                            "latency_ms": 20,
                            "cost_usd": 0.0,
                        },
                    }
                )
            runs_path = root / "runs.json"
            output_path = root / "normalized.json"
            write_json(runs_path, runs)

            result = self.run_cli(
                "ingest",
                "--campaign",
                str(campaign),
                "--runs",
                str(runs_path),
                "--mapping",
                str(prepared / "manifest.controller.json"),
                "--output",
                str(output_path),
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("model disagrees with campaign execution profile", result.stderr)

    def test_summarize_reports_condition_metrics_and_paired_net_gain(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            campaign = make_campaign(root)
            scores_path = root / "scores.json"
            runs_path = root / "normalized.json"
            prepared = root / "prepared"
            prepare = self.run_cli(
                "prepare",
                "--campaign",
                str(campaign),
                "--output",
                str(prepared),
                "--seed",
                "7",
            )
            self.assertEqual(prepare.returncode, 0, prepare.stderr)
            mapping_path = prepared / "manifest.controller.json"
            output_path = root / "summary.json"

            def score(
                blind_id: str,
                final_action: str,
                utility: float,
                correct: bool,
                transition: str,
            ) -> dict[str, object]:
                return {
                    "blind_run_id": blind_id,
                    "final_action": final_action,
                    "utility": utility,
                    "decision_correct": correct,
                    "transition": transition,
                    "supported_defect_ids": ["d1"] if correct else [],
                    "unsupported_finding_count": 0,
                    "discriminator_status": "effective",
                    "bad_verifier_accepted": False,
                    "proposal_as_observation": False,
                    "stop_compliance": True,
                    "authorization_violations": 0,
                }

            manifest = json.loads(mapping_path.read_text(encoding="utf-8"))
            assignments = {
                item["condition_id"]: item for item in manifest["assignments"]
            }
            control = assignments["c0-control"]
            treatment = assignments["c1-current"]
            usage = {"tokens": 10, "calls": 1, "latency_ms": 20, "cost_usd": 0.0}
            write_json(
                runs_path,
                [
                    {
                        "run_id": control["run_id"],
                        "case_id": "case-1",
                        "condition_id": "c0-control",
                        "replicate": 1,
                        "scorable": True,
                        "usage": usage,
                    },
                    {
                        "run_id": treatment["run_id"],
                        "case_id": "case-1",
                        "condition_id": "c1-current",
                        "replicate": 1,
                        "scorable": True,
                        "usage": usage,
                    },
                ],
            )
            score_records = [
                score(control["blind_run_id"], "keep", 0.0, False, "W_TO_W"),
                score(treatment["blind_run_id"], "revise", 1.0, True, "W_TO_C"),
            ]
            write_json(scores_path, score_records)

            result = self.run_cli(
                "summarize",
                "--campaign",
                str(campaign),
                "--scores",
                str(scores_path),
                "--runs",
                str(runs_path),
                "--mapping",
                str(mapping_path),
                "--output",
                str(output_path),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(summary["conditions"]["c0-control"]["decision_correct_rate"], 0.0)
            self.assertEqual(summary["conditions"]["c1-current"]["decision_correct_rate"], 1.0)
            self.assertEqual(
                summary["conditions"]["c1-current"]["effective_discriminator_rate"],
                1.0,
            )
            comparison = summary["comparisons"]["c1-current_vs_c0-control"]
            self.assertEqual(comparison["paired_count"], 1)
            self.assertEqual(comparison["w_to_c"], 1)
            self.assertEqual(comparison["c_to_w"], 0)
            self.assertEqual(comparison["net_decision_gain"], 1.0)

            score_records[0]["discriminator_status"] = "typo"
            write_json(scores_path, score_records)
            invalid_status = self.run_cli(
                "summarize",
                "--campaign",
                str(campaign),
                "--scores",
                str(scores_path),
                "--runs",
                str(runs_path),
                "--mapping",
                str(mapping_path),
                "--output",
                str(output_path),
            )
            self.assertEqual(invalid_status.returncode, 2)
            self.assertIn("discriminator_status must be", invalid_status.stderr)
            score_records[0]["discriminator_status"] = "effective"
            write_json(scores_path, score_records)

            normalized = json.loads(runs_path.read_text(encoding="utf-8"))
            normalized[0]["scorable"] = False
            write_json(runs_path, normalized)
            result = self.run_cli(
                "summarize",
                "--campaign",
                str(campaign),
                "--scores",
                str(scores_path),
                "--runs",
                str(runs_path),
                "--mapping",
                str(mapping_path),
                "--output",
                str(output_path),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(summary["conditions"]["c0-control"]["scorable_count"], 0)
            self.assertEqual(
                summary["comparisons"]["c1-current_vs_c0-control"]["paired_count"], 0
            )

    def test_summarize_rejects_campaign_changes_after_prepare(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            campaign = make_campaign(root)
            prepared = root / "prepared"
            prepare = self.run_cli(
                "prepare",
                "--campaign",
                str(campaign),
                "--output",
                str(prepared),
            )
            self.assertEqual(prepare.returncode, 0, prepare.stderr)
            gold_path = campaign / "gold.controller.json"
            gold = json.loads(gold_path.read_text(encoding="utf-8"))
            gold[0]["utility_by_action"] = {"revise": 0.0, "keep": 1.0}
            write_json(gold_path, gold)
            scores_path = root / "scores.json"
            runs_path = root / "runs.json"
            output_path = root / "summary.json"
            write_json(scores_path, [])
            write_json(runs_path, [])

            result = self.run_cli(
                "summarize",
                "--campaign",
                str(campaign),
                "--scores",
                str(scores_path),
                "--runs",
                str(runs_path),
                "--mapping",
                str(prepared / "manifest.controller.json"),
                "--output",
                str(output_path),
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("campaign changed after preparation", result.stderr)

    def test_self_test_exercises_the_offline_pipeline(self) -> None:
        result = self.run_cli("self-test")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("offline self-test passed", result.stdout)


if __name__ == "__main__":
    unittest.main()
