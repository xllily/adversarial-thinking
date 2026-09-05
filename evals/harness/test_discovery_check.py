import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from evals.harness import provider as p, shakedown as s, discovery_check as d
from evals.harness.test_provider import config
from evals.harness.test_shakedown import response


class GlmTests(unittest.TestCase):
    def test_endpoint_allows_only_exact_official_extension(self):
        for endpoint, valid in [(p.BIGMODEL_ENDPOINT, True),
                (p.BIGMODEL_ENDPOINT.replace('https:', 'http:'), False),
                (p.BIGMODEL_ENDPOINT.replace('/v4/', '/v4//'), False),
                (p.BIGMODEL_ENDPOINT.replace('open.bigmodel.cn', 'example.com'), False),
                (p.BIGMODEL_ENDPOINT + '?x=1', False)]:
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp).resolve() / 'config'
                cfg = dict(config(), T1_ENDPOINT_URL=endpoint)
                path.write_text('\n'.join(k+'='+v for k,v in cfg.items())); path.chmod(0o600)
                if valid: self.assertEqual(p.load_config(path)['T1_ENDPOINT_URL'], endpoint)
                else:
                    with self.assertRaises(p.ProbeError): p.load_config(path)

    def test_decimal_rates_round_up_and_preserve_historical_money(self):
        carry = dict(s.CostBudget(lambda *x: None).snapshot(), estimated_cost_cny='0.093633',
                     carried_reservation_cny='0.022569', reserved_requests=13,
                     reported_prompt_tokens=12497, reported_completion_tokens=6238)
        b = s.CostBudget(lambda *x: None, policy=d.POLICY, carried=carry,
                         carried_policy=s.COST_POLICY, completion_cap=4096)
        self.assertEqual((b.spent, b.carried_reservation, b.requests), (93633,22569,13))
        self.assertEqual(b.estimate(1,1), 4)
        b.reserve(b'{}')
        self.assertEqual(b.pending, 11880)
        b.observe(response())
        self.assertEqual(b.snapshot()['estimated_cost_cny'], '0.093769')
        self.assertEqual(b.carried_reservation, 22569)
        with self.assertRaisesRegex(ValueError, 'policy mismatch'):
            s.CostBudget(lambda *x: None, policy=d.POLICY, carried=carry)

    def test_glm_replays_reasoning_and_uses_full_reservation_cap(self):
        first = response('read', {'path': '/skills/SKILL.md'})
        first['choices'][0]['message']['reasoning_content'] = 'private test reasoning'
        replies = iter([first, response()]); requests = []
        def send(cfg, payload, seconds):
            requests.append(p.strict_json(payload)); return next(replies)
        s.run_agent(dict(config(), T1_ENDPOINT_URL=p.BIGMODEL_ENDPOINT), 'p', '', lambda *x: {},
                    lambda *x: None, lambda *x: None, send, limits=d.LIMITS, payload_options=d.OPTIONS)
        self.assertEqual(requests[1]['messages'][2]['reasoning_content'], 'private test reasoning')
        self.assertEqual(requests[0]['max_tokens'], 4096)
        self.assertNotIn('max_completion_tokens', requests[0])
        self.assertNotIn('parallel_tool_calls', requests[0])

    def test_tool_runtime_error_stops_without_second_request(self):
        sent = []
        def send(*x): sent.append(1); return response('read', {'path':'missing'})
        with self.assertRaisesRegex(ValueError, 'tool execution failed'):
            s.run_agent(config(), 'p', '', lambda *x: {'error':'missing'}, lambda *x: None,
                        lambda *x: None, send)
        self.assertEqual(len(sent), 1)

    def test_plan_drift_blocks_before_paid_request(self):
        with patch.object(d, 'prepare', return_value={'new':1}):
            with self.assertRaisesRegex(ValueError, 'drift'):
                d.execute(Path('/tmp'), config(), {'old':1}, s.digest({'old':1}))


class JournalTests(unittest.TestCase):
    def test_failure_retains_reservation_and_claim_prevents_replay(self):
        carry = dict(s.CostBudget(lambda *x: None).snapshot(), estimated_cost_cny='0.093633',
                     carried_reservation_cny='0.022569', reserved_requests=13)
        plan = {'carry': {'cost_monitor':carry, 'historical_policy':s.COST_POLICY},
                'entries':[{'id':'high-risk','prompt':'p'}, {'id':'low-risk','prompt':'q'}],
                'assignment':{}, 'discovery':''}
        def fail(*args, **kwargs):
            kwargs['cost_budget'].reserve(b'{}')
            raise p.ProbeError('provider HTTP status 429')
        with tempfile.TemporaryDirectory() as tmp, patch.object(p,'RUNS',Path(tmp)), \
                patch.object(d,'prepare',return_value=plan), \
                patch.object(d.i,'invoke',return_value={'receipt':{}}), \
                patch.object(d.i,'check_receipt'), patch.object(s,'run_agent',side_effect=fail) as agent:
            (Path(tmp)/d.PREVIOUS).mkdir()
            with self.assertRaisesRegex(ValueError,'stopped'):
                d.execute(Path(tmp),config(),plan,s.digest(plan))
            failure=p.strict_json((Path(tmp)/('discovery-'+s.digest(plan))/'failure.json').read_bytes())
            self.assertEqual(failure['error'],'provider HTTP status 429')
            self.assertEqual(failure['completed'],[])
            self.assertEqual(failure['cost_monitor']['reserved_requests'],14)
            self.assertEqual(failure['cost_monitor']['pending_reservation_cny'],'0.011880')
            with self.assertRaises(FileExistsError): d.execute(Path(tmp),config(),plan,s.digest(plan))
            agent.assert_called_once()

if __name__ == '__main__': unittest.main()
