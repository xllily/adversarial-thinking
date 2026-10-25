# Offline controller validation

Starting revision: `8cf6dbb`.
Scope: the 39 behavioral specifications, existing adapter contract, and two
frozen development campaigns. Static review found no concrete contradiction
requiring a change to the v0.1.1 Skill. This work repairs the offline controller;
it does not establish behavioral improvement or reverse either candidate's
historical non-adoption decision.

## Findings and applied corrections

- `summarize` trusted stored `scorable` flags without checking the original
  evidence. Missing receipts could be counted by changing that flag; old model
  records could also be paired with a newly prepared execution profile.
  Ingestion and summarization now share validation of complete run records,
  assignments, model profiles, usage, and isolation receipts. Derived flags must
  agree with the evidence. Valid isolation failures remain excluded from metrics.
- JSON literals such as `1e999` passed validation as infinity, then crashed
  preparation. Parsing now rejects overflow before output creation and rejects
  duplicate fields instead of silently choosing the last value. Schema versions
  must be integer 1; campaign file references must resolve within the campaign.
- Sixteen tests assumed a platform-specific temporary directory. Tests now use
  the platform temporary directory. Synthetic fixture preparation mocks only
  the extracted ancestry check, with separate tests covering clean ancestors and
  all three discovery markers at two ancestor levels. Production preparation
  still checks every real ancestor and rejects contaminated paths.

New regression cases were observed failing before their controller fixes.
The final diff review found no blocking regression.

## Verification

| Check | Starting revision | Updated workspace |
| --- | --- | --- |
| Harness unit tests | 79 discovered: 61 passed, 16 errors, 2 skipped | 86 discovered: 84 passed, 0 errors, 2 skipped |
| Frozen T1 pilot tests | 10 passed | 10 passed |
| T1 source verification | 12 cases, 4 conditions valid | 12 cases, 4 conditions valid |
| Controller self-test | Not separately measured | Passed: prepare, ingest, blind, summarize |
| Recommendation-quality preparation | Historical freeze retained | Two fresh preparations byte-identical; all 8 prompt hashes and manifest match the freeze |

Reproduce the unit and controller checks from the repository root:

```sh
python3 -m unittest discover -s evals/harness -p 'test_*.py' -v
python3 -m unittest discover -s evals/campaigns/t1_pilot_v1 -p 'test_*.py' -v
python3 evals/campaigns/t1_pilot_v1/pilot.py verify
python3 evals/harness/eval.py self-test
git diff --check
```

The two skipped tests require optional pinned tokenizer integration assets.
No provider/model calls, Docker rehearsal, or native installation ran. Synthetic
unit fixtures do not establish physical isolation. Core Skill files, the 39
behavioral specifications, and both frozen campaigns remain unchanged.
Behavior, tokenizer integration, physical isolation, installation, cost, latency,
and causal uplift remain unverified by this work.
