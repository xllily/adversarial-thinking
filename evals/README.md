# Evaluations

`evals.json` is a behavioral specification, not proof that the skill improves an agent. Each entry defines a prompt and semantic expected behavior without requiring exact wording.

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

The current public evidence is paired smoke only. It does not meet the retrospective A/B level because the nominal baseline was not isolated from the globally installed skill. See [`results/2026-08-31-retrospective-ab.md`](results/2026-08-31-retrospective-ab.md).
