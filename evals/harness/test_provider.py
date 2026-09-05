import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evals.harness import provider as p


def config():
    return dict(T1_PROTOCOL='openai-chat', T1_ENDPOINT_URL='http://127.0.0.1:9507/v1/chat/completions',
                T1_MODEL_ID='test/model', T1_MODEL_VERSION='unknown', T1_API_KEY='secret-for-tests',
                T1_SUPPORTS_TOOL_CALLS='true')


def first():
    return {'choices': [{'finish_reason': 'tool_calls', 'message': {'role': 'assistant',
            'tool_calls': [{'id': 'call_1', 'type': 'function',
                            'function': {'name': 'probe_nonce', 'arguments': '{}'}}]}}],
            'usage': {'prompt_tokens': 30, 'completion_tokens': 10, 'total_tokens': 40}}


class Mock:
    def __init__(self, response=None):
        self.response = first() if response is None else response
        self.payloads = []

    def __call__(self, cfg, raw):
        body = json.loads(raw)
        self.payloads.append(body)
        if len(self.payloads) == 1:
            return self.response
        return {'choices': [{'finish_reason': 'stop', 'message': {
            'role': 'assistant', 'content': body['messages'][-1]['content']}}]}


class ProviderTests(unittest.TestCase):
    def test_handshake_and_wire_contract(self):
        mock, attempts = Mock(), []
        result = p.Session(config(), mock, attempts.append).handshake()
        self.assertEqual(attempts, [1, 2])
        self.assertTrue(result['tool_handshake_passed'])
        self.assertEqual(result['usage'], [first()['usage'], None])
        self.assertIsNone(result['cost_usd'])
        a, b = mock.payloads
        self.assertEqual(a['max_completion_tokens'], 256)
        self.assertNotIn('max_tokens', a)
        self.assertEqual(a['tool_choice']['function']['name'], 'probe_nonce')
        self.assertEqual(b['tool_choice'], 'none')
        self.assertEqual(b['messages'][-1]['tool_call_id'], 'call_1')
        self.assertNotIn(config()['T1_API_KEY'], json.dumps(mock.payloads))

    def test_invalid_calls_stop_before_second_request(self):
        for kind in ('name', 'id', 'arguments', 'multiple', 'truncated', 'duplicate_json', 'null'):
            with self.subTest(kind=kind):
                response = first()
                choice = response['choices'][0]
                call = choice['message']['tool_calls'][0]
                if kind == 'name': call['function']['name'] = 'shell'
                if kind == 'id': call['id'] = ''
                if kind == 'arguments': call['function']['arguments'] = '{"cmd":"rm"}'
                if kind == 'multiple': choice['message']['tool_calls'] *= 2
                if kind == 'truncated': choice['finish_reason'] = 'length'
                if kind == 'duplicate_json': call['function']['arguments'] = '{"a":1,"a":2}'
                if kind == 'null': call['function']['arguments'] = 'null'
                mock = Mock(response)
                with self.assertRaises(p.ProbeError): p.Session(config(), mock, lambda n: None).handshake()
                self.assertEqual(len(mock.payloads), 1)

    def test_final_truncation_and_wrong_nonce(self):
        for reason, content in [('length', 'nonce'), ('stop', 'wrong')]:
            mock = Mock()
            def send(cfg, raw):
                result = mock(cfg, raw)
                if len(mock.payloads) == 2:
                    result['choices'][0]['finish_reason'] = reason
                    result['choices'][0]['message']['content'] = content
                return result
            with self.assertRaises(p.ProbeError): p.Session(config(), send, lambda n: None).handshake()
            self.assertEqual(len(mock.payloads), 2)

    def test_usage_invalid_or_missing(self):
        for value in [True, -1, 1.5]:
            response = first()
            response['usage']['total_tokens'] = value
            with self.assertRaises(p.ProbeError):
                p.Session(config(), Mock(response), lambda n: None).handshake()
        response = first()
        del response['usage']
        self.assertEqual(p.Session(config(), Mock(response), lambda n: None).handshake()['usage'], [None, None])

    def test_timeout_redacted_and_consumed(self):
        def fail(*args): raise TimeoutError('secret-for-tests')
        attempts = []
        session = p.Session(config(), fail, attempts.append)
        with self.assertRaisesRegex(p.ProbeError, 'transport failed') as caught:
            session.handshake()
        self.assertNotIn('secret-for-tests', str(caught.exception))
        self.assertEqual(attempts, [1])

    def test_budget_and_journal_failure(self):
        mock = Mock()
        session = p.Session(config(), mock, lambda n: None)
        session.handshake()
        with self.assertRaisesRegex(p.ProbeError, 'budget'): session.request([], 'none')
        self.assertEqual(len(mock.payloads), 2)
        def disk_full(n): raise OSError('full')
        with self.assertRaises(OSError): p.Session(config(), mock, disk_full).request([], 'none')
        self.assertEqual(len(mock.payloads), 2)

    def test_config_security(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d).resolve() / 'provider.env'
            def write(cfg):
                path.write_text('\n'.join(k + '=' + v for k, v in cfg.items()))
                path.chmod(0o600)
            write(config())
            self.assertEqual(p.load_config(path), config())
            path.chmod(0o644)
            with self.assertRaises(p.ProbeError): p.load_config(path)
            path.chmod(0o600)
            link = path.parent / 'link'
            link.symlink_to(path)
            with self.assertRaises(p.ProbeError): p.load_config(link)
            for key, value in [('T1_ENDPOINT_URL', 'hhttp://127.0.0.1:9507/v1/chat/completions'),
                               ('T1_ENDPOINT_URL', 'http://example.com/v1/chat/completions'),
                               ('T1_API_KEY', '$(touch /tmp/no)'),
                               ('T1_MODEL_VERSION', 'immutable-provider-version')]:
                cfg = config(); cfg[key] = value; write(cfg)
                with self.assertRaises(p.ProbeError): p.load_config(path)
            write(config())
            with path.open('a') as handle: handle.write('\nT1_API_KEY=duplicate')
            with self.assertRaises(p.ProbeError): p.load_config(path)

    def test_plan_drift_and_replay(self):
        with tempfile.TemporaryDirectory() as d, patch.object(p, 'RUNS', Path(d)):
            cfg = config(); approved = p.plan(cfg); mock = Mock()
            drift = copy.deepcopy(approved); drift['budget']['requests'] = 3
            with self.assertRaises(p.ProbeError): p.execute(cfg, drift, mock)
            self.assertEqual(mock.payloads, [])
            p.execute(cfg, approved, mock)
            with self.assertRaises(FileExistsError): p.execute(cfg, approved, mock)
            self.assertEqual(len(mock.payloads), 2)
            ledger = next(Path(d).iterdir())
            self.assertTrue((ledger / 'attempt-2.json').exists())
            self.assertNotIn(cfg['T1_API_KEY'], ''.join(f.read_text() for f in ledger.iterdir()))

    def test_interrupted_attempt_cannot_replay(self):
        with tempfile.TemporaryDirectory() as d, patch.object(p, 'RUNS', Path(d)):
            def interrupt(*args): raise KeyboardInterrupt()
            with self.assertRaises(KeyboardInterrupt): p.execute(config(), p.plan(config()), interrupt)
            with self.assertRaises(FileExistsError): p.execute(config(), p.plan(config()), Mock())
            self.assertTrue((next(Path(d).iterdir()) / 'attempt-1.json').exists())

    def test_http_redirect_errors_and_size(self):
        for status in (302, 401, 429, 500):
            with patch.object(p.http.client, 'HTTPConnection') as cls:
                cls.return_value.getresponse.return_value.status = status
                with self.assertRaisesRegex(p.ProbeError, str(status)):
                    p.transport(config(), b'{}')
                self.assertEqual(cls.return_value.request.call_count, 1)
        with patch.object(p.http.client, 'HTTPConnection') as cls:
            response = cls.return_value.getresponse.return_value
            response.status = 200; response.read.return_value = b'x' * 65537
            with self.assertRaisesRegex(p.ProbeError, 'byte limit'): p.transport(config(), b'{}')


if __name__ == '__main__': unittest.main()
