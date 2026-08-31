# Evaluations

`evals.json` is a behavioral specification, not proof that the skill improves an agent. Each entry defines a prompt and semantic expected behavior without requiring exact wording.

## Evaluation protocol

1. Select scenarios before reading outputs.
2. Freeze a scoring rubric that measures behavior, not headings or keywords.
3. Run the prompt in a fresh context without the skill.
4. Run the same prompt in a fresh context with the skill explicitly loaded.
5. Repeat each variant at least three times.
6. Record the host, model, skill revision, complete outputs, scores, and limitations.
7. Treat a strong baseline as evidence that the scenario does not yet discriminate skill value; do not report baseline parity as improvement.

For automatic invocation, run a separate discovery campaign without explicitly loading or naming the skill. Include both positive triggers and low-risk negative cases.

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

## Evidence levels

- **Specification only:** scenario and expected behavior exist.
- **Retrospective A/B:** baseline and skill-enabled runs exist, but the skill predates the baseline.
- **Prospective RED/GREEN:** a failing baseline was captured before the behavior-changing instruction was written.
- **Cross-model:** the same protocol passes on every declared supported model.

The current public evidence is retrospective A/B only. See [`results/2026-08-31-retrospective-ab.md`](results/2026-08-31-retrospective-ab.md).
