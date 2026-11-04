# Change-decision candidate: static and offline checks

Date: 2026-11-04. Source baseline: `673f5664ebe13f22e5cc1fe53bf5f625c9a19e7e`.
Status: local, uncommitted candidate; specification and offline checks only.

## Change

Add a conditional `references/change-decision.md` within the existing four modes.
It distinguishes accepted decisions from provisional implementation choices,
compares future costs of keeping and changing a route, and separates assessment
depth from the need for new authorization. Add seven behavioral specifications;
preserve the original 39 entries, mode rules, metadata and discovery description.
Navigation and specification counts are updated. The user's host-level autonomy
principles are maintained separately; this report does not publish that private
configuration or claim that every host loads it.

The intended next behavior is to continue authorized work with appropriate
verification, while surfacing only uncovered boundary changes. This is a design
intent, not an observed model result.

## Checks

- Skill Creator `quick_validate.py`: passed on the candidate.
- Specification JSON: 46 unique, nonempty cases; the original 39 entries compare
  equal to the baseline. Seven additions are specification-only.
- Metadata and discovery description compare unchanged to the baseline.
- Reference links, Markdown fences, whitespace and original-file drift checks:
  passed. The four existing mode reference files and the evaluation harness are
  outside the edit scope.
- Existing offline controller suite:
  `python3 -B -m unittest discover -s evals/harness -p 'test*.py'`.
  Result: 86 tests run, 84 passed, two optional tokenizer tests skipped.
  The controller code is unchanged; this does not execute or score the seven new
  natural-language specifications.

## Limits and next evidence

No fresh-context model trials, API calls, paid evaluations, comparative scores,
behavioral uplift, automatic discovery improvement, release or CI/CD run is
claimed. Historical frozen campaigns and reports remain unchanged.

Use the existing protocol for subsequent behavior evaluation: isolate conditions,
freeze criteria before seeing outputs, retain full trial records, repeat the
pairs, and include both unwanted route replacement and authorized improvements.
Keep the existing normal-execution, Brainstorm, review-only and supported-plan
cases as regressions. Judge completion, executable corrective recommendations,
uncovered scope changes, duplicate permission requests and total burden, rather
than rewarding more caution or longer reports. A small smoke comparison alone
would still not establish general causal improvement.
