#!/usr/bin/env python3
"""Bounded OpenAI Chat tool probe. Independent of evaluation/isolation records."""
import argparse
import hashlib
import http.client
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import stat
import sys
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / 'evals/.runs/t1-provider.env'
RUNS = ROOT / 'evals/.runs'
BIGMODEL_ENDPOINT = 'https://open.bigmodel.cn/api/paas/v4/chat/completions'
FIELDS = {'T1_PROTOCOL', 'T1_ENDPOINT_URL', 'T1_MODEL_ID', 'T1_MODEL_VERSION',
          'T1_API_KEY', 'T1_SUPPORTS_TOOL_CALLS'}
BUDGET = {'requests': 2, 'max_completion_tokens_per_request': 256,
          'socket_timeout_seconds': 30, 'max_request_bytes': 4096,
          'max_response_bytes': 65536, 'retries': 0, 'redirects': 0}
TOOL = {'type': 'function', 'function': {'name': 'probe_nonce',
        'description': 'Return a fresh nonce with no external side effects.',
        'parameters': {'type': 'object', 'properties': {},
                       'required': [], 'additionalProperties': False}}}


class ProbeError(ValueError):
    """Only fixed, secret-free diagnostics may cross the CLI boundary."""


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ProbeError('duplicate JSON key')
            result[key] = value
        return result
    def constant(_):
        raise ProbeError('non-finite JSON')
    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, TypeError, RecursionError):
        raise ProbeError('invalid JSON') from None


def load_config(path=CONFIG):
    # No shell expansion, dotenv evaluation, subprocesses, or secret-bearing repr.
    try:
        for parent in path.absolute().parents:
            if parent.is_symlink():
                raise ProbeError('config ancestor symlink rejected')
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as handle:
            info = os.fstat(handle.fileno())
            if (not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600
                    or info.st_uid != os.getuid() or info.st_nlink != 1):
                raise ProbeError('config requires owned regular single-link file with mode 600')
            raw = handle.read(16385)
        if len(raw) > 16384:
            raise ProbeError('config too large')
        values = {}
        for line in raw.decode('utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            key, sep, value = line.partition('=')
            if sep != '=' or key not in FIELDS or key in values:
                raise ProbeError('invalid or duplicate config field')
            if value[:1] in {'"', "'"}:
                if len(value) < 2 or value[-1] != value[0]:
                    raise ProbeError('unmatched config quote')
                value = value[1:-1]
            if not value or not value.isascii() or any(ord(c) < 33 for c in value):
                raise ProbeError('invalid config value')
            if any(c in value for c in '$`\\\"\''):
                raise ProbeError('config expansion or quoting syntax rejected')
            values[key] = value
        if values.keys() != FIELDS:
            raise ProbeError('missing config fields')
        if values['T1_PROTOCOL'] != 'openai-chat':
            raise ProbeError('only configured openai-chat protocol implemented')
        if values['T1_SUPPORTS_TOOL_CALLS'] not in {'true', 'false'}:
            raise ProbeError('invalid tool capability declaration')
        u = urlsplit(values['T1_ENDPOINT_URL'])
        if (u.scheme not in {'http', 'https'} or not u.hostname or u.username
                or u.password or u.query or u.fragment or not (u.path == '/v1/chat/completions'
                or values['T1_ENDPOINT_URL'] == BIGMODEL_ENDPOINT)):
            raise ProbeError('endpoint requires http(s) origin and /v1/chat/completions without credentials/query')
        _ = u.port
        if u.scheme == 'http':
            try:
                local = ipaddress.ip_address(u.hostname).is_loopback
            except ValueError:
                local = False
            if not local:
                raise ProbeError('plaintext HTTP requires literal loopback address')
        for key in ('T1_MODEL_ID', 'T1_MODEL_VERSION'):
            if not re.fullmatch(r'[A-Za-z0-9._:/-]{1,160}', values[key]):
                raise ProbeError('invalid model identifier')
        if values['T1_MODEL_VERSION'] == 'immutable-provider-version':
            raise ProbeError('replace version placeholder with actual version or unknown')
        return values
    except (OSError, UnicodeError, ValueError) as exc:
        if isinstance(exc, ProbeError):
            raise
        raise ProbeError('config unreadable or malformed') from None


def plan(config):
    # Includes credential rotation in binding, never exports the credential itself.
    fingerprint = hashlib.sha256(encode(config)).hexdigest()
    return {'schema': 1, 'config_sha256': fingerprint,
            'adapter_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'protocol': config['T1_PROTOCOL'], 'endpoint': config['T1_ENDPOINT_URL'],
            'model': config['T1_MODEL_ID'], 'declared_version': config['T1_MODEL_VERSION'],
            'immutable_version_verified': False, 'tool_support_declared': config['T1_SUPPORTS_TOOL_CALLS'],
            'tool_support_verified': False, 'cost_usd': None, 'budget': BUDGET,
            'evidence_scope': 'synthetic tool handshake only'}


def transport(config, payload, timeout=None):
    """One direct POST, no proxy environment, redirects, or retry handler."""
    u = urlsplit(config['T1_ENDPOINT_URL'])
    cls = http.client.HTTPSConnection if u.scheme == 'https' else http.client.HTTPConnection
    conn = cls(u.hostname, u.port, timeout=BUDGET['socket_timeout_seconds'] if timeout is None else timeout)
    try:
        conn.request('POST', u.path, body=payload, headers={
            'Authorization': 'Bearer ' + config['T1_API_KEY'], 'Content-Type': 'application/json'})
        response = conn.getresponse()
        if response.status != 200:
            raise ProbeError('provider HTTP status ' + str(response.status))
        raw = response.read(BUDGET['max_response_bytes'] + 1)
        if len(raw) > BUDGET['max_response_bytes']:
            raise ProbeError('response byte limit exceeded')
        return strict_json(raw)
    finally:
        conn.close()


class Session:
    def __init__(self, config, send, before_send):
        self.config, self.send, self.before_send = config, send, before_send
        self.attempts = 0
        self.usage = []

    def request(self, messages, choice):
        if self.attempts >= BUDGET['requests']:
            raise ProbeError('request budget exhausted')
        payload = encode({'model': self.config['T1_MODEL_ID'], 'messages': messages,
                          'tools': [TOOL], 'tool_choice': choice, 'parallel_tool_calls': False,
                          'max_completion_tokens': 256, 'n': 1, 'stream': False})
        if len(payload) > BUDGET['max_request_bytes']:
            raise ProbeError('request byte limit exceeded')
        self.before_send(self.attempts + 1)
        self.attempts += 1
        try:
            data = self.send(self.config, payload)
        except ProbeError:
            raise
        except Exception:
            raise ProbeError('transport failed; attempt consumed; no retry') from None
        try:
            usage = data.get('usage')
            if usage is None:
                self.usage.append(None)
            else:
                keys = ('prompt_tokens', 'completion_tokens', 'total_tokens')
                if any(type(usage[k]) is not int or usage[k] < 0 for k in keys):
                    raise ProbeError('invalid usage')
                if usage['total_tokens'] != usage['prompt_tokens'] + usage['completion_tokens']:
                    raise ProbeError('inconsistent usage')
                self.usage.append({k: usage[k] for k in keys})
            choices = data['choices']
            if len(choices) != 1 or choices[0]['message']['role'] != 'assistant':
                raise ProbeError('invalid assistant choices')
            return choices[0]
        except (KeyError, TypeError, AttributeError, IndexError):
            raise ProbeError('malformed provider response') from None

    def handshake(self):
        messages = [{'role': 'user', 'content':
                     'Call probe_nonce with no arguments. Then return only the nonce from its result.'}]
        first = self.request(messages, {'type': 'function', 'function': {'name': 'probe_nonce'}})
        try:
            calls = first['message']['tool_calls']
            if first['finish_reason'] != 'tool_calls' or len(calls) != 1:
                raise ProbeError('expected one complete tool call')
            call = calls[0]
            if (call['type'] != 'function' or call['function']['name'] != 'probe_nonce'
                    or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', call['id'])
                    or strict_json(call['function']['arguments']) != {}):
                raise ProbeError('invalid tool name, id, or arguments')
            # Generate only after successful validation. Never dispatch model-selected code.
            nonce = secrets.token_hex(16)
            messages += [{'role': 'assistant', 'content': None, 'tool_calls': [{'id': call['id'], 'type': 'function',
                             'function': {'name': 'probe_nonce', 'arguments': '{}'}}]},
                         {'role': 'tool', 'tool_call_id': call['id'], 'content': nonce}]
            second = self.request(messages, 'none')
            if (second['finish_reason'] != 'stop' or second['message'].get('tool_calls')
                    or second['message']['content'] != nonce):
                raise ProbeError('nonce mismatch or incomplete final output')
        except (KeyError, TypeError, AttributeError):
            raise ProbeError('malformed tool handshake') from None
        return {'tool_handshake_passed': True, 'requests_attempted': self.attempts,
                'usage': self.usage, 'cost_usd': None, 'immutable_version_verified': False,
                'isolation_verified': False, 'evaluation_record': False}


def write_new(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as handle:
        handle.write(encode(value) + b'\n')
        handle.flush()
        os.fsync(handle.fileno())
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def execute(config, approved, send=transport):
    expected = plan(config)
    if approved != expected:
        raise ProbeError('plan/config mismatch; fresh review required')
    if config['T1_SUPPORTS_TOOL_CALLS'] != 'true':
        raise ProbeError('tool support not declared')
    ledger = RUNS / ('probe-' + expected['config_sha256'])
    # Exclusive permanent claim: interruption or failure forbids restarting this binding.
    ledger.mkdir(mode=0o700)
    parent_fd = os.open(RUNS, os.O_RDONLY)
    try:
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)
    write_new(ledger / 'plan.json', expected)
    session = Session(config, send, lambda n: write_new(
        ledger / ('attempt-' + str(n) + '.json'), {'attempt': n, 'time': time.time(),
                                                 'outcome': 'unknown_before_send'}))
    try:
        result = session.handshake()
    except Exception:
        write_new(ledger / 'result.json', {'tool_handshake_passed': False,
                  'requests_attempted': session.attempts, 'usage': session.usage,
                  'cost_usd': None, 'outcome': 'failed_or_unknown_no_retry'})
        raise ProbeError('probe failed; inspect ledger; do not retry') from None
    write_new(ledger / 'result.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['preflight', 'plan', 'probe'])
    parser.add_argument('--plan', type=Path, default=RUNS / 't1-probe-plan.json')
    parser.add_argument('--authorize-config-sha256')
    args = parser.parse_args()
    try:
        config = load_config()
        expected = plan(config)
        if args.command == 'preflight':
            result = expected
        elif args.command == 'plan':
            write_new(args.plan, expected)
            result = expected
        else:
            approved = strict_json(args.plan.read_bytes())
            if args.authorize_config_sha256 != expected['config_sha256']:
                raise ProbeError('explicit authorization fingerprint required')
            result = execute(config, approved)
        print(json.dumps(result, indent=2))
        return 0
    except Exception as exc:
        print(str(exc) if isinstance(exc, ProbeError) else 'local operation failed; no automatic retry', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
