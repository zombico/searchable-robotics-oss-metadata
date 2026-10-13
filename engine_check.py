"""Engine evidence for the example gripper (requires: pip install -r requirements-sim.txt).

Writes a forward-simulated episode plus engine, replay and convergence reports and an
engine_checked release declaration that hashes them. Exits non-zero if any declared
threshold fails. Evidence is scoped to this demonstrator in MuJoCo; it is not physical
validation and makes no accuracy claim.

  python engine_check.py                        # regenerate evidence/example_gripper/
  python engine_check.py --out DIR              # write elsewhere (CI uses a temp dir)
  python engine_check.py --replay EPISODE.json  # replay a recorded episode on this machine
"""
import hashlib, json, pathlib, platform, sys
import mujoco
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent
MODEL = ROOT / 'example.mjcf.xml'
DT, DECIMATION, EFFORT, TRAVEL, NO_LOAD_SPEED = 0.001, 20, 5.0, 0.025, 0.1
SCHEDULE = [-EFFORT] * 50 + [EFFORT] * 50  # 2 s at 50 Hz: close, then open
THRESHOLDS = {
    'stop_overshoot_m': 0.001,         # beyond either joint stop
    'jaw_coupling_m': 0.0002,          # |left - right| for the equality-coupled jaws
    'peak_speed_m_s': NO_LOAD_SPEED,   # declared no-load speed of the drive
    'replay_same_process_m': 0.0,      # forward action replay, same build and process
    'replay_cross_machine_m': 1e-6,    # committed episode replayed on another machine
    'continuation_m': 0.0,             # restore full integration state mid-episode and continue
    'timestep_halving_m': 5e-5,        # dt vs dt/2 at control instants
}

def sha256(path): return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()

def load(dt=DT):
    m = mujoco.MjModel.from_xml_path(str(MODEL)); m.opt.timestep = dt
    d = mujoco.MjData(m); mujoco.mj_resetDataKeyframe(m, d, 0)
    return m, d

def rollout(actions, dt=DT, checkpoint_at=None):
    """Zero-order-hold actions at 50 Hz; returns qpos at every control instant and per-step extremes."""
    m, d = load(dt); sub = int(round(DT * DECIMATION / dt))
    states, stats, checkpoint = [d.qpos.copy()], {'lo': d.qpos.min(), 'hi': d.qpos.max(), 'couple': 0.0, 'speed': 0.0, 'finite': True}, None
    for k, u in enumerate(actions):
        if k == checkpoint_at:
            spec = mujoco.mjtState.mjSTATE_INTEGRATION
            checkpoint = np.empty(mujoco.mj_stateSize(m, spec)); mujoco.mj_getState(m, d, checkpoint, spec)
        d.ctrl[0] = u
        for _ in range(sub):
            mujoco.mj_step(m, d)
            stats['finite'] &= bool(np.isfinite(d.qpos).all() and np.isfinite(d.qvel).all())
            stats['lo'] = min(stats['lo'], d.qpos.min()); stats['hi'] = max(stats['hi'], d.qpos.max())
            stats['couple'] = max(stats['couple'], abs(d.qpos[0] - d.qpos[1])); stats['speed'] = max(stats['speed'], abs(d.qvel).max())
        states.append(d.qpos.copy())
    return np.array(states), stats, checkpoint

def continue_from(checkpoint, actions):
    m, d = load(); mujoco.mj_setState(m, d, checkpoint, mujoco.mjtState.mjSTATE_INTEGRATION)
    states = [d.qpos.copy()]
    for u in actions:
        d.ctrl[0] = u
        for _ in range(DECIMATION): mujoco.mj_step(m, d)
        states.append(d.qpos.copy())
    return np.array(states)

def episode(states, asset):
    step = DT * DECIMATION
    def obs(k): return {'qpos': {'value': [float(x) for x in states[k]], 'unit': 'm', 'capture_t_s': round(k * step, 9), 'release_t_s': round(k * step, 9)}}
    transitions = [{'t_s': round(k * step, 9), 'next_t_s': round((k + 1) * step, 9), 'action': [u],
                    'observation': obs(k), 'next_observation': obs(k + 1), 'terminated': False,
                    'truncated': k == len(SCHEDULE) - 1, 'outcome': 'timeout' if k == len(SCHEDULE) - 1 else 'ongoing'}
                   for k, u in enumerate(SCHEDULE)]
    return {'schema_version': '0.2.0', 'origin': 'forward_simulation', 'episode_id': 'example-gripper-sweep-001', 'split': 'train',
            'leakage_group': 'example-gripper-scripted-sweep', 'generator': {'type': 'scripted', 'revision': 'engine_check.py full-effort close/open'},
            'manifest': {'clock': {'physics_dt_s': DT, 'control_decimation': DECIMATION, 'control_hz': 1 / (DT * DECIMATION)},
                         'asset_sha256': asset, 'seed': 0,
                         'engine': {'name': 'mujoco', 'version': mujoco.__version__, 'runtime_scope': 'CPU mj_step, default solver; see replay_report.json for tolerances'},
                         'action_contract': {'mode': 'joint_force', 'unit': 'N', 'frame': 'joint', 'dimension': 1, 'hold': 'zero_order',
                                             'controller_id': 'linear_force_speed_drive_v1', 'lower': -EFFORT, 'upper': EFFORT},
                         'observation_contract': {'policy_channels': ['qpos'], 'privileged_channels': ['qvel', 'actuator_force']}},
            'transitions': transitions}

def replay(ep):
    """Forward action replay of a recorded episode; returns max |qpos - recorded| over control instants."""
    if ep['manifest']['asset_sha256'] != sha256(MODEL): raise SystemExit('episode was recorded with a different model asset')
    states, _, _ = rollout([t['action'][0] for t in ep['transitions']])
    recorded = [ep['transitions'][0]['observation']['qpos']['value']] + [t['next_observation']['qpos']['value'] for t in ep['transitions']]
    return float(np.abs(states - np.array(recorded)).max())

def build(out):
    out.mkdir(parents=True, exist_ok=True); asset = sha256(MODEL)
    states, stats, checkpoint = rollout(SCHEDULE, checkpoint_at=50)
    env = {'mujoco': mujoco.__version__, 'numpy': np.__version__, 'python': platform.python_version(), 'machine': platform.machine(), 'system': platform.system()}
    measured = {'stop_overshoot_m': max(-stats['lo'], stats['hi'] - TRAVEL, 0.0), 'jaw_coupling_m': stats['couple'], 'peak_speed_m_s': stats['speed']}
    ep = episode(states, asset)
    again, _, _ = rollout(SCHEDULE)
    measured['replay_same_process_m'] = float(np.abs(again - states).max())
    measured['continuation_m'] = float(np.abs(continue_from(checkpoint, SCHEDULE[50:]) - states[50:]).max())
    trace = {dt: rollout(SCHEDULE, dt)[0] for dt in (DT, DT / 2, DT / 4)}
    measured['timestep_halving_m'] = float(np.abs(trace[DT] - trace[DT / 2]).max())
    quarter = float(np.abs(trace[DT / 2] - trace[DT / 4]).max())  # ~half of the halving error if convergence is first order
    passed = {k: bool(v <= THRESHOLDS[k]) for k, v in measured.items()}
    passed['finite_state'] = stats['finite']
    common = {'asset': 'example.mjcf.xml', 'asset_sha256': asset, 'environment': env, 'scope': 'example gripper demonstrator in MuJoCo only; not physical validation'}
    reports = {
        'engine_report.json': dict(common, kind='engine_report', schedule='100 control steps at 50 Hz: -5 N for 1 s, then +5 N for 1 s',
            metrics={k: measured[k] for k in ('stop_overshoot_m', 'jaw_coupling_m', 'peak_speed_m_s')}, finite_state=stats['finite'],
            thresholds={k: THRESHOLDS[k] for k in ('stop_overshoot_m', 'jaw_coupling_m', 'peak_speed_m_s')}),
        'replay_report.json': dict(common, kind='replay_report',
            metrics={'replay_same_process_m': measured['replay_same_process_m'], 'continuation_m': measured['continuation_m']},
            thresholds={k: THRESHOLDS[k] for k in ('replay_same_process_m', 'continuation_m', 'replay_cross_machine_m')},
            method={'action_replay': 'recorded actions replayed from the open keyframe; qpos compared at every control instant',
                    'continuation': 'mjSTATE_INTEGRATION captured at t=1.0 s, restored in a fresh MjData, remaining actions applied',
                    'cross_machine': 'CI replays the committed episode on its runner (engine_check.py --replay); bitwise equality across platforms is not claimed'}),
        'convergence_report.json': dict(common, kind='convergence_report',
            metrics={'timestep_halving_m': measured['timestep_halving_m'], 'timestep_quartering_vs_halving_m': quarter,
                     'observed_order': float(np.log2(measured['timestep_halving_m'] / quarter)) if quarter > 0 else None},
            thresholds={'timestep_halving_m': THRESHOLDS['timestep_halving_m']}, timesteps_s=[DT, DT / 2, DT / 4],
            method='same zero-order-hold action schedule; qpos compared at 50 Hz control instants'),
    }
    files = dict(reports, **{'episode.json': ep})
    for name, data in files.items(): (out / name).write_text(json.dumps(data, indent=2) + '\n')
    kinds = {'engine_report.json': 'engine_report', 'replay_report.json': 'replay_report', 'convergence_report.json': 'convergence_report', 'episode.json': 'episode'}
    release = {'schema_version': '0.2.0', 'qualification': 'engine_checked', 'accuracy_claim': False, 'operating_envelope': None, 'metrics': [],
               'asset_sha256': asset, 'evidence': [{'path': n, 'sha256': sha256(out / n), 'kind': k} for n, k in kinds.items()],
               'note': 'Engine-checked within the declared MuJoCo test envelope for this demonstrator only. No calibration, no physical accuracy claim.'}
    (out / 'release.json').write_text(json.dumps(release, indent=2) + '\n')
    return measured, passed

def main(argv):
    if len(argv) == 3 and argv[1] == '--replay':
        err = replay(json.loads(pathlib.Path(argv[2]).read_text()))
        ok = err <= THRESHOLDS['replay_cross_machine_m']
        print(json.dumps({'replay_cross_machine_m': err, 'threshold': THRESHOLDS['replay_cross_machine_m'], 'pass': ok}))
        raise SystemExit(0 if ok else 1)
    out = pathlib.Path(argv[2]) if len(argv) == 3 and argv[1] == '--out' else ROOT / 'evidence' / 'example_gripper'
    if len(argv) not in (1, 3): raise SystemExit(__doc__)
    measured, passed = build(out)
    for k in passed: print(f"{'PASS' if passed[k] else 'FAIL'} {k}" + (f": {measured[k]:.3g} (limit {THRESHOLDS[k]:.3g})" if k in measured else ''))
    raise SystemExit(0 if all(passed.values()) else 1)

if __name__ == '__main__': main(sys.argv)
