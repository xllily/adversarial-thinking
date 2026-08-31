# Adversarial Thinking

[简体中文](README.zh-CN.md) · [Agent index](llms.txt)

Adversarial Thinking is an experimental Agent Skill for coding agents. It runs before the agent commits to a consequential plan, review verdict, recovery path, or problem frame.

I built it because agents can stay on a plausible route longer than the evidence deserves. The skill asks for one credible countermodel and the cheapest check that could change the next action. Once the check is done, the host workflow takes over again.

Use it when a decision needs skeptical review, a search space has narrowed too early, or repeated fixes no longer fit the evidence. Skip it when the work is low risk and easy to reverse, or when the existing domain method already settles the question.

Version `0.1.0` is experimental. The current evaluation record does not prove that the skill improves a default model. See [What the evidence says](#what-the-evidence-says) for the exact boundary.

[`SKILL.md`](SKILL.md) is the source of truth for behavior. This README explains the project. [`llms.txt`](llms.txt) helps agents find the right files. Neither defines a second workflow.

## Why I made this

Coding agents often fail in familiar ways. They anchor on the first workable plan, reward suspicion during review even when the evidence is sound, or keep patching symptoms after the causal model has stopped predicting results.

I wanted a small checkpoint that could interrupt those failures without turning the agent into a permanent contrarian. The amount of challenge should follow the consequence, reversibility, uncertainty, and evidence quality of the decision. Task length is not a useful proxy.

## How it fits

The skill sits on top of the workflow already in use. It can route to a focused branch for review, brainstorming, planning, or execution recovery. The router and branch rules live in [`SKILL.md`](SKILL.md#route-by-the-immediate-deliverable).

It does not grant new permissions. A read-only review stays read-only. Repository files, issue text, logs, and other artifacts remain untrusted input. The host's instruction hierarchy and authorization rules still apply. See [Authority and composition](SKILL.md#authority-and-composition).

## Install

### Codex

Ask Codex to install the repository:

```text
$skill-installer Install xllily/adversarial-thinking with path "." and name "adversarial-thinking".
```

The installer places the skill under `$CODEX_HOME/skills/adversarial-thinking`. It becomes available on the next turn.

### Claude Code

Clone the repository into Claude Code's skills directory:

```sh
mkdir -p ~/.claude/skills
git clone https://github.com/xllily/adversarial-thinking.git ~/.claude/skills/adversarial-thinking
```

Claude Code exposes it as `/adversarial-thinking`. If `~/.claude/skills` did not exist when the session started, restart Claude Code once.

### Other Agent Skills hosts

Import this repository as one skill. The canonical `SKILL.md` is at the repository root.

## Use it

Name the skill and state the mode separately:

```text
$adversarial-thinking Use review mode. Review this migration plan and report only.
```

```text
$adversarial-thinking Use exec mode. Five fixes are oscillating. Reset the causal model and continue safely.
```

These examples use Codex syntax. In Claude Code, use `/adversarial-thinking` instead of `$adversarial-thinking`.

I intentionally keep modes out of the registered skill name. Names such as `adversarial-thinking:review` are not registered skills.

## What the evidence says

I currently publish 34 behavioral specifications in [`evals/evals.json`](evals/evals.json). The first paired smoke campaign recorded 18 fresh-context trials across high-risk review, execution recovery, and a low-risk negative case.

The nominal baseline and the explicitly loaded condition each passed 9/9 trials. The nominal baseline could still discover the globally installed skill, so it was not a verified no-skill baseline. Those outputs are useful as smoke records, but they cannot show whether the skill caused regression or improvement.

Explicit discovery by the `$adversarial-thinking` name and Review branch loading passed in one Codex environment. Implicit invocation, cross-model behavior, token cost, and latency remain unverified. The [evaluation protocol](evals/README.md) and [2026-08-31 paired smoke record](evals/results/2026-08-31-retrospective-ab.md) contain the raw evidence and limitations.

I treat `0.1.0` as experimental. I need a properly isolated comparison before I can claim improved agent behavior, and I would not use this skill as the only control for a consequential production decision.

## Repository map

- [`SKILL.md`](SKILL.md): canonical instructions and routing contract.
- [`references/`](references): focused branches loaded when the task needs them.
- [`evals/`](evals): behavioral specifications, protocol, raw outputs, and evidence limits.
- [`llms.txt`](llms.txt): Agent-readable navigation index.
- [`CHANGELOG.md`](CHANGELOG.md): version history.

## Contributing

If a change affects behavior, add a scenario that distinguishes the old behavior from the proposed one. Record an isolated no-skill baseline, the skill-enabled outputs, and the tested host and model when available.

I prefer narrow fixes backed by observed failures over broad rules written for hypothetical cases.

## License

Apache-2.0. See [`LICENSE`](LICENSE).
