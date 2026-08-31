# Adversarial Thinking

An experimental Agent Skill for running a bounded disconfirmation checkpoint before consequential commitments.

It is not a permanent contrarian persona. It challenges only assumptions that could change the next commitment, integrates the evidence, and returns control to the host workflow.

## Why it exists

Agents can anchor on a proposed route, reward reviewer suspicion, continue symptom patches after the causal model has failed, or confuse authority with evidence. This skill provides one shared checkpoint across those failure modes without replacing domain-specific review, planning, brainstorming, or debugging methods.

## Modes

| Immediate deliverable | Mode | Output |
|---|---|---|
| Judgment or report | Review | Evidence-grounded verdict or no-finding result |
| Frame or option widening | Brainstorm | Distinct mechanisms followed by convergence |
| Executable course before commitment | Plan | Ordered plan with validation, abort, and recovery gates |
| Repeated execution failure or drift | Exec | Causal reset and smallest predicted correction |

With no branch signal, the skill runs only its core Frame → Countermodel → Discriminate → Integrate checkpoint. It defaults to one decision-relevant countermodel and one discriminating check.

## When not to use it

- Work is merely long, difficult, or open-ended.
- A low-risk reversible action has no decision-relevant countermodel.
- A domain method already resolves the question and another checkpoint cannot change the next commitment.
- The intent is security penetration testing or adversarial machine-learning research.

## Install

This repository root is the skill directory.

- **Codex:** ask the built-in `$skill-installer` to install the published repository URL, or place this directory in a Codex-configured skills location.
- **Claude Code:** place or link this directory at `~/.claude/skills/adversarial-thinking`.
- **Other Agent Skills hosts:** add the repository root to the host's skill discovery path.

Restart or refresh the host's skill list after installation. Confirm activation in a fresh task before relying on automatic discovery.

## Invoke

Use the canonical skill name plus a separate mode instruction:

```text
Use adversarial-thinking in review mode. Review this migration plan and report only.
```

```text
Use adversarial-thinking in exec mode. Five fixes are oscillating; reset the causal model and continue safely.
```

Colon-suffixed names such as `adversarial-thinking:review` are not separate registered skills.

## Evidence status

The package contains 34 behavioral specifications in [`evals/evals.json`](evals/evals.json). A first retrospective A/B campaign ran 18 fresh-context trials across high-risk review, execution-loop recovery, and a low-risk negative case.

Both the no-skill baseline and skill-enabled runs passed all 9 trials. This establishes no observed regression in those scenarios, but **does not establish incremental improvement over the tested default model**. Model identity, cross-model portability, automatic-trigger accuracy, token cost, and latency remain unverified. See [`evals/README.md`](evals/README.md) and the [2026-08-31 result](evals/results/2026-08-31-retrospective-ab.md).

Fresh-context discovery by the explicit `$adversarial-thinking` name and Review branch loading passed in the installed Codex environment. Implicit invocation without naming the skill remains unverified.

Treat version 0.1.0 as experimental. Do not rely on it as the sole control for consequential production decisions.

## Contributing

Behavior changes should include a scenario that would distinguish the old and proposed behavior, fresh-context baseline and skill-enabled outputs, the tested host/model when available, and a concise result. Prefer narrow corrections supported by observed failures over adding speculative universal rules.

## License

Apache-2.0. See [`LICENSE`](LICENSE).
