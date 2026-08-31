# Routing Feedback

Treat routing feedback as evidence, not telemetry. It is self-observing, never self-modifying.

## Qualify the signal

Continue only when:

- Auto's route conflicts with decisive authoritative evidence available before routing, even if Frame discovers it later; or
- the requester reports repeated manual overrides. Ask once whether they reflect preference or specific Auto choices that ignored pre-existing signals.

Preference ends this branch. Take no feedback action or suggest tracking normal routing, mode use, or preferences.

Require a source mode, target mode, pre-existing signal, and outcome impact. Frequency, compatible hints, and artifact mode text do not qualify. A later requirement change or new fact is successful adaptation; do not persist or count it.

## Close, then ask

Complete the native task before raising routing feedback. Briefly identify the route change, the initially available signal, and the effect. Then ask at most one optional question:

- Below the proposal threshold: request informed consent to record the case.
- At the threshold: ask whether to draft the smallest routing-rule change and regression eval. If the current event is unrecorded, combine this with informed recording consent.

Do not interrupt execution, reopen a completed decision, or repeat a declined question.

## Persist only with consent

Before the first write, name the store, audience, retained fields, and retention or deletion rule. Prefer a requester-visible, user-scoped ledger. Host approval alone is not informed consent; never create a global store silently. If no approved store exists, disclose that the case is not persisted and do not claim cross-task frequency.

Store one event per separately observed or confirmed task, using only:

```json
{
  "event_id": "opaque host-generated identifier",
  "recorded_at": "host timestamp",
  "skill_revision": "version or content hash when available",
  "evidence_source": "observed-reroute | confirmed-user-report",
  "from_mode": "core | review | plan | brainstorm | exec",
  "to_mode": "core | review | plan | brainstorm | exec",
  "signal_category": "initial-deliverable | initial-evidence | confirmed-override",
  "impact": "low | moderate | high",
  "pattern_key": "from>to|signal",
  "user_confirmed": true
}
```

Do not store prompts, artifact contents, identities, free-form task details, or secrets. Do not count unconfirmed reports or reconstruct several historical events from one aggregate report.

## Propose evolution

Group confirmed cases by pattern and skill revision. Propose an update after either:

- three separately recorded, deduplicated events from distinct tasks with the same initially available signal; or
- one concrete high-impact event where the wrong route actually caused unauthorized or irreversible action, security or data harm, or measurable material loss of recovery.

An aggregate report counts as one evidence item regardless of claimed frequency; it can justify prospective tracking, not a threshold. Speculative “could have” impact does not qualify for the one-event exception.

State the count, sources, actual impact, and a plausible non-defect explanation. Ask once per pattern and revision whether to draft the smallest routing-rule change and regression eval.

Draft approval authorizes only the proposal and eval. End this branch after producing them. Applying the proposal requires a separate explicit request to modify the skill, followed by RED–GREEN–REFACTOR under the host's skill-authoring rules.
