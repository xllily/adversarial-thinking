#!/usr/bin/env python3
"""Bounded diagnostic agent runner for the eight T1 isolation targets."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import signal
import sys
import time

if __package__:
    from . import isolation, provider
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from evals.harness import isolation, provider

LIMITS = {'runs': 8, 'model_requests_per_run': 12, 'model_requests_total': 96,
          'completion_tokens_per_request': 1024, 'completion_tokens_total': 98304,
          'reported_total_token_stop_threshold_per_run': 16000,
          'request_bytes': 12288, 'tool_calls_per_run': 12,
          'run_deadline_seconds': 180, 'request_deadline_seconds': 30,
          'retries': 0, 'redirects': 0, 'delegation': 0}
TOOLS = [
    {'type': 'function', 'function': {'name': 'read', 'description':
     'Read one regular UTF-8 file under /workspace or the available /skills directory.',
     'parameters': {'type': 'object', 'properties': {'path': {'type': 'string'}},
                    'required': ['path'], 'additionalProperties': False}}},
    {'type': 'function', 'function': {'name': 'shell', 'description':
     'Run the frozen deterministic check. The only command is python3 verify.py.',
     'parameters': {'type': 'object', 'properties': {'command': {'type': 'string',
                    'enum': ['python3 verify.py']}}, 'required': ['command'],
                    'additionalProperties': False}}}]


def digest(value):
    return hashlib.sha256(provider.encode(value)).hexdigest()


def make_plan(root, config):
    manifest = isolation.load_manifest(root)
    # Require actual completed offline evidence; never synthesize it from assignments.
    summary = provider.strict_json((root / 'offline-evidence/summary.json').read_bytes())
    if summary.get('isolated_workspaces_checked') != 8 or summary.get('model_calls') != 0:
        raise ValueError('offline rehearsal incomplete')
    evidence_hashes = {}
    for a in manifest['assignments']:
        path = root / 'offline-evidence' / (a['target'] + '.json')
        observed = provider.strict_json(path.read_bytes())
        isolation.check_receipt(observed, a)
        evidence_hashes[a['target']] = digest(observed)
    code = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in
            [Path(__file__), Path(isolation.__file__), isolation.WORKER,
             Path(provider.__file__), Path(isolation.pilot.__file__)]}
    return {'schema': 1, 'purpose': 'diagnostic agent isolation shakedown',
            'root': str(root), 'provider': {k: v for k, v in provider.plan(config).items()
            if k in {'config_sha256', 'protocol', 'endpoint', 'model', 'declared_version',
                     'immutable_version_verified', 'tool_support_declared'}}, 'limits': LIMITS,
            'manifest_sha256': digest(manifest), 'offline_evidence_sha256': evidence_hashes,
            'code_sha256': code, 'tools': TOOLS, 'cost_usd': None,
            'evaluation_record': False, 'immutable_version_verified': False,
            'scoring_blockers': ['price/cost unknown', 'immutable version unverified',
                                 'provider input token upper bound unverified'],
            'input_token_limit_note': 'Reported usage is checked after each response. '
            'Before dispatch, request bytes plus completion cap are compared with remaining '
            'tokens as a conservative guard, not a proven tokenizer bound. A response can '
            'cross 16000; abort and record the overrun. No claim of billing cap or T0 budget parity.'}


def bounded_send(config, payload, seconds):
    def alarm(*_):
        raise TimeoutError('request deadline')
    previous = signal.signal(signal.SIGALRM, alarm)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        return provider.transport(config, payload)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def parse_response(data):
    try:
        usage = data['usage']
        keys = ('prompt_tokens', 'completion_tokens', 'total_tokens')
        if any(type(usage[k]) is not int or usage[k] < 0 for k in keys):
            raise ValueError('invalid usage')
        if usage['prompt_tokens'] + usage['completion_tokens'] != usage['total_tokens']:
            raise ValueError('inconsistent usage')
        choices = data['choices']
        if len(choices) != 1 or choices[0]['message']['role'] != 'assistant':
            raise ValueError('invalid choices')
        choice = choices[0]
        if choice['finish_reason'] not in ('stop', 'tool_calls'):
            raise ValueError('incomplete response')
        content = choice['message'].get('content')
        if content is not None and not isinstance(content, str):
            raise ValueError('invalid assistant text')
        return choice, {k: usage[k] for k in keys}
    except (KeyError, TypeError, IndexError, AttributeError):
        raise ValueError('malformed response or missing usage') from None


def run_agent(config, prompt, discovery, execute_tool, before_send, record,
              send=bounded_send, clock=time.monotonic):
    started = clock()
    messages = [{'role': 'system', 'content':
        'Work within /workspace using the available read and shell tools. Do not edit files. '
        'Skill files listed below may be read when their description matches the task. '
        'Use their instructions when applicable. Stop with a final answer when evidence is sufficient.\n'
        + discovery}, {'role': 'user', 'content': prompt}]
    calls, tokens, tool_count, ids = 0, 0, 0, set()
    while calls < LIMITS['model_requests_per_run']:
        remaining = LIMITS['run_deadline_seconds'] - (clock() - started)
        if remaining <= 0: raise ValueError('run deadline exceeded')
        payload = provider.encode({'model': config['T1_MODEL_ID'], 'messages': messages,
                                  'tools': TOOLS, 'tool_choice': 'auto', 'parallel_tool_calls': False,
                                  'max_completion_tokens': LIMITS['completion_tokens_per_request'],
                                  'n': 1, 'stream': False})
        if len(payload) > LIMITS['request_bytes']:
            raise ValueError('request byte budget exhausted')
        if tokens + len(payload) + LIMITS['completion_tokens_per_request'] > 16000:
            raise ValueError('conservative token dispatch guard exhausted')
        before_send(calls + 1)
        calls += 1
        data = send(config, payload, min(remaining, LIMITS['request_deadline_seconds']))
        # Persist full response locally (redacted by controller), even if parsing fails.
        record('response', calls, data)
        choice, usage = parse_response(data)
        tokens += usage['total_tokens']
        if tokens > 16000 or usage['completion_tokens'] > LIMITS['completion_tokens_per_request']:
            raise ValueError('reported token budget exceeded')
        if clock() - started >= LIMITS['run_deadline_seconds']:
            raise ValueError('run deadline exceeded')
        message = choice['message']
        if choice['finish_reason'] == 'stop':
            if message.get('tool_calls') or not message.get('content'):
                raise ValueError('invalid final response')
            return {'complete_output': message['content'], 'model_requests': calls,
                    'reported_total_tokens': tokens, 'tool_calls': tool_count,
                    'latency_ms': round((clock() - started) * 1000), 'cost_usd': None,
                    'evaluation_record': False}
        raw_calls = message.get('tool_calls')
        if not isinstance(raw_calls, list) or len(raw_calls) != 1:
            raise ValueError('expected one nonparallel tool call')
        call = raw_calls[0]
        try:
            call_id, name = call['id'], call['function']['name']
            if (call['type'] != 'function' or not isinstance(call_id, str) or
                    not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', call_id) or call_id in ids or
                    name not in ('read', 'shell')):
                raise ValueError('invalid tool name or id')
            arguments = provider.strict_json(call['function']['arguments'])
            field = 'path' if name == 'read' else 'command'
            if not isinstance(arguments, dict) or set(arguments) != {field} or not isinstance(arguments[field], str):
                raise ValueError('invalid tool arguments')
            if name == 'shell' and arguments['command'] != 'python3 verify.py':
                raise ValueError('shell command not allowed')
        except (KeyError, TypeError):
            raise ValueError('malformed tool call') from None
        if tool_count >= LIMITS['tool_calls_per_run']:
            raise ValueError('tool budget exhausted')
        ids.add(call_id)
        tool_count += 1
        result = execute_tool(name, arguments)
        record('tool', tool_count, {'id': call_id, 'name': name, 'arguments': arguments, 'result': result})
        messages += [{'role': 'assistant', 'content': message.get('content'), 'tool_calls': [
                      {'id': call_id, 'type': 'function', 'function': {
                       'name': name, 'arguments': json.dumps(arguments)}}]},
                     {'role': 'tool', 'tool_call_id': call_id, 'content': json.dumps(result)}]
    raise ValueError('model request budget exhausted without final output')


def execute(root, config, approved, authorization):
    current = make_plan(root, config)
    if approved != current or authorization != digest(current):
        raise ValueError('reviewed plan/config/code/evidence mismatch')
    if config['T1_SUPPORTS_TOOL_CALLS'] != 'true':
        raise ValueError('tool support not declared')
    ledger = provider.RUNS / ('shakedown-' + digest(current))
    ledger.mkdir(mode=0o700)
    # Claim is durable before any invocation; replay is forbidden for this plan.
    provider.write_new(ledger / 'plan.json', current)
    import os
    fd = os.open(ledger.parent, os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)
    manifest = isolation.load_manifest(root)
    completed = []
    try:
        for a in manifest['assignments']:
            run = ledger / a['target']
            run.mkdir()
            fd = os.open(ledger, os.O_RDONLY)
            try: os.fsync(fd)
            finally: os.close(fd)
            def persist(kind, number, value):
                safe = provider.encode(value).replace(config['T1_API_KEY'].encode(), b'[REDACTED]')
                provider.write_new(run / f'{kind}-{number}.json', provider.strict_json(safe))
            observed = isolation.invoke(root, a, {'operation': 'inspect'})
            isolation.check_receipt(observed, a)
            provider.write_new(run / 'isolation-before.json', observed)
            discovery = 'Workspace files: ' + ', '.join(observed['runtime']['workspace_files'])
            if observed['receipt']['skill_present']:
                text = isolation.invoke(root, a, {'name': 'read', 'arguments': {'path': '/skills/SKILL.md'}})['content']
                if not text.startswith('---\n') or '\n---\n' not in text[4:]:
                    raise ValueError('invalid skill discovery header')
                header = text.split('\n---\n', 1)[0]
                discovery += '\nAvailable skill: /skills/SKILL.md\n' + header
            else:
                discovery += '\nAvailable skills: []'
            result = run_agent(config, a['case']['prompt'], discovery,
                               lambda n, v: isolation.invoke(root, a, {'name': n, 'arguments': v}),
                               lambda n: provider.write_new(run / f'attempt-{n}.json',
                                          {'attempt': n, 'time': time.time(), 'outcome': 'unknown_before_send'}),
                               persist)
            after = isolation.invoke(root, a, {'operation': 'inspect'})
            isolation.check_receipt(after, a)
            if after['receipt'] != observed['receipt']:
                raise ValueError('isolation changed during agent run')
            provider.write_new(run / 'isolation-after.json', after)
            persist('result', 1, result)
            completed.append({'target': a['target'], 'model_requests': result['model_requests'],
                              'reported_total_tokens': result['reported_total_tokens']})
            print('diagnostic agent completed: ' + a['target'], flush=True)
    except BaseException:
        provider.write_new(ledger / 'failure.json', {'outcome': 'failed_or_unknown_no_retry',
                           'completed': completed, 'evaluation_record': False})
        raise ValueError('shakedown stopped; inspect attempt ledger; no retry') from None
    result = {'completed_runs': len(completed), 'runs': completed, 'evaluation_record': False,
              'cost_usd': None, 'immutable_version_verified': False}
    provider.write_new(ledger / 'summary.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['plan', 'run'])
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--authorize-plan-sha256')
    args = parser.parse_args()
    try:
        config = provider.load_config()
        plan_path = args.root / 'shakedown-plan.controller.json'
        if args.command == 'plan':
            plan = make_plan(args.root, config)
            provider.write_new(plan_path, plan)
            print(json.dumps({'plan': str(plan_path), 'plan_sha256': digest(plan), 'limits': LIMITS,
                              'model': plan['provider']['model'], 'cost_usd': None}, indent=2))
        else:
            approved = provider.strict_json(plan_path.read_bytes())
            print(json.dumps(execute(args.root, config, approved, args.authorize_plan_sha256), indent=2))
        return 0
    except Exception:
        print('shakedown operation failed; no automatic retry; inspect local plan/ledger', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
