import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evals.harness import shakedown as s
from evals.harness.test_provider import config


def response(name=None, arguments=None, call_id='call_1', usage=True):
    message = {'role': 'assistant', 'content': None if name else 'Observed the deterministic check.'}
    if name:
        message['tool_calls'] = [{'type': 'function', 'id': call_id,
                                  'function': {'name': name, 'arguments': json.dumps(arguments)}}]
    result = {'choices': [{'finish_reason': 'tool_calls' if name else 'stop', 'message': message}]}
    if usage: result['usage'] = {'prompt_tokens': 100, 'completion_tokens': 20, 'total_tokens': 120}
    return result


class AgentTests(unittest.TestCase):
    def test_multistep_loop_with_tool_results_and_complete_trace(self):
        responses = iter([response('read', {'path': 'proposal.md'}),
                          response('shell', {'command': 'python3 verify.py'}, 'call_2'), response()])
        attempts, requests, records, tools = [], [], [], []
        def send(cfg, payload, timeout):
            requests.append(json.loads(payload)); return next(responses)
        def execute(name, args):
            tools.append((name, args)); return {'exit_code': 0, 'stdout': 'PASS'}
        result = s.run_agent(config(), 'Public prompt', 'Workspace files: proposal.md, verify.py',
                             execute, attempts.append, lambda *args: records.append(args), send)
        self.assertEqual(attempts, [1, 2, 3])
        self.assertEqual(result['reported_total_tokens'], 360)
        self.assertEqual(result['tool_calls'], 2)
        self.assertEqual(len(records), 5)
        self.assertFalse(result['evaluation_record'])
        self.assertIsNone(result['cost_usd'])
        self.assertEqual(requests[-1]['messages'][-1]['tool_call_id'], 'call_2')
        self.assertNotIn('secret-for-tests', json.dumps(requests))

    def test_invalid_tool_and_duplicate_id_abort_without_dispatch(self):
        for name, args in [('shell', {'command': 'curl https://example.com'}),
                           ('read', {'path': 'a', 'extra': True}), ('exec', {'command': 'id'})]:
            with self.subTest(name=name), patch('builtins.print'):
                tools = []
                with self.assertRaises(ValueError):
                    s.run_agent(config(), 'p', '', lambda *x: tools.append(x), lambda n: None,
                                lambda *x: None, lambda *x: response(name, args))
                self.assertEqual(tools, [])
        tools = []
        with self.assertRaises(ValueError):
            s.run_agent(config(), 'p', '', lambda *x: tools.append(x), lambda n: None,
                        lambda *x: None, lambda *x: response('read', {'path': 'a'}))
        self.assertEqual(len(tools), 1)

    def test_batch_calls_execute_in_order_with_matching_results(self):
        batch = response('read', {'path': 'proposal.md'})
        batch['choices'][0]['message']['tool_calls'].append(
            response('shell', {'command': 'python3 verify.py'}, 'call_2')['choices'][0]['message']['tool_calls'][0]
        )
        replies = iter([batch, response()])
        seen, requests = [], []
        def send(cfg, payload, timeout):
            requests.append(json.loads(payload)); return next(replies)
        result = s.run_agent(config(), 'p', '', lambda n, a: seen.append(n),
                             lambda n: None, lambda *x: None, send)
        self.assertEqual(seen, ['read', 'shell'])
        self.assertEqual(result['tool_calls'], 2)
        self.assertEqual(result['model_requests'], 2)
        self.assertEqual([m['tool_call_id'] for m in requests[-1]['messages'][-2:]], ['call_1', 'call_2'])

    def test_invalid_later_batch_member_prevents_all_dispatch(self):
        for second in [response('shell', {'command': 'id'}, 'call_2'),
                       response('read', {'path': 'a'}, 'call_1'),
                       response('read', {'path': '/etc/passwd'}, 'call_2')]:
            batch = response('read', {'path': 'a'})
            batch['choices'][0]['message']['tool_calls'] += second['choices'][0]['message']['tool_calls']
            dispatched = []
            with self.assertRaises(ValueError):
                s.run_agent(config(), 'p', '', lambda *x: dispatched.append(x),
                            lambda n: None, lambda *x: None, lambda *x: batch)
            self.assertEqual(dispatched, [])

    def test_oversized_batch_consumes_no_tool_budget(self):
        batch = response('read', {'path': 'a'})
        batch['choices'][0]['message']['tool_calls'] *= 13
        dispatched = []
        with self.assertRaisesRegex(ValueError, 'tool budget'):
            s.run_agent(config(), 'p', '', lambda *x: dispatched.append(x),
                        lambda n: None, lambda *x: None, lambda *x: batch)
        self.assertEqual(dispatched, [])

    def test_missing_usage_and_truncation_are_not_complete(self):
        for data in [response(usage=False), response()]:
            if 'usage' in data: data['choices'][0]['finish_reason'] = 'length'
            calls = []
            with self.assertRaises(ValueError):
                s.run_agent(config(), 'p', '', lambda *x: {}, calls.append,
                            lambda *x: None, lambda *x: data)
            self.assertEqual(calls, [1])

    def test_reported_overrun_saved_before_abort(self):
        data = response(); data['usage'] = {'prompt_tokens': 17000, 'completion_tokens': 20, 'total_tokens': 17020}
        records = []
        with self.assertRaisesRegex(ValueError, 'token budget'):
            s.run_agent(config(), 'p', '', lambda *x: {}, lambda n: None,
                        lambda *x: records.append(x), lambda *x: data)
        self.assertEqual(records[0][2]['usage']['total_tokens'], 17020)

    def test_request_and_wall_clock_budgets(self):
        attempts = []
        with self.assertRaisesRegex(ValueError, 'byte budget'):
            s.run_agent(config(), 'p' * 13000, '', lambda *x: {}, attempts.append, lambda *x: None)
        self.assertEqual(attempts, [])
        clock = iter([0, 181])
        with self.assertRaisesRegex(ValueError, 'deadline'):
            s.run_agent(config(), 'p', '', lambda *x: {}, attempts.append,
                        lambda *x: None, clock=lambda: next(clock))
        self.assertEqual(attempts, [])

    def test_http_timeout_is_not_retried(self):
        attempts = []
        def timeout(*args): raise TimeoutError()
        with self.assertRaises(TimeoutError):
            s.run_agent(config(), 'p', '', lambda *x: {}, attempts.append, lambda *x: None, timeout)
        self.assertEqual(attempts, [1])

    def test_attempt_write_failure_prevents_send(self):
        def fail(n): raise OSError('disk full')
        with patch.object(s, 'bounded_send') as send:
            with self.assertRaises(OSError):
                s.run_agent(config(), 'p', '', lambda *x: {}, fail, lambda *x: None, send)
            send.assert_not_called()

    def test_plan_drift_prevents_any_target_start(self):
        with patch.object(s, 'make_plan', return_value={'frozen': 1}), patch.object(s.isolation, 'invoke') as invoke:
            with self.assertRaises(ValueError): s.execute(Path('/tmp'), config(), {'frozen': 2}, 'bad')
            invoke.assert_not_called()

    def test_interruption_claim_cannot_be_replayed(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(s.provider, 'RUNS', Path(tmp)), \
             patch.object(s, 'make_plan', return_value={'frozen': 1}), \
             patch.object(s.isolation, 'load_manifest', return_value={'assignments': [{'target': 'test'}]}), \
             patch.object(s.isolation, 'invoke', side_effect=KeyboardInterrupt):
            plan = {'frozen': 1}
            with self.assertRaisesRegex(ValueError, 'stopped'): s.execute(Path(tmp), config(), plan, s.digest(plan))
            with self.assertRaises(FileExistsError): s.execute(Path(tmp), config(), plan, s.digest(plan))
            self.assertTrue((next(Path(tmp).iterdir()) / 'failure.json').exists())


class FakeClock:
    def __init__(self):
        self.now = 0
        self.sleeps = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class PacingTests(unittest.TestCase):
    def test_response_end_gap_crosses_targets_without_spending_active_deadline(self):
        clock = FakeClock()
        pacer = s.RequestPacer(clock, clock.sleep)
        sent, ended = [], []
        def send(*args):
            sent.append(clock())
            clock.now += 2
            ended.append(clock())
            i = len(sent)
            return response('read', {'path': 'a'}, f'call_{i}') if i < 5 else response()
        first = s.run_agent(config(), 'p', '', lambda *x: {}, lambda *x: None,
                            lambda *x: None, send, clock, pacer=pacer)
        second = s.run_agent(config(), 'p', '', lambda *x: {}, lambda *x: None,
                             lambda *x: None, send, clock, pacer=pacer)
        self.assertEqual(first['pacing_wait_ms'], 240000)
        self.assertEqual(first['active_latency_ms'], 10000)
        self.assertEqual(second['pacing_wait_ms'], 60000)
        self.assertTrue(all(start - end >= 60 for start, end in zip(sent[1:], ended)))
        self.assertLessEqual(max(clock.sleeps), 30)

    def test_tool_time_counts_toward_gap_and_active_deadline(self):
        clock = FakeClock()
        pacer = s.RequestPacer(clock, clock.sleep)
        replies = iter([response('read', {'path': 'a'}), response()])
        def tool(*args): clock.now += 20; return {}
        result = s.run_agent(config(), 'p', '', tool, lambda *x: None,
                             lambda *x: None, lambda *x: next(replies), clock, pacer=pacer)
        self.assertEqual(result['pacing_wait_ms'], 40000)
        self.assertEqual(result['active_latency_ms'], 20000)
        clock = FakeClock()
        pacer = s.RequestPacer(clock, clock.sleep)
        attempts = []
        def slow(*args): clock.now += 181; return {}
        with self.assertRaisesRegex(ValueError, 'deadline'):
            s.run_agent(config(), 'p', '', slow, attempts.append, lambda *x: None,
                        lambda *x: response('read', {'path': 'a'}), clock, pacer=pacer)
        self.assertEqual(attempts, [1])

    def test_interrupted_wait_sends_no_request_or_reservation(self):
        clock = FakeClock()
        def interrupted(*args): raise KeyboardInterrupt()
        pacer = s.RequestPacer(clock, interrupted); pacer.finished()
        budget = s.CostBudget(lambda *x: None)
        attempts, sends = [], []
        with self.assertRaises(KeyboardInterrupt):
            s.run_agent(config(), 'p', '', lambda *x: {}, attempts.append,
                        lambda *x: None, lambda *x: sends.append(x), clock, budget, pacer)
        self.assertEqual((attempts, sends, budget.requests), ([], [], 0))

    def test_failed_request_is_not_retried_when_paced(self):
        clock = FakeClock()
        pacer = s.RequestPacer(clock, clock.sleep)
        attempts = []
        def fail(*args): raise s.provider.ProbeError('provider HTTP status 429')
        with self.assertRaises(s.provider.ProbeError):
            s.run_agent(config(), 'p', '', lambda *x: {}, attempts.append,
                        lambda *x: None, fail, clock, pacer=pacer)
        self.assertEqual(attempts, [1])
        self.assertEqual(pacer.ready_at, 60)


class ContinuationTests(unittest.TestCase):
    def prior_budget(self):
        return dict(s.CostBudget(lambda *x: None).snapshot(),
                    estimated_cost_cny='0.031566', pending_reservation_cny='0.022569',
                    reserved_requests=6, reported_prompt_tokens=4414, reported_completion_tokens=2036)

    def test_prior_cost_unknown_reservation_and_attempts_stay_charged(self):
        budget = s.CostBudget(lambda *x: None, carried=self.prior_budget())
        self.assertEqual((budget.spent, budget.carried_reservation, budget.requests), (31566, 22569, 6))
        budget.reserve(b'{}'); budget.observe(response())
        self.assertEqual((budget.spent, budget.carried_reservation, budget.requests), (32046, 22569, 7))
        exhausted = dict(self.prior_budget(), estimated_cost_cny='2.980000')
        with self.assertRaisesRegex(ValueError, 'request not sent'):
            s.CostBudget(lambda *x: None, carried=exhausted).reserve(b'{}')
        exhausted = dict(self.prior_budget(), reserved_requests=96)
        with self.assertRaisesRegex(ValueError, 'request not sent'):
            s.CostBudget(lambda *x: None, carried=exhausted).reserve(b'{}')

    def test_malformed_previous_accounting_is_rejected(self):
        for key, value in [('reserved_requests', True), ('reserved_requests', -1),
                           ('pending_reservation_cny', 'NaN'), ('limit_cny', '30.000000')]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                s.CostBudget(lambda *x: None, carried=dict(self.prior_budget(), **{key: value}))

    def test_continuation_binds_original_campaign_and_failed_evidence(self):
        current = dict(root='/tmp/test', provider={'config_sha256': 'cfg'}, manifest_sha256='manifest',
                       offline_evidence_sha256={'a': 'receipt'})
        failure = dict(outcome='failed_or_unknown_no_retry', completed=[{'target': 'a'}],
                       cost_monitor=self.prior_budget())
        previous = s.digest(current)
        with tempfile.TemporaryDirectory() as tmp, patch.object(s.provider, 'RUNS', Path(tmp)):
            ledger = Path(tmp) / ('shakedown-' + previous); ledger.mkdir()
            s.provider.write_new(ledger / 'plan.json', current)
            s.provider.write_new(ledger / 'failure.json', failure)
            result = s.continuation_context(previous, current, {'assignments': [{'target': 'a'}]})
            self.assertEqual(result['failure_sha256'], s.digest(failure))
            with self.assertRaisesRegex(ValueError, 'mismatch'):
                s.continuation_context(previous, dict(current, provider={}), {'assignments': []})
            with self.assertRaisesRegex(ValueError, 'completed targets'):
                s.continuation_context(previous, current, {'assignments': []})

    def test_completed_target_is_skipped_and_failed_parent_can_only_continue_once(self):
        previous = 'a' * 64
        continuation = {'plan_sha256': previous, 'completed': [{'target': 'done'}],
                        'cost_monitor': self.prior_budget()}
        plan = {'continuation': continuation}
        assignments = [{'target': t, 'case': {'prompt': 'p'}} for t in ['done', 'todo']]
        receipt = {'receipt': {'skill_present': False}, 'runtime': {'workspace_files': []}}
        result = {'model_requests': 1, 'reported_total_tokens': 120}
        with tempfile.TemporaryDirectory() as tmp, patch.object(s.provider, 'RUNS', Path(tmp)), \
             patch.object(s, 'make_plan', return_value=plan), \
             patch.object(s.isolation, 'load_manifest', return_value={'assignments': assignments}), \
             patch.object(s.isolation, 'invoke', return_value=receipt) as invoke, \
             patch.object(s.isolation, 'check_receipt'), \
             patch.object(s, 'run_agent', return_value=result) as agent, patch('builtins.print'):
            (Path(tmp) / ('shakedown-' + previous)).mkdir()
            outcome = s.execute(Path(tmp), config(), plan, s.digest(plan))
            self.assertEqual(outcome['completed_runs'], 2)
            self.assertEqual([c.args[1]['target'] for c in invoke.call_args_list], ['todo', 'todo'])
            agent.assert_called_once()
            self.assertEqual(agent.call_args.kwargs['cost_budget'].requests, 6)
            changed = dict(plan, code='changed')
            with patch.object(s, 'make_plan', return_value=changed), self.assertRaises(FileExistsError):
                s.execute(Path(tmp), config(), changed, s.digest(changed))
            agent.assert_called_once()


class CostBudgetTests(unittest.TestCase):
    def test_reservation_blocks_before_attempt_or_network(self):
        events, attempts, sends = [], [], []
        budget = s.CostBudget(lambda *x: events.append(x), limit_micro_cny=1)
        with self.assertRaisesRegex(ValueError, 'request not sent'):
            s.run_agent(config(), 'p', '', lambda *x: {}, attempts.append,
                        lambda *x: None, lambda *x: sends.append(x), cost_budget=budget)
        self.assertEqual(attempts, [])
        self.assertEqual(sends, [])
        self.assertEqual(events[-1][0], 'blocked')

    def test_accumulates_across_agent_runs_at_peak_rates(self):
        budget = s.CostBudget(lambda *x: None)
        for _ in range(2):
            s.run_agent(config(), 'p', '', lambda *x: {}, lambda *x: None,
                        lambda *x: None, lambda *x: response(), cost_budget=budget)
        self.assertEqual(budget.spent, 2 * (100 * 3 + 20 * 9))
        self.assertEqual(budget.snapshot()['estimated_cost_cny'], '0.000960')
        self.assertIsNone(budget.snapshot()['actual_gateway_cost_cny'])
        self.assertEqual(budget.pending, 0)

    def test_missing_usage_or_timeout_keeps_unknown_reservation(self):
        for missing in [True, False]:
            budget = s.CostBudget(lambda *x: None)
            attempts = []
            def send(*args):
                if missing: return response(usage=False)
                raise TimeoutError()
            with self.assertRaises((ValueError, TimeoutError)):
                s.run_agent(config(), 'p', '', lambda *x: {}, attempts.append,
                            lambda *x: None, send, cost_budget=budget)
            self.assertEqual(attempts, [1])
            self.assertGreater(budget.pending, 0)
            with self.assertRaisesRegex(ValueError, 'unresolved'):
                budget.reserve(b'{}')

    def test_overshoot_records_cost_and_sends_no_followup(self):
        budget = s.CostBudget(lambda *x: None)
        data = response()
        data['usage'] = {'prompt_tokens': 1000000, 'completion_tokens': 20, 'total_tokens': 1000020}
        attempts = []
        with self.assertRaisesRegex(ValueError, 'CNY estimate reached'):
            s.run_agent(config(), 'p', '', lambda *x: {}, attempts.append,
                        lambda *x: None, lambda *x: data, cost_budget=budget)
        self.assertEqual(attempts, [1])
        self.assertEqual(budget.snapshot()['estimated_cost_cny'], '3.000180')

    def test_truncated_response_usage_still_counts(self):
        budget = s.CostBudget(lambda *x: None)
        data = response(); data['choices'][0]['finish_reason'] = 'length'
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            s.run_agent(config(), 'p', '', lambda *x: {}, lambda *x: None,
                        lambda *x: None, lambda *x: data, cost_budget=budget)
        self.assertEqual(budget.spent, 480)
        self.assertEqual(budget.pending, 0)

    def test_cost_journal_failure_prevents_request(self):
        def disk_full(*args): raise OSError('disk full')
        budget = s.CostBudget(disk_full)
        with patch.object(s, 'bounded_send') as send:
            with self.assertRaises(OSError):
                s.run_agent(config(), 'p', '', lambda *x: {}, lambda *x: None,
                            lambda *x: None, send, cost_budget=budget)
            send.assert_not_called()


if __name__ == '__main__': unittest.main()
