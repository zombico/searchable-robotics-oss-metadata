"""Generate scripted pick episodes (requires mujoco and numpy).

  python tasks/pick/generate.py --episodes 1000 --out datasets/pick_v0   # datasets/ is gitignored
  python tasks/pick/generate.py --replay EPISODE.json                    # forward-replay a recorded episode

Writes episodes.jsonl (contract-valid episodes, success and task failures alike), quarantine.jsonl
(physically invalid rollouts with the reason) and summary.json (counts, per-split outcomes, energy,
parameter coverage, throughput). Every episode passes verify_release.validate_episode before it is written.
"""
import argparse, hashlib, json, pathlib, platform, sys, time
import mujoco
import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(HERE), str(ROOT)]
from env import PickEnv, TASK, POLICY_CHANNELS, PRIVILEGED_CHANNELS, leakage_group, split_for
from scripted import ScriptedPicker
from verify_release import validate_episode, validate_split_groups

GENERATOR = {'type': 'scripted', 'source': 'tasks/pick/scripted.py', 'source_sha256': hashlib.sha256((HERE / 'scripted.py').read_bytes()).hexdigest()}

def stamp(obs, t):
    return {k: {'value': v, 'unit': POLICY_CHANNELS[k][1], 'capture_t_s': t, 'release_t_s': t} for k, v in obs.items()}

def run(env, seed, params=None, actions=None):
    """Roll out the scripted policy (or replay `actions`); returns the episode dict and outcome."""
    obs, info = env.reset(seed=seed, params=params); policy = ScriptedPicker(); transitions = []
    step = TASK['clock']['physics_dt_s'] * TASK['clock']['control_decimation']; peak = {'grip_N': 0.0, 'power_W': [0.0] * 3, 'lift_m': 0.0}
    while True:
        k = len(transitions); t = round(k * step, 9)
        action = actions[k] if actions is not None else [float(x) for x in np.clip(policy(obs), env.lower, env.upper)]
        phase = policy.phase if actions is None else None
        nobs, reward, terminated, truncated, info = env.step(action)
        outcome = info.pop('outcome'); work = info.pop('positive_work_J')
        peak['grip_N'] = max(peak['grip_N'], info['grip_normal_force']); peak['lift_m'] = max(peak['lift_m'], env.lifted_max)
        peak['power_W'] = [max(a, abs(b)) for a, b in zip(peak['power_W'], info['mechanical_power'])]
        transitions.append({'t_s': t, 'next_t_s': round((k + 1) * step, 9), 'action': action, 'observation': stamp(obs, t),
                            'next_observation': stamp(nobs, round((k + 1) * step, 9)), 'terminated': terminated, 'truncated': truncated,
                            'outcome': outcome, 'reward': reward, 'phase': phase, 'diagnostics': info})
        obs = nobs
        if terminated or truncated or (actions is not None and len(transitions) == len(actions)): break
    group = leakage_group(env.params)
    episode = {'schema_version': '0.2.0', 'origin': 'forward_simulation', 'episode_id': f'pick-v0-seed{seed}', 'split': split_for(group), 'leakage_group': group,
               'generator': GENERATOR,
               'manifest': {'clock': {'physics_dt_s': TASK['clock']['physics_dt_s'], 'control_decimation': TASK['clock']['control_decimation'], 'control_hz': 1 / step},
                            'asset_sha256': env.asset_sha256, 'seed': seed,
                            'engine': {'name': 'mujoco', 'version': mujoco.__version__, 'runtime_scope': 'CPU mj_step; replay tolerance in generate.py'},
                            'action_contract': {'mode': 'joint_force', 'unit': 'N', 'frame': 'joint', 'dimension': 3, 'hold': 'zero_order',
                                                'controller_id': 'pick_force_speed_drives_v1', 'axes': ['x_slide', 'z_slide', 'left_slide (jaws coupled)'],
                                                'lower': [float(x) for x in env.lower], 'upper': [float(x) for x in env.upper]},
                            'observation_contract': {'policy_channels': list(POLICY_CHANNELS), 'channel_dims': {k: v[0] for k, v in POLICY_CHANNELS.items()},
                                                     'channel_units': {k: v[1] for k, v in POLICY_CHANNELS.items()}, 'privileged_channels': PRIVILEGED_CHANNELS,
                                                     'joint_order': ['x_slide', 'z_slide', 'left_slide', 'right_slide'], 'sensor_models': TASK['sensor']},
                            'task': {'name': TASK['task'], 'config': 'tasks/pick/task.json', 'sampled_parameters': env.params}},
               'summary': {'outcome': transitions[-1]['outcome'], 'steps': len(transitions), 'duration_s': round(len(transitions) * step, 9),
                           'positive_mechanical_work_J': work, 'peak_abs_mechanical_power_W': peak['power_W'], 'peak_grip_normal_force_N': peak['grip_N'],
                           'max_object_lift_m': peak['lift_m'],
                           'energy_note': 'Mechanical work at the joints only; electrical energy needs motor constants and drive efficiency, which this demonstrator does not have.'},
               'transitions': transitions}
    return episode

def replay(path):
    """Forward action replay with the recorded sampled parameters and seed; returns max joint_pos error (m)."""
    ep = json.loads(pathlib.Path(path).read_text()); env = PickEnv()
    if ep['manifest']['asset_sha256'] != env.asset_sha256: raise SystemExit('episode recorded with a different scene asset')
    again = run(env, ep['manifest']['seed'], ep['manifest']['task']['sampled_parameters'], [t['action'] for t in ep['transitions']])
    a = np.array([t['next_observation']['joint_pos']['value'] for t in ep['transitions']])
    b = np.array([t['next_observation']['joint_pos']['value'] for t in again['transitions']])
    return float(np.abs(a - b).max()) if a.shape == b.shape else float('inf')

def generate(n, out, seed0=0):
    out.mkdir(parents=True, exist_ok=True); env = PickEnv(); kept, quarantined = [], []; t0 = time.perf_counter()
    with open(out / 'episodes.jsonl', 'w') as good, open(out / 'quarantine.jsonl', 'w') as bad:
        for seed in range(seed0, seed0 + n):
            ep = run(env, seed)
            if ep['summary']['outcome'].startswith('invalid'):
                bad.write(json.dumps({'seed': seed, 'reason': ep['summary']['outcome'], 'sampled_parameters': env.params}) + '\n'); quarantined.append(seed); continue
            validate_episode(ep); good.write(json.dumps(ep) + '\n'); kept.append({k: ep[k] for k in ('episode_id', 'split', 'leakage_group', 'summary')} | {'params': env.params})
    elapsed = time.perf_counter() - t0
    validate_split_groups([{'episode_id': e['episode_id'], 'split': e['split'], 'leakage_group': e['leakage_group']} for e in kept])
    by = lambda key: {v: sum(1 for e in kept if key(e) == v) for v in sorted({key(e) for e in kept})}
    outcomes = sorted({e['summary']['outcome'] for e in kept})
    per_split = {s: {o: sum(1 for e in kept if e['split'] == s and e['summary']['outcome'] == o) for o in outcomes} for s in ('train', 'validation', 'test')}
    work = np.array([e['summary']['positive_mechanical_work_J'] for e in kept])
    summary = {'task': TASK['task'], 'attempted': n, 'valid': len(kept), 'quarantined': len(quarantined), 'outcomes': by(lambda e: e['summary']['outcome']),
               'outcomes_by_split': per_split, 'episodes_by_group': by(lambda e: e['leakage_group']),
               'success_rate': round(sum(e['summary']['outcome'] == 'success' for e in kept) / max(len(kept), 1), 4),
               'mean_duration_s': round(float(np.mean([e['summary']['duration_s'] for e in kept])), 4),
               'positive_mechanical_work_J_mean': [round(float(x), 5) for x in work.mean(0)], 'positive_mechanical_work_J_max': [round(float(x), 5) for x in work.max(0)],
               'slip_vs_friction_mass': 'slips concentrate where object weight exceeds pad friction capacity; see per-episode sampled_parameters',
               'throughput': {'episodes_per_hour': round(n / elapsed * 3600), 'seconds': round(elapsed, 2), 'environment': {'mujoco': mujoco.__version__, 'numpy': np.__version__,
                              'python': platform.python_version(), 'machine': platform.machine()}, 'note': 'single process, machine-dependent'},
               'generator': GENERATOR, 'seeds': [seed0, seed0 + n - 1]}
    (out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    return summary

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--episodes', type=int, default=100); ap.add_argument('--out', default=str(ROOT / 'datasets' / 'pick_v0'))
    ap.add_argument('--seed0', type=int, default=0); ap.add_argument('--replay')
    args = ap.parse_args()
    if args.replay:
        err = replay(args.replay); ok = err <= 1e-6
        print(json.dumps({'replay_joint_pos_max_error_m': err, 'threshold_m': 1e-6, 'pass': ok})); raise SystemExit(0 if ok else 1)
    s = generate(args.episodes, pathlib.Path(args.out), args.seed0)
    print(json.dumps({k: s[k] for k in ('attempted', 'valid', 'quarantined', 'outcomes', 'success_rate')} | {'episodes_per_hour': s['throughput']['episodes_per_hour']}))
