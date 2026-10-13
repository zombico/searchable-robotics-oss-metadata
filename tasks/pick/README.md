# Pick task v0: example gripper on a Cartesian carriage

The example gripper (`example.json`) hangs from an x/z carriage and picks a box off the floor. This is the first manipulation environment and dataset generator in the repository. It is a synthetic demonstrator: every mass, drive, range and threshold is a proposed value in `task.json`, not measured hardware, and the data is `forward_simulation` at the `synthetic_only` level.

## Files

| File | Purpose |
|---|---|
| `task.json` | Carriage, drives, clock, randomization bounds, sensor model, outcome and quarantine rules, split groups |
| `scene.py` → `pick_scene.mjcf.xml` | MJCF built from `example.json` and `task.json` (standard library); CI fails if the committed scene drifts |
| `env.py` | `PickEnv`: Gymnasium-style `reset(seed, params)` / `step(action)` without a gymnasium dependency |
| `scripted.py` | Scripted demonstrator that uses only policy observations |
| `generate.py` | Dataset generator and `--replay` checker |
| `sample/` | Two episodes (a success and a slip) and the summary of a 1,000-episode run |

## Interface

- **Action:** `[Fx, Fz, Fjaw]` in N, held for 20 ms (50 Hz). Each axis is a linear force-speed drive: x ±20 N / 0.3 m/s, z ±30 N / 0.2 m/s, jaws ±5 N / 0.1 m/s (negative closes).
- **Policy observations:** `joint_pos` and `joint_vel` for `[x_slide, z_slide, left_slide, right_slide]`, and `object_x_measured`: the true object x plus 1 mm Gaussian noise, captured and released each step.
- **Diagnostics (privileged, never observations):** object pose, pad normal force, actuator forces, per-axis mechanical power and sampled parameters, recorded per transition under `diagnostics`.
- **Reward:** sparse, 1 at success. Shaped rewards belong to the RL work.

## Per-episode randomization

Independent uniform sampling of box width 20–45 mm, depth 20–40 mm, height 30–50 mm, mass 0.02–0.3 kg, friction 0.3–1.0 and x position ±80 mm. Box inertia is recomputed from mass and size, and collision bounds are updated with the new size: without that update, MuJoCo missed jaw contacts on boxes larger than nominal (a test covers this). The sampled values and the config they came from are stored in every episode.

## Outcomes

`success` (lifted at least 30 mm and held 0.5 s), `slip` (gripped, then lost), `miss` (jaws closed without ever gripping), `collision` (box tilted over 30°), `timeout` (6 s). Rollouts with non-finite state or more than 5 mm penetration are quarantined with the reason; they are never counted as task failures.

## Splits

Leakage groups are object families: 3 width bins × 3 mass bins. `w1-m2` is validation; `w2-m0` and `w0-m1` are test. No family appears in two splits, and the generator checks this.

## What a 1,000-episode run produced

From `sample/summary_1000_episodes.json` (seeds 0–999, MuJoCo 3.15.0, one CPU process):

| | Success | Slip |
|---|---|---|
| Train (664) | 578 | 86 |
| Validation (105) | 75 | 30 |
| Test (231) | 222 | 9 |

- **No misses, collisions, timeouts or quarantined rollouts** from the scripted demonstrator.
- **Slips are friction-limited.** The 5 N jaw drive gives about 2.5 N normal force per pad, so a 0.29 kg box at friction 0.52 (seed 1) exceeds the grip's holding force. The validation family is the heaviest mass bin and slips most (29%); the test families are lighter and slip least (4%). Per-split success rates therefore reflect object difficulty, not only generalization.
- **Mean episode length** 2.1 s. **Mean positive mechanical work** 0.06 J (x), 0.48 J (z), 0.009 J (jaws). Electrical energy is not reported: it needs motor constants and drive efficiency this demonstrator does not have.
- **Throughput** about 56,000 episodes per hour in this environment. This is machine-dependent.
- **Storage** about 160 KB per episode as JSON. That suits inspection and reference; compact storage belongs to the training-format export.

## Usage

```sh
pip install -r requirements-sim.txt
python tasks/pick/generate.py --episodes 1000 --out datasets/pick_v0
python tasks/pick/generate.py --replay tasks/pick/sample/pick-v0-seed1_slip.json
REQUIRE_ENGINE=1 python -m unittest tests.test_pick_engine -v
```

```python
import sys; sys.path.insert(0, 'tasks/pick')
from env import PickEnv
from scripted import ScriptedPicker
env = PickEnv(); obs, info = env.reset(seed=0); policy = ScriptedPicker()
while True:
    obs, reward, terminated, truncated, info = env.step(policy(obs))
    if terminated or truncated: break
print(info['outcome'], env.params)
```

## Limits

- No camera or depth observations yet; state-only.
- The perception channel is idealised: Gaussian noise, no latency, no occlusion.
- Contact is MuJoCo's soft-contact model with default solver settings. Grasp forces are solver quantities, not sensor-equivalent measurements.
- Policies trained on this data are not expected to transfer to any real gripper.
