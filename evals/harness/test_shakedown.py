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


if __name__ == '__main__': unittest.main()
