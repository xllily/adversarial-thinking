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

`shakedown.py` maintains fresh model history per target. Discovery lists actual
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
- at most 12 tool calls and a 180-second agent-loop deadline per target;
- a 30-second deadline for each provider request on this Unix controller;
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

Plans and attempt ledgers use exclusive creation and fsync before transmission.
Rerunning the same plan is refused, even after interruption or success. An
unknown outcome consumes authorization; inspect saved attempts and obtain new
scope before recovery. Never delete evidence to make a retry possible. For a
separately reviewed repair, `plan` and `run` accept `--plan NEW_PLAN_PATH`, allowing
a new plan to reuse unchanged, verified mounts without overwriting the previous
plan or its failed ledger.

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
a provider or require Docker. The separate `rehearse` command is the actual
Docker runtime test and makes zero model calls.
