# GLM automatic discovery diagnostic — 2026-09-05

The first real behavioral request returned **HTTP 429**. The batch stopped with
no retry and no model response. Automatic activation and low-risk skipping remain
**unverified**. No Skill behavior changed; version remains 0.1.1.

## Intended test and actual evidence

The frozen two-conversation plan advertised only the current Skill frontmatter.
The high-risk migration review required an observed read of `SKILL.md` followed
by `references/review.md`. The independent low-risk conversation asked for a
plain-English rewrite of one sentence and should skip Skill reads. The low-risk
conversation was never attempted. No API-only connectivity probe was sent.

Before the request, actual non-root, read-only, network-disabled Docker receipts
passed, forbidden read/shell commands were denied, and all seven Skill files
matched the installed current version. The existing migration mount was reused;
no old frozen fixture, gold, worker, or receipt profile was changed. All mounted
payload files matched published commit `dea67ec` of the public repository.

The request reached an HTTP endpoint that returned 429. The harness deliberately
does not expose error bodies, so this status does not distinguish rate limiting,
quota, concurrency, or another provider policy. Model availability and tool
compatibility remain unverified. There is no observed Skill decision or tool
read to score and no harder paired cases were attempted after this error.

## Runtime and accounting

- Provider: `https://open.bigmodel.cn/api/paas/v4/chat/completions`,
  model `glm-5.3-flash`, immutable version unknown.
- New cohort: `9493fa5245d26ddf6ec770e40c8a6399ec1c8ec5516482bd449061d093f5120d`.
- Frozen settings: 4096 `max_tokens`, enabled thinking, `low` effort,
  full tool-call reasoning replay; 60-second response-end pacing and request
  timeout; first provider/runtime error stops. The documented model requires
  thinking, so disabling it was not used. See the [official API contract](https://docs.bigmodel.cn/api-reference/模型-api/对话补全.md).
- One new attempt; 14 cumulative reserved requests out of 96. No new reported
  token usage. No retry or second conversation.
- Prior reference spend: CNY 0.093633, plus CNY 0.022569 held for prior unknown
  usage. Those historical amounts were carried without repricing old tokens.
- New unknown request reservation: CNY 0.013466. Combined reference allocation:
  **CNY 0.129668 / 3.000000**. The unknown reservation remains held even for 429.
- New estimates use original [BigModel reference prices](https://bigmodel.cn/pricing)
  checked 2026-09-05: CNY 0.8/2.8 per million input/completion tokens, no temporary
  or cache discount. Decimal calculations round conservatively upward to whole
  microyuan per request. Actual provider invoice charges remain unknown.

## Conclusion

This is a provider-status block, not evidence of Skill success or failure.
Earlier explicit reviews remain Skill 2/2 and baseline 2/2 with no observed
advantage; they are a different model cohort and cannot establish a GLM effect.
Keep the Skill unchanged. A future separately authorized attempt must first
inspect this failure journal and retain both historical and new held amounts.
Do not replay this claimed plan or resume it automatically.

The accompanying [sanitized evidence](2026-09-05-glm-discovery.json) records the
plan, settings, receipt digest, failure category, and accounting. No credentials,
raw reasoning, private runtime paths, or provider response bodies are published.

Local validation: 66 harness tests and 10 pilot tests passed (76 total).
