# Execution Rescue Mode

## Reset the model, not the goal

1. Freeze further mutations and preserve the current state, diff, failures, and observations.
2. Reconstruct the authoritative contract and invariants from requirements, callers, tests, interfaces, and observed behavior. Separate what must remain true from the approach chosen so far.
3. Group symptoms by violated invariant. Identify which assumption predicted the wrong outcome and the smallest check that distinguishes competing causes.
4. Classify current work as reusable, questionable, wrong, or missing. Preserve verified work.
5. Choose the smallest recoverable correction, bounded experiment, pivot, or rollback that stays within authority. Resume only with a predicted validation result.
6. Run the validation. If the prediction fails, update the causal model before editing again; do not append another symptom patch.

Persistence attaches to the goal, not to the current approach. Do not declare a blocker while safe in-scope evidence gathering remains. Pause only for a specific need for new authority, essential unavailable facts, consequential validation, or a credible recovery decision.

## Completion criterion

Exec mode is complete when the mismatch has been traced to a sufficiently discriminated assumption, the smallest corrective move is chosen, and its validation behaves as predicted. If that criterion cannot be met, report the exact blocker and evidence already established.
