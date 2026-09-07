# Native Kilo explicit-read C1/C3 diagnostic

Recorded 2026-09-07 from controller-observed summaries of four completed native
Kilo sessions. The sessions completed before this documentation closeout; exact
session timestamps and a full transcript export are unavailable here. This is a
separate cohort from the [earlier prompt-permission pairs](2026-09-05-kilo-ui-skill-check.md).

Both conditions rejected the incompatible migration and accepted the supported
dual-write rollout. No C3 advantage was demonstrated. Keep Skill **0.1.1**.
These are nonblind diagnostic observations, not scored T0/T1 evaluation records.

## Conditions and task instructions

C1 used the frozen current-0.1.1 bundle; C3 used the frozen
operational-discriminator candidate. Each of the two cases had one valid,
independent native session per condition. All four sessions explicitly confirmed
reading their assigned `skill/SKILL.md` and `skill/references/review.md`.
This is evidence of the assigned reads, not proof of comprehension or full
seven-file loading.

The following is a paraphrase of the common task requirements, not a recovered
verbatim prompt: read and confirm both assigned instruction files; review only
the assigned workspace and those files; make no edits; execute exactly
`python3 verify.py` in the workspace; separate observed evidence from future
recommendations; stop once evidence is sufficient. Exact submitted prompts,
session IDs and full traces are not reconstructed.

The UI showed the **GLM-5.3** alias. It did not establish an immutable model
version or equivalence to the standard API harness's `glm-5.3-flash` profile.
The native sessions did not execute the M1 standard API runner.

## Observed outcomes and provenance

| Case / condition | Retained verifier evidence | Final judgment |
| --- | --- | --- |
| migration-compat-01 / C1 | Prior controller UI summary: exit 1, `FAIL incompatible deployed workers: worker-v1, worker-v2`; no full exported transcript | Not ready |
| migration-compat-01 / C3 | Prior controller UI summary: exit 1, same incompatible workers; no full exported transcript | Not ready |
| dual-write-06 / C1 | Controller saw the command card display `PASS complete mixed-version rehearsal; zero dual-write gaps`; the final also reported exit 0 | Sound; proceed with the plan as written |
| dual-write-06 / C3 | Final reported successful verifier execution; controller did not expand the raw command-output card | Sound; proceed to the 1% canary |

Both dual-write finals were observed in the Done state. Their evidence provenance
is different: the C3 command result is retained as a final-answer report, not as
an independently inspected raw command-output card.

The frozen dual-write rehearsal lists worker-v1/v2/v3 in both deployed and
rehearsed inventories, 25,000 checked records and zero dual-write gaps. C1 found
no material issue, said the countermodel did not change the decision, and kept
the existing canary, abort-on-gap and preserved rollback. It noted that the
artifact proves coverage only of the listed versions.

C3 also found no required correction before proceeding. It noted that both
inventories came from the same artifact, leaving freshness and completeness
unverified, and added a nonblocking recommendation to re-confirm deployed worker
inventory at canary start while keeping abort-on-gap armed. C1 did not add that
check. This single difference is neither a stable regression nor causal evidence
of benefit. More recommendations do not by themselves establish better decisions.

## Frozen fixture references

Fixtures are relative to `evals/campaigns/t1_pilot_v1/workspaces/`. The following
SHA256 values come from the available frozen manifest. During closeout the four
current target mounts matched that manifest. This is not a historical before/after
hash comparison and does not prove that no files changed during the native runs.

| Artifact | SHA256 |
| --- | --- |
| migration-compat-01 workspace | `6a96b3164fdc4eef164269a61ff2fd23f88cabee45c0ff5bfb4c98a9895fc697` |
| dual-write-06 workspace | `8fb36a383e8770e08ab4388759de167b59b09e20e733e13439ffe698e206f9e0` |
| C1 bundle | `358031f17f5c16d93a00231d6d37b631e527f6e94c38f96d65dd9c3dd1f308cf` |
| C3 bundle | `f59a39495d8155cb2dbee9e45a5849f6b582065e681f9ddf144b7262835f262c` |

## Limits and decision

- One valid run per cell, manual nonblind observation and public development
  fixtures cannot establish statistical reliability, generalization or causality.
- At least three invalid startup attempts were excluded; their inventory is
  incomplete. They are not counted as model failures or additional valid samples.
- Physical isolation in native Kilo was not verified. Approval provenance differed:
  C1 dual-write displayed auto-approval through a global bash rule. Equal effective
  permissions and manual allow-once for every command are not established.
- Actual usage and cost are unknown. A UI `$0.00` indicator is not billing proof.
  UI timing is not performance evidence. The harness's limits, receipts and
  accounting cannot be transferred to this cohort.
- Retained evidence consists of controller-observed excerpts and summaries with
  incomplete raw evidence. There are no fabricated prompts, logs or model IDs,
  and no formal scores, strict acceptance or verified cost-benefit comparison.

This closeout made zero provider/model calls. Its separate offline M1 checks do
not strengthen the native cohort into a controlled experiment. M2 export, M3
sentinel work and any further real experiment remain separately gated. The
observed outcome supports retaining 0.1.1; it does not justify applying C3.
