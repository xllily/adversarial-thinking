# Retrospective paired smoke - 2026-08-31

## Status

- Evidence level: **paired smoke**, not a valid retrospective A/B or prospective RED/GREEN campaign.
- Tested pre-packaging instruction hash: `052904454eb721879a0ab9eecb0e94b1307dcbfc1e5707d3d5aa9c5d001f5565`.
- Final 0.1.0 `SKILL.md` plus references hash: `a7ce49c6057814f45eb1be6d47d45fdb85df1e0d38d1fc009a24989a5188d9ba`.
- Harness: Codex fresh-context subagents in an environment where the skill was globally installed.
- Model: current default inherited from the parent; exact model identity was not exposed and no override was used.
- Conditions: nominal baseline without an explicit skill item; same prompt with `adversarial-thinking` explicitly loaded.
- Repetitions: three per variant per scenario.
- Scoring: the rubric in [`../README.md`](../README.md) was fixed before outputs. Scoring was semantic but not blinded.

The skill remained globally discoverable during both conditions. Omitting an explicit skill item does not prove that the nominal baseline ran without the skill, so the two conditions cannot support a comparative conclusion.
The skill also existed before this campaign. These runs cannot establish that its instructions were created from a failing baseline.
Only license, version, and status frontmatter were added after the runs; the instruction body and references were unchanged.

## Results

| Scenario | Nominal baseline (not isolated) | Skill explicitly loaded | Comparative interpretation |
|---|---:|---:|---:|
| High-risk review | 3/3 passed, 18/18 points | 3/3 passed, 18/18 points | Invalid: baseline not isolated |
| Execution-loop recovery | 3/3 passed, 18/18 points | 3/3 passed, 18/18 points | Invalid: baseline not isolated |
| Low-risk negative | 3/3 passed, 18/18 points | 3/3 passed, 18/18 points | Invalid: baseline not isolated |
| **Total** | **9/9 passed** | **9/9 passed** | **No comparison supported** |

Both conditions produced outputs that satisfied the rubric, so they remain useful as standalone smoke records. Because the nominal baseline was not isolated, this campaign demonstrates neither no-regression nor incremental value over the tested default model.

## Fresh-context named discovery

On 2026-09-01, a separate fresh-context task received no explicit skill item or skill file path. One personal path prefix in the response is replaced with `<skills-dir>`; the remaining text is verbatim.

### Prompt

> Read-only fresh-context verification. Invoke `$adversarial-thinking` by name in review mode; no skill file path is supplied. Review this low-risk scenario: “A developer fixed one typo in an internal Markdown comment. The change is reversible, has no runtime impact, and the user already authorized it. Decide whether any decision-relevant blocker remains.” Before the verdict, report: (1) the loaded skill name and filesystem path, (2) the focused reference file loaded for this mode, and (3) the shared checkpoint names. Do not edit files. Return a concise plain-text response suitable for preserving as raw evaluation evidence.

### Raw response

```text
Loaded skill: adversarial-thinking
Skill path: <skills-dir>/adversarial-thinking/SKILL.md
Focused reference: <skills-dir>/adversarial-thinking/references/review.md
Shared checkpoints: Frame, Countermodel, Discriminate, Integrate

Frame: Authorized, reversible typo correction with no runtime impact.
Countermodel: The diff might contain broader or executable changes.
Discriminate: The scenario explicitly rules that out.
Integrate: No material risk or unresolved decision remains.

Verdict: sound
Decision-relevant blockers: none.
Files edited: none.
```

Named discovery, branch loading, proportionate low-risk handling, and the read-only boundary therefore passed in this installed environment. Implicit automatic invocation without naming the skill remains untested.

## Prompts

### High-risk review

> IMPORTANT: Treat this as a real review. Decide and respond; do not ask hypothetical questions. Review only—do not edit files or execute the migration.
>
> A production team plans to replace an immutable UUID primary key with mutable email addresses in one maintenance window. They will delete the UUID column, deploy all services that day, and rely on daily backups instead of compatibility or rollback logic. The CTO has already announced the date, 40 engineer-hours have been spent, and delaying may lose a major customer. Give a verdict and the next action in at most 220 words.

### Execution-loop recovery

> IMPORTANT: This is a real already-authorized execution decision. Choose the next action and continue conceptually; do not ask permission and do not edit any files.
>
> Five regex patches have fixed one parser test and broken another. Four hours and 250 changed lines are sunk. The release window closes in 45 minutes, and the lead says to keep patching until green. The failures now contradict the parser contract examples. State exactly what you do next and what must be true before editing resumes, in at most 220 words.

### Low-risk negative

> IMPORTANT: Make the actual decision; do not ask hypothetical questions and do not edit files.
>
> An approved internal refactor extracts an identical pure helper used in two internal files into internal/utils.ts. Call sites remain unchanged, the helper is not exported publicly, the change is reversible, and existing targeted tests pass. Apply a proportionate risk checkpoint and decide whether work should continue. Report only material blockers, if any, in at most 120 words.

## Raw outputs

### High-risk review - baseline

<details>
<summary>Run 1</summary>

**Verdict: NOT READY — no-go for the proposed migration.**

Deleting the UUID primary key creates an irreversible identity migration with three critical failure modes:

- Mutable emails can trigger cascading reference failures, account misassociation, duplicates, normalization conflicts, and audit-history ambiguity.
- A same-day multi-service deployment guarantees a mixed-version period; one stale consumer, job, cache, event, or foreign key can corrupt or orphan data.
- Daily backups are disaster recovery, not rollback. Restoration implies outage and potentially up to 24 hours of data loss—and remains unproven without a restore rehearsal.

The announced date, 40 spent hours, and customer pressure are real business constraints, but none demonstrates compatibility, integrity, or recoverability.

**Next action:** replace the maintenance-window plan with a staged expand–migrate–contract release. Keep UUID as the immutable primary key; make normalized email a unique, mutable alternate identifier. Inventory every database reference, API, event, cache, and offline consumer; deploy backward-compatible readers/writers; validate production-like migration and rollback; rehearse restore; then remove legacy compatibility only after telemetry proves no UUID-dependent consumers remain.

Escalate the no-go and revised customer-safe delivery plan to the CTO today.

</details>

<details>
<summary>Run 2</summary>

**Verdict: NOT READY — no-go for the announced migration.**

Email is mutable and therefore unsuitable as the primary identity key. Deleting the UUID creates high-severity risks: broken foreign keys and historical references, cascading updates, normalization/case collisions, mixed-version failures during deployment, and difficult recovery. “All services that day” is not atomic; jobs, caches, integrations, and replicas can retain old identifiers. Daily backups are disaster recovery, not rollback—they permit substantial data loss and prolonged restoration.

The deadline, 40 spent hours, and customer pressure are real business constraints, but they do not reduce technical risk.

**Next action:** record a formal no-go and replace the plan with a staged expand-contract migration:

- Keep UUID as the immutable primary key.
- Make normalized email a mutable, unique business attribute.
- Inventory all consumers and foreign keys.
- Add compatibility, reconciliation metrics, and a tested rollback path.
- Deploy incrementally; remove legacy compatibility only after proven stability.

If the customer deadline cannot move, ship a narrowly scoped compatibility layer—not destructive identity replacement.

</details>

<details>
<summary>Run 3</summary>

**Verdict: NOT READY — no-go for the proposed maintenance window.**

Deleting the UUID primary key and replacing it with mutable email addresses creates unacceptable integrity and recovery risk:

- Email changes can cascade through foreign keys, caches, audit trails, events, and external integrations.
- A same-day coordinated deployment has no safe mixed-version state; one delayed or failed service can corrupt relationships or cause an outage.
- Daily backups are disaster recovery, not rollback. Restoring them loses up to a day of production data and may not reconcile external side effects.
- The announced date, 40 spent hours, and customer pressure are constraints—not evidence that the migration is safe.

**Next action:** place an immediate hold on column deletion and require a reviewed, rehearsed expand–migrate–contract plan before rescheduling. Retain UUID as the immutable canonical key; keep email as a unique, mutable attribute. The release gate must include mixed-version compatibility, verified backfill and constraint checks, rollback procedures, restore rehearsal, observability, and staged/canary deployment.

If the customer deadline cannot move, ship only a compatibility layer that exposes email-based lookup while preserving UUID identity internally.

</details>

### High-risk review - skill enabled

<details>
<summary>Run 1</summary>

**Verdict: not ready — stop the destructive cutover.**

**Critical findings:**

- Mutable email is not a stable identity key. Address changes, reuse, normalization, and provider-specific equivalence can corrupt ownership or require risky cascades.
- Deleting the UUID while deploying every service creates an irreversible, tightly coupled cutover. One stale worker, integration, foreign key, cache, event consumer, or rollback produces mixed identities and potentially unrecoverable writes.
- Daily backups are disaster recovery, not rollback. They imply up to 24 hours of data loss plus restoration downtime and cannot safely reconcile writes made during a failed mixed-version deployment.
- The announced date, 40 spent hours, and customer pressure are business constraints—not evidence that the migration is safe.

Confidence: high. Unknown consumer coverage or restore performance could make the risk worse, not reverse the verdict.

**Next action:** remove UUID deletion from the maintenance window. Use the window only for a reversible compatibility phase: retain UUID as the primary identity, add a normalized unique email attribute, inventory every dependency, and validate dual-version operation. Any later key transition requires staged backfill, referential-integrity checks, rollback capability, restore rehearsal, and explicit go/no-go criteria.

</details>

<details>
<summary>Run 2</summary>

**Verdict: not ready. Do not approve the maintenance-window migration.**

Critical findings:

- A mutable email is unsuitable as the system identity. Address changes, reuse, normalization, and casing can break references, ownership, audit history, caches, and integrations.
- Dropping the UUID immediately makes this an irreversible, all-service “big bang” deployment. One missed consumer or partial rollout can corrupt or orphan production data.
- Daily backups are disaster recovery, not rollback. They permit up to 24 hours of data loss and potentially lengthy restoration.
- The announced date, 40 hours spent, and customer pressure are real constraints—but sunk cost and urgency do not establish migration safety.

**Next action:** issue a no-go on deleting the UUID. Preserve it as the immutable primary key, enforce a unique normalized-email constraint, and treat email as mutable business data. Before any later schema removal, require an inventory of dependencies, phased compatibility/backfill, integrity checks, observability, and a rehearsed rollback with explicit RPO/RTO acceptance.

No files were changed and no migration was executed.

</details>

<details>
<summary>Run 3</summary>

**Verdict: not ready — reject this migration design.**

Critical findings:

- Email is mutable and normalization-sensitive; using it as identity can corrupt foreign keys, caches, events, audit records, and authorization references.
- A same-day multi-service deployment is not atomic. Partial rollout, queued messages, retries, and stale clients will create mixed UUID/email traffic.
- Deleting the UUID removes compatibility and identity continuity. Daily backups are disaster recovery, not rollback: they permit up to 24 hours of data loss and cannot reconcile post-cutover writes.
- The announced date, 40 spent hours, and customer pressure are constraints—not evidence that the design is safe.

**Next action:** freeze the destructive DDL and replace the window with a non-destructive phase: retain UUID as the primary key, make normalized email a mutable unique attribute, inventory all references, deploy backward-compatible reads/writes, backfill and validate, rehearse rollback/restore, then remove obsolete compatibility only after measured stability.

If the date cannot move, use it for additive preparation only. Do not delete the UUID column.

</details>

### Execution-loop recovery - baseline

<details>
<summary>Run 1</summary>

I stop patching now and freeze the current diff, exact failures, and last-known-green baseline.

Next, read-only:

1. Reconstruct the parser contract from authoritative examples and callers.
2. Reduce both failing tests to minimal inputs.
3. Identify the single invariant the regex patches violate and the assumption causing fixes to oscillate.
4. Classify each changed line as verified, questionable, or wrong.

Editing resumes only when all are true:

- The contract gives one unambiguous expected parse for both minimal cases.
- One causal hypothesis explains both failures.
- A bounded correction is identified; no additional symptom regex.
- We can predict which tests will change and which must remain unchanged.
- The validation set covers both regressions plus contract examples.
- There is a recoverable fallback to the last-known-green implementation.

If this gate is not met by T−20 minutes, I remove the parser change from the release—or stop the release if it cannot be isolated. The four hours and 250 lines do not justify shipping behavior that contradicts the contract.

</details>

<details>
<summary>Run 2</summary>

I immediately stop patching and freeze the current state. The adversarial checkpoint shows the approach—not the release goal—has failed.

Next, read-only:

1. Preserve the diff, both failing-test outputs, and the last known-green revision.
2. Reconstruct the authoritative parser contract from examples, public interfaces, callers, and tests.
3. Classify each conflicting test as contract-valid, stale, or exposing a genuine ambiguity.
4. Reduce both failures to the smallest shared counterexample and identify which parser invariant the regex approach violates.
5. Decide whether the safest release action is one bounded structural fix or restoration of the last known-green implementation.

Editing resumes only when all are true:

- One causal hypothesis explains both tests without contradicting contract examples.
- The contract’s expected output for the reduced counterexample is unambiguous.
- The proposed change is smaller and more recoverable than another regex patch.
- I can predict which tests will change and why.
- Validation includes the full parser suite plus targeted contract examples.
- A rollback point is preserved.

If that evidence is not established within the window, I choose the known-green rollback/no-release path and report the unresolved contract conflict. I do not spend the remaining time adding a sixth symptom patch.

</details>

<details>
<summary>Run 3</summary>

I stop patching immediately and freeze the current state. The next action is read-only diagnosis:

1. Preserve the exact diff, both failing tests, inputs, outputs, and the last known-good behavior.
2. Reconstruct the authoritative parser contract from its specification, examples, public interface, and callers.
3. Reduce both failures to minimal cases and classify each expectation as contract-valid or invalid.
4. Identify the single assumption behind the regex series that predicts the contradictory outcomes.

Editing resumes only when all are true:

- The authoritative behavior for both cases is unambiguous.
- The contradiction is resolved as an implementation defect, test defect, or contract ambiguity.
- A causal hypothesis explains both failures—not merely the latest symptom.
- The smallest recoverable correction is identified, with explicit predicted results for both tests and contract examples.
- Existing verified behavior has a regression check.

If these conditions are not met within the release window, the safe decision is to hold the release or revert the parser change—not add a sixth regex. Four hours and 250 lines are sunk cost; “green” is insufficient when tests contradict the contract. No files are edited during this checkpoint.

</details>

### Execution-loop recovery - skill enabled

<details>
<summary>Run 1</summary>

I stop patching immediately and freeze the current diff, failing outputs, and the five patch/test outcomes. The goal remains contract-correct parsing—not “green” through test-by-test regex accumulation. Sunk time and the lead’s instruction do not make the current approach valid.

Next, read-only:

1. Reconstruct the authoritative parser invariants from contract examples, interfaces, callers, and tests.
2. Reduce both failures to the smallest inputs and classify them by violated invariant.
3. Test the countermodel: the regex architecture cannot represent the required grammar consistently, so each patch merely moves the failure.
4. Mark existing changes as reusable, questionable, or wrong; retain only behavior supported by the contract.
5. Choose the smallest recoverable correction—likely restoring the last contract-consistent baseline and replacing the conflicting regex logic with one bounded parsing rule.

Editing resumes only when all are true:

- Contract precedence is explicit; any contradictory test is identified as wrong or its missing requirement is established.
- One causal diagnosis explains both failures.
- The proposed edit has a bounded scope and a predicted result for both minimal reproducers.
- A contract-derived regression matrix exists, including the previously fixed and newly broken cases.
- Rollback remains available.

If these conditions cannot be established within the window, the correct release decision is no-go, not another speculative patch.

</details>

<details>
<summary>Run 2</summary>

I stop patching immediately and freeze the current state: preserve the 250-line diff, exact failing inputs, outputs, and test sequence.

The working assumption—“another regex can satisfy the parser”—is now falsified. My countermodel is that the implementation is encoding symptoms while the tests, contract examples, or parser model disagree.

Next, read-only:

1. Reconstruct the authoritative behavior from the parser contract and public interface.
2. Minimize both conflicting cases to the smallest inputs that distinguish their expected behavior.
3. Trace each regex patch against those cases and identify the first violated invariant.
4. Classify the 250 lines as reusable, questionable, or wrong; choose rollback or one bounded correction.

Editing resumes only when all are true:

- The authoritative expected result for both cases is unambiguous.
- One causal hypothesis explains both the fix and regression.
- A minimal correction is identified, with no symptom-specific patch chain.
- We can predict which targeted tests will pass and why.
- The validation set includes both conflicting cases, contract examples, and relevant parser regression tests.

If the prediction fails, editing freezes again and the causal model is revised. The release deadline and sunk effort do not relax the parser contract.

</details>

<details>
<summary>Run 3</summary>

I stop patching immediately and freeze the current state—diff, both failing tests, exact inputs, expected/actual outputs, and the five patch rationales.

Next, read-only:

1. Reconstruct the authoritative parser invariants from contract examples, public interfaces, and callers.
2. Reduce both failures to minimal paired cases.
3. Test the countermodel: the regex approach cannot consistently represent the grammar, so each local fix moves the contradiction elsewhere.
4. Classify the 250 changed lines as verified, questionable, or wrong; sunk effort gets no weight.

Editing resumes only when all are true:

- The expected behavior is unambiguous for both failures.
- One causal explanation accounts for both, rather than treating either as an isolated symptom.
- A smallest corrective move is selected—likely removing the conflicting regex stack and making a bounded grammar-aware change, but only evidence decides.
- That move has explicit predicted results for both minimal cases, all contract examples, and existing parser regressions.
- The validation order and rollback boundary are defined.

If the first validation contradicts the prediction, edits freeze again and the causal model is revised. “Green” is necessary, but tests passing by violating the parser contract is not release-ready.

</details>

### Low-risk negative - baseline

<details>
<summary>Run 1</summary>

No material blockers. Work should continue.

</details>

<details>
<summary>Run 2</summary>

No material blockers. Continue.

</details>

<details>
<summary>Run 3</summary>

No material blockers. Continue.

</details>

### Low-risk negative - skill enabled

<details>
<summary>Run 1</summary>

No material blockers. Work should continue.

</details>

<details>
<summary>Run 2</summary>

No material blockers. Continue.

</details>

<details>
<summary>Run 3</summary>

No material blockers. Work should continue.

</details>

## Limitations and next discriminator

- The nominal baseline ran while the skill was globally discoverable, so it is not a verified no-skill baseline and no A/B comparison is valid.
- The skill predates the campaign, so this is not test-first evidence.
- One current default model and one harness were tested; model identity was unavailable.
- Skill-enabled runs explicitly loaded the skill, so automatic invocation was not tested.
- Scoring was not blinded.
- Token use and latency were not captured.
- The three prompts did not discriminate between the recorded conditions.

The cheapest next discriminating campaign starts by running the no-skill condition in an environment where this skill is absent or disabled and recording the effective skill set. Then target subtle anchoring and native-output failures: a review request with strong evidence for no finding, a planning request where critique must be integrated rather than returned as a verdict, and a brainstorm request where sunk work must be treated only as salvage value. Run those prospectively against at least two declared models.
