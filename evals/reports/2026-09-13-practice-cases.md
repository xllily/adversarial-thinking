# Practice-derived review cases

These retrospective observations motivate behavioral specifications, not a
causal effectiveness claim. They were selected after seeing favorable outcomes.
No matched skill-absent runs, blind scores, or comparable cost measurements are
available. This review also has prior exposure to the proposed interpretation.

## Roadmap sequencing

Source: codex://threads/01a076c5-1093-7903-b0cb-856586e0299c
("评审 v0.3.0 路线图").

The reviewed roadmap combined a packaging repair and plugin delivery with broad
scenario and infrastructure expansion. The observed recommendation prioritized
the LICENSE gap, a minimal plugin wrapper, and then one demonstrated backend
scenario. Missing comparative isolation prevented an uplift claim.

Competing explanation: ordinary repository inspection and the user's scope
preferences could produce the same recommendation without the Skill. The
decision change is useful practice evidence; its cause and saved effort are
unmeasured. The case does not establish delivery or production success.

Derived specification: `practice-roadmap-evidence-sequencing`.

## Native platform reuse

Source: codex://threads/01a07ef6-8c27-74f2-94f8-91f5ed3bd7c0
("增加 new-api 二开项目规则").

The user explicitly required maximum reuse and a minimal implementation path.
The observed documentation revision used Channel, Group, Tag, Multi-Key and
Relay Token, and removed unsupported capacity configuration, new Account/Pool
tables, a special import API, global locking and a complex state machine.

Competing explanation: following the user's explicit constraint accounts for
the convergence. Documentation changes do not prove runtime adequacy, reduced
defects, or a Skill-specific improvement.

Derived specification: `practice-platform-capability-reuse`.

## Calibration and evaluation boundary

`practice-supported-extension-retained` is a synthetic contrast, not a third
observed practice. It supplies a demonstrated native-capability gap and a tested
minimal extension. Correct review retains the extension. Together these cases
check evidence-sensitive judgment rather than a preference for smaller designs.

The three public specifications are development data. Semantic review checks
requirement coverage, evidence attribution, unnecessary blocking, and scope
expansion. JSON validation cannot establish that a model passes them. Future
comparisons must freeze prompts and rubrics before outputs, use fresh isolated
contexts, and retain cost and failure records. These additions do not alter the
frozen T1 pilot or justify promoting C3.

## Plan review and local verification

Verdict: proceed with corrected acceptance criteria. The initial ticket plan
assumed that the existing eight-run diagnostic runner could feed T0 scoring and
then expand to the sentinel. The runner documentation explicitly excludes T0
export, sentinel expansion and automatic judging. The local tickets therefore
include these delivery gaps and require blind-judge validation before outputs.
A C1/C3-only sentinel cannot establish improvement over skill-absent C0.

On 2026-09-13, all 39 behavioral specifications parsed with unique IDs and valid
nonempty prompt/expected-output fields. The frozen T1 pilot passed verification
(12 cases, four conditions). Actual Docker isolation rehearsal passed all eight
targets using the cached pinned image, with zero model calls. Runtime artifacts
remain local and may be ephemeral; machine-specific paths are omitted here.
These checks validate specifications, fixture integrity and offline isolation;
no new model behavior or causal effect was measured.
