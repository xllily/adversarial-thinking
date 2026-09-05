# Current Skill paired review check

The earlier diagnostic model saw the discovery description but never read the
Skill body. Its API/tool results do not establish current-Skill effectiveness.
This separate check tests explicit invocation of the installed 0.1.1 Skill.

For each of two frozen fixtures, the controller reads all workspace files and
runs `python3 verify.py` inside the existing isolated Docker mount. Both members
of each pair receive byte-identical artifact and observed-check evidence. The
only message difference is the treatment system content: the full unmodified
`SKILL.md` and `references/review.md`, plus explicit review-mode invocation.
Every file in the frozen C1 bundle must equal the current installed source.
C0 remains physically Skill-absent during evidence capture and receives no
Skill text. All receipts are retained; gold and condition labels stay outside
model messages. Order is C0/C1 for the first fixture and C1/C0 for the second.

Before requests, freeze these acceptance criteria:

- Migration: block the incompatible column removal, identify affected deployed
  readers, and distinguish the controller's observed failure from future checks.
- Dual-write: retain the staged canary when the complete rehearsal defeats the
  specified countermodel, preserve rollback/abort criteria, and invent no blocker.

There are exactly four fresh requests, at most 4096 completion tokens each,
with a shared 60-second gap and the previous CNY 3 budget carried forward,
including unresolved reservations and prior attempts. Errors, missing usage,
truncation, or budget overruns stop without retry. Preparation executes only
local Docker checks and makes zero model calls.

```sh
python3 evals/harness/skill_check.py prepare --root ISOLATED_ROOT \
  --previous-plan-sha256 PREVIOUS_FAILED_PLAN_SHA --plan NEW_PLAN_FILE
python3 evals/harness/skill_check.py run --root ISOLATED_ROOT \
  --plan NEW_PLAN_FILE --authorize-plan-sha256 REVIEWED_SHA
```

The result is a small supplied-evidence judgment check, reviewed against the
frozen criteria. It does not test automatic discovery, autonomous tool use,
other Skill modes, candidate variants, or statistically reliable uplift.
Responses are not exported as T0 scored evaluation records. Report paired
decisions and evidence quality even when the baseline also succeeds; differences
in formatting alone are not improvements. Actual gateway billing and immutable
model version remain unknown.
