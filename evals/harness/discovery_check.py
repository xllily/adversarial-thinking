#!/usr/bin/env python3
"""Frozen GLM automatic discovery diagnostic; no probe or automatic continuation."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from evals.harness import isolation as i, provider as p, shakedown as s

POLICY = dict(s.COST_POLICY, basis='BigModel original reference rates; no cache discount',
              input_cny_per_million='0.8', output_cny_per_million='2.8',
              source='https://bigmodel.cn/pricing')
LIMITS = dict(s.LIMITS, runs=2, completion_tokens_per_request=4096,
              completion_tokens_total=98304, request_bytes=32768,
              reported_total_token_stop_threshold_per_run=64000,
              run_deadline_seconds=360, request_deadline_seconds=60)
OPTIONS = {'max_tokens': 4096, 'thinking': {'type': 'enabled', 'clear_thinking': False},
           'reasoning_effort': 'low'}
LOW = 'Rewrite this sentence in plain English, preserving its meaning: "The meeting will commence at noon." Return only the rewritten sentence.'
PREVIOUS = 'skill-check-b8b43567f06578ee0cb70eae3250a13afe15b4db669f425bf0ac9533b797b271'


def prepare(root, config):
    if config['T1_ENDPOINT_URL'] != p.BIGMODEL_ENDPOINT or config['T1_MODEL_ID'] != 'glm-5.3-flash':
        raise ValueError('diagnostic requires exact GLM provider binding')
    base = s.make_plan(root, config)
    previous = p.strict_json((p.RUNS / PREVIOUS / 'summary.json').read_bytes())
    budget = previous['cost_monitor']
    s.CostBudget(lambda *x: None, carried=budget, policy=POLICY, carried_policy=s.COST_POLICY, completion_cap=4096)
    manifest = i.load_manifest(root)
    a = next(a for a in manifest['assignments'] if a['case']['id'] == 'migration-compat-01'
             and a['condition']['condition_id'] == 'c1-current-0.1.1')
    spec = i.pilot.load_json(i.pilot.SOURCE_ROOT / 'bundle-spec.json')
    for path in spec['paths']:
        if (root / 'targets' / a['target'] / 'skill' / path).read_bytes() != (p.ROOT / path).read_bytes():
            raise ValueError('mounted Skill differs from current Skill')
    observed = i.invoke(root, a, {'operation': 'inspect'})
    i.check_receipt(observed, a)
    for req in [dict(name='read', arguments={'path': '/controller/gold.controller.json'}),
                dict(name='shell', arguments={'command': 'cat /etc/passwd'})]:
        if 'error' not in i.invoke(root, a, req):
            raise ValueError('denial preflight failed')
    header = i.invoke(root, a, dict(name='read', arguments={'path': '/skills/SKILL.md'}))['content'].split('\n---\n', 1)[0]
    discovery = ('Workspace files: ' + ', '.join(observed['runtime']['workspace_files']) +
                 '\nAvailable skill: /skills/SKILL.md\n' + header)
    return {'schema': 1, 'purpose': 'automatic activation and low-risk skip diagnostic',
            'base': base, 'limits': LIMITS, 'payload_options': OPTIONS, 'cost_policy': POLICY,
            'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'carry': {'ledger': PREVIOUS, 'summary_sha256': s.digest(previous),
                      'cost_monitor': budget, 'historical_policy': s.COST_POLICY},
            'assignment': a, 'preflight': observed, 'discovery': discovery,
            'entries': [{'id': 'high-risk', 'prompt': a['case']['prompt'],
                         'required_reads': ['/skills/SKILL.md', '/skills/references/review.md']},
                        {'id': 'low-risk', 'prompt': LOW, 'required_reads': []}],
            'scope': 'Two fresh independent conversations with frontmatter discovery only; low-risk inline rewrite uses the same available mount. No causal uplift estimate or harder-case result.'}


def execute(root, config, plan, authorization):
    if authorization != s.digest(plan) or plan != prepare(root, config):
        raise ValueError('plan/provider/code/receipt/budget drift')
    if config['T1_SUPPORTS_TOOL_CALLS'] != 'true':
        raise ValueError('tools not declared')
    ledger = p.RUNS / ('discovery-' + authorization)
    ledger.mkdir(mode=0o700)
    p.write_new(ledger / 'plan.json', plan)
    p.write_new(p.RUNS / PREVIOUS / 'continuation-claim.json', {'next_plan_sha256': authorization,
                'purpose': 'new provider cohort; monetary carry only; not same-provider continuation'})
    def event(kind, n, value):
        p.write_new(ledger / f'cost-{n:03d}-{kind}.json', value)
    budget = s.CostBudget(event, carried=plan['carry']['cost_monitor'], completion_cap=4096,
                          policy=POLICY, carried_policy=plan['carry']['historical_policy'])
    pacer = s.RequestPacer(); pacer.finished()
    completed = []
    try:
        for e in plan['entries']:
            run = ledger / e['id']; run.mkdir(mode=0o700)
            def record(kind, n, value):
                safe = p.strict_json(p.encode(value).replace(config['T1_API_KEY'].encode(), b'[REDACTED]'))
                p.write_new(run / f'{kind}-{n}.json', safe)
                if kind == 'response':
                    print(e['id'] + ': response ' + str(n) + ' received', flush=True)
                elif kind == 'tool':
                    print(e['id'] + ': ' + value['name'] + ' ' + json.dumps(value['arguments']), flush=True)
            before = i.invoke(root, plan['assignment'], {'operation': 'inspect'})
            i.check_receipt(before, plan['assignment'])
            p.write_new(run / 'isolation-before.json', before)
            result = s.run_agent(config, e['prompt'], plan['discovery'],
                lambda name, args: i.invoke(root, plan['assignment'], dict(name=name, arguments=args)),
                lambda n: p.write_new(run / f'attempt-{n}.json', {'time': time.time(), 'outcome': 'unknown_before_send'}),
                record, cost_budget=budget, pacer=pacer, limits=LIMITS, payload_options=OPTIONS)
            after = i.invoke(root, plan['assignment'], {'operation': 'inspect'})
            i.check_receipt(after, plan['assignment'])
            if before['receipt'] != after['receipt']: raise ValueError('receipt drift')
            p.write_new(run / 'isolation-after.json', after)
            record('result', 1, result)
            completed.append(e['id'])
            print(e['id'] + ': completed', flush=True)
    except BaseException as exc:
        category = 'controller_or_runtime_failure'
        if isinstance(exc, TimeoutError): category = 'timeout'
        if isinstance(exc, p.ProbeError) and str(exc).startswith('provider HTTP status '): category = str(exc)
        p.write_new(ledger / 'failure.json', {'outcome': 'failed_or_unknown_no_retry', 'error': category,
                     'completed': completed, 'cost_monitor': budget.snapshot()})
        raise ValueError('diagnostic stopped; inspect journal; no retry') from None
    result = {'completed': completed, 'cost_monitor': budget.snapshot(), 'scope': plan['scope']}
    p.write_new(ledger / 'summary.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'run'])
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--authorize-plan-sha256')
    args = parser.parse_args()
    try:
        config = p.load_config()
        if args.command == 'prepare':
            plan = prepare(args.root, config); p.write_new(args.plan, plan)
            print(json.dumps({'plan_sha256': s.digest(plan), 'limits': LIMITS, 'carry': plan['carry']}))
        else:
            print(json.dumps(execute(args.root, config, p.strict_json(args.plan.read_bytes()), args.authorize_plan_sha256)))
        return 0
    except Exception:
        print('diagnostic operation stopped; inspect local journal; no retry', file=sys.stderr)
        return 2

if __name__ == '__main__': sys.exit(main())
