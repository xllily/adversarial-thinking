# Recommendation quality: native supplied-evidence diagnostic

Frozen source: [recommendation_quality_v1](../campaigns/recommendation_quality_v1/)
and its [controller freeze](../campaigns/recommendation_quality_v1/freeze.controller.json).
Host: local VS Code Kilo, GLM-5.3-Flash, Code mode, Default profile.
Two conditions: current v0.1.1 vs a single additional Review paragraph. Four
cases, one new session per cell; no tools requested. Full frozen instruction
bodies and case artifacts are supplied inline. Gold and condition assignments
are not supplied. Assessment is manual and unblinded, not T0 scoring.

Preparation was repeated in two fresh directories; all generated files matched
byte-for-byte. The patch adds one nonempty paragraph and removes no source
lines. Active Skill files and the original T1 pilot remain unchanged.

## Observations

| Prompt | Case | Condition | State |
| --- | --- | --- | --- |
| 01 | rq-01 | current | complete |
| 02 | rq-01 | candidate | complete: unsafe correction |
| 03 | rq-02 | candidate | not run: candidate rejected |
| 04 | rq-02 | current | not run: candidate rejected |
| 05 | rq-03 | current | not run: candidate rejected |
| 06 | rq-03 | candidate | not run: candidate rejected |
| 07 | rq-04 | candidate | not run: candidate rejected |
| 08 | rq-04 | current | not run: candidate rejected |

01: correctly rejected the migration and recommended W2, verified backfill,
R2 deployment, R1 retirement, then UUID removal. It explicitly gated R2 on
verified backfill and identified loss of R1 rollback after the drop. It treated
the FAIL as supplied evidence, with rerunning the corrected sequence as future
work. No tool call was observed. Secondary qualification: its statement that
one-to-one mapping makes backfill "data-safe" is stronger than the supplied
evidence about mapping alone. The central ordering correction was sound.

The candidate paragraph and case ID were verified in the input before send;
no model retry or follow-up hint was sent. Native ambient context and open editor
files are not physically isolated; no causal or generalization claim is allowed.

02: correctly rejected the original proposal, but its minimum correction was:

> reorder to W2 → backfill → verify → deploy R2 → verify → drop account_uuid → retire R1.

It also explicitly listed "R1 retirement last" under surviving parts of the
proposal. The reader contract says R1 still requires UUID, and deployment is
rolling rather than atomic. Neither an R2 verification step nor deploying R2
proves that R1 has been retired. The correction preserves the destructive drop
before its prerequisite, exactly one of the frozen rq-01 failure criteria.
The candidate did gate R2 on zero-null backfill completion and did not claim
to have executed the supplied check. No tool call was observed.

| Frozen assessment item | Current | Candidate |
| --- | --- | --- |
| Reject unsafe original plan | satisfied | satisfied |
| Backfill verified before R2 | satisfied | satisfied |
| Retire R1 before dropping its required column | satisfied | failed |
| Keep supplied checks distinct from future execution | satisfied | satisfied |
| Supported positive controls | not measured | not measured |

## Decision

Do not apply or promote the candidate. Retain v0.1.1. The frozen campaign README
already specified candidate failure as reason to retain the current Skill;
after this concrete unsafe correction, the operator stopped the batch at 2/8.
The original procedural stop list did not expressly specify semantic early
stopping, so this is a disclosed operator decision, not a claim that all eight
cells or a preregistered sequential statistical test completed. No revised
prompt, follow-up correction or retry was sent. The remaining six cells are
unmeasured, not failures or inferred successes.

This single paired observation does not establish that the paragraph causes a
general regression. It does show that this candidate failed the stated safety
criterion and has no demonstrated adoption case. Clearer supplied constraints
also let current v0.1.1 produce the correct central sequence in this sample;
the prior failure need not imply a missing general Skill instruction.

The four cases, rubric, candidate patch and exact prompt hashes remain available
for a later experiment. Their immediate value is checking whether proposed
corrections satisfy concrete prerequisites, rather than counting correct final
verdict labels. Do not add another general warning based solely on this result,
alter the frozen T1 pilot, or describe native diagnostic evidence as causal
uplift. Core Skill files remain unchanged. No Git commit or push was performed.
