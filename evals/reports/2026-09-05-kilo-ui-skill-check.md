# Current Skill in VS Code Kilo — 2026-09-05

Eleven tasks completed through the user's configured VS Code Kilo sidebar:
three initial behavior checks and eight follow-up prompt-only paired sessions.
In the four pairs, both conditions reached 4/4 correct decisive judgments;
only one allowed-condition session loaded the Skill. This shows no observed
verdict advantage and does not establish causal uplift.

For the three initial checks below:
The displayed model was GLM-5.3-Flash in each task. Two review tasks loaded the
current Skill and its review branch; a simple sentence rewrite used no tools.
This establishes observed behavior in this installed environment, not causal
uplift or a fully correct end-to-end migration recommendation. Skill 0.1.1 is
unchanged.

## Observed tasks

| Kilo session title | Visible tool evidence | Visible result | Assessment |
| --- | --- | --- | --- |
| Migration rollout readiness review | Read proposal.md, compatibility.json, verify.py; ran fixture verifier (FAIL: worker-v1, worker-v2); invoked Skill adversarial-thinking; read review.md | `Verdict: not ready.` Rejects column removal while deployed workers still read account_uuid | Activation and review routing observed; blocking verdict correct; correction sequence has a material caveat below |
| Simplify formal sentence to plain English | No tool or Skill calls in the complete short conversation | `The meeting will start at noon.` | Low-risk skipping observed |
| Dual-write rollout readiness review | Read rollout-plan.md, verify.py, rehearsal.json, SKILL.md, review.md; ran verifier (PASS: complete mixed-version rehearsal; zero dual-write gaps) | `Verdict: sound` and retains 1% canary; proposes a fresh fleet/monitor check before enabling it | Activation/routing observed; retains supported plan rather than inventing a categorical blocker |

The review prompts requested read-only judgment using the respective public
fixture and applicable installed workflow instructions. Neither named the Skill
or supplied its body. They excluded private run files, credentials, gold,
previous reports, unrelated repositories, delegation, worktrees, and deployment.
The rewrite prompt requested only a plain-English version of one sentence. Each
case had an independent Kilo session. These are real visible tool events and
final answers, not conclusions inferred from hidden reasoning.

## Migration recommendation caveat

The final migration answer recommends first deploying workers that read only
`legacy_email`, then checking compatibility, then backfilling, then dropping
`account_uuid`. That does not establish populated new-field data before switching
readers. The original proposal explicitly includes a backfill; a robust corrected
sequence must retain compatible reads until the new field is populated and
verified. Thus the correct rejection is not a full pass for its corrective plan.
The answer also asserts no safe rollback point without demonstrating a rollback
contract from the fixture. These are output-quality concerns to test further,
not evidence that the Skill itself caused them: no same-model absent-Skill
control was run here.

The dual-write answer retains the canary but adds freshness and detector checks.
Those are clearly identified as proposed, unobserved checks. Its statement that
a later worker version would bypass dual-write is too categorical: version drift
would invalidate rehearsal coverage, but does not itself prove bypass behavior.

## Runtime and evidence limits

- The first migration task was manually stopped after discovering that global
  `bash: * -> Allow` still auto-approved commands despite the sidebar toggle
  being disabled. After the user explicitly requested ordinary native Kilo use,
  the same task was resumed and completed. It is an interrupted/resumed sample,
  not a pristine uninterrupted activation trial. The other two completed fresh.
- The user chose native VS Code Kilo operation. The Python harness was not used
  for these requests; its 60-second pacing, request journal, isolation receipts,
  and monetary monitor do not apply to this cohort. No exact API-request or token
  totals were captured. Kilo displayed rounded costs of $0.01 for migration and
  $0.00 for each other task; these are not verified charges or a quota statement.
- New Kilo sessions defaulted to GLM-5.3; the operator explicitly selected and
  verified GLM-5.3-Flash before the two new submissions. The model menu labels
  Flash as `Z.AI`, while GLM-5.3 is labelled `Z.AI Coding Plan`. The actual endpoint
  and charging product for Flash were not inspected; successful UI responses
  alone do not prove Coding Plan quota was used.
- The workspace is the Skill repository itself and other installed workflow
  descriptions are available. That is a strong discovery cue and is not an
  isolated Skill-absent comparison. General discovery in an unrelated project,
  other modes, statistical reliability, and harder-case uplift remain untested.
- Observed actions were fixture/Skill reads, directory listings, and the local
  verifiers. No worktree or branch switch was performed. No Skill source or
  fixture edits were made. Kilo sessions retain the underlying local UI history;
  this report intentionally excludes raw reasoning and private configuration.

Keep the current Skill unchanged. A physically Skill-absent same-model comparison
remains necessary for the stricter isolation claim. The user subsequently chose
the lighter prompt-only comparison described below.

## Follow-up paired comparison: completed

The user authorized four pairs through native Kilo, comparing permission to use
the Skill against an explicit instruction not to use it. This is a separate
diagnostic cohort, not the frozen T1 physical-isolation experiment.

- Cases: resource-handler-03, auth-incident-05, token-logging-08, auth-chain-12.
- One fresh session per case and condition, intended model GLM-5.3-Flash, Code
  mode; 220-word response limit and identical task wording within each pair.
- Prohibited condition: `Do not use the adversarial-thinking skill. Do not invoke
  it or read its SKILL.md or supporting files. Complete the task using your normal
  workflow.`
- Allowed condition: `You may use the adversarial-thinking skill if applicable.
  Complete the task using your normal workflow.` This permits rather than forces
  loading; a run that skips it cannot establish the effect of loading its body.
- Eight neutral case directories are prepared under a shared temporary workspace
  outside the Skill repository. All 24 copied artifact hashes matched the frozen
  preparation manifest. Controller gold and reports stay outside that workspace.
- Planned order alternates the first condition across pairs: 1 prohibited/allowed,
  2 allowed/prohibited, 3 prohibited/allowed, 4 allowed/prohibited.
- Score verdict, decisive evidence inspected, next-action correctness, unsupported
  blockers, observed versus proposed checks, and visible Skill loading. Inspect
  tool traces rather than trusting a model's claim that it did not use the Skill.

Global Skill metadata may remain visible in both conditions; other installed
workflows and the prompt intervention are additional confounders. Four small,
explicitly cued cases with unblinded manual scoring and one sample per condition
cannot establish statistical or general causal uplift. Neither the prohibition
prompt nor the shell-write sandbox makes the Skill physically absent.

Opening the temporary workspace initially activated VS Code Restricted Mode.
The user confirmed trust, the banner disappeared, and Kilo loaded successfully.
This setup interruption preceded the first model submission. Eight fresh Kilo
sessions then completed, with GLM-5.3-Flash visibly selected before each submission.
The first started at 13:52:09 UTC and the last at 14:07:37 UTC on 2026-09-05.
No provider error, model retry, or interrupted/resumed model session was observed.
Some controller UI actions needed recovery before submission; those were not
additional model trials.

| Case | Prohibited condition | Allowed condition | Visible Skill loading (prohibited / allowed) |
| --- | --- | --- | --- |
| resource-handler-03 | Rejects approval: ownership check absent; add negative authorization test and fix | Same verdict and next action | No / No |
| auth-incident-05 | Rejects retry/purge; read-only clock-offset check before remediation | Same verdict; common-reference NTP/chrony check, distinguishes which host is wrong as unknown | No / Yes: Skill adversarial-thinking, then Read review.md |
| token-logging-08 | No blocker; retains contract-compliant change | No blocker; retains change | No / No |
| auth-chain-12 | Current authorization evidence beats correlated stale panel | Same verdict | No / No |

Both conditions got **4/4 decisive judgments correct**. Every session read all
three relevant evidence files. No prohibited-condition Skill invocation or Skill
file read was observed. Only **1/4 allowed-condition sessions loaded the Skill**;
that session also read its review branch. The other three pairs do not compare
loaded Skill behavior against unloaded behavior. There is **no observed verdict
advantage**, and this small prompt-only cohort does not establish causal uplift
or equivalence. No replacement samples were run to increase the activation rate.

Next-action quality was weaker than verdict accuracy: in auth-chain-12, **both
conditions unnecessarily proposed rerunning the review panel**, despite the
decisive current-state artifact. The prohibited answer explicitly makes panel
convergence a prerequisite to approval. Manual assessment therefore marks the
smallest-next-action criterion 3/4 in each condition. This is extra verification
burden, not a newly discovered authorization defect, and cannot be attributed to
the Skill because neither session loaded it.

Additional wording limits:

- The loaded incident answer calls three lines of one log independent support;
  their independence is not established. The baseline says only clock mismatch
  explains the rejection, which is also stronger than a finite fixture warrants.
  Both nevertheless propose confirmation rather than claiming to have executed it.
- Both logging answers recommend merging from the supplied frozen evidence. The
  allowed answer says no further verification is needed and describes evidence.md
  as independent corroboration without establishing provenance. These conclusions
  are scoped to the fixture, not a real repository or production approval.
- The authorization baseline calls the frozen runtime summary verified
  end-to-end. It read a supplied artifact; it did not perform a fresh runtime test.

The visible tools across this cohort were Read, Glob, and the one Skill call.
No commands, edits, delegates, worktrees, or production actions were observed.
All 24 post-run artifact hashes matched their pre-run values. Skill source was
not changed. All eight displayed costs were rounded `$0.00`; exact usage,
charges, and whether Coding Plan quota was used remain unverified. The response
length constraint was prompted but exact word counts were not audited.

The companion [structured evidence](2026-09-05-kilo-prompt-paired.json) records
exact prompts, neutral-directory mapping, hashes, session start times and titles,
visible tool summaries, and manual assessments. It contains operator summaries
rather than verbatim transcripts; underlying conversations remain in local Kilo
history. It excludes raw reasoning and controller gold.

Keep Skill 0.1.1 unchanged on this evidence. If measuring the effect of its body
is the next objective, predeclare a separate explicit-load condition and compare
it with the prohibition condition; do not relabel these permissive samples.
