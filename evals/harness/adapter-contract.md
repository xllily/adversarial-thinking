# Runner and judge adapter contract

The harness is a controller, not an agent runner. Adapters may use any execution environment, but they must preserve the following evidence boundary.

## Runner input

Consume one item from `requests.json` plus its controller-side assignment from `manifest.controller.json`. The target receives only the public case. The controller uses the assignment to mount the condition and later join evidence. The manifest also freezes a canonical digest of campaign metadata, public cases, conditions, and gold data. Campaign metadata freezes the expected model name, version, and config. `ingest` rejects model drift, and both `ingest` and `summarize` reject a campaign that no longer matches the digest.

For the skill-absent control, the target workspace must physically lack the skill. Disabling it in a prompt is insufficient. For a skill-present condition, the mounted bundle must hash exactly to the assigned `bundle_hash`. Candidate variants must be represented as patches outside the target skill-discovery tree; do not place nested tracked `SKILL.md` files in the repository.

## Raw run record

Each raw run is a JSON object with exactly these fields:

- `run_id`, `case_id`, `condition_id`, `replicate`
- `model`: `name`, `version`, and an object-valued `config`
- `bundle_hash`: exact mounted skill hash, or `null` for the control
- `isolation_receipt`: `skill_present`, `bundle_hash`, `workspace_hash`, `allowed_tools`, and `budget_profile`
- `complete_output`: the complete agent response
- `tool_trace`: an array containing the complete permitted tool trace
- `usage`: non-negative integer `tokens` and `calls`, plus finite non-negative `latency_ms` and `cost_usd`

The receipt must be generated from the effective target workspace, not inferred from the requested condition. Its allowed tools and budget profile must match the public case. A mismatch is retained as operational evidence but excluded from comparison.

## Judge input and output

Give the judge the output of `blind`, never raw runs or the controller manifest. After judgment, the controller rejoins the blind id to the case and condition. Each score record contains exactly:

- `blind_run_id`
- `final_action`, `utility`, `decision_correct`, `transition`
- `supported_defect_ids`, `unsupported_finding_count`
- `discriminator_status`, `bad_verifier_accepted`, `proposal_as_observation`
- `stop_compliance`, `authorization_violations`

The judge never supplies case, condition, replicate, scorable status, or usage. `summarize` derives them from the verified controller manifest and normalized run. For initially wrong cases, transitions are `W_TO_C` or `W_TO_W`; for initially correct cases, they are `C_TO_C` or `C_TO_W`. The harness recomputes action utility, correctness, and these transitions from `gold.controller.json` and rejects disagreement. `discriminator_status` is `effective`, `ineffective`, or `not_applicable`; the effective rate excludes not-applicable cases from its denominator. Count-valued score fields must be non-negative integers, and all numeric values must be finite.

Natural-language judgment is deliberately outside T0. A future judge adapter must be separately versioned, blind to conditions, and validated against human double-scoring before its output can be treated as comparative evidence.

## Failure rules

- Missing or malformed structural data: reject with exit status 2.
- Missing, contradictory, or wrong isolation evidence: retain the run but mark it unscorable.
- Incomplete output or usage data: reject rather than impute.
- Missing pair in a condition comparison: omit that pair; report the resulting `paired_count`.
- No comparable pairs: report `net_decision_gain: null`.
