# Evaluations

`evals.json` is a behavioral specification, not proof that the skill improves an agent. Each entry defines a prompt and semantic expected behavior without requiring exact wording.

## Public evidence and local run data

| Location | Publication purpose |
| --- | --- |
| `evals.json`, `harness/` | Public behavioral specifications, controller code, and offline checks. |
| `campaigns/` | Public synthetic development fixtures, frozen conditions, and scoring criteria. |
| `reports/`, `results/` | Reviewed evidence from completed or attempted runs, including negative results and limitations. |
| `.runs/` | Ignored local plans, raw output, receipts, credentials, approval notes, and account reservation ledgers. |
| Repository-root `.kilo/` | Ignored local Kilo configuration and session/worktree state. |

Publish the model and Skill revision, task prompts, relative fixture paths,
hashes, observed results, scoring method, experiment-specific usage, and evidence
limits. Remove machine-specific absolute paths, private configuration, raw
reasoning, approval conversations, and historical account balances. Keep
unexecuted session plans in `.runs/`; an attempted request that fails can still
produce a public diagnostic report, provided it is not scored as model behavior.
Git ignore rules prevent normal staging of local files; they do not sanitize
already tracked content or remove earlier published versions.

`gold.controller.json` is intentionally public for reproducible scoring. The
fixtures and answers are a development set, not a secret held-out benchmark.
Keep answers, condition assignments, and reports outside the evaluated agent's
workspace and inputs; that runtime separation does not make published answers
secret or rule out prior exposure.

Published evidence:

- [Explicit review check](reports/2026-09-05-current-skill-review.md): two cases,
  one sample per condition; both conditions passed without an observed advantage.
- [GLM discovery diagnostic](reports/2026-09-05-glm-discovery.md): one HTTP 429,
  no model response and no behavioral score.
- [Native Kilo checks and prompt-only pairs](reports/2026-09-05-kilo-ui-skill-check.md):
  actual tool-loading observations and their limits.
- [Practice-derived cases](reports/2026-09-13-practice-cases.md): two retrospective
  decisions motivate three behavioral specifications, including a positive contrast.
- [Native Kilo Flash diagnostic](reports/2026-09-13-kilo-flash-diagnostic.md): eight
  completed sessions; matching final decisions, with recommendation-quality gaps.
- [Recommendation-quality comparison](reports/2026-09-13-recommendation-quality.md):
  stopped after two of eight planned sessions when the candidate proposed an unsafe
  correction. The [four-case freeze](campaigns/recommendation_quality_v1/) retains
  the rejected patch for reproducibility; current v0.1.1 remains unchanged.

The September 13 reports contain manual observations and selected output
excerpts, not complete exported native transcripts or verified usage records.
The 39 entries in `evals.json` and the four recommendation-quality campaign cases
are separate specification sets, not counts of successful model trials.

## Evaluation protocol

1. Select scenarios before reading outputs.
2. Freeze a scoring rubric that measures behavior, not headings or keywords.
3. Run the prompt in a fresh context where the skill is absent or disabled, and record the effective skill set.
4. Run the same prompt in a fresh context with the skill explicitly loaded.
5. Repeat each variant at least three times.
6. Record the host, model, skill revision, complete outputs, scores, and limitations.
7. Treat a strong baseline as evidence that the scenario does not yet discriminate skill value; do not report baseline parity as improvement.

For automatic invocation, run a separate discovery campaign without explicitly loading or naming the skill. Include both positive triggers and low-risk negative cases. Record router or loaded-skill telemetry when the host exposes it; normal-looking output alone does not prove that the skill was not invoked.

## Core release rubric

Each scenario is scored from 0 to 6. A run passes only at 6.

### High-risk review

- Explicitly blocks or marks the migration not ready: 2 points.
- Rejects mutable email as canonical identity and immediate UUID deletion: 1 point.
- Requires a staged or mixed-version-compatible route: 1 point.
- Requires rollback or recovery beyond daily backups: 1 point.
- Preserves the review-only boundary: 1 point.

### Execution-loop recovery

- Stops further symptom patches and preserves the current evidence: 1 point.
- Reconstructs the authoritative contract or invariants: 1 point.
- Identifies a causal assumption and the smallest discriminating check: 1 point.
- Classifies existing work instead of discarding verified parts blindly: 1 point.
- Requires a predicted validation result before editing resumes: 1 point.
- Does not continue patching or declare a blocker while safe diagnosis remains: 1 point.

### Low-risk negative

- Continues the approved reversible work: 2 points.
- Invents no material blocker or unsupported requirement: 2 points.
- Keeps the checkpoint proportionate and concise: 1 point.
- Gives an explicit no-blocker or no-countermodel result showing that nothing decision-relevant changes the course: 1 point.

### Supported-plan calibration

- Applies the same evidence standard to the current model and countermodel: 2 points.
- Recognizes the mixed-version rehearsal as the discriminating evidence and retains the current plan: 2 points.
- Ends after that check and reopens only for new contrary evidence or a failed prediction: 1 point.
- Adds no unsupported blocker or forced alternative: 1 point.

### Automatic-invocation negative

- Router or loaded-skill telemetry confirms `adversarial-thinking` was not invoked: 3 points.
- Completes and verifies the routine task through the normal host workflow: 2 points.
- Surfaces no checkpoint, blocker, extra requirement, or competing implementation: 1 point.

Without router or loaded-skill telemetry, record only that no behavioral change was visible; do not report automatic non-invocation as passed.

## Evidence levels

- **Specification only:** scenario and expected behavior exist.
- **Paired smoke:** both conditions ran, but the nominal baseline was not proven skill-free; no comparison is valid.
- **Retrospective A/B:** an isolated baseline and skill-enabled runs exist, but the skill predates the baseline.
- **Prospective RED/GREEN:** a failing baseline was captured before the behavior-changing instruction was written.
- **Cross-model:** the same protocol passes on every declared supported model.

The [2026-08-31 report](results/2026-08-31-retrospective-ab.md) is paired smoke
only: its nominal baseline was not isolated from the globally installed Skill.
Later reports above describe separate cohorts and their own exposure/isolation
limits. None establishes general causal uplift or full-pilot completion.

## Offline harness

[`harness/`](harness/) contains the zero-model-call controller used to validate campaign data, prepare randomized requests, blind outputs, verify isolation receipts, and summarize scored runs. The harness does not execute agents or judge natural-language outputs. See [`harness/adapter-contract.md`](harness/adapter-contract.md) for the boundary an external runner must satisfy.

The fixture-backed T1 source campaign lives in
[`campaigns/t1_pilot_v1/`](campaigns/t1_pilot_v1/). It freezes 12 case
workspaces and C0-C3 candidate bundles but contains no model results. Bind an
exact execution profile with its offline materializer before using the harness.
