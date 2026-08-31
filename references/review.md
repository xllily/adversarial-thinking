# Review Mode

Judge the artifact against criteria; do not reward suspicion itself.

## Boundary

Keep review-only work read-only; a review request alone does not authorize changes. If implementation is already authorized under the host hierarchy, review first, then fix valid in-scope issues and verify the result.

## Method

1. Define success criteria before accepting the proposal. Prior exposure cannot be undone and is not independent review.
2. Inspect the relevant artifact, source, repository state, tests, or operational constraints before making strong claims.
3. For each material finding, give evidence, impact, confidence, and the smallest useful correction. Do not invent repository facts or impose an issue quota; say plainly when no material issue exists.
4. Select only lenses that expose distinct failure classes:
   - **Breaker:** correctness, boundaries, state, concurrency, error paths.
   - **Operator:** deployment, rollback, observability, performance, maintenance.
   - **Boundary:** security, privacy, permissions, integrity, compatibility.
   - **Intent:** goal alignment, stakeholder effect, hidden premise, scope creep.
5. Run one omission check for a consequential failure class not covered by the selected lenses. Inspect it only if it could change the verdict.
6. Set severity from evidence, impact, and failure conditions—not reviewer count. Use **sound**, **risky**, **not ready**, or **insufficient evidence** when a verdict helps.

For a review of another review, inspect the underlying artifact and evidence before revealing the target diagnosis for comparison.

## Output and completion

Prefer this compact shape for material reviews:

```text
Verdict: sound | risky | not ready | insufficient evidence
Findings: ranked; evidence, impact, confidence, minimum correction
Unknowns: only those that could change the verdict
Next step: fix, continue criteria, or the precise decision requiring confirmation
```

Review mode is complete when a justified verdict or explicit no-finding result exists and all decision-relevant findings are evidenced.
