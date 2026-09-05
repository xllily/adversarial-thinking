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

The first fixture-backed source campaign is
[`../campaigns/t1_pilot_v1/`](../campaigns/t1_pilot_v1/). Its template must be
materialized with an exact model profile before `prepare`; the tracked template
itself is not behavioral evidence.

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

## Independent provider probe (T1 preflight)

`provider.py` is a separate, potentially networked CLI. The controller `eval.py`
remains offline. The adapter currently implements only the configured
`openai-chat` protocol; it does not produce evaluation records or isolation
receipts. A successful probe proves only a synthetic tool handshake at that
endpoint. It does not validate C0 isolation, agent behavior, Skill effects,
immutable model versions, prices, or billing.

The implementation follows the official [Chat Completions create contract](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)
(accessed 2026-09-05): named function choice, matching `tool_call_id`, and
`max_completion_tokens` (including reasoning tokens). Compatibility with the
configured third-party target is unverified. Unsupported parameters fail without
switching to `max_tokens`, changing model/protocol, following redirects, or retrying.

Configuration is read literally from `evals/.runs/t1-provider.env` by the Python
controller itself, never sourced or exported to a child process. It requires
an owned regular file with mode 600, rejects symlinks/duplicate fields/expansion
syntax, and allows exactly these fields:

```text
T1_PROTOCOL=openai-chat
T1_ENDPOINT_URL=http://127.0.0.1:9507/v1/chat/completions
T1_MODEL_ID=YOUR_MODEL_ID
T1_MODEL_VERSION=unknown
T1_API_KEY=YOUR_KEY
T1_SUPPORTS_TOOL_CALLS=true
```

HTTPS is required except for literal loopback IPs. The exact endpoint path must
be `/v1/chat/completions`; credentials, query, and fragment are prohibited.
Use `unknown` when no immutable version is known. A declared version and returned
model name are not immutable-version proof; tool support is only a declaration.
Do not paste real keys into commands or tracked files.

Offline commands, from the repository root:

```sh
python3 -m unittest evals.harness.test_provider -v
python3 evals/harness/provider.py preflight
python3 evals/harness/provider.py plan
```

`plan` exclusively creates ignored `evals/.runs/t1-probe-plan.json`. It includes
the target, configuration fingerprint (including credential rotation), adapter
source digest, and budget. Review it and obtain explicit user authorization
before executing this command with the reviewed fingerprint:

```sh
python3 evals/harness/provider.py probe \
  --authorize-config-sha256 REVIEWED_CONFIG_SHA256
```

Budget: at most 2 POST requests, 256 completion tokens each (512 total), 4096
request bytes and 65536 response bytes per request, 30-second socket timeout,
zero retries and redirects. Socket timeout is an inactivity timeout, not a hard
wall-clock deadline. Input token count is not known before the provider returns
usage; the byte limit bounds payload size, not billed tokens. Price and cost are
unknown (`null`), never zero-filled. No campaign fixtures or secrets enter model
messages. Only the fixed `probe_nonce` function is handled; arguments must be
exactly `{}`. A fresh nonce is generated after validating the first response and
must be returned exactly in a complete second response.

Before sending, an exclusive durable `probe-CONFIG_SHA256` ledger is claimed and
each attempt is fsynced. Failure/interruption consumes the attempt; the same
configuration cannot be replayed, including after success. Never delete the
ledger to retry: inspect it and request separate authorization for any recovery.
Missing usage is retained as `null`; partial failure evidence is diagnostic only.
The ledger stores only local attempt metadata and normalized usage, not raw
provider bodies or error text. Later isolation shakedown and pilot runs require
separate authorization and an actual runner.

## T1 isolation and agent shakedown

The next operational step is documented in [shakedown.md](shakedown.md).
`isolation.py` performs a zero-model-call Docker rehearsal of eight isolated
workspaces. `shakedown.py` provides the separately authorized diagnostic model
loop. Its results remain outside T0 scoring while version/cost/budget evidence
is incomplete.
