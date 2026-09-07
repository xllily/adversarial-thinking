import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
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


class ExplicitReviewTests(unittest.TestCase):
    """Synthetic receipts and responses here are offline test fixtures only."""
    def setUp(self):
        temp = tempfile.TemporaryDirectory(dir='/private/tmp')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve() / 'isolation'
        self.manifest = s.isolation.prepare(self.root)
        self.config = dict(config(), T1_ENDPOINT_URL=s.provider.BIGMODEL_ENDPOINT,
                           T1_MODEL_ID='glm-5.3-flash')
        self.policy = {'model': 'glm-5.3-flash', 'input_cny_per_million': '0.8',
                       'output_cny_per_million': '2.8', 'source': 'https://bigmodel.cn/pricing',
                       'checked_date': '2026-09-05'}
        self.tokenizer_dir = Path(temp.name).resolve() / 'synthetic-tokenizer'
        class Counter:
            def __init__(self, directory):
                self.policy = {'directory': str(directory), 'test_only': True, 'margin_tokens': 512}
            def __call__(self, payload):
                return len(payload) // 4
        counter_patch = patch.object(s, 'ReviewTokenCounter', Counter, create=True)
        counter_patch.start(); self.addCleanup(counter_patch.stop)
        self.counter = Counter(self.tokenizer_dir)
        self.receipts = {}
        evidence = self.root / 'offline-evidence'; evidence.mkdir()
        for a in self.manifest['assignments']:
            target = self.root / 'targets' / a['target']
            observed = {'receipt': dict(a['condition'], **{k: a['case'][k] for k in
                        ('workspace_hash', 'allowed_tools', 'budget_profile')}),
                        'runtime': {'uid': 65534, 'active_interfaces': ['lo'], 'ipv4_route_count': 0,
                                    'workspace_read_only': True, 'forbidden_paths_unavailable': True,
                                    'credential_env_absent': True,
                                    'workspace_files': sorted(p.name for p in (target / 'workspace').iterdir()),
                                    'skill_files': ['SKILL.md'] if a['condition']['skill_present'] else []}}
            observed['receipt'] = {k: observed['receipt'][k] for k in
                                   ('skill_present', 'bundle_hash', 'workspace_hash', 'allowed_tools', 'budget_profile')}
            self.receipts[a['target']] = observed
            s.provider.write_new(evidence / (a['target'] + '.json'), observed)
        s.provider.write_new(evidence / 'summary.json', {'isolated_workspaces_checked': 8, 'model_calls': 0})

    def plan(self):
        return s.make_plan(self.root, self.config, profile='explicit-review', cost_policy=self.policy,
                           tokenizer_dir=self.tokenizer_dir)

    def invoke(self, root, assignment, operation):
        if operation.get('operation') == 'inspect':
            return self.receipts[assignment['target']]
        path = operation['arguments']['path']
        base = 'skill' if path.startswith('/skills/') else 'workspace'
        relative = path.removeprefix('/skills/').removeprefix('/workspace/')
        return {'content': (root / 'targets' / assignment['target'] / base / relative).read_bytes().decode('utf-8')}

    def test_all_eight_first_requests_have_exact_assigned_bodies_and_bound_glm_options(self):
        plan = self.plan()
        self.assertEqual(plan['limits']['completion_tokens_per_request'], 4096)
        self.assertEqual(plan['limits']['completion_tokens_total'], 96 * 4096)
        self.assertEqual(plan['cost_policy']['model'], self.config['T1_MODEL_ID'])
        self.assertEqual(plan['cost_policy']['input_cny_per_million'], '0.8')
        self.assertIsNone(plan['cost_policy']['actual_gateway_cost_cny'])
        for a in self.manifest['assignments']:
            with self.subTest(target=a['target']):
                system, exposure = s.review_exposure(self.root, a, self.config, token_counter=self.counter)
                self.assertEqual(exposure, plan['exposure'][a['target']])
                captures, events = [], []
                replies = iter([response('read', {'path': 'proposal.md'}), response()])
                def send(cfg, payload, timeout):
                    captures.append(payload); return next(replies)
                budget = s.CostBudget(lambda *x: events.append(x), policy=plan['cost_policy'], completion_cap=4096)
                result = s.run_agent(self.config, a['case']['prompt'], '', lambda *x: {'content': 'fixture'},
                                     lambda n: None, lambda *x: None, send, cost_budget=budget,
                                     limits=plan['limits'], payload_options=plan['payload_options'],
                                     system_message=system, first_request_sha256=exposure['first_request_sha256'],
                                     token_counter=self.counter)
                self.assertEqual(result['model_requests'], 2)
                self.assertEqual(hashlib.sha256(captures[0]).hexdigest(), exposure['first_request_sha256'])
                self.assertEqual(len(captures[0]), exposure['first_request_bytes'])
                expected_reservation = budget.estimate(len(captures[0]) + 512, 4096)
                self.assertEqual(events[0][2]['pending_reservation_cny'], f'{expected_reservation / 1000000:.6f}')
                for payload in captures:
                    wire = json.loads(payload)
                    self.assertEqual(wire['max_tokens'], 4096)
                    self.assertEqual(wire['thinking'], {'type': 'enabled', 'clear_thinking': False})
                    self.assertEqual(wire['reasoning_effort'], 'low')
                    self.assertFalse(wire['stream'])
                    for absent in ('n', 'parallel_tool_calls', 'max_completion_tokens'):
                        self.assertNotIn(absent, wire)
                    if not a['condition']['skill_present']:
                        self.assertNotRegex(json.dumps(wire['messages']), r'adversarial-thinking|SKILL.md|Available skill')
                        self.assertEqual(exposure['instruction_sha256'], {})
                    else:
                        for path in ('SKILL.md', 'references/review.md'):
                            raw = (self.root / 'targets' / a['target'] / 'skill' / path).read_bytes()
                            self.assertIn('\n--- ' + path + ' ---\n' + raw.decode('utf-8'), wire['messages'][0]['content'])
                            self.assertEqual(exposure['instruction_sha256'][path], hashlib.sha256(raw).hexdigest())

    def test_missing_or_changed_instruction_rejects_plan(self):
        a = next(a for a in self.manifest['assignments'] if a['condition']['skill_present'])
        path = self.root / 'targets' / a['target'] / 'skill/references/review.md'
        raw = path.read_bytes(); path.chmod(0o644); path.write_bytes(raw + b'drift')
        with self.assertRaises(ValueError): self.plan()
        path.parent.chmod(0o755); path.unlink()
        with self.assertRaises((ValueError, FileNotFoundError)): self.plan()

    def test_complete_evidence_path_and_conservative_guard_with_synthetic_usage(self):
        plan = self.plan()
        for a in self.manifest['assignments']:
            workspace = self.root / 'targets' / a['target'] / 'workspace'
            files = sorted(p.name for p in workspace.iterdir())
            batch = response('read', {'path': files[0]}, 'read_0')
            batch['choices'][0]['message']['tool_calls'] += [
                response('read', {'path': name}, f'read_{i}')['choices'][0]['message']['tool_calls'][0]
                for i, name in enumerate(files[1:], 1)]
            batch['choices'][0]['message']['reasoning_content'] = 'Inspect the evidence before concluding.'
            checked = subprocess.run(['python3', 'verify.py'], cwd=workspace, capture_output=True, text=True, check=False)
            tool_result = {'exit_code': checked.returncode, 'stdout': checked.stdout, 'stderr': checked.stderr}
            system, exposure = s.review_exposure(self.root, a, self.config, token_counter=self.counter)
            requests = []
            replies = iter([batch, response('shell', {'command': 'python3 verify.py'}, 'verify'), response()])
            def send(cfg, payload, timeout):
                requests.append(json.loads(payload)); return next(replies)
            def tool(name, args):
                if name == 'read': return {'content': (workspace / args['path']).read_text()}
                return tool_result
            with self.subTest(target=a['target']):
                result = s.run_agent(self.config, a['case']['prompt'], '', tool, lambda n: None,
                                     lambda *x: None, send, limits=plan['limits'], payload_options=plan['payload_options'],
                                     system_message=system, first_request_sha256=exposure['first_request_sha256'],
                                     token_counter=self.counter)
                self.assertEqual((result['model_requests'], result['tool_calls']), (3, 4))
                self.assertEqual(requests[1]['messages'][2]['reasoning_content'], 'Inspect the evidence before concluding.')
                contents = [json.loads(m['content']) for m in requests[-1]['messages'] if m['role'] == 'tool']
                self.assertEqual(contents, [{'content': (workspace / name).read_text()} for name in files] + [tool_result])
                # This is a chosen counterexample, not measured GLM usage. An intact
                # evidence path must stop rather than silently widen the frozen guard.
                high_usage = copy.deepcopy(batch)
                high_usage['usage'] = {'prompt_tokens': 11500, 'completion_tokens': 20, 'total_tokens': 11520}
                attempts = []
                with self.assertRaisesRegex(ValueError, 'input tokens exceeded local estimate'):
                    s.run_agent(self.config, a['case']['prompt'], '', tool, attempts.append, lambda *x: None,
                                lambda *x: high_usage, limits=plan['limits'], payload_options=plan['payload_options'],
                                system_message=system, first_request_sha256=exposure['first_request_sha256'],
                                token_counter=self.counter)
                self.assertEqual(attempts, [1])

    def test_runtime_body_drift_rejects_before_reservation_or_send(self):
        plan = self.plan()
        # No model run is allowed before the changed mounted read is checked.
        selected = next(a for a in self.manifest['assignments'] if a['condition']['skill_present'])
        observed_manifest = dict(self.manifest, assignments=[selected])
        def changed(root, a, operation):
            result = self.invoke(root, a, operation)
            if operation.get('name') == 'read': result['content'] += '\ndrift'
            return result
        with tempfile.TemporaryDirectory() as tmp, patch.object(s.provider, 'RUNS', Path(tmp)), \
             patch.object(s, 'make_plan', return_value=plan), \
             patch.object(s.isolation, 'load_manifest', return_value=observed_manifest), \
             patch.object(s.isolation, 'invoke', side_effect=changed), patch.object(s, 'run_agent') as agent:
            with self.assertRaisesRegex(ValueError, 'stopped'):
                s.execute(self.root, self.config, plan, s.digest(plan))
            agent.assert_not_called()
            self.assertEqual(list(Path(tmp).rglob('cost-*-reserved.json')), [])

    def test_policy_is_explicit_model_specific_and_dated(self):
        self.assertEqual(self.plan()['cost_policy']['model'], self.config['T1_MODEL_ID'])
        for policy, error in (
                (None, 'explicit-review requires model-specific dated reference rates'),
                (s.COST_POLICY, 'explicit-review requires model-specific dated reference rates'),
                (dict(self.policy, model='deepseek-chat'), 'invalid reference policy provenance'),
                (dict(self.policy, source=''), 'invalid reference policy provenance'),
                (dict(self.policy, checked_date='yesterday'), 'invalid reference policy date'),
                (dict(self.policy, input_cny_per_million='NaN'), 'invalid reference rates')):
            with self.subTest(policy=policy), self.assertRaisesRegex(ValueError, '^' + error + '$'):
                s.make_plan(self.root, self.config, profile='explicit-review', cost_policy=policy,
                            tokenizer_dir=self.tokenizer_dir)
        with self.assertRaisesRegex(
                ValueError, '^explicit-review requires the planned GLM endpoint/model/tools$'):
            s.make_plan(self.root, config(), profile='explicit-review', cost_policy=self.policy,
                        tokenizer_dir=self.tokenizer_dir)
        with self.assertRaisesRegex(
                ValueError, '^explicit-review requires a separately reviewed fresh batch; no continuation$'):
            s.make_plan(self.root, self.config, 'a' * 64, profile='explicit-review', cost_policy=self.policy,
                        tokenizer_dir=self.tokenizer_dir)

    def test_plan_and_first_payload_drift_prevent_send(self):
        plan = self.plan()
        for field in ('limits', 'cost_policy', 'payload_options', 'exposure', 'provider', 'input_token_policy'):
            changed = copy.deepcopy(plan); changed[field]['drift'] = True
            with self.subTest(field=field), patch.object(s.isolation, 'invoke') as invoke:
                with self.assertRaises(ValueError):
                    s.execute(self.root, self.config, changed, s.digest(changed))
                invoke.assert_not_called()
        a = self.manifest['assignments'][0]
        system, exposure = s.review_exposure(self.root, a, self.config, token_counter=self.counter)
        with patch.object(s, 'bounded_send') as send:
            with self.assertRaisesRegex(ValueError, 'first request'):
                s.run_agent(self.config, a['case']['prompt'], '', lambda *x: {}, lambda n: None,
                            lambda *x: None, send, limits=plan['limits'], payload_options=plan['payload_options'],
                            system_message=system + 'drift', first_request_sha256=exposure['first_request_sha256'],
                            token_counter=self.counter)
            send.assert_not_called()

    def test_explicit_failures_stop_batch_and_keep_attempts_responses_and_reservations(self):
        plan = self.plan()
        missing = response(usage=False)
        truncated = response(); truncated['choices'][0]['finish_reason'] = 'length'
        overrun = response(); overrun['usage'] = {'prompt_tokens': 16000, 'completion_tokens': 20, 'total_tokens': 16020}
        for outcome in (s.provider.ProbeError('provider HTTP status 429'), missing, truncated, overrun):
            with self.subTest(outcome=outcome), tempfile.TemporaryDirectory() as tmp:
                clock = FakeClock(); sends = []
                def send(cfg, payload, timeout):
                    sends.append(payload)
                    if isinstance(outcome, Exception): raise outcome
                    return outcome
                original = s.run_agent
                def agent(*args, **kwargs):
                    return original(*args, **kwargs, send=send, clock=clock)
                with patch.object(s.provider, 'RUNS', Path(tmp)), patch.object(s.isolation, 'invoke', side_effect=self.invoke), \
                     patch.object(s, 'RequestPacer', return_value=s.RequestPacer(clock, clock.sleep)), \
                     patch.object(s, 'run_agent', side_effect=agent), patch('builtins.print'):
                    with self.assertRaisesRegex(ValueError, 'stopped'):
                        s.execute(self.root, self.config, plan, s.digest(plan))
                self.assertEqual(len(sends), 1)
                ledger = next(Path(tmp).iterdir())
                self.assertTrue(ledger.name.startswith('shakedown-explicit-review-'))
                failure = json.loads((ledger / 'failure.json').read_text())
                self.assertEqual(failure['completed'], [])
                self.assertEqual(failure['cost_monitor']['reserved_requests'], 1)
                self.assertEqual(len(list(ledger.glob('*/attempt-1.json'))), 1)
                self.assertEqual(len(list(ledger.glob('*/request-1.json'))), 1)
                self.assertEqual(len(list(ledger.glob('*/exposure.json'))), 1)
                if isinstance(outcome, Exception) or 'usage' not in outcome:
                    self.assertGreater(float(failure['cost_monitor']['pending_reservation_cny']), 0)
                if not isinstance(outcome, Exception):
                    self.assertEqual(json.loads(next(ledger.glob('*/response-1.json')).read_text()), outcome)


class LocalInputGuardTests(unittest.TestCase):
    def test_cumulative_boundary_and_bytes_limit_are_independent(self):
        # 1000 prior tokens + 10392 current + 512 margin + 4096 = 16000.
        for second_count, allowed in ((10392, True), (10393, False)):
            counts = iter([100, second_count])
            first = response('read', {'path': 'a'})
            first['usage'] = {'prompt_tokens': 600, 'completion_tokens': 400, 'total_tokens': 1000}
            replies = iter([first, response()]); attempts = []
            def run():
                return s.run_agent(config(), 'p', '', lambda *x: {'content': 'evidence'}, attempts.append,
                                   lambda *x: None, lambda *x: next(replies), limits=s.REVIEW_LIMITS,
                                   token_counter=lambda payload: next(counts))
            if allowed:
                self.assertEqual(run()['model_requests'], 2)
            else:
                with self.assertRaisesRegex(ValueError, 'token dispatch guard'): run()
                self.assertEqual(attempts, [1])
        attempts = []
        with self.assertRaisesRegex(ValueError, 'byte budget'):
            s.run_agent(config(), 'p' * 13000, '', lambda *x: {}, attempts.append,
                        lambda *x: None, limits=s.REVIEW_LIMITS, token_counter=lambda payload: 1)
        self.assertEqual(attempts, [])

    def test_input_overestimate_violation_records_cost_and_stops_before_tools(self):
        data = response('read', {'path': 'a'})
        data['usage'] = {'prompt_tokens': 613, 'completion_tokens': 20, 'total_tokens': 633}
        records, attempts, dispatched = [], [], []
        budget = s.CostBudget(lambda *x: None, completion_cap=4096)
        with self.assertRaisesRegex(ValueError, 'input tokens exceeded local estimate'):
            s.run_agent(config(), 'p', '', lambda *x: dispatched.append(x), attempts.append,
                        lambda *x: records.append(x), lambda *x: data, limits=s.REVIEW_LIMITS,
                        cost_budget=budget, token_counter=lambda payload: 100)
        self.assertEqual(attempts, [1]); self.assertEqual(dispatched, [])
        self.assertEqual(next(r[2] for r in records if r[0] == 'response'), data)
        estimate = next(r[2] for r in records if r[0] == 'request')
        self.assertEqual(estimate['input_tokens_reserved'], 612)
        self.assertEqual((budget.prompt_tokens, budget.pending), (613, 0))
        self.assertGreater(budget.spent, 0)

    def test_counter_failure_or_invalid_count_never_falls_back(self):
        def broken(payload): raise ValueError('counter failed')
        for counter in (broken, lambda p: -1, lambda p: True, lambda p: 1.5):
            attempts = []
            with self.assertRaises(ValueError):
                s.run_agent(config(), 'p', '', lambda *x: {}, attempts.append, lambda *x: None,
                            limits=s.REVIEW_LIMITS, token_counter=counter)
            self.assertEqual(attempts, [])


class TokenizerAssetTests(unittest.TestCase):
    def test_missing_or_wrong_official_assets_rejected_without_dependencies(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises((ValueError, FileNotFoundError)):
                s.ReviewTokenCounter(root)
            for name in ('tokenizer.json', 'tokenizer_config.json', 'chat_template.jinja'):
                (root / name).write_text('wrong assets')
            with self.assertRaisesRegex(ValueError, 'tokenizer asset'):
                s.ReviewTokenCounter(root)

    @unittest.skipUnless(os.environ.get('T1_TOKENIZER_DIR'), 'optional pinned tokenizer integration assets')
    def test_pinned_tokenizer_counts_full_history_and_rejects_runtime_drift(self):
        counter = s.ReviewTokenCounter(Path(os.environ['T1_TOKENIZER_DIR']))
        self.assertEqual(counter.policy['margin_tokens'], 512)
        self.assertEqual(counter.policy['revision'], '690b705278a3a58e538fcb37c2ca8b5f9511213c')
        messages = [{'role': 'system', 'content': 'Review the evidence.'}, {'role': 'user', 'content': 'Check proposal.'}]
        cfg = dict(config(), T1_ENDPOINT_URL=s.provider.BIGMODEL_ENDPOINT, T1_MODEL_ID='glm-5.3-flash')
        first = counter(s.encode_request(cfg, messages, s.REVIEW_LIMITS, s.REVIEW_OPTIONS))
        messages += [response('read', {'path': 'proposal.md'})['choices'][0]['message'],
                     {'role': 'tool', 'tool_call_id': 'call_1', 'content': '{"content":"Evidence rules out the claim."}'}]
        messages[2]['reasoning_content'] = 'Reasoning trace. ' * 30
        original = copy.deepcopy(messages)
        payload = s.encode_request(cfg, messages, s.REVIEW_LIMITS, s.REVIEW_OPTIONS)
        full = counter(payload)
        self.assertGreater(full, first)
        without_reasoning = json.loads(payload)
        without_reasoning['messages'][2].pop('reasoning_content')
        self.assertLess(counter(s.provider.encode(without_reasoning)), full)
        without_tools = json.loads(payload); without_tools['tools'] = []
        self.assertLess(counter(s.provider.encode(without_tools)), full)
        self.assertEqual(messages, original)
        with patch.dict(s.REVIEW_TOKENIZER_PACKAGES, {'tokenizers': 'incorrect-version'}):
            with self.assertRaisesRegex(ValueError, 'tokenizer dependency'):
                s.ReviewTokenCounter(Path(os.environ['T1_TOKENIZER_DIR']))

    @unittest.skipUnless(os.environ.get('T1_TOKENIZER_DIR'), 'optional pinned tokenizer integration assets')
    def test_real_local_input_counts_complete_all_eight_evidence_trajectories(self):
        counter = s.ReviewTokenCounter(Path(os.environ['T1_TOKENIZER_DIR']))
        cfg = dict(config(), T1_ENDPOINT_URL=s.provider.BIGMODEL_ENDPOINT, T1_MODEL_ID='glm-5.3-flash')
        expected_c3 = {'migration-compat-01': [1741, 2083, 2131], 'dual-write-06': [1742, 2075, 2121]}
        with tempfile.TemporaryDirectory(dir='/private/tmp') as tmp:
            root = Path(tmp).resolve() / 'isolation'
            for a in s.isolation.prepare(root)['assignments']:
                workspace = root / 'targets' / a['target'] / 'workspace'
                files = sorted(p.name for p in workspace.iterdir())
                batch = response('read', {'path': files[0]}, 'read_0')
                batch['choices'][0]['message']['tool_calls'] += [
                    response('read', {'path': name}, f'read_{i}')['choices'][0]['message']['tool_calls'][0]
                    for i, name in enumerate(files[1:], 1)]
                batch['choices'][0]['message']['reasoning_content'] = 'Inspect the evidence before concluding.'
                checked = subprocess.run(['python3', 'verify.py'], cwd=workspace, capture_output=True, text=True, check=False)
                observed = {'exit_code': checked.returncode, 'stdout': checked.stdout, 'stderr': checked.stderr}
                system, exposure = s.review_exposure(root, a, cfg, token_counter=counter)
                replies = iter([batch, response('shell', {'command': 'python3 verify.py'}, 'verify'), response()])
                counts, records = [], []
                def send(cfg, payload, timeout):
                    count = counter(payload); counts.append(count)
                    answer = copy.deepcopy(next(replies))
                    # Input counts are real local counts; completion is a chosen
                    # nonzero scenario, not observed provider output/usage.
                    answer['usage'] = {'prompt_tokens': count, 'completion_tokens': 200, 'total_tokens': count + 200}
                    return answer
                def tool(name, arguments):
                    return {'content': (workspace / arguments['path']).read_text()} if name == 'read' else observed
                with self.subTest(case=a['case']['id'], condition=a['condition']['condition_id']), \
                     patch.object(s.provider, 'transport', side_effect=AssertionError('provider calls forbidden')):
                    result = s.run_agent(cfg, a['case']['prompt'], '', tool, lambda n: None,
                                         lambda *x: records.append(x), send, limits=s.REVIEW_LIMITS,
                                         payload_options=s.REVIEW_OPTIONS, token_counter=counter, system_message=system,
                                         first_request_sha256=exposure['first_request_sha256'])
                    self.assertEqual((result['model_requests'], result['tool_calls']), (3, 4))
                    self.assertEqual(result['reported_total_tokens'], sum(counts) + 600)
                    self.assertEqual([r[2]['input_tokens_reserved'] for r in records if r[0] == 'request'],
                                     [n + 512 for n in counts])
                    if a['condition']['condition_id'].startswith('c3-'):
                        self.assertEqual(counts, expected_c3[a['case']['id']])


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
