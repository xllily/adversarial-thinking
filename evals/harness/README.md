# Offline evaluation harness

This directory contains a standard-library-only controller for prospective evaluations. It makes no model, network, provider, or paid calls. An external runner is responsible for executing agents and producing run records; a human or separately authorized judge is responsible for producing score records.

The controller keeps three boundaries explicit:

- Public case data may enter the target workspace.
- Condition assignments, bundle hashes, isolation receipts, and run identities remain controller-only.
- Gold answers remain controller-only and are used only to validate final score records.

## Commands

Run commands from the repository root:

```sh
python3 evals/harness/eval.py validate --campaign CAMPAIGN_DIR
python3 evals/harness/eval.py prepare --campaign CAMPAIGN_DIR --output evals/.runs/prepared --replicates 3 --seed 20260904
python3 evals/harness/eval.py ingest --campaign CAMPAIGN_DIR --runs RAW_RUNS.json --mapping evals/.runs/prepared/manifest.controller.json --output NORMALIZED_RUNS.json
python3 evals/harness/eval.py blind --runs NORMALIZED_RUNS.json --mapping evals/.runs/prepared/manifest.controller.json --output BLINDED_RUNS.json
python3 evals/harness/eval.py summarize --campaign CAMPAIGN_DIR --scores SCORES.json --runs NORMALIZED_RUNS.json --mapping evals/.runs/prepared/manifest.controller.json --output SUMMARY.json
python3 evals/harness/eval.py self-test
```

`prepare` writes two files. `requests.json` is safe for the target runner: it contains an opaque blind id, replicate number, and public case. `manifest.controller.json` is not safe for the target: it records the canonical campaign digest and maps blind ids to condition assignments, bundle hashes, and internal run ids.

`ingest` verifies the campaign digest, frozen model profile, and runner assignment fields against the controller manifest, then applies isolation checks. The isolation receipt must also reproduce the case's allowed tools and budget profile. Structurally malformed, misassigned, or model-drifted records exit with status 2. A structurally valid run with a missing or mismatched isolation claim is retained but marked `scorable: false` with explicit `isolation_errors`.

`blind` removes the top-level controller identity and isolation fields before outputs are given to a judge. `summarize` rejoins scores to the controller manifest and normalized runs by blind id. It derives case, condition, replicate, scorable status, and usage from those controller-owned artifacts; checks action utility, correctness, and transition against gold data; then reports per-condition metrics, effective discriminator rate, and paired net decision gain against the single skill-absent control. The summary includes the verified campaign digest.

Generated raw runs belong under `evals/.runs/`, which is ignored by Git. Do not put gold files, controller manifests, candidate patches, or globally installed skills in target workspaces.

## Campaign layout

A campaign directory contains:

```text
campaign.json
cases.public.json
conditions.json
gold.controller.json
```

`campaign.json` names the other three files, declares `schema_version: 1`, and freezes an `execution_profile.model` object containing `name`, `version`, and `config`. Validation is strict: unknown fields, missing fields, duplicate ids, invalid references, path traversal, and any condition set without exactly one skill-absent control are rejected. The precise runner-side record shapes are defined in [`adapter-contract.md`](adapter-contract.md).

## Verification

```sh
python3 -m unittest evals.harness.test_eval -v
python3 evals/harness/eval.py self-test
```
