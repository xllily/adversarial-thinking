# T1 isolation rehearsal and diagnostic agent shakedown

The next step after the successful two-request provider probe is an eight-target
operational check: `migration-compat-01` and `dual-write-06`, each under C0–C3.
The scripts here do not modify `eval.py`, fabricate isolation receipts, supply
judge scores, or export T0 run records.

## Offline isolation layer

`isolation.py` copies each fixture and assigned bundle into a separate directory
outside Skill discovery trees. It never imports provider configuration. Each
container mounts only its fixture, its assigned Skill (absent under C0), and a
credential-free tool worker. The controller manifest, gold, other conditions,
repository, user home, and Docker socket are not mounted.

The pinned official Python image is:

```text
python@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254
```

Containers use `--pull=never`, `--network=none`, `--read-only`, UID 65534,
`--cap-drop=ALL`, `no-new-privileges`, and CPU/memory/PID limits. The worker starts
with a cleared environment. Each tool invocation gets a fresh container; it is
removed on completion, failure, or normal interruption. An uncatchable host kill
can still leave a container; inspect the `t1-isolation-` prefix before recovery.
No generic shell execution is available. `shell` accepts exactly
`python3 verify.py`, and `read` is restricted to regular files below `/workspace`
or `/skills`, without traversal or symlinks. This restricted tool contract is
identical across the eight targets and is explicitly a shakedown runner, not a
claim of parity with a general coding agent.

The worker hashes actual mounted files. The controller compares the observed
receipt with frozen workspace and bundle hashes. Offline rehearsal also checks
non-root identity, read-only workspace, active loopback-only interfaces and no
IPv4 routes, unavailable controller/global-configuration paths, absence of
credential environment variables, working reads/verifiers, and rejected escape
attempts. Docker Desktop may expose inactive tunnel interfaces; those are not
mistaken for network access.

From the repository root, using a new canonical directory on each rehearsal:

```sh
python3 evals/harness/isolation.py prepare --root /private/tmp/t1-isolation-NEW
python3 evals/harness/isolation.py rehearse --root /private/tmp/t1-isolation-NEW
```

The official image must already be cached. Setup and these commands make zero
provider calls. A verifier exit code of 1 is a valid observed negative result,
not an infrastructure failure. All eight receipts must match before planning
real agent requests. An offline receipt is not evidence that a model ran.

Runtime controls follow the official [Docker run reference](https://docs.docker.com/reference/cli/docker/container/run/)
and the [official Python image](https://hub.docker.com/_/python), checked 2026-09-05.

## Diagnostic agent runner

`shakedown.py` maintains fresh model history per target. The default `discovery` profile lists actual
workspace files and, for C1–C3, the mounted Skill's frontmatter and path. It does
not inject the full Skill body unless the model reads it. C0 has no Skill mount.
Only the public prompt, discovery information, and tool results reach the model;
no gold, condition labels, assignments, or credentials enter the messages.

The controller holds the API key. Docker subprocesses get only explicitly
allowlisted client environment variables, and the container gets a cleared
environment. Model-selected tool names, IDs, JSON arguments, and the shell
command are validated for the entire response batch before dispatch. If a gateway
returns several calls despite `parallel_tool_calls=false`, they execute
sequentially after the whole batch fits the remaining tool budget. Duplicate IDs
or an invalid later member reject the whole batch. Provider response bodies and full tool
traces are retained locally with key redaction; console failures are generic.

Generate the reviewable plan after successful offline rehearsal:

```sh
python3 evals/harness/shakedown.py plan --root /private/tmp/t1-isolation-NEW
```

The plan binds the provider configuration fingerprint, runtime image, manifest,
all offline receipts, tools, budgets, and relevant source digests. Creation does
not authorize requests. After explicit approval of that plan, execute:

```sh
python3 evals/harness/shakedown.py run \
  --root /private/tmp/t1-isolation-NEW \
  --authorize-plan-sha256 REVIEWED_PLAN_SHA256
```

The operational envelope is:

- 8 targets, at most 12 model requests per target / 96 total;
- at most 1024 completion tokens per request / 98304 total requested maximum;
- 12288 request bytes per request and 65536 response bytes;
- at most 12 tool calls and a 180-second active agent-loop deadline per target;
- a 30-second deadline for each provider request on this Unix controller;
- at least 60 seconds from each response ending to the next request, across targets;
- no retries, redirects, model/protocol fallback, delegation, or automatic judge;
- abort the entire batch on its first failed or incomplete run.

Provider requests use `max_completion_tokens` and the existing Chat Completions
transport. [Official parameter documentation](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)
was rechecked 2026-09-05. A truncated response, missing/invalid usage, duplicate
call ID, malformed call, or exceeded budget ends the batch.

The frozen 16000-total-token profile is checked against reported usage after
responses. A conservative request-bytes-plus-completion-cap guard prevents
obvious overspending before dispatch, but no provider tokenizer bound has been
verified. Input billing can differ and a response can cross the threshold; such
an overrun is recorded and aborts execution. Do not present this as a hard input
token cap or a monetary ceiling. Infrastructure inspection/cleanup time is
outside the agent-loop timer.

The shared request pacer measures the gap with a monotonic clock. Tool execution
already consumes part of that gap; any remaining wait is excluded from the
180-second active deadline. Result records report total latency, active latency,
and pacing wait separately. Interrupting a wait sends no request. A failed HTTP
request still ends the batch without retry, regardless of the pacing policy.

The discovery profile's CNY 3 reference threshold is monitored across all eight runs by
`CostBudget`, using integer microyuan and the official peak reference rates
(CNY 3 / million input, CNY 9 / million output), without a cache discount. The
rate source and date are bound into the plan. Before transmission, the controller
journals a reservation based on request bytes plus 512 input-overhead tokens and
the completion cap. It blocks a request that could reach the estimate threshold.
After every response, reported usage replaces that reservation; reaching CNY 3
or exceeding the request reservation stops the batch. Missing usage, timeouts,
or journal failures also stop; unresolved reservations are never treated as zero.

This is a reference-price monitor, not actual gateway billing telemetry. The
assumed input-token bound and the gateway's fee/multiplier remain unverified;
`actual_gateway_cost_cny` stays null. Each `cost-*-reserved/observed/blocked.json`
and the summary/failure file records the monitor state. A response can cross a
threshold before it is observed; no later request is sent. The CNY 3 scope is
this newly authorized batch, excluding the earlier three diagnostic requests.

Plans and attempt ledgers use exclusive creation and fsync before transmission.
Rerunning the same plan is refused, even after interruption or success. An
unknown outcome consumes authorization; inspect saved attempts and obtain new
scope before recovery. Never delete evidence to make a retry possible. For a
separately reviewed repair, `plan` and `run` accept `--plan NEW_PLAN_PATH`, allowing
a new plan to reuse unchanged, verified mounts without overwriting the previous
plan or its failed ledger.

When the user authorizes continuation after a failed batch, prepare a fresh plan
with `--previous-plan-sha256 PREVIOUS_DIGEST --plan NEW_PLAN_PATH`. The controller
binds the failed ledger and unchanged campaign, provider, and offline evidence;
skips completed targets; and restarts only incomplete targets with fresh messages.
Previously reported cost, unresolved reservations, usage, and attempted requests
carry forward against the same CNY 3 and 96-request limits. Each failed parent
can be claimed by only one continuation. Continuation begins with a 60-second
cooldown, retains all earlier evidence, and does not reuse a partial transcript.
This requires new user scope after the failure; it is never automatic recovery.

## Explicit Review body exposure (M1)

The opt-in `explicit-review` profile measures behavior after providing the frozen
Review instructions. It does not measure automatic Skill discovery. It uses the
same eight targets, full seven-file treatment bundles, case prompts and permitted
tools. C0 still physically lacks the Skill mount. C1–C3 receive the exact UTF-8
contents of their assigned `SKILL.md` and `references/review.md` in the first
system message; the other five files remain available through `read`.

All targets start with this common system text, followed by `Workspace files: `
and the sorted file listing:

```text
Work within /workspace using the available read and shell tools. Do not edit files. Stop with a final answer when evidence is sufficient.
```

Only C1–C3 then receive the instruction to use adversarial-thinking in review
mode and the two bodies separated by `--- SKILL.md ---` and
`--- references/review.md ---`. C0 receives no such suffix or discovery metadata.
The controller does not supply fixture contents or verifier outcomes in advance.
The model selects its own evidence reads and checks. Exposure is not proof of
comprehension, compliance, or improved decisions.

This narrow profile requires `openai-chat`, the BigModel standard API endpoint
`https://open.bigmodel.cn/api/paas/v4/chat/completions`, model `glm-5.3-flash`, and
declared tool support. It binds these request options in the plan:

```json
{"max_tokens":4096,"thinking":{"type":"enabled","clear_thinking":false},"reasoning_effort":"low"}
```

Requests remain nonstreaming and omit `n`, `parallel_tool_calls`, and
`max_completion_tokens`. The completion reservation also uses 4096, giving a
maximum requested allowance of 393216 over 96 requests. The 16000 cumulative
reported-token stop threshold, 12288 request bytes, 12 tools, 180 seconds active
time, 30-second request deadline, 60-second gap and CNY 3 reference stop threshold
remain unchanged. All conditions use the same caps; extra instruction tokens
count against the treatment's budget. Real usage and actual billing remain
unknown until observed; this profile does not establish a provider billing cap.

For this profile, the pre-send token check is now:

```text
prior reported total + local input token count + 512 margin + completion cap <= 16000
```

The 12288-byte wire check remains independent. Local input counting includes
the complete messages, tool definitions/calls/results, retained reasoning and
generation prompt. A response whose reported input exceeds the local count plus
512 stops the batch after preserving the response and reference-cost accounting,
before executing its tools or sending again. The 512 margin is an explicit
unverified allowance, not a proven hosted-tokenizer upper bound. The monetary
reservation still uses wire bytes plus 512 and the completion cap; its policy
is distinct from this token dispatch check. Default discovery keeps its old guard.

Counting uses only the three official files `tokenizer.json`,
`tokenizer_config.json`, and `chat_template.jinja` at
[GLM-5.3-Flash revision 690b705278a3a58e538fcb37c2ca8b5f9511213c](https://huggingface.co/zai-org/GLM-5.3-Flash/tree/690b705278a3a58e538fcb37c2ca8b5f9511213c).
Place these files in a local asset directory. The runner verifies their fixed
SHA256 values before parsing and never downloads files or loads model weights or
remote Python. Use a separate environment with the pinned counting dependencies:

```sh
python3 -m venv /private/tmp/glm-tokenizer-env
/private/tmp/glm-tokenizer-env/bin/python -m pip install --only-binary=:all: tokenizers==0.23.2 jinja2==3.1.6
```

Missing/changed assets or mismatched dependency versions reject planning or
execution. The plan binds the resolved asset directory, three hashes, package
and Python versions, and margin policy. Runtime uses those verified in-memory
assets. Other profiles do not import these additional dependencies.

There is no default GLM price. Supply a JSON object with these required fields:

| Field | Required value |
|---|---|
| `model` | `glm-5.3-flash`, matching the selected model |
| `input_cny_per_million`, `output_cny_per_million` | Positive finite reference rates in CNY per million tokens |
| `source` | HTTPS source for the supplied rates |
| `checked_date` | Valid `YYYY-MM-DD` date, no later than today |

The controller binds the supplied source/date/rates; it does not verify their
truth, current applicability, account entitlements or actual charges. Obtain
those facts before requesting real-call approval. The historical 0.8/2.8 GLM
rates in offline tests are fixtures, not a current pricing claim. DeepSeek's
default policy cannot substitute for the required model-specific GLM policy.

After a fresh offline rehearsal, generate the plan without making model calls:

```sh
/private/tmp/glm-tokenizer-env/bin/python evals/harness/shakedown.py plan \
  --root /private/tmp/t1-isolation-NEW \
  --profile explicit-review \
  --cost-policy /private/tmp/glm-reference-policy.json \
  --tokenizer-dir /private/tmp/glm-tokenizer-assets \
  --plan /private/tmp/t1-isolation-NEW/explicit-review-plan.controller.json
```

The plan binds each target's two raw-file hashes (empty for C0), first serialized
request hash/size and input estimate/reservation, GLM options, reference policy and completion cap, in addition
to the existing configuration, code and isolation fingerprints. At execution,
the controller reconstructs the plan and re-reads the two files through the
actual isolated tool mounts. Any mismatch stops before that target's first send.
The local ledger retains `exposure.json` and `request-N.json` digests/sizes and input estimates/reservations,
alongside durable attempts, responses, tool traces and cost reservations.

Only after approval of that exact plan and its reference-monitor limitations:

```sh
/private/tmp/glm-tokenizer-env/bin/python evals/harness/shakedown.py run \
  --root /private/tmp/t1-isolation-NEW \
  --plan /private/tmp/t1-isolation-NEW/explicit-review-plan.controller.json \
  --authorize-plan-sha256 REVIEWED_PLAN_SHA256
```

`run` takes its profile, tokenizer policy and rates from the approved plan and rejects plan-time
option overrides. This profile uses an exclusive `shakedown-explicit-review-`
ledger and rejects `--previous-plan-sha256`. It does not resume old discovery or
supplied-evidence cohorts. Earlier reservations and ledgers remain intact; a
new batch and any recovery require their own explicit authorization. Any HTTP
error, truncation, missing usage, drift or budget failure stops the batch without
a retry or replacement. A verifier exit code of 1 is evidence, not a transport
failure. M1 does not implement T0 export, sentinel expansion or automatic judging.

## Evidence and remaining gates

Current provider version is `unknown` and price/cost is unknown. Diagnostic
outputs therefore explicitly contain `evaluation_record: false` and
`cost_usd: null`. They are not ingested or scored. Returned model names and
declared version strings do not establish immutable version identity.

A successful real diagnostic shakedown proves that these tools, mounted
conditions, model loop, and receipts work together for these eight targets. It
does not establish Skill uplift, general agent behavior, immutable-version
reproducibility, or billing correctness. The original T0-scored shakedown gate
still requires trustworthy complete usage/cost, model/version provenance, and
budget parity before integration. The 12-run sentinel, blind judge validation,
and 144-run pilot remain separately authorized work.

## Verification

```sh
python3 -m unittest evals.harness.test_isolation evals.harness.test_shakedown -v
```

These tests use temporary workspaces and injected mocks; they never connect to
a provider or require Docker. The ordinary standard-library suite skips the two
optional pinned-tokenizer integration tests. Run those with the local assets:

```sh
T1_TOKENIZER_DIR=/private/tmp/glm-tokenizer-assets \
  /private/tmp/glm-tokenizer-env/bin/python -m unittest evals.harness.test_shakedown -v
```

The separate `rehearse` command is the actual
Docker runtime test and makes zero model calls.

Explicit Review tests capture all eight first requests, verify assigned bodies
and C0 isolation, GLM options and reservation rates, drift rejection, and failure
journals with no second send. They also read all three files in each real fixture,
execute its verifier locally, and replay the full results through three mocked
model responses. Synthetic usage proves protocol/guard behavior only. It cannot
prove that GLM will follow that trajectory or fit the remaining token budget;
the over-budget case stops with evidence intact rather than widening the caps.

The earlier bytes-based guard rejected the fixed three-response C3 fixture
replay (including its short synthetic reasoning text). Its wire sizes and old
last-dispatch thresholds were:

| Fixture | Request bytes, in order | Maximum reported usage accumulated before request 3 |
|---|---|---:|
| `migration-compat-01` | 8647 / 10499 / 10829 | 1075 tokens |
| `dual-write-06` | 8652 / 10395 / 10728 | 1176 tokens |

The last column is `16000 - request_bytes - 4096`, not observed GLM usage.
The successful replay uses only 240 synthetic tokens before request 3. Actual
reasoning, response lengths and token counts can exhaust the guard sooner.
The pinned local tokenizer subsequently counted C3 inputs as 1741/2083/2131 and
1742/2075/2121 respectively. Under that local-count scenario, even zero completion
tokens caused the old guard to stop C3 before request 2 and C1/C2 before request 3.
This motivated the profile-specific estimation correction above.

The optional integration test now replays all eight full evidence trajectories
with those real local input counts and an explicitly synthetic 200 completion
tokens per response. It also checks that omitting tools or reasoning decreases
the count. This verifies the corrected dispatch rule for that scenario, not
hosted-template parity, real model behavior, or actual billing. Existing caps
and post-response abort rules remain in force.
