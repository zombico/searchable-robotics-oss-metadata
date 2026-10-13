"""Composer v0: compose a gripper drive for the pick task from catalog parts, screen it, simulate it, report.

    python compose/pick_gripper.py                  # full run: screen, simulate 300 paired seeds, write reports
    python compose/pick_gripper.py --screen-only    # requirements and static screening only (standard library)

Design space: smart servo (electronics catalog) x module-1 pinion between twin racks (catalog M05) driving
the parallel jaws (M13, geometry from example.json), on a 12 V rail (E72). The example gripper's 5 N
linear drive is simulated as a reference. Every number below is either derived from task.json, read from
a catalog record (with its verification level), or a named design assumption in ASSUMPTIONS.

Servo jaws are modeled as current-limited: velocity command up to the no-load speed, force = kv * (v_cmd - v)
with kv = stall force / no-load speed (the torque-speed line), capped at the configured current limit (the
required grip force). The motor's reflected rotor inertia, J_rotor * (gear ratio / pinion radius)^2, is added as
joint armature; it dominates the jaw's effective mass and keeps the stiff line stable. ROBOTIS does not publish
J_rotor, so every servo design is simulated at two assumed values a decade apart and the report separates
conclusions that hold at both from those that depend on the unknown.

Claims are scoped: a "feasible" design is feasible in simulation under these assumptions, not a built robot.
"""
import argparse, json, math, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path[:0] = [str(ROOT / 'electronics'), str(ROOT / 'tasks' / 'pick'), str(ROOT)]
import swap

TASK = json.loads((ROOT / 'tasks/pick/task.json').read_text())
GRIPPER = json.loads((ROOT / 'example.json').read_text())
G = 9.81
ASSUMPTIONS = {
    'safety_factor': 1.5,                 # on grip friction capacity
    'lift_accel_m_s2': 2.0,               # design vertical acceleration while lifting
    'rack_pinion_efficiency': 0.9,        # spur rack-and-pinion mesh, not measured
    'pinion_module_mm': 1.0,              # catalog M05 proposed module
    'pinion_teeth_options': [12, 20, 30, 40],
    'min_teeth_without_profile_shift': 17,  # 20 deg pressure angle undercut limit
    'max_full_stroke_close_s': 0.6,       # proposed cycle-time requirement
    'rail_voltage_V': 12.0,
    'supply': 'E72',
    'servo_candidates': ['E01', 'E03', 'E04'],
    'torque_current_model': 'current proportional to torque between zero and the published stall point (assumption)',
    'rotor_inertia_kg_m2_sweep': [1e-8, 1e-7],  # unsourced: two assumed values a decade apart; not published for XM430
}

def requirements():
    r = TASK['object_randomization']; m, mu = r['mass_kg'][1], r['friction'][0]
    sf, a = ASSUMPTIONS['safety_factor'], ASSUMPTIONS['lift_accel_m_s2']
    pad = sf * m * (G + a) / (2 * mu)          # two pads, Coulomb friction on each
    travel = GRIPPER['jaw_travel_mm'] / 1000
    need_open = r['width_m'][1] + 0.005        # widest box plus 2.5 mm clearance per side
    carriage = TASK['carriage']['z_mass_kg'] + GRIPPER['base_mass_kg'] + 2 * GRIPPER['jaw_mass_kg']
    return {
        'pad_normal_force_N': {'value': pad, 'formula': 'SF * m_max * (g + a_lift) / (2 * mu_min)',
                               'inputs': {'SF': sf, 'm_max_kg': m, 'g': G, 'a_lift_m_s2': a, 'mu_min': mu}},
        'jaw_drive_force_N': {'value': 2 * pad, 'formula': 'twin racks: total rack force = 2 * pad normal force'},
        'jaw_opening_m': {'value': need_open, 'available': GRIPPER['closed_gap_mm'] / 1000 + 2 * travel, 'formula': 'w_max + 2 * 2.5 mm'},
        'per_jaw_travel_m': {'value': travel, 'formula': 'example.json jaw_travel_mm'},
        'max_close_time_s': {'value': ASSUMPTIONS['max_full_stroke_close_s'], 'formula': 'proposed requirement'},
        'z_payload_N': {'value_without_servo': (carriage + m) * (G + a), 'limit': TASK['carriage']['z_drive']['effort_limit_N'],
                        'formula': '(carriage + gripper + servo + m_max) * (g + a_lift)'},
    }

def candidates():
    out = [{'name': 'baseline_example_drive', 'servo': None, 'teeth': None}]
    for sid in ASSUMPTIONS['servo_candidates']:
        for z in ASSUMPTIONS['pinion_teeth_options']: out.append({'name': f'{sid}_z{z}', 'servo': sid, 'teeth': z})
    return out

def check(name, value, required, ok, detail='', verification=None):
    result = 'unknown' if value is None or ok is None else ('pass' if ok else 'fail')
    return {'check': name, 'value': value, 'required': required, 'result': result, 'detail': detail, 'verification': verification}

def screen(c, req, by_id):
    """Static screening against requirements. Unknown inputs give 'unknown', never 'pass'."""
    V = ASSUMPTIONS['rail_voltage_V']; eta = ASSUMPTIONS['rack_pinion_efficiency']; checks, warnings = [], []
    if c['servo'] is None:
        F, v = GRIPPER['effort_limit_N'], GRIPPER['velocity_limit_m_s']
        drive = {'effort_limit_N': F, 'no_load_speed_m_s': v, 'servo_mass_kg': 0.0}
        checks.append(check('jaw_drive_force_N', F, req['jaw_drive_force_N']['value'], F >= req['jaw_drive_force_N']['value'], 'example.json ideal drive (proposed values)'))
        checks.append(check('full_stroke_close_s', req['per_jaw_travel_m']['value'] / v, req['max_close_time_s']['value'], req['per_jaw_travel_m']['value'] / v <= req['max_close_time_s']['value']))
        return finish(c, checks, warnings, drive, None)
    servo = by_id[c['servo']]; r = ASSUMPTIONS['pinion_module_mm'] * c['teeth'] / 2 / 1000
    ver = lambda f: sorted({e['verification'] for e in swap.spec(servo, f, V)[1]}) or None
    supply = swap.spec(servo, 'supply_voltage_V')[0]
    checks.append(check('supply_voltage_V', supply, V, None if supply is None else swap.passes('requirement_within_range', supply, V), f'rail {V:g} V', ver('supply_voltage_V')))
    tau, rpm, amps, mass = (swap.spec(servo, f, V)[0] for f in ('stall_torque_Nm', 'no_load_speed_rpm', 'stall_current_A', 'mass_kg'))
    F = None if tau is None else eta * tau / r
    v = None if rpm is None else rpm * 2 * math.pi / 60 * r
    checks.append(check('jaw_drive_force_N', F, req['jaw_drive_force_N']['value'], None if F is None else F >= req['jaw_drive_force_N']['value'],
                        f'eta * stall torque at {V:g} V / pinion radius {r * 1000:g} mm', ver('stall_torque_Nm')))
    t_close = None if v is None else req['per_jaw_travel_m']['value'] / v
    checks.append(check('full_stroke_close_s', t_close, req['max_close_time_s']['value'], None if t_close is None else t_close <= req['max_close_time_s']['value'],
                        'per-jaw travel / (no-load speed * pinion radius); no-load is an upper bound', ver('no_load_speed_rpm')))
    payload = None if mass is None else req['z_payload_N']['value_without_servo'] + mass * (G + ASSUMPTIONS['lift_accel_m_s2'])
    checks.append(check('z_payload_N', payload, req['z_payload_N']['limit'], None if payload is None else payload <= req['z_payload_N']['limit'],
                        'servo rides on the z carriage', ver('mass_kg')))
    binding = {'slots': [{'slot_id': 'jaw_servo', 'interface': 'actuator.smart_servo', 'bound_component': servo['id'], 'requirements': {'supply_voltage_V': V}}],
               'rails': [{'rail_id': f'{V:g}V', 'voltage_V': V, 'source_component': ASSUMPTIONS['supply'], 'loads': ['jaw_servo']}]}
    rail = swap.rail_budget(binding, by_id)[0]
    checks.append(check('rail_worst_case_A', rail['worst_case_total_A'] if not rail['unknown_loads'] else None, rail['limit_continuous_A'],
                        {'within_budget': True, 'over_budget': False}.get(rail['status']), 'gripper servo at stall on the supply; carriage drives are not catalog parts and are not counted'))
    if c['teeth'] < ASSUMPTIONS['min_teeth_without_profile_shift']: warnings.append(f"{c['teeth']}-tooth pinion is below the {ASSUMPTIONS['min_teeth_without_profile_shift']}-tooth undercut limit; needs profile shift")
    if 'search_snippet' in sum((x['verification'] or [] for x in checks), []): warnings.append('relies on search-snippet values; verify against a datasheet')
    drive = None if F is None or v is None else {'effort_limit_N': F, 'no_load_speed_m_s': v, 'servo_mass_kg': mass or 0.0, 'pinion_radius_m': r,
                                                 'stall_torque_Nm': tau, 'stall_current_A': amps}
    if drive and amps is not None:  # torque needed to hold the required grip, and the current it implies (linear model, see ASSUMPTIONS)
        hold_tau = req['jaw_drive_force_N']['value'] * r / eta
        drive.update(holding_torque_Nm=hold_tau, holding_current_A_est=amps * hold_tau / tau, holding_power_W_est=V * amps * hold_tau / tau)
    return finish(c, checks, warnings, drive, servo)

def finish(c, checks, warnings, drive, servo):
    req = requirements()['jaw_opening_m']
    checks.insert(0, check('jaw_opening_m', req['available'], req['value'], req['available'] >= req['value'], 'closed gap + 2 * per-jaw travel (example.json)'))
    results = {x['result'] for x in checks}
    status = 'rejected' if 'fail' in results else 'undetermined' if 'unknown' in results else 'feasible'
    if c['servo'] is None: status = 'reference_' + status
    return dict(c, status=status, checks=checks, warnings=warnings, drive=drive, servo_name=servo['name'] if servo else 'example.json linear drive (5 N, 0.1 m/s)')

def bill_of_materials(s, by_id):
    if s['servo'] is None: return None
    servo = by_id[s['servo']]; protocol = swap.spec(servo, 'protocol')[0] or 'unknown'
    adapter = 'E20 ROBOTIS U2D2 (USB to TTL/RS-485)' if protocol.startswith('dynamixel') else 'not in catalog: a host adapter for this protocol is still unresearched'
    return [{'item': 'jaw servo', 'part': f"{servo['id']} {servo['name']}", 'qty': 1},
            {'item': 'pinion', 'part': f"module {ASSUMPTIONS['pinion_module_mm']:g}, {s['teeth']} teeth, 20 deg (proposed, catalog M05)", 'qty': 1},
            {'item': 'racks', 'part': 'module 1 racks on each jaw carriage (proposed, catalog M05)', 'qty': 2},
            {'item': 'jaws and base', 'part': 'parallel jaws per example.json (proposed, catalog M13)', 'qty': 1},
            {'item': 'jaw guides', 'part': 'linear guide, e.g. MGN-family (catalog C06; size not selected)', 'qty': 2},
            {'item': 'bus adapter', 'part': adapter, 'qty': 1},
            {'item': 'supply', 'part': f"{ASSUMPTIONS['supply']} {by_id[ASSUMPTIONS['supply']]['name']}", 'qty': 1}]

def screen_all():
    _, catalog = swap.load(); by_id = {c['id']: c for c in catalog['components']}; req = requirements()
    screened = [screen(c, req, by_id) for c in candidates()]
    for s in screened: s['bill_of_materials'] = bill_of_materials(s, by_id)
    return req, screened

def simulate(screened, seeds, out):
    """Paired evaluation: every simulated variant sees the same seeds (same boxes, same sensor noise)."""
    req_cmd = requirements()['jaw_drive_force_N']['value']; out.mkdir(parents=True, exist_ok=True); results = {}
    _, catalog = swap.load(); by_id = {c['id']: c for c in catalog['components']}
    for s in screened:
        if s['status'] not in ('feasible', 'reference_rejected', 'reference_feasible') or s['drive'] is None: continue
        d = s['drive']
        if s['servo'] is None:  # reference: the example force drive, commanded at its full 5 N
            results[s['name']] = evaluate(s, s['name'], {'jaw_drive': d}, d['effort_limit_N'], d['effort_limit_N'], None, seeds, out)
            continue
        # Servo: velocity command at no-load speed, grip set by the current limit, unknown rotor inertia swept.
        grip = min(d['effort_limit_N'], req_cmd); ratio = swap.spec(by_id[s['servo']], 'gear_ratio')[0]
        for J in ASSUMPTIONS['rotor_inertia_kg_m2_sweep']:
            servo = {'stall_force_N': d['effort_limit_N'], 'no_load_speed_m_s': d['no_load_speed_m_s'], 'force_limit_N': grip,
                     'armature_kg': J * (ratio / d['pinion_radius_m']) ** 2}
            results[f"{s['name']}_J{J:.0e}"] = evaluate(s, f"{s['name']}_J{J:.0e}", {'jaw_servo': servo}, grip, d['no_load_speed_m_s'], J, seeds, out)
    return results

def evaluate(s, name, overrides, grip, command, J, seeds, out):
    import numpy as np, scene
    from env import PickEnv
    from generate import run
    from scripted import ScriptedPicker
    d = s['drive']; path = scene.build(dict(overrides, model=name, z_extra_mass_kg=d['servo_mass_kg']), out / f"{name}.mjcf.xml")
    env = PickEnv(path); rows = []
    for seed in seeds:
        ep = run(env, seed, policy=ScriptedPicker(jaw_command=command, extra_mass_kg=d['servo_mass_kg']))
        rows.append({'seed': seed, 'outcome': ep['summary']['outcome'], 'duration_s': ep['summary']['duration_s'], 'split': ep['split'], 'params': env.params,
                     'close_phase_s': sum(t['phase'] == 'close' for t in ep['transitions']) * env.dt, 'peak_grip_N': ep['summary']['peak_grip_normal_force_N']})
    ok = [r for r in rows if r['outcome'] == 'success']; outcomes = sorted({r['outcome'] for r in rows})
    split_rate = lambda sp: round(sum(r['outcome'] == 'success' for r in rows if r['split'] == sp) / max(1, sum(r['split'] == sp for r in rows)), 4)
    return {'design': s['name'], 'rotor_inertia_kg_m2': J, 'armature_kg': overrides.get('jaw_servo', {}).get('armature_kg'), 'commanded_grip_N': grip,
            'jaw_actuator': 'velocity, current-limited' if s['servo'] else 'force-speed drive', 'scene': str(path.relative_to(ROOT)), 'episodes': len(rows),
            'outcomes': {o: sum(r['outcome'] == o for r in rows) for o in outcomes}, 'success_rate': len(ok) / len(rows),
            'success_rate_by_split': {sp: split_rate(sp) for sp in ('train', 'validation', 'test')},
            'mean_success_duration_s': float(np.mean([r['duration_s'] for r in ok])) if ok else None,
            'mean_close_phase_s': float(np.mean([r['close_phase_s'] for r in rows])),
            'peak_grip_N_mean': float(np.mean([r['peak_grip_N'] for r in rows])), 'peak_grip_N_max': float(max(r['peak_grip_N'] for r in rows)), 'rows': rows}

def requirement_model_check(rows, drive_force):
    """Predict slip per episode from the friction model with no safety factor, compare with the simulated outcome."""
    a = ASSUMPTIONS['lift_accel_m_s2']; tally = {'predicted_slip_and_slipped': 0, 'predicted_slip_but_held': 0, 'predicted_hold_but_slipped': 0, 'predicted_hold_and_held': 0}
    for r in rows:
        p = r['params']; capacity = p['friction'] * drive_force          # 2 pads x mu x (F / 2)
        slip_pred = p['mass_kg'] * (G + a) > capacity; slipped = r['outcome'] == 'slip'
        tally[('predicted_slip_and_slipped' if slipped else 'predicted_slip_but_held') if slip_pred else ('predicted_hold_but_slipped' if slipped else 'predicted_hold_and_held')] += 1
    n = sum(tally.values()); return dict(tally, agreement=(tally['predicted_slip_and_slipped'] + tally['predicted_hold_and_held']) / n, episodes=n,
                                          model='slip if m*(g + a_lift) > mu * F_drive (two pads, each F_drive/2), a_lift = %g m/s2, no safety factor' % a)

def robustness(screened, sims):
    """Per feasible design: worst case over the unknown-inertia sweep, and what depends on the unknown."""
    out = {}
    for s in screened:
        runs = [v for v in sims.values() if v['design'] == s['name'] and v['rotor_inertia_kg_m2'] is not None]
        if s['status'] != 'feasible' or not runs: continue
        rates = [r['success_rate'] for r in runs]; peaks = [r['peak_grip_N_max'] for r in runs]; times = [r['mean_success_duration_s'] or 1e9 for r in runs]
        out[s['name']] = {'worst_success_rate': min(rates), 'best_success_rate': max(rates), 'worst_mean_success_duration_s': max(times),
                          'peak_grip_N_range': [min(peaks), max(peaks)], 'grip_limit_N': runs[0]['commanded_grip_N'],
                          'success_robust_to_rotor_inertia': max(rates) - min(rates) <= 0.01,
                          'impact_force_depends_on_rotor_inertia': max(peaks) > 1.2 * min(peaks)}
    return out

def rank(robust):
    """Feasible designs by worst-case success, then worst-case successful episode time."""
    return sorted(robust, key=lambda n: (-robust[n]['worst_success_rate'], robust[n]['worst_mean_success_duration_s']))

def markdown(report):
    L = ['# Composed pick gripper: report', '', report['scope'], '', '## Requirements (derived from tasks/pick/task.json)', '']
    for k, v in report['requirements'].items():
        val = v.get('value', v.get('value_without_servo'))
        L.append(f"- **{k}**: {val:.4g} — `{v['formula']}`" + (f" (limit {v['limit']:g})" if 'limit' in v else '') + (f" (available {v['available']:.4g})" if 'available' in v else ''))
    L += ['', f"Assumptions: {', '.join(f'{k}={v}' for k, v in report['assumptions'].items() if not isinstance(v, list))}.", '', '## Screening', '',
          '| Design | Servo | Status | Failed or unknown checks | Warnings |', '|---|---|---|---|---|']
    for s in report['screened']:
        bad = '; '.join(f"{c['check']} {c['result']}" + (f" ({c['value']:.3g} vs {c['required']:.3g})" if isinstance(c['value'], (int, float)) and isinstance(c['required'], (int, float)) else '') for c in s['checks'] if c['result'] != 'pass') or '-'
        L.append(f"| {s['name']} | {s['servo_name']} | {s['status']} | {bad} | {'; '.join(s['warnings']) or '-'} |")
    if report.get('simulation'):
        L += ['', f"## Simulation ({report['simulation_seeds']} paired seeds)", '', '| Variant | Rotor inertia (kg m²) | Grip limit (N) | Success | Outcomes | Mean close phase (s) | Mean successful episode (s) | Peak pad force mean / max (N) |', '|---|---|---|---|---|---|---|---|']
        for name, r in report['simulation'].items():
            J = '-' if r['rotor_inertia_kg_m2'] is None else f"{r['rotor_inertia_kg_m2']:.0e} (armature {r['armature_kg']:.3g} kg)"
            dur = '-' if r['mean_success_duration_s'] is None else f"{r['mean_success_duration_s']:.2f}"
            L.append(f"| {name} | {J} | {r['commanded_grip_N']:.1f} | {r['success_rate']:.1%} | {r['outcomes']} | {r['mean_close_phase_s']:.2f} | {dur} | {r['peak_grip_N_mean']:.1f} / {r['peak_grip_N_max']:.1f} |")
        L += ['', '## What holds regardless of the unknown rotor inertia', '', '| Design | Worst-case success | Success robust? | Peak pad force range (N) vs grip limit | Impact force depends on rotor inertia? |', '|---|---|---|---|---|']
        for n, r in report['robustness'].items():
            L.append(f"| {n} | {r['worst_success_rate']:.1%} | {'yes' if r['success_robust_to_rotor_inertia'] else 'no'} | {r['peak_grip_N_range'][0]:.0f}–{r['peak_grip_N_range'][1]:.0f} vs {r['grip_limit_N']:.1f} | {'yes' if r['impact_force_depends_on_rotor_inertia'] else 'no'} |")
        m = report['requirement_model_check']
        L += ['', '## Does the requirement model predict the simulator?', '', f"On the reference drive: {m['model']}.", '',
              f"Agreement {m['agreement']:.1%} over {m['episodes']} episodes: {m['predicted_slip_and_slipped']} predicted slips slipped, {m['predicted_hold_and_held']} predicted holds held, "
              f"{m['predicted_slip_but_held']} predicted slips held, {m['predicted_hold_but_slipped']} predicted holds slipped.", '',
              '## Ranking', '', 'Feasible designs ranked by worst-case simulated success over the inertia sweep, then worst-case successful episode time:', '']
        L += [f"{i + 1}. {n}" for i, n in enumerate(report['ranking'])]
        if report['ranking']:
            best = next(s for s in report['screened'] if s['name'] == report['ranking'][0]); d = best['drive']
            L += ['', '## Holding the grip: torque, current and power (estimates)', '', '| Design | Holding torque (N·m) | Current (A) | Electrical power at the rail (W) |', '|---|---|---|---|']
            L += [f"| {n} | {x['drive']['holding_torque_Nm']:.2f} | {x['drive']['holding_current_A_est']:.2f} | {x['drive']['holding_power_W_est']:.1f} |"
                  for n in report['ranking'] for x in report['screened'] if x['name'] == n]
            L += ['', f"From {ASSUMPTIONS['torque_current_model']}; the stall point is published (verification in the screening checks), the linear line between is not."]
            L += ['', f"## Bill of materials: {best['name']}", '', '| Item | Part | Qty |', '|---|---|---|'] + [f"| {b['item']} | {b['part']} | {b['qty']} |" for b in best['bill_of_materials']]
    L += ['', '## Not claimed', ''] + [f'- {x}' for x in report['not_claimed']]
    return '\n'.join(L) + '\n'

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--screen-only', action='store_true'); ap.add_argument('--seeds', type=int, default=300)
    ap.add_argument('--out', default=str(HERE / 'reports')); args = ap.parse_args()
    req, screened = screen_all()
    report = {'composer': 'pick_gripper_v0', 'scope': 'Feasible means feasible in MuJoCo under the stated assumptions and catalog values. Release level: synthetic_only.',
              'assumptions': ASSUMPTIONS, 'requirements': req, 'screened': screened,
              'not_claimed': ['a built or tested gripper', 'continuous torque or thermal capacity (unpublished for these servos)',
                              'backlash, rack friction or compliance (not modeled)',
                              'packaging: whether the pinion, racks and servo fit the 100 x 50 mm gripper base (not checked; a 40-tooth module-1 pinion is 40 mm across)',
                              'gentle handling: impact pad forces exceed the grip limit and depend on the unpublished rotor inertia', 'electrical behavior of the carriage drives (not catalog parts)',
                              'accuracy of MuJoCo contact for these materials']}
    if args.screen_only:  # prints only; the committed report always comes from a full run
        for s in screened: print(f"{s['name']:<26} {s['status']:<20} " + '; '.join(f"{c['check']}={c['result']}" for c in s['checks'] if c['result'] != 'pass'))
        return
    out = pathlib.Path(args.out); out.mkdir(parents=True, exist_ok=True)
    if not args.screen_only:
        sims = simulate(screened, list(range(args.seeds)), ROOT / 'compose' / 'build')
        report.update(simulation_seeds=args.seeds, simulation={k: {x: y for x, y in v.items() if x != 'rows'} for k, v in sims.items()},
                      requirement_model_check=requirement_model_check(sims['baseline_example_drive']['rows'], GRIPPER['effort_limit_N']))
        report['robustness'] = robustness(screened, sims); report['ranking'] = rank(report['robustness'])
    (out / 'pick_gripper_v0.json').write_text(json.dumps(report, indent=2) + '\n')
    (out / 'pick_gripper_v0.md').write_text(markdown(report))
    for s in screened: print(f"{s['name']:<26} {s['status']}")
    if not args.screen_only: print('ranking:', report['ranking']); print('model agreement:', round(report['requirement_model_check']['agreement'], 4))

if __name__ == '__main__': main()
