# Automatic Skill discovery diagnostic

`discovery_check.py` tests the current Skill with frontmatter-only discovery in
two fresh conversations: a consequential migration review and a simple inline
sentence rewrite. The high-risk case must read both `/skills/SKILL.md` and
`/skills/references/review.md`; the low-risk case must answer without Skill reads.
Both use the same already-frozen, read-only mount. The rewrite does not modify
or derive a new campaign fixture. This diagnostic is not a paired uplift study.

The exact HTTPS BigModel endpoint and `glm-5.3-flash` model are required. The
2026-09-05 cached official contract requires thinking for this model. The frozen
payload uses `max_tokens=4096`, enabled thinking, `reasoning_effort=low`, and
`clear_thinking=false`. Tool-call reasoning is replayed verbatim, controller-local;
it must never be included in public reports. The GLM payload omits `n` and the
undocumented `parallel_tool_calls` hint; returned calls execute sequentially.

Before execution, preparation checks actual container receipts and denials,
current Skill equality, source hashes, prior accounting, and the old manifest.
Execution recomputes the plan, claims its ledger exclusively, and claims the
previous summary once. It does not bypass same-provider continuation guards.
Only historical monetary amounts and usage counts carry to the new cohort.
Original reference rates are CNY 0.8/2.8 per million input/completion tokens;
new request estimates round upward to a whole microyuan. Historical DeepSeek
money and unresolved reservations are preserved without repricing token counts.

The cumulative reference ceiling stays CNY 3 and 96 requests, with at least 60
seconds after every response before the next attempt. Each request reserves its
full 4096 completion cap plus request-byte-based input allowance before sending.
The input allowance is not a proven tokenizer bound or an invoice guarantee.
The new diagnostic freezes a 64,000 cumulative reported-token stop threshold per
conversation, 32,768 request bytes, 12 model requests and 12 tool calls per run,
60-second request deadlines and 360 active seconds per run (pacing excluded).
The old shakedown defaults remain unchanged. The first provider/runtime error
stops the batch without retry. No standalone connectivity probe is called.

Prepare is zero-model-call work; run requires the exact plan digest and existing
user authorization. Interrupted/failed executions must be inspected, never
restarted automatically. Raw responses and configuration stay ignored under
`evals/.runs`; publish only reviewed visible answers, tool reads, receipt hashes,
usage, timing, and clearly limited conclusions.
