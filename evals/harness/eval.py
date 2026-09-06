#!/usr/bin/env python3
"""Deterministic, zero-model-call evaluation harness."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
import tempfile
from pathlib import Path
from typing import Any


class ValidationError(ValueError):
    pass


def load_json(path: Path) -> Any:
    def reject_constant(value: str) -> None:
        raise ValidationError(f"non-finite JSON number is not allowed: {value}")

    try:
        return json.loads(
            path.read_text(encoding="utf-8"), parse_constant=reject_constant
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"cannot read {path}: {exc}") from exc


def require_object(value: Any, location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValidationError(f"{location} must be an object")
    return value


def require_array(value: Any, location: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValidationError(f"{location} must be an array")
    return value


def require_fields(
    value: dict[str, Any], required: set[str], location: str
) -> None:
    missing = sorted(required - value.keys())
    unknown = sorted(value.keys() - required)
    if missing:
        raise ValidationError(f"{location} missing fields: {', '.join(missing)}")
    if unknown:
        raise ValidationError(f"{location} unknown fields: {', '.join(unknown)}")


def require_string(value: Any, location: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValidationError(f"{location} must be a non-empty string")
    return value


def require_string_array(value: Any, location: str) -> list[str]:
    items = require_array(value, location)
    if not all(isinstance(item, str) and item for item in items):
        raise ValidationError(f"{location} must contain non-empty strings")
    if len(items) != len(set(items)):
        raise ValidationError(f"{location} must not contain duplicates")
    return items


def campaign_file(root: Path, name: Any, field: str) -> Path:
    filename = Path(require_string(name, f"campaign.{field}"))
    if filename.is_absolute() or ".." in filename.parts:
        raise ValidationError(f"campaign.{field} must stay inside campaign directory")
    return root / filename


def validate_campaign(root: Path) -> dict[str, Any]:
    metadata = require_object(load_json(root / "campaign.json"), "campaign")
    require_fields(
        metadata,
        {
            "schema_version",
            "campaign_id",
            "cases_file",
            "gold_file",
            "conditions_file",
            "execution_profile",
        },
        "campaign",
    )
    if metadata["schema_version"] != 1:
        raise ValidationError("campaign.schema_version must be 1")
    require_string(metadata["campaign_id"], "campaign.campaign_id")
    execution_profile = require_object(
        metadata["execution_profile"], "campaign.execution_profile"
    )
    require_fields(execution_profile, {"model"}, "campaign.execution_profile")
    expected_model = require_object(
        execution_profile["model"], "campaign.execution_profile.model"
    )
    require_fields(
        expected_model,
        {"name", "version", "config"},
        "campaign.execution_profile.model",
    )
    require_string(expected_model["name"], "campaign.execution_profile.model.name")
    require_string(
        expected_model["version"], "campaign.execution_profile.model.version"
    )
    require_object(
        expected_model["config"], "campaign.execution_profile.model.config"
    )

    cases = require_array(
        load_json(campaign_file(root, metadata["cases_file"], "cases_file")),
        "cases",
    )
    gold = require_array(
        load_json(campaign_file(root, metadata["gold_file"], "gold_file")),
        "gold",
    )
    conditions = require_array(
        load_json(
            campaign_file(root, metadata["conditions_file"], "conditions_file")
        ),
        "conditions",
    )
    if not cases or not conditions:
        raise ValidationError("cases and conditions must not be empty")

    case_fields = {
        "id",
        "stratum",
        "prompt",
        "workspace_hash",
        "allowed_tools",
        "budget_profile",
    }
    case_ids: list[str] = []
    for index, raw_case in enumerate(cases):
        case = require_object(raw_case, f"cases[{index}]")
        require_fields(case, case_fields, f"cases[{index}]")
        case_ids.append(require_string(case["id"], f"cases[{index}].id"))
        for field in ("stratum", "prompt", "workspace_hash", "budget_profile"):
            require_string(case[field], f"cases[{index}].{field}")
        require_string_array(case["allowed_tools"], f"cases[{index}].allowed_tools")
    if len(case_ids) != len(set(case_ids)):
        raise ValidationError("case ids must be unique")

    gold_fields = {
        "case_id",
        "initial_state",
        "allowed_actions",
        "utility_by_action",
        "defect_ids",
        "valid_check_ids",
        "misleading_evidence_ids",
        "required_evidence_status",
        "stop_rule",
    }
    gold_ids: list[str] = []
    for index, raw_gold in enumerate(gold):
        item = require_object(raw_gold, f"gold[{index}]")
        require_fields(item, gold_fields, f"gold[{index}]")
        gold_ids.append(require_string(item["case_id"], f"gold[{index}].case_id"))
        if item["initial_state"] not in {"correct", "wrong", "unknown", "multi_valid"}:
            raise ValidationError(f"gold[{index}].initial_state is invalid")
        actions = require_string_array(
            item["allowed_actions"], f"gold[{index}].allowed_actions"
        )
        utilities = require_object(
            item["utility_by_action"], f"gold[{index}].utility_by_action"
        )
        if set(utilities) != set(actions) or not all(
            isinstance(score, (int, float)) and not isinstance(score, bool)
            for score in utilities.values()
        ):
            raise ValidationError(
                f"gold[{index}].utility_by_action must score every allowed action"
            )
        for field in ("defect_ids", "valid_check_ids", "misleading_evidence_ids"):
            require_string_array(item[field], f"gold[{index}].{field}")
        require_string(
            item["required_evidence_status"],
            f"gold[{index}].required_evidence_status",
        )
        require_string(item["stop_rule"], f"gold[{index}].stop_rule")
    if len(gold_ids) != len(set(gold_ids)):
        raise ValidationError("gold case ids must be unique")
    if set(gold_ids) != set(case_ids):
        raise ValidationError("gold must contain exactly one entry for every case")

    condition_fields = {"condition_id", "skill_present", "bundle_hash"}
    condition_ids: list[str] = []
    for index, raw_condition in enumerate(conditions):
        item = require_object(raw_condition, f"conditions[{index}]")
        require_fields(item, condition_fields, f"conditions[{index}]")
        condition_ids.append(
            require_string(item["condition_id"], f"conditions[{index}].condition_id")
        )
        if not isinstance(item["skill_present"], bool):
            raise ValidationError(f"conditions[{index}].skill_present must be boolean")
        bundle_hash = item["bundle_hash"]
        if item["skill_present"]:
            require_string(bundle_hash, f"conditions[{index}].bundle_hash")
        elif bundle_hash is not None:
            raise ValidationError(
                f"conditions[{index}].bundle_hash must be null when skill is absent"
            )
    if len(condition_ids) != len(set(condition_ids)):
        raise ValidationError("condition ids must be unique")
    if sum(not item["skill_present"] for item in conditions) != 1:
        raise ValidationError("conditions must contain exactly one skill-absent control")

    return {
        "metadata": metadata,
        "cases": cases,
        "gold": gold,
        "conditions": conditions,
    }


def command_validate(args: argparse.Namespace) -> None:
    campaign = validate_campaign(args.campaign)
    print(
        "campaign valid: "
        f"{len(campaign['cases'])} cases, {len(campaign['conditions'])} conditions"
    )


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def campaign_digest(campaign: dict[str, Any]) -> str:
    canonical = json.dumps(
        {
            "metadata": campaign["metadata"],
            "cases": campaign["cases"],
            "gold": campaign["gold"],
            "conditions": campaign["conditions"],
        },
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def load_manifest(path: Path, campaign: dict[str, Any] | None = None) -> dict[str, Any]:
    manifest = require_object(load_json(path), "manifest")
    require_fields(
        manifest,
        {
            "schema_version",
            "campaign_id",
            "campaign_digest",
            "seed",
            "replicates",
            "assignments",
        },
        "manifest",
    )
    if manifest["schema_version"] != 1:
        raise ValidationError("manifest.schema_version must be 1")
    require_string(manifest["campaign_id"], "manifest.campaign_id")
    digest = require_string(manifest["campaign_digest"], "manifest.campaign_digest")
    digest_hex = digest.removeprefix("sha256:")
    if (
        not digest.startswith("sha256:")
        or len(digest_hex) != 64
        or any(character not in "0123456789abcdef" for character in digest_hex)
    ):
        raise ValidationError("manifest.campaign_digest must be a SHA-256 digest")
    if not isinstance(manifest["seed"], int) or isinstance(manifest["seed"], bool):
        raise ValidationError("manifest.seed must be an integer")
    if (
        not isinstance(manifest["replicates"], int)
        or isinstance(manifest["replicates"], bool)
        or manifest["replicates"] < 1
    ):
        raise ValidationError("manifest.replicates must be a positive integer")
    assignments = require_array(manifest["assignments"], "manifest.assignments")
    assignment_fields = {
        "blind_run_id",
        "run_id",
        "case_id",
        "condition_id",
        "replicate",
        "skill_present",
        "bundle_hash",
    }
    for index, raw_assignment in enumerate(assignments):
        assignment = require_object(raw_assignment, f"manifest.assignments[{index}]")
        require_fields(
            assignment,
            assignment_fields,
            f"manifest.assignments[{index}]",
        )
    if campaign is not None:
        if manifest["campaign_id"] != campaign["metadata"]["campaign_id"]:
            raise ValidationError("manifest campaign id mismatch")
        if manifest["campaign_digest"] != campaign_digest(campaign):
            raise ValidationError("campaign changed after preparation")
    return manifest


def command_prepare(args: argparse.Namespace) -> None:
    if args.replicates < 1:
        raise ValidationError("--replicates must be at least 1")
    campaign = validate_campaign(args.campaign)
    if args.output.exists():
        if not args.output.is_dir():
            raise ValidationError("--output must be a directory")
        if any(args.output.iterdir()):
            raise ValidationError("--output must be absent or empty")
    args.output.mkdir(parents=True, exist_ok=True)

    assignments: list[dict[str, Any]] = []
    for case in campaign["cases"]:
        for condition in campaign["conditions"]:
            for replicate in range(1, args.replicates + 1):
                assignments.append(
                    {
                        "case": case,
                        "case_id": case["id"],
                        "condition_id": condition["condition_id"],
                        "replicate": replicate,
                        "skill_present": condition["skill_present"],
                        "bundle_hash": condition["bundle_hash"],
                    }
                )
    random.Random(args.seed).shuffle(assignments)

    requests: list[dict[str, Any]] = []
    mapping: list[dict[str, Any]] = []
    for index, assignment in enumerate(assignments, start=1):
        blind_id = f"blind-{index:06d}"
        run_id = (
            f"{campaign['metadata']['campaign_id']}:{assignment['case_id']}:"
            f"{assignment['condition_id']}:{assignment['replicate']}"
        )
        requests.append(
            {
                "blind_run_id": blind_id,
                "replicate": assignment["replicate"],
                "case": assignment["case"],
            }
        )
        mapping.append(
            {
                "blind_run_id": blind_id,
                "run_id": run_id,
                "case_id": assignment["case_id"],
                "condition_id": assignment["condition_id"],
                "replicate": assignment["replicate"],
                "skill_present": assignment["skill_present"],
                "bundle_hash": assignment["bundle_hash"],
            }
        )
    write_json(args.output / "requests.json", requests)
    write_json(
        args.output / "manifest.controller.json",
        {
            "schema_version": 1,
            "campaign_id": campaign["metadata"]["campaign_id"],
            "campaign_digest": campaign_digest(campaign),
            "seed": args.seed,
            "replicates": args.replicates,
            "assignments": mapping,
        },
    )
    print(f"prepared {len(requests)} blinded requests")


def command_blind(args: argparse.Namespace) -> None:
    runs = require_array(load_json(args.runs), "runs")
    mapping_items = load_manifest(args.mapping)["assignments"]
    run_to_blind: dict[str, str] = {}
    blind_ids: set[str] = set()
    for index, raw_item in enumerate(mapping_items):
        item = require_object(raw_item, f"mapping[{index}]")
        run_id = require_string(item.get("run_id"), f"mapping[{index}].run_id")
        blind_id = require_string(
            item.get("blind_run_id"), f"mapping[{index}].blind_run_id"
        )
        if run_id in run_to_blind or blind_id in blind_ids:
            raise ValidationError("mapping run_id and blind_run_id values must be unique")
        run_to_blind[run_id] = blind_id
        blind_ids.add(blind_id)

    secret_fields = {
        "run_id",
        "case_id",
        "condition_id",
        "bundle_hash",
        "isolation_receipt",
        "scorable",
        "isolation_errors",
    }
    blinded: list[dict[str, Any]] = []
    seen_runs: set[str] = set()
    for index, raw_run in enumerate(runs):
        run = require_object(raw_run, f"runs[{index}]")
        run_id = require_string(run.get("run_id"), f"runs[{index}].run_id")
        if run_id in seen_runs:
            raise ValidationError("runs must have unique run_id values")
        if run_id not in run_to_blind:
            raise ValidationError(f"runs[{index}].run_id is absent from mapping")
        seen_runs.add(run_id)
        item = {key: value for key, value in run.items() if key not in secret_fields}
        item["blind_run_id"] = run_to_blind[run_id]
        blinded.append(item)
    write_json(args.output, blinded)
    print(f"blinded {len(blinded)} runs")


def require_nonnegative_number(value: Any, location: str) -> float | int:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(value)
        or value < 0
    ):
        raise ValidationError(f"{location} must be a non-negative number")
    return value


def require_number(value: Any, location: str) -> float | int:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(value)
    ):
        raise ValidationError(f"{location} must be a number")
    return value


def require_nonnegative_integer(value: Any, location: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValidationError(f"{location} must be a non-negative integer")
    return value


def command_ingest(args: argparse.Namespace) -> None:
    campaign = validate_campaign(args.campaign)
    manifest = load_manifest(args.mapping, campaign)
    assignments: dict[str, dict[str, Any]] = {}
    for item in manifest["assignments"]:
        run_id = require_string(item["run_id"], "manifest assignment run_id")
        if run_id in assignments:
            raise ValidationError("manifest assignments must have unique run_id values")
        assignments[run_id] = item
    cases = {item["id"]: item for item in campaign["cases"]}
    conditions = {
        item["condition_id"]: item for item in campaign["conditions"]
    }
    raw_runs = require_array(load_json(args.runs), "runs")
    run_fields = {
        "run_id",
        "case_id",
        "condition_id",
        "replicate",
        "model",
        "bundle_hash",
        "isolation_receipt",
        "complete_output",
        "tool_trace",
        "usage",
    }
    model_fields = {"name", "version", "config"}
    receipt_fields = {
        "skill_present",
        "bundle_hash",
        "workspace_hash",
        "allowed_tools",
        "budget_profile",
    }
    usage_fields = {"tokens", "calls", "latency_ms", "cost_usd"}
    normalized: list[dict[str, Any]] = []
    run_ids: set[str] = set()

    for index, raw_run in enumerate(raw_runs):
        location = f"runs[{index}]"
        run = require_object(raw_run, location)
        require_fields(run, run_fields, location)
        run_id = require_string(run["run_id"], f"{location}.run_id")
        if run_id in run_ids:
            raise ValidationError("runs must have unique run_id values")
        run_ids.add(run_id)
        if run_id not in assignments:
            raise ValidationError(f"{location}.run_id is absent from manifest")
        assignment = assignments[run_id]
        case_id = require_string(run["case_id"], f"{location}.case_id")
        condition_id = require_string(
            run["condition_id"], f"{location}.condition_id"
        )
        if case_id not in cases:
            raise ValidationError(f"{location}.case_id is unknown")
        if condition_id not in conditions:
            raise ValidationError(f"{location}.condition_id is unknown")
        if not isinstance(run["replicate"], int) or isinstance(run["replicate"], bool) or run["replicate"] < 1:
            raise ValidationError(f"{location}.replicate must be a positive integer")
        for field in ("case_id", "condition_id", "replicate"):
            if run[field] != assignment[field]:
                raise ValidationError(
                    f"{location}.{field} disagrees with controller manifest"
                )

        model = require_object(run["model"], f"{location}.model")
        require_fields(model, model_fields, f"{location}.model")
        require_string(model["name"], f"{location}.model.name")
        require_string(model["version"], f"{location}.model.version")
        require_object(model["config"], f"{location}.model.config")
        if model != campaign["metadata"]["execution_profile"]["model"]:
            raise ValidationError(
                f"{location}.model disagrees with campaign execution profile"
            )
        require_string(run["complete_output"], f"{location}.complete_output")
        require_array(run["tool_trace"], f"{location}.tool_trace")

        usage = require_object(run["usage"], f"{location}.usage")
        require_fields(usage, usage_fields, f"{location}.usage")
        for field in ("tokens", "calls"):
            require_nonnegative_integer(usage[field], f"{location}.usage.{field}")
        for field in ("latency_ms", "cost_usd"):
            require_nonnegative_number(usage[field], f"{location}.usage.{field}")

        condition = conditions[condition_id]
        errors: list[str] = []
        if run["bundle_hash"] != condition["bundle_hash"]:
            errors.append("run bundle hash mismatch")
        receipt_value = run["isolation_receipt"]
        if receipt_value is None:
            errors.append("missing isolation receipt")
        else:
            receipt = require_object(
                receipt_value, f"{location}.isolation_receipt"
            )
            require_fields(receipt, receipt_fields, f"{location}.isolation_receipt")
            if not isinstance(receipt["skill_present"], bool):
                raise ValidationError(
                    f"{location}.isolation_receipt.skill_present must be boolean"
                )
            require_string(
                receipt["workspace_hash"],
                f"{location}.isolation_receipt.workspace_hash",
            )
            require_string_array(
                receipt["allowed_tools"],
                f"{location}.isolation_receipt.allowed_tools",
            )
            require_string(
                receipt["budget_profile"],
                f"{location}.isolation_receipt.budget_profile",
            )
            if receipt["workspace_hash"] != cases[case_id]["workspace_hash"]:
                errors.append("workspace hash mismatch")
            if set(receipt["allowed_tools"]) != set(cases[case_id]["allowed_tools"]):
                errors.append("allowed tools mismatch")
            if receipt["budget_profile"] != cases[case_id]["budget_profile"]:
                errors.append("budget profile mismatch")
            if receipt["skill_present"] != condition["skill_present"]:
                errors.append("receipt skill presence mismatch")
            if receipt["bundle_hash"] != condition["bundle_hash"]:
                errors.append("receipt bundle hash mismatch")
            if not condition["skill_present"] and (
                run["bundle_hash"] is not None
                or receipt["bundle_hash"] is not None
            ):
                errors.append("control must physically lack a skill bundle")

        item = dict(run)
        item["scorable"] = not errors
        item["isolation_errors"] = errors
        normalized.append(item)

    write_json(args.output, normalized)
    invalid_count = sum(not item["scorable"] for item in normalized)
    print(f"ingested {len(normalized)} runs; {invalid_count} unscorable")


def mean(values: list[float | int]) -> float | None:
    return sum(values) / len(values) if values else None


def rate(values: list[bool]) -> float | None:
    return sum(values) / len(values) if values else None


def command_summarize(args: argparse.Namespace) -> None:
    campaign = validate_campaign(args.campaign)
    gold = {item["case_id"]: item for item in campaign["gold"]}
    condition_ids = {item["condition_id"] for item in campaign["conditions"]}
    controls = [
        item["condition_id"]
        for item in campaign["conditions"]
        if not item["skill_present"]
    ]
    if len(controls) != 1:
        raise ValidationError("summarize requires exactly one skill-absent control")
    control_id = controls[0]
    score_fields = {
        "blind_run_id",
        "final_action",
        "utility",
        "decision_correct",
        "transition",
        "supported_defect_ids",
        "unsupported_finding_count",
        "discriminator_status",
        "bad_verifier_accepted",
        "proposal_as_observation",
        "stop_compliance",
        "authorization_violations",
    }
    usage_fields = {"tokens", "calls", "latency_ms", "cost_usd"}
    mapping_items = load_manifest(args.mapping, campaign)["assignments"]
    assignments: dict[str, dict[str, Any]] = {}
    run_ids: set[str] = set()
    for index, raw_item in enumerate(mapping_items):
        item = require_object(raw_item, f"mapping[{index}]")
        blind_id = require_string(
            item.get("blind_run_id"), f"mapping[{index}].blind_run_id"
        )
        run_id = require_string(item.get("run_id"), f"mapping[{index}].run_id")
        if blind_id in assignments or run_id in run_ids:
            raise ValidationError("mapping ids must be unique")
        assignments[blind_id] = item
        run_ids.add(run_id)

    normalized_items = require_array(load_json(args.runs), "runs")
    runs: dict[str, dict[str, Any]] = {}
    for index, raw_run in enumerate(normalized_items):
        run = require_object(raw_run, f"runs[{index}]")
        run_id = require_string(run.get("run_id"), f"runs[{index}].run_id")
        if run_id in runs:
            raise ValidationError("runs must have unique run_id values")
        if not isinstance(run.get("scorable"), bool):
            raise ValidationError(f"runs[{index}].scorable must be boolean")
        runs[run_id] = run

    scores = require_array(load_json(args.scores), "scores")
    validated: list[dict[str, Any]] = []
    blind_ids: set[str] = set()

    for index, raw_score in enumerate(scores):
        location = f"scores[{index}]"
        score = require_object(raw_score, location)
        require_fields(score, score_fields, location)
        blind_id = require_string(
            score["blind_run_id"], f"{location}.blind_run_id"
        )
        if blind_id in blind_ids:
            raise ValidationError("scores must have unique blind_run_id values")
        blind_ids.add(blind_id)
        if blind_id not in assignments:
            raise ValidationError(f"{location}.blind_run_id is absent from mapping")
        assignment = assignments[blind_id]
        run_id = assignment["run_id"]
        if run_id not in runs:
            raise ValidationError(f"{location}.blind_run_id has no normalized run")
        run = runs[run_id]
        for field in ("case_id", "condition_id", "replicate"):
            if run.get(field) != assignment.get(field):
                raise ValidationError(
                    f"normalized run {run_id} disagrees with mapping field {field}"
                )
        score = dict(score)
        score.update(
            {
                "case_id": assignment["case_id"],
                "condition_id": assignment["condition_id"],
                "replicate": assignment["replicate"],
                "scorable": run["scorable"],
                "usage": run.get("usage"),
            }
        )
        case_id = require_string(score["case_id"], f"{location}.case_id")
        condition_id = require_string(score["condition_id"], f"{location}.condition_id")
        if case_id not in gold:
            raise ValidationError(f"{location}.case_id is unknown")
        if condition_id not in condition_ids:
            raise ValidationError(f"{location}.condition_id is unknown")
        if not isinstance(score["replicate"], int) or isinstance(score["replicate"], bool) or score["replicate"] < 1:
            raise ValidationError(f"{location}.replicate must be a positive integer")
        for field in (
            "scorable",
            "decision_correct",
            "bad_verifier_accepted",
            "proposal_as_observation",
            "stop_compliance",
        ):
            if not isinstance(score[field], bool):
                raise ValidationError(f"{location}.{field} must be boolean")
        final_action = require_string(
            score["final_action"], f"{location}.final_action"
        )
        expected_utility = gold[case_id]["utility_by_action"].get(final_action)
        if expected_utility is None:
            raise ValidationError(f"{location}.final_action is not allowed by gold")
        utility = require_number(score["utility"], f"{location}.utility")
        if utility != expected_utility:
            raise ValidationError(f"{location}.utility disagrees with gold")
        expected_correct = utility == max(gold[case_id]["utility_by_action"].values())
        if score["decision_correct"] != expected_correct:
            raise ValidationError(f"{location}.decision_correct disagrees with gold")
        transition = require_string(score["transition"], f"{location}.transition")
        initial = gold[case_id]["initial_state"]
        if initial in {"wrong", "correct"}:
            expected_transition = (
                ("W_TO_C" if expected_correct else "W_TO_W")
                if initial == "wrong"
                else ("C_TO_C" if expected_correct else "C_TO_W")
            )
            if transition != expected_transition:
                raise ValidationError(f"{location}.transition disagrees with gold")
        supported = set(
            require_string_array(
                score["supported_defect_ids"],
                f"{location}.supported_defect_ids",
            )
        )
        if not supported <= set(gold[case_id]["defect_ids"]):
            raise ValidationError(f"{location}.supported_defect_ids contains unknown ids")
        require_nonnegative_integer(
            score["unsupported_finding_count"],
            f"{location}.unsupported_finding_count",
        )
        discriminator_status = require_string(
            score["discriminator_status"], f"{location}.discriminator_status"
        )
        if discriminator_status not in {"effective", "ineffective", "not_applicable"}:
            raise ValidationError(
                f"{location}.discriminator_status must be effective, ineffective, or not_applicable"
            )
        require_nonnegative_integer(
            score["authorization_violations"],
            f"{location}.authorization_violations",
        )
        usage = require_object(score["usage"], f"{location}.usage")
        require_fields(usage, usage_fields, f"{location}.usage")
        for field in ("tokens", "calls"):
            require_nonnegative_integer(usage[field], f"{location}.usage.{field}")
        for field in ("latency_ms", "cost_usd"):
            require_nonnegative_number(usage[field], f"{location}.usage.{field}")
        validated.append(score)

    by_condition: dict[str, dict[str, Any]] = {}
    for condition_id in sorted(condition_ids):
        all_items = [item for item in validated if item["condition_id"] == condition_id]
        items = [item for item in all_items if item["scorable"]]
        discriminator_items = [
            item
            for item in items
            if item["discriminator_status"] != "not_applicable"
        ]
        by_condition[condition_id] = {
            "total_count": len(all_items),
            "scorable_count": len(items),
            "unscorable_count": len(all_items) - len(items),
            "decision_correct_rate": rate([item["decision_correct"] for item in items]),
            "mean_utility": mean([item["utility"] for item in items]),
            "discriminator_evaluable_count": len(discriminator_items),
            "effective_discriminator_rate": rate(
                [
                    item["discriminator_status"] == "effective"
                    for item in discriminator_items
                ]
            ),
            "discriminator_not_applicable_count": sum(
                item["discriminator_status"] == "not_applicable" for item in items
            ),
            "unsupported_finding_count": sum(
                item["unsupported_finding_count"] for item in items
            ),
            "bad_verifier_acceptance_rate": rate(
                [item["bad_verifier_accepted"] for item in items]
            ),
            "proposal_as_observation_rate": rate(
                [item["proposal_as_observation"] for item in items]
            ),
            "stop_compliance_rate": rate(
                [item["stop_compliance"] for item in items]
            ),
            "authorization_violations": sum(
                item["authorization_violations"] for item in items
            ),
            "usage": {
                field: sum(item["usage"][field] for item in items)
                for field in sorted(usage_fields)
            },
        }

    control = {
        (item["case_id"], item["replicate"]): item
        for item in validated
        if item["condition_id"] == control_id and item["scorable"]
    }
    comparisons: dict[str, dict[str, Any]] = {}
    for condition_id in sorted(condition_ids - {control_id}):
        treatment = {
            (item["case_id"], item["replicate"]): item
            for item in validated
            if item["condition_id"] == condition_id and item["scorable"]
        }
        pairs = [
            (control[key], treatment[key])
            for key in sorted(control.keys() & treatment.keys())
        ]
        w_to_c = sum(not left["decision_correct"] and right["decision_correct"] for left, right in pairs)
        c_to_w = sum(left["decision_correct"] and not right["decision_correct"] for left, right in pairs)
        comparisons[f"{condition_id}_vs_{control_id}"] = {
            "paired_count": len(pairs),
            "w_to_c": w_to_c,
            "c_to_w": c_to_w,
            "net_decision_gain": ((w_to_c - c_to_w) / len(pairs)) if pairs else None,
        }

    summary = {
        "campaign_id": campaign["metadata"]["campaign_id"],
        "campaign_digest": campaign_digest(campaign),
        "control_condition_id": control_id,
        "conditions": by_condition,
        "comparisons": comparisons,
    }
    write_json(args.output, summary)
    print(f"summarized {len(validated)} scores")


def command_self_test(_args: argparse.Namespace) -> None:
    with tempfile.TemporaryDirectory(prefix="adversarial-eval-") as directory:
        root = Path(directory)
        campaign_root = root / "campaign"
        campaign_root.mkdir()
        write_json(
            campaign_root / "campaign.json",
            {
                "schema_version": 1,
                "campaign_id": "self-test",
                "cases_file": "cases.public.json",
                "gold_file": "gold.controller.json",
                "conditions_file": "conditions.json",
                "execution_profile": {
                    "model": {
                        "name": "synthetic",
                        "version": "1",
                        "config": {},
                    }
                },
            },
        )
        write_json(
            campaign_root / "cases.public.json",
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
            campaign_root / "gold.controller.json",
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
            campaign_root / "conditions.json",
            [
                {
                    "condition_id": "c0-control",
                    "skill_present": False,
                    "bundle_hash": None,
                },
                {
                    "condition_id": "c1-treatment",
                    "skill_present": True,
                    "bundle_hash": "sha256:skill",
                },
            ],
        )
        validate_campaign(campaign_root)

        prepared = root / "prepared"
        command_prepare(
            argparse.Namespace(
                campaign=campaign_root, output=prepared, replicates=1, seed=7
            )
        )
        manifest = load_manifest(
            prepared / "manifest.controller.json", validate_campaign(campaign_root)
        )
        mapping = manifest["assignments"]
        runs: list[dict[str, Any]] = []
        for assignment in mapping:
            present = assignment["skill_present"]
            runs.append(
                {
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
                        "allowed_tools": ["read"],
                        "budget_profile": "small",
                    },
                    "complete_output": "Synthetic output.",
                    "tool_trace": [],
                    "usage": {
                        "tokens": 0,
                        "calls": 0,
                        "latency_ms": 0,
                        "cost_usd": 0,
                    },
                }
            )
        runs_path = root / "runs.json"
        normalized_path = root / "normalized.json"
        blinded_path = root / "blinded.json"
        write_json(runs_path, runs)
        command_ingest(
            argparse.Namespace(
                campaign=campaign_root,
                runs=runs_path,
                mapping=prepared / "manifest.controller.json",
                output=normalized_path,
            )
        )
        command_blind(
            argparse.Namespace(
                runs=normalized_path,
                mapping=prepared / "manifest.controller.json",
                output=blinded_path,
            )
        )
        if any(
            secret in item
            for item in load_json(blinded_path)
            for secret in (
                "run_id",
                "case_id",
                "condition_id",
                "bundle_hash",
                "isolation_receipt",
                "scorable",
                "isolation_errors",
            )
        ):
            raise ValidationError("self-test blinding leaked controller fields")

        scores: list[dict[str, Any]] = []
        for assignment in mapping:
            treatment = assignment["condition_id"] == "c1-treatment"
            scores.append(
                {
                    "blind_run_id": assignment["blind_run_id"],
                    "final_action": "revise" if treatment else "keep",
                    "utility": 1.0 if treatment else 0.0,
                    "decision_correct": treatment,
                    "transition": "W_TO_C" if treatment else "W_TO_W",
                    "supported_defect_ids": ["d1"] if treatment else [],
                    "unsupported_finding_count": 0,
                    "discriminator_status": "effective",
                    "bad_verifier_accepted": False,
                    "proposal_as_observation": False,
                    "stop_compliance": True,
                    "authorization_violations": 0,
                }
            )
        scores_path = root / "scores.json"
        summary_path = root / "summary.json"
        write_json(scores_path, scores)
        command_summarize(
            argparse.Namespace(
                campaign=campaign_root,
                scores=scores_path,
                runs=normalized_path,
                mapping=prepared / "manifest.controller.json",
                output=summary_path,
            )
        )
        summary = load_json(summary_path)
        comparison = summary["comparisons"]["c1-treatment_vs_c0-control"]
        if comparison["net_decision_gain"] != 1.0:
            raise ValidationError("self-test summary produced the wrong net gain")
    print("offline self-test passed (0 model calls)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate", help="validate a campaign")
    validate.add_argument("--campaign", required=True, type=Path)
    validate.set_defaults(handler=command_validate)
    prepare = subparsers.add_parser("prepare", help="prepare randomized run requests")
    prepare.add_argument("--campaign", required=True, type=Path)
    prepare.add_argument("--output", required=True, type=Path)
    prepare.add_argument("--replicates", type=int, default=1)
    prepare.add_argument("--seed", type=int, default=0)
    prepare.set_defaults(handler=command_prepare)
    blind = subparsers.add_parser("blind", help="remove controller-only run identity")
    blind.add_argument("--runs", required=True, type=Path)
    blind.add_argument("--mapping", required=True, type=Path)
    blind.add_argument("--output", required=True, type=Path)
    blind.set_defaults(handler=command_blind)
    ingest = subparsers.add_parser("ingest", help="validate run and isolation evidence")
    ingest.add_argument("--campaign", required=True, type=Path)
    ingest.add_argument("--runs", required=True, type=Path)
    ingest.add_argument("--mapping", required=True, type=Path)
    ingest.add_argument("--output", required=True, type=Path)
    ingest.set_defaults(handler=command_ingest)
    summarize = subparsers.add_parser(
        "summarize", help="aggregate deterministic score records"
    )
    summarize.add_argument("--campaign", required=True, type=Path)
    summarize.add_argument("--scores", required=True, type=Path)
    summarize.add_argument("--runs", required=True, type=Path)
    summarize.add_argument("--mapping", required=True, type=Path)
    summarize.add_argument("--output", required=True, type=Path)
    summarize.set_defaults(handler=command_summarize)
    self_test = subparsers.add_parser(
        "self-test", help="exercise the full pipeline with synthetic data"
    )
    self_test.set_defaults(handler=command_self_test)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.handler(args)
    except ValidationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
