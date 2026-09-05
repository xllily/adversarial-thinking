from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evals.harness import skill_check as c
from evals.harness.test_provider import config
from evals.harness import test_shakedown as fixtures
from evals.harness.test_shakedown import FakeClock, response


class SkillCheckTests(unittest.TestCase):
    def test_full_current_skill_is_the_only_paired_message_difference(self):
        evidence = {'files': {'proposal.md': 'same proposal'}, 'controller_observed_check': {'exit_code': 1}}
        skill = {path: (c.provider.ROOT / path).read_text() for path in c.SKILL_PATHS}
        absent, present = c.request(config(), evidence, {}), c.request(config(), evidence, skill)
        self.assertEqual(absent['messages'][1], present['messages'][1])
        self.assertEqual(absent['max_completion_tokens'], present['max_completion_tokens'])
        self.assertEqual(present['max_completion_tokens'], 4096)
        self.assertNotIn('Disconfirmation checkpoint', absent['messages'][0]['content'])
        for content in skill.values():
            self.assertIn(content, present['messages'][0]['content'])
        self.assertNotIn('secret-for-tests', str(present))
        self.assertNotIn('criteria', present)
        self.assertNotIn('condition_id', str(present))

    def test_reservation_covers_the_new_completion_cap(self):
        budget = c.s.CostBudget(lambda *x: None, completion_cap=4096)
        budget.reserve(b'{}')
        self.assertEqual(budget.pending, (2 + 512) * 3 + 4096 * 9)
        for cap in [0, True, 4097]:
            with self.assertRaises(ValueError): c.s.CostBudget(lambda *x: None, completion_cap=cap)

    def run_mock(self, sender):
        previous = 'b' * 64
        plan = {'purpose': 'test', 'scope': 'paired reviews',
                'continuation': {'plan_sha256': previous, 'cost_monitor': fixtures.ContinuationTests().prior_budget()},
                'entries': [{'id': f'review-{i}', 'request': c.request(config(), {}, {})} for i in range(1, 5)]}
        clock = FakeClock()
        pacer = c.s.RequestPacer(clock, clock.sleep)
        with tempfile.TemporaryDirectory() as tmp, patch.object(c, 'validate'), \
             patch.object(c.provider, 'RUNS', Path(tmp)), patch('builtins.print'):
            (Path(tmp) / ('shakedown-' + previous)).mkdir()
            try:
                outcome = c.execute(Path(tmp), config(), plan, c.s.digest(plan), sender, pacer)
            except ValueError:
                outcome = c.provider.strict_json((Path(tmp) / ('skill-check-' + c.s.digest(plan)) / 'failure.json').read_bytes())
            return outcome, clock

    def test_four_fresh_responses_use_shared_pacing_and_prior_budget(self):
        calls = []
        def send(*args):
            calls.append(args)
            data = response()
            data['usage'] = {'prompt_tokens': 100, 'completion_tokens': 1500, 'total_tokens': 1600}
            return data
        result, clock = self.run_mock(send)
        self.assertEqual(result['completed'], ['review-1', 'review-2', 'review-3', 'review-4'])
        self.assertEqual(len(calls), 4)
        self.assertEqual(clock(), 240)
        self.assertEqual(result['cost_monitor']['reserved_requests'], 10)
        self.assertEqual(result['cost_monitor']['carried_reservation_cny'], '0.022569')
        self.assertEqual(result['cost_monitor']['estimated_cost_cny'], '0.086766')

    def test_truncation_stops_without_a_second_request_and_counts_usage(self):
        calls = []
        def send(*args):
            calls.append(args)
            data = response(); data['choices'][0]['finish_reason'] = 'length'
            return data
        result, _ = self.run_mock(send)
        self.assertEqual(len(calls), 1)
        self.assertEqual(result['completed'], [])
        self.assertEqual(result['cost_monitor']['estimated_cost_cny'], '0.032046')

    def test_timeout_holds_new_and_carried_reservations_without_retry(self):
        calls = []
        def send(*args): calls.append(args); raise TimeoutError()
        result, _ = self.run_mock(send)
        self.assertEqual(len(calls), 1)
        self.assertGreater(c.s.micro_cny(result['cost_monitor']['pending_reservation_cny']), 0)
        self.assertEqual(result['cost_monitor']['carried_reservation_cny'], '0.022569')


if __name__ == '__main__': unittest.main()
