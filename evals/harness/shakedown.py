#!/usr/bin/env python3
"""Bounded diagnostic agent runner for the eight T1 isolation targets."""
import argparse
from decimal import Decimal, ROUND_CEILING
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
          'request_gap_seconds': 60,
          'retries': 0, 'redirects': 0, 'delegation': 0}
COST_POLICY = {'limit_cny': '3.000000', 'basis': 'official reference, peak rates, no cache discount',
               'input_cny_per_million': 3, 'output_cny_per_million': 9,
               'source': 'https://api-docs.deepseek.com/zh-cn/quick_start/pricing/',
               'checked_date': '2026-09-05', 'actual_gateway_cost_cny': None,
               'reservation_input': 'request bytes plus 512 overhead tokens; not a proven tokenizer bound'}
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


def continuation_context(previous, current, manifest):
    if previous is None:
        return None
    if not re.fullmatch(r'[0-9a-f]{64}', previous):
        raise ValueError('invalid previous plan digest')
    ledger = provider.RUNS / ('shakedown-' + previous)
    plan = provider.strict_json((ledger / 'plan.json').read_bytes())
    failure = provider.strict_json((ledger / 'failure.json').read_bytes())
    if (digest(plan) != previous or any(plan[k] != current[k] for k in
            ('root', 'provider', 'manifest_sha256', 'offline_evidence_sha256')) or
            failure.get('outcome') != 'failed_or_unknown_no_retry'):
        raise ValueError('previous campaign/config/evidence mismatch')
    completed = failure['completed']
    targets = {a['target'] for a in manifest['assignments']}
    seen = [r['target'] for r in completed]
    if len(seen) != len(set(seen)) or not set(seen) <= targets:
        raise ValueError('invalid previous completed targets')
    budget = failure['cost_monitor']
    # Validate accounting before a new plan can be authorized.
    CostBudget(lambda *x: None, carried=budget)
    return {'plan_sha256': previous, 'failure_sha256': digest(failure),
            'completed': completed, 'cost_monitor': budget,
            'partial_run_policy': 'restart incomplete target with fresh messages; retain all prior cost and attempts'}


def make_plan(root, config, previous=None):
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
    result = {'schema': 1, 'purpose': 'diagnostic agent isolation shakedown',
            'root': str(root), 'provider': {k: v for k, v in provider.plan(config).items()
            if k in {'config_sha256', 'protocol', 'endpoint', 'model', 'declared_version',
                     'immutable_version_verified', 'tool_support_declared'}}, 'limits': LIMITS,
            'manifest_sha256': digest(manifest), 'offline_evidence_sha256': evidence_hashes,
            'code_sha256': code, 'tools': TOOLS, 'cost_usd': None, 'cost_policy': COST_POLICY,
            'evaluation_record': False, 'immutable_version_verified': False,
            'scoring_blockers': ['price/cost unknown', 'immutable version unverified',
                                 'provider input token upper bound unverified'],
            'input_token_limit_note': 'Reported usage is checked after each response. '
            'Before dispatch, request bytes plus completion cap are compared with remaining '
            'tokens as a conservative guard, not a proven tokenizer bound. A response can '
            'cross 16000; abort and record the overrun. No claim of billing cap or T0 budget parity.'}
    result['continuation'] = continuation_context(previous, result, manifest)
    return result


def bounded_send(config, payload, seconds):
    def alarm(*_):
        raise TimeoutError('request deadline')
    previous = signal.signal(signal.SIGALRM, alarm)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        return provider.transport(config, payload, timeout=seconds)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def parse_usage(data):
    try:
        usage = data['usage']
        keys = ('prompt_tokens', 'completion_tokens', 'total_tokens')
        if any(type(usage[k]) is not int or usage[k] < 0 for k in keys):
            raise ValueError('invalid usage')
        if usage['prompt_tokens'] + usage['completion_tokens'] != usage['total_tokens']:
            raise ValueError('inconsistent usage')
        return {k: usage[k] for k in keys}
    except (KeyError, TypeError):
        raise ValueError('missing or malformed usage') from None


def micro_cny(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]+\.[0-9]{6}', value):
        raise ValueError('invalid CNY accounting')
    whole, fractional = value.split('.')
    return int(whole) * 1000000 + int(fractional)


class RequestPacer:
    """One shared response-end-to-next-dispatch gap across every target."""
    def __init__(self, clock=time.monotonic, sleep=time.sleep):
        self.clock, self.sleep, self.ready_at = clock, sleep, None

    def wait(self):
        started = self.clock()
        while self.ready_at is not None:
            remaining = self.ready_at - self.clock()
            if remaining <= 0: break
            self.sleep(min(30, remaining))
        return self.clock() - started

    def finished(self):
        self.ready_at = self.clock() + LIMITS['request_gap_seconds']


class CostBudget:
    """Per-batch integer-microyuan reference estimate; not a gateway billing oracle."""
    def __init__(self, persist, limit_micro_cny=3000000, carried=None, completion_cap=None, policy=None, carried_policy=None):
        self.persist, self.limit = persist, limit_micro_cny
        self.policy = dict(COST_POLICY if policy is None else policy)
        self.rates = [Decimal(str(self.policy[k])) for k in
                      ('input_cny_per_million', 'output_cny_per_million')]
        if any(not r.is_finite() or r <= 0 for r in self.rates):
            raise ValueError('invalid reference rates')
        self.carried_policy = carried_policy
        self.completion_cap = LIMITS['completion_tokens_per_request'] if completion_cap is None else completion_cap
        if type(self.completion_cap) is not int or not 1 <= self.completion_cap <= 4096:
            raise ValueError('invalid completion reservation cap')
        self.spent = self.pending = self.requests = 0
        self.prompt_tokens = self.completion_tokens = 0
        self.carried_reservation = 0
        if carried is not None:
            if (carried['basis'] != (carried_policy or self.policy)['basis'] or
                    micro_cny(carried['limit_cny']) != self.limit):
                raise ValueError('previous cost policy mismatch')
            self.spent = micro_cny(carried['estimated_cost_cny'])
            self.carried_reservation = (micro_cny(carried['pending_reservation_cny']) +
                                        micro_cny(carried.get('carried_reservation_cny', '0.000000')))
            keys = ('reserved_requests', 'reported_prompt_tokens', 'reported_completion_tokens')
            if any(type(carried[k]) is not int or carried[k] < 0 for k in keys):
                raise ValueError('invalid previous usage counts')
            self.requests, self.prompt_tokens, self.completion_tokens = (carried[k] for k in keys)
            if not 0 < self.requests <= LIMITS['model_requests_total']:
                raise ValueError('invalid previous request count')

    def snapshot(self):
        return {'estimated_cost_cny': f'{self.spent / 1000000:.6f}',
                'pending_reservation_cny': f'{self.pending / 1000000:.6f}',
                'carried_reservation_cny': f'{self.carried_reservation / 1000000:.6f}',
                'limit_cny': f'{self.limit / 1000000:.6f}',
                'reserved_requests': self.requests,
                'reported_prompt_tokens': self.prompt_tokens,
                'reported_completion_tokens': self.completion_tokens,
                'actual_gateway_cost_cny': None, 'basis': self.policy['basis']}

    def estimate(self, prompt, completion):
        return int((prompt * self.rates[0] + completion * self.rates[1]).to_integral_value(rounding=ROUND_CEILING))

    def reserve(self, payload):
        if self.pending:
            raise ValueError('unresolved cost reservation; no retry')
        estimate = self.estimate(len(payload) + 512, self.completion_cap)
        if (self.requests >= LIMITS['model_requests_total'] or
                self.spent + self.carried_reservation + estimate >= self.limit):
            self.persist('blocked', self.requests + 1, self.snapshot())
            raise ValueError('CNY budget would be reached; request not sent')
        self.pending = estimate
        self.requests += 1
        self.persist('reserved', self.requests, self.snapshot())

    def observe(self, data):
        usage = parse_usage(data)
        if not self.pending:
            raise ValueError('response without cost reservation')
        actual_estimate = self.estimate(usage['prompt_tokens'], usage['completion_tokens'])
        exceeded_reservation = actual_estimate > self.pending
        self.spent += actual_estimate
        self.prompt_tokens += usage['prompt_tokens']
        self.completion_tokens += usage['completion_tokens']
        self.pending = 0
        self.persist('observed', self.requests, self.snapshot())
        if self.spent + self.carried_reservation >= self.limit or exceeded_reservation:
            raise ValueError('CNY estimate reached limit or exceeded request reservation')


def parse_response(data):
    try:
        usage = parse_usage(data)
        choices = data['choices']
        if len(choices) != 1 or choices[0]['message']['role'] != 'assistant':
            raise ValueError('invalid choices')
        choice = choices[0]
        if choice['finish_reason'] not in ('stop', 'tool_calls'):
            raise ValueError('incomplete response')
        content = choice['message'].get('content')
        if content is not None and not isinstance(content, str):
            raise ValueError('invalid assistant text')
        return choice, usage
    except (KeyError, TypeError, IndexError, AttributeError):
        raise ValueError('malformed response or missing usage') from None


def run_agent(config, prompt, discovery, execute_tool, before_send, record,
              send=bounded_send, clock=time.monotonic, cost_budget=None, pacer=None, limits=None, payload_options=None):
    limits = LIMITS if limits is None else limits
    started = clock()
    paused = 0
    def active_elapsed():
        return clock() - started - paused
    messages = [{'role': 'system', 'content':
        'Work within /workspace using the available read and shell tools. Do not edit files. '
        'Skill files listed below may be read when their description matches the task. '
        'Use their instructions when applicable. Stop with a final answer when evidence is sufficient.\n'
        + discovery}, {'role': 'user', 'content': prompt}]
    calls, tokens, tool_count, ids = 0, 0, 0, set()
    while calls < limits['model_requests_per_run']:
        remaining = limits['run_deadline_seconds'] - active_elapsed()
        if remaining <= 0: raise ValueError('run deadline exceeded')
        request = {'model': config['T1_MODEL_ID'], 'messages': messages,
                                  'tools': TOOLS, 'tool_choice': 'auto', 'parallel_tool_calls': False,
                                  'max_completion_tokens': limits['completion_tokens_per_request'],
                                  'n': 1, 'stream': False}
        if payload_options:
            request.pop('max_completion_tokens')
            request.update(payload_options)
            if config['T1_ENDPOINT_URL'] == provider.BIGMODEL_ENDPOINT:
                request.pop('n')
                request.pop('parallel_tool_calls')
        payload = provider.encode(request)
        if len(payload) > limits['request_bytes']:
            raise ValueError('request byte budget exhausted')
        if tokens + len(payload) + limits['completion_tokens_per_request'] > limits['reported_total_token_stop_threshold_per_run']:
            raise ValueError('conservative token dispatch guard exhausted')
        if pacer is not None:
            waited = pacer.wait()
            paused += waited
            record('pacing', calls + 1, {'waited_seconds': waited,
                                        'minimum_gap_seconds': limits['request_gap_seconds']})
        remaining = limits['run_deadline_seconds'] - active_elapsed()
        if remaining <= 0: raise ValueError('run deadline exceeded')
        if cost_budget is not None:
            cost_budget.reserve(payload)
        before_send(calls + 1)
        calls += 1
        try:
            data = send(config, payload, min(remaining, limits['request_deadline_seconds']))
        finally:
            if pacer is not None: pacer.finished()
        # Persist full response locally (redacted by controller), even if parsing fails.
        record('response', calls, data)
        if cost_budget is not None:
            cost_budget.observe(data)
        choice, usage = parse_response(data)
        tokens += usage['total_tokens']
        if tokens > limits['reported_total_token_stop_threshold_per_run'] or usage['completion_tokens'] > limits['completion_tokens_per_request']:
            raise ValueError('reported token budget exceeded')
        if active_elapsed() >= limits['run_deadline_seconds']:
            raise ValueError('run deadline exceeded')
        message = choice['message']
        if choice['finish_reason'] == 'stop':
            if message.get('tool_calls') or not message.get('content'):
                raise ValueError('invalid final response')
            return {'complete_output': message['content'], 'model_requests': calls,
                    'reported_total_tokens': tokens, 'tool_calls': tool_count,
                    'latency_ms': round((clock() - started) * 1000), 'cost_usd': None,
                    'active_latency_ms': round(active_elapsed() * 1000),
                    'pacing_wait_ms': round(paused * 1000),
                    'evaluation_record': False}
        raw_calls = message.get('tool_calls')
        if not isinstance(raw_calls, list) or not raw_calls:
            raise ValueError('expected nonempty tool calls')
        if tool_count + len(raw_calls) > limits['tool_calls_per_run']:
            raise ValueError('tool budget exhausted')
        validated, batch_ids = [], set()
        # Some compatible gateways return multiple calls despite the parallel hint.
        # Validate the complete batch before dispatch; execute only sequentially.
        for call in raw_calls:
            try:
                call_id, name = call['id'], call['function']['name']
                if (call['type'] != 'function' or not isinstance(call_id, str) or
                        not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', call_id) or
                        call_id in ids or call_id in batch_ids or name not in ('read', 'shell')):
                    raise ValueError('invalid tool name or id')
                arguments = provider.strict_json(call['function']['arguments'])
                field = 'path' if name == 'read' else 'command'
                if not isinstance(arguments, dict) or set(arguments) != {field} or not isinstance(arguments[field], str):
                    raise ValueError('invalid tool arguments')
                if name == 'shell' and arguments['command'] != 'python3 verify.py':
                    raise ValueError('shell command not allowed')
                if name == 'read':
                    path = Path(arguments['path'])
                    if not path.is_absolute(): path = Path('/workspace') / path
                    if '..' in path.parts or not any(r in path.parents for r in (Path('/workspace'), Path('/skills'))):
                        raise ValueError('read path not allowed')
            except (KeyError, TypeError):
                raise ValueError('malformed tool call') from None
            batch_ids.add(call_id)
            validated.append((call_id, name, arguments))
        ids.update(batch_ids)
        messages.append({'role': 'assistant', 'content': message.get('content'), 'tool_calls': [
            {'id': call_id, 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(arguments)}}
            for call_id, name, arguments in validated]})
        if 'reasoning_content' in message:
            if not isinstance(message['reasoning_content'], str):
                raise ValueError('invalid reasoning replay')
            messages[-1]['reasoning_content'] = message['reasoning_content']
        for call_id, name, arguments in validated:
            if active_elapsed() >= limits['run_deadline_seconds']:
                raise ValueError('run deadline exceeded')
            tool_count += 1
            result = execute_tool(name, arguments)
            if isinstance(result, dict) and 'error' in result:
                raise ValueError('tool execution failed')
            record('tool', tool_count, {'id': call_id, 'name': name, 'arguments': arguments, 'result': result})
            messages.append({'role': 'tool', 'tool_call_id': call_id, 'content': json.dumps(result)})
    raise ValueError('model request budget exhausted without final output')


def execute(root, config, approved, authorization):
    previous = (approved.get('continuation') or {}).get('plan_sha256')
    current = make_plan(root, config, previous)
    if approved != current or authorization != digest(current):
        raise ValueError('reviewed plan/config/code/evidence mismatch')
    if config['T1_SUPPORTS_TOOL_CALLS'] != 'true':
        raise ValueError('tool support not declared')
    ledger = provider.RUNS / ('shakedown-' + digest(current))
    ledger.mkdir(mode=0o700)
    # Claim is durable before any invocation; replay is forbidden for this plan.
    provider.write_new(ledger / 'plan.json', current)
    continuation = current.get('continuation')
    if continuation is not None:
        provider.write_new(provider.RUNS / ('shakedown-' + previous) / 'continuation-claim.json',
                           {'next_plan_sha256': digest(current)})
    import os
    fd = os.open(ledger.parent, os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)
    manifest = isolation.load_manifest(root)
    completed = list(continuation['completed']) if continuation else []
    completed_targets = {r['target'] for r in completed}
    def cost_event(kind, number, value):
        provider.write_new(ledger / f'cost-{number:03d}-{kind}.json', value)
        if kind == 'observed':
            print('reference cost estimate CNY ' + value['estimated_cost_cny'] + '/3.000000', flush=True)
    cost_budget = CostBudget(cost_event, carried=continuation['cost_monitor'] if continuation else None)
    pacer = RequestPacer()
    # Include an initial cooldown when continuing a failed batch in a new process.
    if continuation: pacer.finished()
    try:
        for a in manifest['assignments']:
            if a['target'] in completed_targets:
                continue
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
                               persist, cost_budget=cost_budget, pacer=pacer)
            after = isolation.invoke(root, a, {'operation': 'inspect'})
            isolation.check_receipt(after, a)
            if after['receipt'] != observed['receipt']:
                raise ValueError('isolation changed during agent run')
            provider.write_new(run / 'isolation-after.json', after)
            persist('result', 1, result)
            completed.append({'target': a['target'], 'model_requests': result['model_requests'],
                              'reported_total_tokens': result['reported_total_tokens']})
            print('diagnostic agent completed: ' + a['target'], flush=True)
    except BaseException as exc:
        error = {'category': 'controller_or_transport_failure'}
        if isinstance(exc, provider.ProbeError) and re.fullmatch(r'provider HTTP status [0-9]{3}', str(exc)):
            error = {'category': 'provider_http', 'http_status': int(str(exc)[-3:])}
        elif isinstance(exc, TimeoutError):
            error = {'category': 'timeout'}
        provider.write_new(ledger / 'failure.json', {'outcome': 'failed_or_unknown_no_retry',
                           'completed': completed, 'evaluation_record': False,
                           'error': error, 'cost_monitor': cost_budget.snapshot()})
        raise ValueError('shakedown stopped; inspect attempt ledger; no retry') from None
    result = {'completed_runs': len(completed), 'runs': completed, 'evaluation_record': False,
              'cost_usd': None, 'immutable_version_verified': False, 'cost_monitor': cost_budget.snapshot()}
    provider.write_new(ledger / 'summary.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['plan', 'run'])
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--authorize-plan-sha256')
    parser.add_argument('--plan', type=Path, help='explicit new plan file; existing plans are never overwritten')
    parser.add_argument('--previous-plan-sha256', help='plan only: reviewed failed batch whose budget and completed targets carry forward')
    args = parser.parse_args()
    try:
        config = provider.load_config()
        plan_path = args.plan or args.root / 'shakedown-plan.controller.json'
        if args.command == 'plan':
            plan = make_plan(args.root, config, args.previous_plan_sha256)
            provider.write_new(plan_path, plan)
            print(json.dumps({'plan': str(plan_path), 'plan_sha256': digest(plan), 'limits': LIMITS,
                              'model': plan['provider']['model'], 'cost_usd': None, 'cost_policy': COST_POLICY}, indent=2))
        else:
            approved = provider.strict_json(plan_path.read_bytes())
            print(json.dumps(execute(args.root, config, approved, args.authorize_plan_sha256), indent=2))
        return 0
    except Exception:
        print('shakedown operation failed; no automatic retry; inspect local plan/ledger', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
