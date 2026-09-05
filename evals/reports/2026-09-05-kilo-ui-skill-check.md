# Current Skill in VS Code Kilo — 2026-09-05

Three tasks completed through the user's configured VS Code Kilo sidebar.
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

Keep the current Skill unchanged. The next useful evaluation is a fresh,
non-interrupted review in a neutral workspace with a physically Skill-absent
same-model comparison, checking corrective-action correctness as well as verdict.
