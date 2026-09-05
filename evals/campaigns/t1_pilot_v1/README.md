# T1 fixture-backed pilot

This directory freezes the source inputs for the first isolated C0-C3 pilot. It
contains 12 realistic, local-only target workspaces, controller-owned gold data,
and reproducible candidate patches. Building or validating it makes no model,
network, provider, or paid calls.

This is a dataset and condition freeze, not behavioral evidence. Do not report
an uplift, regression, isolation pass, or model result until separately
authorized runs have been ingested and scored.

## Frozen conditions

| Condition | Bundle |
| --- | --- |
| C0: c0-skill-absent | The target physically lacks the skill. A prompt-only disable is invalid. |
| C1: c1-current-0.1.1 | Behavioral bundle from commit 79efafc6d7fdf22cab22ca6d0ecc00d17f58b9ec. |
| C2: c2-discriminate-label | C1 plus a one-line narrative change from Disconfirm to Discriminate; no operational contract. |
| C3: c3-operational-discriminator | C1 plus prediction, evidence-status, verifier-reliability, and decision-rule requirements; the four-step order is unchanged. |

bundle-spec.json defines the behavioral bundle as SKILL.md plus the directly
referenced mode files. Candidate variants stay as controller-side patches; no
nested SKILL.md is tracked. pilot.py reconstructs each bundle from the frozen
commit and checks its canonical tree hash against conditions.json.

If the base PR changes any bundled file, update the base commit, re-review both
patches, and regenerate every affected hash before running the campaign.

## Case strata

The 12 cases cover:

- executable negative and positive verifiers;
- an unavailable future gate that must not be described as observed;
- a passing but coverage-incomplete test suite;
- a sound plan whose execution is not authorized;
- evidence that weakens both offered explanations;
- supported no-change and routine reversible negatives;
- aggressive revision pressure and an exhausted second review;
- high-confidence conflict with a deterministic check;
- a fresh critic contradicted by source/runtime evidence;
- correlated reviewers sharing one stale evidence source.

Each public prompt points to a dedicated fixture workspace. The target receives
only that workspace and its public request. gold.controller.json, condition
assignments, candidate patches, and the campaign source tree must remain outside
the target workspace.

Public case IDs and strata are domain-neutral; outcome and mechanism labels stay
in controller-owned gold. budget-profiles.json freezes equal call, token, tool,
latency, network, and delegation limits across all conditions for a given case.
Its content hash is injected into the materialized model configuration so it is
covered by the campaign digest and must be reproduced in every run record.

## Verify the freeze

From the repository root:

    python3 evals/campaigns/t1_pilot_v1/pilot.py verify
    python3 -m unittest discover -s evals/campaigns/t1_pilot_v1 -p 'test_*.py' -v

The hash is over sorted regular files using length-prefixed UTF-8 relative paths
and raw file bytes. Symlinks and empty trees are rejected. verify checks all
workspace hashes, rebuilds C1-C3 from the frozen commit, applies candidate
patches, verifies bundle hashes, rejects nested skills, and passes a temporary
campaign through the T0 strict validator.

## Bind a real execution profile

campaign.template.json is intentionally not runnable evidence. Materialize it
only after the exact runner-visible model name, immutable version, and complete
configuration are known:

    python3 evals/campaigns/t1_pilot_v1/pilot.py materialize \
      --output /tmp/adversarial-thinking-t1-pilot-v1-MODEL \
      --model-name MODEL_NAME \
      --model-version IMMUTABLE_MODEL_VERSION \
      --model-config-json '{"temperature":0}'

The output contains a harness-valid campaign directory, C1-C3 bundles, fixture
workspaces, and a controller-only materialization receipt. It refuses to
overwrite an existing output directory or write under the skill repository.
Keeping target workspaces outside every ancestor skill-discovery tree is
required for C0. The runner must mount exactly one fixture workspace and only
the assigned bundle; C0 must mount none.

Then prepare requests with the T0 controller:

    python3 evals/harness/eval.py prepare \
      --campaign /tmp/adversarial-thinking-t1-pilot-v1-MODEL/campaign \
      --output /tmp/adversarial-thinking-t1-pilot-v1-MODEL/prepared \
      --replicates 3 \
      --seed 20260904

Materialization and preparation are still zero-model-call operations. After
execution, controller-owned raw records and receipts may be copied back under
the ignored evals/.runs directory; target workspaces must not run there.

## Execution gates

The first external step should be an isolation-receipt shakedown, not a claim
about behavior:

1. Run migration-compat-01 and dual-write-06 once under C0-C3
   (8 runs) to validate physical absence/presence, bundle hashes, workspace
   hashes, tool parity, and budget parity.
2. After those receipts ingest as scorable, run a directional sentinel on six
   strata under C1 and C3 (12 runs). This can expose adapter or rubric defects
   but has no statistical interpretation.
3. Only after both gates pass, separately authorize the full
   12 cases x 3 replicates x 4 conditions = 144 runs pilot.

Freeze the blind judge procedure before viewing outputs. A future judge adapter
remains outside T1 and requires human double-scoring validation.
