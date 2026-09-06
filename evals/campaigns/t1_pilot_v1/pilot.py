#!/usr/bin/env python3
"""Build and verify the T1 fixture-backed pilot without model calls."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


class PilotError(ValueError):
    pass


SOURCE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = SOURCE_ROOT.parents[2]
EXPECTED_CONDITIONS = {
    "c0-skill-absent",
    "c1-current-0.1.1",
    "c2-discriminate-label",
    "c3-operational-discriminator",
}
PROFILE_HASH_FIELD = "campaign_budget_profiles_hash"


def reject_json_constant(value: str) -> None:
    raise PilotError(f"non-finite JSON number is not allowed: {value}")


def load_json(path: Path) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"), parse_constant=reject_json_constant
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise PilotError(f"cannot read {path}: {exc}") from exc


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def safe_relative(value: Any, field: str) -> Path:
    if not isinstance(value, str) or not value:
        raise PilotError(f"{field} must be a non-empty relative path")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise PilotError(f"{field} must stay inside the T1 source tree")
    return path


def canonical_tree_hash(root: Path) -> str:
    if not root.is_dir():
        raise PilotError(f"tree does not exist: {root}")
    entries = list(root.rglob("*"))
    symlinks = [path for path in entries if path.is_symlink()]
    if symlinks:
        raise PilotError(f"tree must not contain symlinks: {symlinks[0]}")
    files = sorted(path for path in entries if path.is_file())
    if not files:
        raise PilotError(f"tree contains no files: {root}")
    digest = hashlib.sha256()
    for path in files:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        data = path.read_bytes()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return f"sha256:{digest.hexdigest()}"


def file_hash(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def git_blob(commit: str, relative_path: str) -> bytes:
    result = subprocess.run(
        ["git", "show", f"{commit}:{relative_path}"],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise PilotError(f"cannot read {relative_path} at {commit}: {message}")
    return result.stdout


def apply_candidate_patch(bundle: Path, patch_path: Path) -> None:
    result = subprocess.run(
        ["git", "apply", "--whitespace=error-all", str(patch_path)],
        cwd=bundle,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise PilotError(
            f"candidate patch does not apply: {patch_path}: {result.stderr.strip()}"
        )


def build_bundle(source: Path, condition_id: str, destination: Path) -> str:
    spec = load_json(source / "bundle-spec.json")
    if set(spec) != {"schema_version", "base_commit", "paths", "conditions"}:
        raise PilotError("bundle spec has an invalid shape")
    if spec["schema_version"] != 1:
        raise PilotError("bundle spec schema_version must be 1")
    if (
        not isinstance(spec["paths"], list)
        or not spec["paths"]
        or len(spec["paths"]) != len(set(spec["paths"]))
    ):
        raise PilotError("bundle spec paths must be a non-empty unique list")
    entries = {item["condition_id"]: item for item in spec["conditions"]}
    if condition_id not in entries:
        raise PilotError(f"bundle spec has no condition {condition_id}")
    destination.mkdir(parents=True, exist_ok=False)
    for index, raw_path in enumerate(spec["paths"]):
        relative_path = safe_relative(raw_path, f"bundle-spec.paths[{index}]")
        target = destination / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(git_blob(spec["base_commit"], relative_path.as_posix()))
    patch_name = entries[condition_id]["patch"]
    if patch_name is not None:
        patch_path = safe_relative(
            patch_name, f"bundle-spec.conditions[{condition_id}].patch"
        )
        apply_candidate_patch(destination, source / patch_path)
    return canonical_tree_hash(destination)


def computed_hashes(source: Path) -> dict[str, Any]:
    cases = load_json(source / "cases.public.json")
    workspaces = {
        case["id"]: canonical_tree_hash(source / "workspaces" / case["id"])
        for case in cases
    }
    bundles: dict[str, str | None] = {"c0-skill-absent": None}
    with tempfile.TemporaryDirectory(prefix="t1-pilot-bundles-") as temp_name:
        temp = Path(temp_name)
        for condition_id in sorted(EXPECTED_CONDITIONS - {"c0-skill-absent"}):
            bundles[condition_id] = build_bundle(
                source, condition_id, temp / condition_id
            )
    return {"bundles": bundles, "workspaces": workspaces}


def load_harness() -> Any:
    harness_path = REPO_ROOT / "evals" / "harness" / "eval.py"
    spec = importlib.util.spec_from_file_location("offline_eval_harness", harness_path)
    if spec is None or spec.loader is None:
        raise PilotError(f"cannot load harness: {harness_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def bind_campaign(source: Path, name: str, version: str, config: dict[str, Any]) -> dict[str, Any]:
    for value, field in ((name, "model name"), (version, "model version")):
        if not isinstance(value, str) or not value.strip():
            raise PilotError(f"{field} must be a non-empty string")
        if "BIND_WITH" in value or value == "MODEL_NAME" or value == "IMMUTABLE_MODEL_VERSION":
            raise PilotError(f"{field} is still a placeholder")
    if PROFILE_HASH_FIELD in config:
        raise PilotError(f"model config field {PROFILE_HASH_FIELD} is controller-owned")
    bound_config = dict(config)
    bound_config[PROFILE_HASH_FIELD] = file_hash(source / "budget-profiles.json")
    campaign = load_json(source / "campaign.template.json")
    campaign["execution_profile"] = {
        "model": {"name": name, "version": version, "config": bound_config}
    }
    return campaign


def verify_source(source: Path) -> dict[str, Any]:
    template = load_json(source / "campaign.template.json")
    cases = load_json(source / template["cases_file"])
    gold = load_json(source / template["gold_file"])
    conditions = load_json(source / template["conditions_file"])
    spec = load_json(source / "bundle-spec.json")
    budget_profiles = load_json(source / "budget-profiles.json")

    if len(cases) != 12:
        raise PilotError(f"T1 must contain exactly 12 pilot cases, found {len(cases)}")
    case_ids = {item["id"] for item in cases}
    if len(case_ids) != 12:
        raise PilotError("T1 case ids must be unique")
    if {item["case_id"] for item in gold} != case_ids or len(gold) != 12:
        raise PilotError("gold must contain exactly one entry per T1 case")
    condition_ids = {item["condition_id"] for item in conditions}
    if condition_ids != EXPECTED_CONDITIONS or len(conditions) != 4:
        raise PilotError("T1 must contain exactly the frozen C0-C3 conditions")
    if {item["condition_id"] for item in spec["conditions"]} != (
        EXPECTED_CONDITIONS - {"c0-skill-absent"}
    ) or len(spec["conditions"]) != 3:
        raise PilotError("bundle spec must define exactly C1-C3")
    workspace_root = source / "workspaces"
    if not workspace_root.is_dir():
        raise PilotError("workspaces directory is missing")
    workspace_entries = list(workspace_root.iterdir())
    if any(not item.is_dir() or item.is_symlink() for item in workspace_entries):
        raise PilotError("workspaces must contain only real case directories")
    if {item.name for item in workspace_entries} != case_ids:
        raise PilotError("workspace directories must match public case ids exactly")
    if (
        set(budget_profiles) != {"schema_version", "profiles"}
        or budget_profiles["schema_version"] != 1
    ):
        raise PilotError("budget profiles must use the strict version 1 shape")
    profiles = budget_profiles["profiles"]
    if not isinstance(profiles, dict) or not profiles:
        raise PilotError("budget profiles must be a non-empty object")
    profile_fields = {
        "allowed_tools",
        "max_model_calls",
        "max_total_tokens",
        "max_tool_calls",
        "max_latency_ms",
        "network_access",
        "delegated_model_calls",
    }
    used_profiles = {case["budget_profile"] for case in cases}
    if used_profiles != set(profiles):
        raise PilotError("every budget profile must exist and be used")
    for profile_id, profile in profiles.items():
        if not isinstance(profile, dict) or set(profile) != profile_fields:
            raise PilotError(f"budget profile {profile_id} has an invalid shape")
        if (
            not isinstance(profile["allowed_tools"], list)
            or not profile["allowed_tools"]
            or not all(isinstance(item, str) and item for item in profile["allowed_tools"])
            or len(profile["allowed_tools"]) != len(set(profile["allowed_tools"]))
        ):
            raise PilotError(f"budget profile {profile_id} has invalid allowed_tools")
        for field in ("max_model_calls", "max_total_tokens", "max_tool_calls", "max_latency_ms"):
            if (
                not isinstance(profile[field], int)
                or isinstance(profile[field], bool)
                or profile[field] < 1
            ):
                raise PilotError(f"budget profile {profile_id}.{field} must be positive")
        if (
            profile["network_access"] is not False
            or not isinstance(profile["delegated_model_calls"], int)
            or isinstance(profile["delegated_model_calls"], bool)
            or profile["delegated_model_calls"] != 0
        ):
            raise PilotError(f"budget profile {profile_id} must disable network and delegation")
    for case in cases:
        profile_tools = set(profiles[case["budget_profile"]]["allowed_tools"])
        if set(case["allowed_tools"]) != profile_tools:
            raise PilotError(f"case {case['id']} tools disagree with its budget profile")
    nested_skills = list(source.rglob("SKILL.md"))
    if nested_skills:
        raise PilotError("candidate source must not contain nested SKILL.md files")

    hashes = computed_hashes(source)
    for case in cases:
        actual = hashes["workspaces"][case["id"]]
        if case["workspace_hash"] != actual:
            raise PilotError(
                f"workspace hash mismatch for {case['id']}: "
                f"expected {case['workspace_hash']}, got {actual}"
            )
    expected_bundles = {
        item["condition_id"]: item["bundle_hash"] for item in conditions
    }
    if expected_bundles != hashes["bundles"]:
        raise PilotError(
            "condition bundle hashes do not match candidate materialization"
        )

    with tempfile.TemporaryDirectory(prefix="t1-pilot-campaign-") as temp_name:
        temp = Path(temp_name)
        write_json(
            temp / "campaign.json",
            bind_campaign(source, "offline-structure-check", "1", {"calls": 0}),
        )
        for filename in (
            template["cases_file"],
            template["gold_file"],
            template["conditions_file"],
        ):
            shutil.copy2(source / filename, temp / filename)
        load_harness().validate_campaign(temp)

    return {
        "campaign_id": template["campaign_id"],
        "cases": len(cases),
        "conditions": len(conditions),
        "model_calls": 0,
    }


def materialize(args: argparse.Namespace) -> None:
    source = args.source.resolve()
    output = args.output.resolve()
    result = verify_source(source)
    try:
        model_config = json.loads(
            args.model_config_json,
            parse_constant=reject_json_constant,
        )
    except json.JSONDecodeError as exc:
        raise PilotError(f"model config is not valid JSON: {exc}") from exc
    if not isinstance(model_config, dict):
        raise PilotError("model config must be a JSON object")
    if output == REPO_ROOT or REPO_ROOT in output.parents:
        raise PilotError(
            "output must stay outside the skill repository so C0 has no "
            "discoverable ancestor skill"
        )
    if output.exists():
        raise PilotError(f"output already exists: {output}")

    campaign_dir = output / "campaign"
    bundles_dir = output / "bundles"
    workspaces_dir = output / "workspaces"
    campaign_dir.mkdir(parents=True)
    bundles_dir.mkdir()
    shutil.copytree(source / "workspaces", workspaces_dir)

    template = load_json(source / "campaign.template.json")
    bound_campaign = bind_campaign(
        source, args.model_name, args.model_version, model_config
    )
    write_json(campaign_dir / "campaign.json", bound_campaign)
    for filename in (
        template["cases_file"],
        template["gold_file"],
        template["conditions_file"],
        "budget-profiles.json",
    ):
        shutil.copy2(source / filename, campaign_dir / filename)

    bundle_hashes: dict[str, str] = {}
    for condition_id in sorted(EXPECTED_CONDITIONS - {"c0-skill-absent"}):
        bundle_hashes[condition_id] = build_bundle(
            source, condition_id, bundles_dir / condition_id
        )
    load_harness().validate_campaign(campaign_dir)
    write_json(
        output / "materialization.controller.json",
        {
            "campaign_id": result["campaign_id"],
            "model": bound_campaign["execution_profile"]["model"],
            "bundle_hashes": bundle_hashes,
            "budget_profiles_hash": file_hash(source / "budget-profiles.json"),
            "model_calls": 0,
        },
    )
    print(f"materialized T1 pilot at {output} (0 model calls)")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE_ROOT)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("verify", help="verify fixtures, patches, and frozen hashes")
    subparsers.add_parser("hashes", help="print computed workspace and bundle hashes")
    materialize_parser = subparsers.add_parser(
        "materialize", help="bind an exact model profile into an ignored run directory"
    )
    materialize_parser.add_argument("--output", type=Path, required=True)
    materialize_parser.add_argument("--model-name", required=True)
    materialize_parser.add_argument("--model-version", required=True)
    materialize_parser.add_argument("--model-config-json", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        if args.command == "verify":
            result = verify_source(args.source.resolve())
            print(
                f"T1 pilot valid: {result['cases']} cases, "
                f"{result['conditions']} conditions, 0 model calls"
            )
        elif args.command == "hashes":
            print(json.dumps(computed_hashes(args.source.resolve()), indent=2, sort_keys=True))
        else:
            materialize(args)
    except (OSError, PilotError, subprocess.SubprocessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
