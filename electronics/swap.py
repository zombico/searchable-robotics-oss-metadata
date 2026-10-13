"""Electronics slot/swap checker (standard library only).

Classifies a candidate component for an assembly slot as drop_in, retune, rewire,
remount or incompatible, using electronics/interfaces.json rules and published specs
in electronics/components.json. Unknown or conflicting values never count as a pass:
a result that depends on them is reported as undetermined.

A binding may also declare supply rails; the static rail budget sums every load's
published worst-case current (actuators at stall) against the rail source's rating,
and a swap that overloads its rail is incompatible even if it fits its own slot.

Usage:
  python electronics/swap.py BINDING.json SLOT_ID              # rank every candidate for the slot
  python electronics/swap.py BINDING.json SLOT_ID COMPONENT_ID # one candidate, full report
  python electronics/swap.py BINDING.json --budget             # static worst-case rail budgets
"""
import json, math, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
SEVERITY = ['drop_in', 'retune', 'rewire', 'remount', 'incompatible']
RPM = 2 * math.pi / 60

def load():
    interfaces = json.loads((HERE / 'interfaces.json').read_text())['interfaces']
    catalog = json.loads((HERE / 'components.json').read_text())
    return interfaces, catalog

def spec(component, field):
    """Return (value, entries). value is None when unpublished or when sources disagree."""
    entries = [s for s in component['specs'] if s['field'] == field]
    values = {json.dumps(s['value'], sort_keys=True) for s in entries}
    return (entries[0]['value'] if len(values) == 1 else None), entries

def as_list(v): return v if isinstance(v, list) else [v]
def norm(v): return v.strip().lower() if isinstance(v, str) else v

def passes(rule, have, need):
    if rule == 'requirement_within_range':
        if isinstance(have, list) and have and all(isinstance(x, list) for x in have):  # disjoint operating modes
            return any(passes(rule, r, need) for r in have)
        if isinstance(have, list) and len(have) == 2 and all(isinstance(x, (int, float)) for x in have):
            return have[0] <= need <= have[1]
        return isinstance(have, (int, float)) and math.isclose(have, need, rel_tol=0.05)
    if rule == 'component_at_least': return max(as_list(have)) >= need
    if rule == 'component_at_most': return min(as_list(have)) <= need
    if rule == 'equals': return norm(have) == norm(need)
    if rule == 'contains':
        have = [norm(x) for x in as_list(have)]
        return all(norm(x) in have for x in as_list(need))
    raise ValueError('unknown rule ' + rule)

def differs(a, b, rel_tol=0.01):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)): return not math.isclose(a, b, rel_tol=rel_tol)
    return json.dumps(a, sort_keys=True) != json.dumps(b, sort_keys=True)

def solver_parameters(component):
    """Simulation parameters implied by published specs; assumptions are named, unknowns stay None."""
    get = lambda f: spec(component, f)[0]
    if component['interface'] == 'actuator.smart_servo':
        tau, rpm, counts = get('stall_torque_Nm'), get('no_load_speed_rpm'), get('position_resolution_counts')
        return {
            'forcerange_Nm': [-tau, tau] if tau is not None else None,
            'torque_speed_slope_Nm_s_rad': -tau / (rpm * RPM) if tau is not None and rpm else None,
            'position_quantization_rad': 2 * math.pi / counts if counts else None,
            'assumption': 'linear torque-speed line between published stall and no-load points at the stated voltage'}
    if component['interface'] == 'sensor.angle_absolute':
        bits = get('resolution_bits')
        return {'position_quantization_rad': 2 * math.pi / 2 ** bits if bits else None}
    if component['interface'] == 'sensor.encoder_incremental':
        ppr = get('ppr')
        return {'quadrature_counts_per_rev': 4 * max(as_list(ppr)) if ppr else None}
    return {}

CURRENT_FIELDS = ['stall_current_A', 'supply_current_max_A']
LIMIT_FIELDS = {'power.source': 'current_continuous_A', 'power.conversion': 'output_current_A'}

def rail_budget(binding, by_id, substitute=None):
    """Static worst case per rail. substitute=(slot_id, component) evaluates a proposed swap."""
    slots = {s['slot_id']: s for s in binding['slots']}
    reports = []
    for rail in binding.get('rails', []):
        source = by_id[rail['source_component']]
        limit, limit_entries = spec(source, LIMIT_FIELDS[source['interface']])
        peak = spec(source, 'current_peak_A')[0]
        loads, unknown, assumed = [], [], []
        for slot_id in rail['loads']:
            slot = slots[slot_id]
            part = substitute[1] if substitute and substitute[0] == slot_id else by_id[slot['bound_component']]
            current = next((v for v in (spec(part, f)[0] for f in CURRENT_FIELDS) if v is not None), None)
            declared = slot.get('declared_current_A')
            if current is None and declared and not (substitute and substitute[0] == slot_id):
                current = declared['value']; assumed.append(slot_id)
            if current is None: unknown.append(slot_id); continue
            loads.append({'slot': slot_id, 'component': part['id'], 'worst_case_A': current, 'assumed': slot_id in assumed})
        total = sum(l['worst_case_A'] for l in loads)
        if limit is None: status = 'undetermined'
        elif total > limit: status = 'over_budget'
        else: status = 'within_budget' if not unknown else 'undetermined'
        reports.append({'rail': rail['rail_id'], 'voltage_V': rail['voltage_V'], 'source': source['id'], 'members': rail['loads'],
                        'limit_continuous_A': limit, 'limit_peak_A': peak, 'worst_case_total_A': round(total, 6),
                        'headroom_A': None if limit is None else round(limit - total, 6), 'status': status,
                        'loads': loads, 'unknown_loads': unknown, 'assumed_loads': assumed,
                        'limit_from_search_snippet_only': any(e['verification'] == 'search_snippet' for e in limit_entries)})
    return reports

def check(slot, candidate, bound, interfaces, binding=None, by_id=None):
    iface = interfaces[slot['interface']]
    report = {'slot': slot['slot_id'], 'candidate': candidate['id'], 'name': candidate['name'],
              'findings': [], 'unknown': [], 'conflicting': [], 'search_snippet_only': []}
    if candidate['interface'] != slot['interface']:
        report.update(classification='incompatible', complete=True)
        report['findings'].append({'field': 'interface', 'result': 'incompatible',
                                   'detail': f"{candidate['interface']} does not implement {slot['interface']}"})
        return report
    worst = 'drop_in'
    for field, r in iface['fields'].items():
        have, entries = spec(candidate, field)
        if have is None:
            if entries: report['conflicting'].append(field)
            elif field in slot['requirements'] or (r.get('sim') and bound): report['unknown'].append(field)
            continue
        if any(e['verification'] == 'search_snippet' for e in entries): report['search_snippet_only'].append(field)
        outcome = None
        if field in slot['requirements'] and r['rule'] != 'sim_compare':
            need = slot['requirements'][field]
            if not passes(r['rule'], have, need):
                outcome = r['on_fail']
                report['findings'].append({'field': field, 'result': outcome, 'rule': r['rule'], 'required': need, 'candidate': have})
        if outcome is None and r.get('sim') and bound is not None and bound['id'] != candidate['id']:
            was = spec(bound, field)[0]
            if was is None: report['unknown'].append(field + ' (bound component)')
            elif differs(have, was):
                outcome = 'retune'
                report['findings'].append({'field': field, 'result': 'retune', 'bound': was, 'candidate': have})
        if outcome and SEVERITY.index(outcome) > SEVERITY.index(worst): worst = outcome
    if binding is not None:
        for rail in rail_budget(binding, by_id, (slot['slot_id'], candidate)):
            if slot['slot_id'] not in rail['members']: continue
            if rail['status'] == 'over_budget':
                worst = 'incompatible'
                report['findings'].append({'field': 'rail_budget', 'result': 'incompatible', 'rail': rail['rail'],
                                           'worst_case_total_A': rail['worst_case_total_A'], 'limit_continuous_A': rail['limit_continuous_A']})
            elif slot['slot_id'] in rail['unknown_loads']: report['unknown'].append('rail_budget (' + rail['rail'] + ')')
    complete = not report['unknown'] and not report['conflicting']
    # Missing data can hide a failure, so a clean or retune-only result is not trusted until complete.
    report['classification'] = worst if complete or SEVERITY.index(worst) >= SEVERITY.index('rewire') else 'undetermined'
    report['complete'] = complete
    report['solver_parameters'] = solver_parameters(candidate)
    return report

def main(argv):
    if len(argv) not in (3, 4): raise SystemExit(__doc__)
    interfaces, catalog = load()
    by_id = {c['id']: c for c in catalog['components']}
    binding = json.loads(pathlib.Path(argv[1]).read_text())
    if argv[2] == '--budget':
        print(json.dumps(rail_budget(binding, by_id), indent=2))
        return
    slot = next((s for s in binding['slots'] if s['slot_id'] == argv[2]), None)
    if slot is None: raise SystemExit('unknown slot ' + argv[2])
    bound = by_id.get(slot.get('bound_component'))
    if len(argv) == 4:
        if argv[3] not in by_id: raise SystemExit('unknown component ' + argv[3])
        print(json.dumps(check(slot, by_id[argv[3]], bound, interfaces, binding, by_id), indent=2))
        return
    rows = [check(slot, c, bound, interfaces, binding, by_id) for c in catalog['components'] if c['interface'] == slot['interface']]
    order = SEVERITY[:2] + ['undetermined'] + SEVERITY[2:]
    for r in sorted(rows, key=lambda r: order.index(r['classification'])):
        why = ', '.join(f"{f['field']}:{f['result']}" for f in r['findings']) or '-'
        gaps = ', '.join(r['unknown'] + r['conflicting'])
        print(f"{r['candidate']:<4} {r['classification']:<13} {r['name']:<34} {why}" + (f"  [missing: {gaps}]" if gaps else ''))

if __name__ == '__main__': main(sys.argv)
