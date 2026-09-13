# Native Kilo Flash diagnostic

Execution target authorized by the user: local VS Code Kilo extension,
GLM-5.3-Flash. UI observation: Kilo 7.6.2, Code mode, Default profile.
An older open session displayed GLM-5.3; the new session displayed
GLM-5.3-Flash before the first send. No provider settings were changed.

## Prospective scope

Two frozen fixtures (migration-compat-01 and dual-write-06), four requested
exposures per fixture, one fresh session per cell. Baseline receives no explicit
Skill loading request. Treatments explicitly read the assigned frozen SKILL.md
and Review branch. Each receives the same read-only, no-network, no-delegation,
assigned-artifact-only restriction and deterministic-check requirement.

Stop on transport failure or model change; do not retry failed cells or expand
to sentinel/pilot. Task completion requires the observed verifier outcome and
final decision, not merely sending the prompt. Human permission handling is
part of native latency; no hard request/token/monetary cap is enforced by this
UI workflow. Actual billing and immutable model identity remain unknown.

## Evidence limits

VS Code remains rooted in the Skill repository, with globally available skills.
The nominal baseline is **not physically isolated C0**. Docker rehearsal receipts
do not apply to native Kilo's tools. Treatment reads demonstrate exposure only;
model compliance and additional ambient context must be observed separately.
This is a native diagnostic, not the scorable eight-run T0 gate. No causal uplift,
blind-score claim, or cost comparison is permitted from these cells.

The workspace roots were prepared outside the repository. The table below
identifies each local target; machine-specific root paths are omitted.
Controller manifests, gold, prior reports and other conditions are not included
in the user prompts. They are not technically inaccessible to native Kilo.

## Cells

| Cell | Fixture | Requested exposure | Target | State |
| --- | --- | --- | --- | --- |
| 01 | migration | baseline | target-8fa6c3c40bdb | complete: not ready, FAIL observed |
| 02 | migration | C1 | target-6c823862a19a | complete: not ready, FAIL observed |
| 03 | migration | C2 | target-7ac418941f03 | complete: not ready, FAIL observed |
| 04 | migration | C3 | target-2d672461345c | complete: not ready, FAIL observed |
| 05 | dual-write | baseline | target-b46d41c26a12 | complete: proceed, PASS observed |
| 06 | dual-write | C1 | target-eb1de52e13ac | complete: sound/proceed, PASS observed |
| 07 | dual-write | C2 | target-09513b7edfb1 | complete: sound/proceed, PASS observed |
| 08 | dual-write | C3 | target-e3831608eeb1 | complete: sound/proceed, PASS observed |

## Initial observations

Cells 01 and 02 both read the three fixture artifacts and ran the verifier,
observing `FAIL incompatible deployed workers: worker-v1, worker-v2` (exit 1).
Both rejected the proposed migration and separated observations from future
recommendations. C1 visibly read the assigned Skill and Review bodies. Its
reasoning also mentioned a discovered Skill path in an old worktree; no load
of that additional copy was observed in the displayed tool sequence.

Recommendation-quality concern, not independently scored: baseline recommended
deploying readers that read only legacy_email, then backfill, then drop UUID.
C1 recommended updated readers, verify, backfill, then removal. Neither specified
a compatibility fallback or readiness condition before switching reads to the
not-yet-backfilled field. The fixture proves column-dependency failure, not
whether this new ordering is safe. Both correct verdicts therefore leave an
unresolved recommendation gap; this is not a treatment-specific regression.

C2 also read both assigned instruction files, ran the same failed check, and
rejected the migration. Its advice to keep the column drop a "separate,
reversible step" did not establish a reversal mechanism. Separating a destructive
step does not itself make it reversible. This is a recommendation-quality
concern despite a correct verdict, not evidence that C2 is generally worse.

C3 read its assigned instruction bodies and also rejected the failed migration.
Its final answer said "no upgrade step exists in the plan", although its own
evidence summary correctly listed reader deployment after column removal. The
problem is ordering, not absence. This unsupported statement did not change the
correct verdict but shows that the operational-discriminator variant did not
eliminate evidence-fidelity defects in this sample.

The dual-write baseline read the three artifacts, ran verify.py and observed
`PASS complete mixed-version rehearsal; zero dual-write gaps`. It retained the
1% canary and stated abort/rollback guardrails, then stopped. This positive
control supports the narrow conclusion that the baseline can both reject the
bad migration and retain the supported rollout in these supplied fixtures.

Dual-write C1 read the assigned bodies, observed PASS and retained the canary.
It explicitly distinguished the artifact's internal consistency from independent
fleet inventory and recommended refreshing that inventory at rollout time. This
was a future recommendation, not a claim that a new check had already passed.
The final decision matched baseline; no additional blocking action was taken.

Dual-write C2 also read both instruction bodies, observed PASS and retained the
canary. It noted the self-reported census and recommended refresh/rechecking
when new worker versions deploy. It stopped after its final answer.

Dual-write C3 read both assigned instruction bodies and observed PASS. It
retained the canary, distinguished frozen inventory from live inventory, and
noticed that verify.py does not enforce records_checked > 0. It explicitly
recognized that the supplied 25,000-record artifact is nonempty and made
verifier hardening a future recommendation rather than a canary blocker. This
is a useful observed detail, not a replicated advantage over C1 or baseline.

## Closeout

All eight native sessions reached a final answer with the requested deterministic
check visibly executed. All six treatment sessions visibly read the assigned
Skill and Review bodies. The model selector remained GLM-5.3-Flash across these
sessions. No retries or extra model sessions were dispatched. Eight fixture and
bundle trees were hash-checked after completion and remained unchanged. This
post-run check does not establish what other files native Kilo could access.

| Observed outcome | Baseline | C1 | C2 | C3 |
| --- | --- | --- | --- | --- |
| Failed migration check; reject proposal | yes | yes | yes | yes |
| Passed dual-write check; retain canary | yes | yes | yes | yes |
| Assigned Skill/Review read in both cases | not requested | yes | yes | yes |
| Valid isolated comparison evidence | no | no | no | no |

This is an unblinded manual reading of two familiar fixtures, one run per cell.
Do not interpret eight expected final decisions as an effectiveness rate or
proof of generalization. No verified model version, complete usage ledger,
actual billing or comparative latency was collected from the native UI.

Decision: retain v0.1.1 and keep the scored T0 gate open. This batch neither
justifies promoting C3 nor advancing to the sentinel. It does provide concrete
future evaluation targets: recommendation safety after a correct diagnosis,
faithful description of existing plan steps, and distinguishing a verifier's
general blind spot from a defect in the supplied artifact. These should be
frozen as separate future cases, with supported no-change contrasts, before
testing any rule revision. Do not modify the frozen pilot to absorb these
post-hoc observations.

The user-selected native route was used throughout. No custom provider adapter,
core Skill edit, Git commit or push was performed. The local ticket retains its uncompleted scored-run
criteria; native diagnostic completion is not ticket-02 completion.
