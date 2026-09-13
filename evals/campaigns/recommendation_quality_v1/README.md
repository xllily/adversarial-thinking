# Recommendation quality diagnostic

Four public development cases derived from the 2026-09-13 native observations:
unsafe migration advice, inaccurate description of step ordering, and a supported
positive contrast for each. These are deliberately small supplied-evidence
cases, not held-out tasks or an extension of the frozen T1 pilot.

Current: v0.1.1 Skill and Review bodies from the pinned commit in prepare.py.
Candidate: the same bodies plus one Review paragraph, stored only as a patch.
The active Skill remains unchanged. Gold stays controller-side and is never
included in target prompts. Full bodies and case artifacts are supplied inline
to reduce file-discovery and manual permission confounds seen in the prior run.

Prepare outside the repository using a fresh output directory:

    python3 evals/campaigns/recommendation_quality_v1/prepare.py --output /private/tmp/rq-v1-NEW

Preparation checks the four case IDs and patch shape, applies the patch to a
temporary copy, and hashes source files and exact prompts. Re-preparation must
produce identical prompt hashes. Eight cells run once each in fresh native
Kilo sessions, with GLM-5.3-Flash, Code mode and the current Default profile.
Use numbered prompts in order; the condition order alternates between cases.
No follow-up hints, retries, mode/model changes or automated judging. Stop for
transport failure, model drift, or unexpected tool use; preserve partial results.

Freeze the rubric before sending any prompt. Read results against decision,
correction safety, source fidelity, evidence honesty and unnecessary blocking.
One run per cell, familiar synthetic cases and ambient native context prevent
causal or generalization claims. This is not an isolated C0 experiment. Compare
current vs candidate only, and do not infer model comprehension from exposure.
Native cost and immutable model identity remain unverified; no monetary cap is
claimed. A candidate failure or both conditions passing is reason to retain the
current Skill. An apparent improvement requires fresh-case replication before
promotion. New post-hoc failure cases belong in a subsequent freeze.
