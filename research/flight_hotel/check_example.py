"""Finite candidate test, not a provider integration or a proof of prior systems.

One trusted logical service knows all flight changes. Sink checking is atomic
with capture in this model; independent real providers do not supply that fact
merely because a service can read them. The scope is sealed: no unlisted future
admissions, external routes, retries, disputes or additional compensations.
"""
import argparse
import hashlib
import itertools
import json
from pathlib import Path

EVENTS = ('prepare_hotel', 'cancel_flight', 'commit_hotel')
ORDERS = [x for x in itertools.permutations(EVENTS)
          if x.index('prepare_hotel') < x.index('commit_hotel')]
PROFILES = {'full_refund': 300, 'refund_less_40': 260, 'refund_refused': 0}
MODES = ('approval_snapshot', 'atomic_current_guard')
OWNER = {'prepare_hotel': 'hotel', 'commit_hotel': 'hotel', 'cancel_flight': 'flight'}


def initial():
    return {'flight_active': True, 'hotel_permit': False, 'hotel_paid': False,
            'violations': 0, 'effects': [('flight', 'flight_capture', 300)],
            'outcomes': [], 'remaining': list(EVENTS)}


def step(state, event, refund, mode):
    s = json.loads(json.dumps(state))
    assert event in s['remaining']
    if event == 'prepare_hotel':
        s['hotel_permit'] = s['flight_active']
        outcome = 'approved' if s['hotel_permit'] else 'rejected'
    elif event == 'cancel_flight':
        # Booking cancellation and its final refund outcome are atomic toy steps.
        # Refund refusal does NOT mean the flight remains usable.
        s['flight_active'] = False
        if refund:
            s['effects'].append(['flight', 'flight_refund', -refund])
        outcome = 'refund_refused' if refund == 0 else 'refunded'
    else:
        assert 'prepare_hotel' not in s['remaining']
        accepted = s['hotel_permit'] and (mode == 'approval_snapshot' or s['flight_active'])
        if accepted:
            s['hotel_paid'] = True
            s['effects'].append(['hotel', 'hotel_capture', 200])
            s['violations'] += int(not s['flight_active'])
        s['hotel_permit'] = False
        outcome = 'captured' if accepted else 'rejected'
    s['outcomes'].append([event, outcome])
    s['remaining'].remove(event)
    return s


def projection(state, provider):
    return [list(x) for x in state['effects'] if x[0] == provider]


def closed(state, provider):
    # Complete truthful reporting is stipulated: every processed step is recorded.
    # Outstanding provider work includes an approved-but-not-captured hotel.
    return not any(OWNER[e] == provider for e in state['remaining'])


def suffixes(state):
    for order in itertools.permutations(state['remaining']):
        if 'prepare_hotel' in order and 'commit_hotel' in order:
            if order.index('prepare_hotel') > order.index('commit_hotel'):
                continue
        yield order


def run():
    records = []
    suffix_checks = 0
    joint_closure_counterexamples = 0
    for mode, (profile, refund), order in itertools.product(MODES, PROFILES.items(), ORDERS):
        state = initial()
        prefixes = [state]
        for event in order:
            state = step(state, event, refund, mode)
            prefixes.append(state)
        for prefix in prefixes:
            for suffix in suffixes(prefix):
                future = prefix
                for event in suffix:
                    future = step(future, event, refund, mode)
                suffix_checks += 1
                for provider in ('flight', 'hotel'):
                    if closed(prefix, provider):
                        assert projection(future, provider) == projection(prefix, provider)
                if all(closed(prefix, p) for p in ('flight', 'hotel')):
                    if future['effects'] != prefix['effects']:
                        joint_closure_counterexamples += 1
        records.append({'mode': mode, 'profile': profile, 'order': order,
                        'commit_policy_violations': state['violations'],
                        'hotel_without_flight_at_end': state['hotel_paid'] and not state['flight_active'],
                        'both_payment_scopes_closed': all(closed(state,p) for p in ('flight','hotel')),
                        'net_spend': sum(x[2] for x in state['effects']),
                        'effects': state['effects'], 'outcomes': state['outcomes']})
    assert len(records) == 18 and joint_closure_counterexamples == 0
    # Specific witnesses/controls, independent of aggregate totals.
    for profile, refund in PROFILES.items():
        for mode in MODES:
            stale = next(r for r in records if r['mode']==mode and r['profile']==profile
                         and tuple(r['order'])==EVENTS)
            assert stale['commit_policy_violations'] == int(mode == 'approval_snapshot')
            assert stale['net_spend'] == 300-refund+(200 if mode=='approval_snapshot' else 0)
            early = next(r for r in records if r['mode']==mode and r['profile']==profile
                         and tuple(r['order'])==('prepare_hotel','commit_hotel','cancel_flight'))
            assert early['commit_policy_violations'] == 0
            assert early['hotel_without_flight_at_end']  # Distinct final business property.
    prefix = step(step(initial(),'prepare_hotel',260,'approval_snapshot'),
                  'cancel_flight',260,'approval_snapshot')
    assert closed(prefix,'flight') and not closed(prefix,'hotel')
    later = step(prefix,'commit_hotel',260,'approval_snapshot')
    assert projection(prefix,'hotel') != projection(later,'hotel')
    summary = {'trace_records':len(records),'distinct_event_orders':len(ORDERS),
               'profiles':len(PROFILES),'prefix_records_checked':len(records)*4,
               'suffix_replays_checked':suffix_checks,
               'joint_exact_closure_counterexamples':joint_closure_counterexamples,
               'early_hotel_closure_rejected':True,'real_provider_calls':0,
               'machine_checked_theorems_added':0,
               'comparison':'Local encodings of two rules, not implementations or reproductions of cited systems.',
               'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               'by_mode':{m:{'traces':sum(r['mode']==m for r in records),
                            'commit_policy_violating_traces':sum(r['commit_policy_violations']>0 for r in records if r['mode']==m),
                            'final_business_property_failures':sum(r['hotel_without_flight_at_end'] for r in records if r['mode']==m)} for m in MODES}}
    return {'summary':summary,'records':records}


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=run()
    with args.output.open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(result['summary'],indent=2))
