"""Pick-box environment (requires mujoco and numpy; see requirements-sim.txt).

Gymnasium-style API without depending on gymnasium:
    obs, info = env.reset(seed=..., params=None)
    obs, reward, terminated, truncated, info = env.step(action)   # action: [Fx, Fz, Fjaw] in N, held 20 ms

Policy observations are only the declared deployable channels. Object pose, contact force,
sampled parameters, actuator force and mechanical power are diagnostics (info), never observations.
"""
import hashlib, json, math, pathlib
import mujoco
import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
SCENE = HERE / 'pick_scene.mjcf.xml'
TASK = json.loads((HERE / 'task.json').read_text())
POLICY_CHANNELS = {'joint_pos': (4, 'm'), 'joint_vel': (4, 'm/s'), 'object_x_measured': (1, 'm')}
PRIVILEGED_CHANNELS = ['object_pose', 'grip_normal_force', 'actuator_force', 'mechanical_power', 'sampled_parameters']

def sample_parameters(rng):
    r = TASK['object_randomization']
    return {k: float(rng.uniform(*r[k])) for k in ('width_m', 'depth_m', 'height_m', 'mass_kg', 'friction', 'x_m')}

def leakage_group(p):
    s = TASK['splits']; w = int(np.searchsorted(s['width_bins_m'][1:-1], p['width_m'], side='right'))
    m = int(np.searchsorted(s['mass_bins_kg'][1:-1], p['mass_kg'], side='right'))
    return f'w{w}-m{m}'

def split_for(group):
    s = TASK['splits']
    return 'test' if group in s['test_groups'] else 'validation' if group in s['validation_groups'] else 'train'

class PickEnv:
    def __init__(self):
        self.model = mujoco.MjModel.from_xml_path(str(SCENE)); self.data = mujoco.MjData(self.model)
        m = self.model; name = lambda kind, n: mujoco.mj_name2id(m, kind, n)
        self.joints = [m.jnt_qposadr[name(mujoco.mjtObj.mjOBJ_JOINT, j)] for j in ('x_slide', 'z_slide', 'left_slide', 'right_slide')]
        self.dofs = [m.jnt_dofadr[name(mujoco.mjtObj.mjOBJ_JOINT, j)] for j in ('x_slide', 'z_slide', 'left_slide', 'right_slide')]
        self.obj_body = name(mujoco.mjtObj.mjOBJ_BODY, 'object'); self.obj_geom = name(mujoco.mjtObj.mjOBJ_GEOM, 'object')
        self.pads = {name(mujoco.mjtObj.mjOBJ_GEOM, 'left_pad'), name(mujoco.mjtObj.mjOBJ_GEOM, 'right_pad')}
        self.obj_qpos = m.jnt_qposadr[name(mujoco.mjtObj.mjOBJ_JOINT, 'object_free')]
        self.decimation = TASK['clock']['control_decimation']; self.dt = m.opt.timestep * self.decimation
        self.horizon = int(round(TASK['clock']['episode_s'] / self.dt))
        self.lower, self.upper = m.actuator_ctrlrange[:, 0].copy(), m.actuator_ctrlrange[:, 1].copy()
        self.asset_sha256 = hashlib.sha256(SCENE.read_bytes()).hexdigest()

    def _apply(self, p):
        """Set object geometry, mass, consistent box inertia, friction and start pose."""
        m, d = self.model, self.data; size = np.array([p['width_m'], p['depth_m'], p['height_m']]) / 2
        m.geom_size[self.obj_geom] = size; m.body_mass[self.obj_body] = p['mass_kg']
        # Collision broadphase uses these bounds; stale values would silently miss contacts after resizing.
        m.geom_rbound[self.obj_geom] = np.linalg.norm(size); m.geom_aabb[self.obj_geom] = np.concatenate([np.zeros(3), size])
        w, dp, h = 2 * size
        m.body_inertia[self.obj_body] = p['mass_kg'] / 12 * np.array([dp**2 + h**2, w**2 + h**2, w**2 + dp**2])
        m.geom_friction[self.obj_geom, 0] = p['friction']
        mujoco.mj_setConst(m, d)  # refresh derived constants after editing mass/inertia
        mujoco.mj_resetData(m, d)
        d.qpos[self.joints[2]] = d.qpos[self.joints[3]] = m.jnt_range[mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, 'left_slide'), 1]
        d.qpos[self.obj_qpos:self.obj_qpos + 7] = [p['x_m'], 0, p['height_m'] / 2, 1, 0, 0, 0]
        mujoco.mj_forward(m, d)

    def reset(self, seed, params=None):
        rng = np.random.default_rng(seed)
        self.params = params or sample_parameters(rng)
        self.sensor_rng = np.random.default_rng([seed, 1])
        self._apply(self.params)
        self.t = 0; self.lifted_max = 0.0; self.hold = 0; self.energy = np.zeros(3); self.gripped = False
        self.rest_z = self.data.xpos[self.obj_body][2]
        return self._obs(), self._info()

    def _obs(self):
        d = self.data; noise = TASK['sensor']['object_x_measured']['noise_std_m']
        return {'joint_pos': [float(d.qpos[i]) for i in self.joints], 'joint_vel': [float(d.qvel[i]) for i in self.dofs],
                'object_x_measured': [float(d.xpos[self.obj_body][0] + self.sensor_rng.normal(0, noise))]}

    def _grip_force(self):
        d, total, f = self.data, 0.0, np.zeros(6)
        for i in range(d.ncon):
            c = d.contact[i]
            if {c.geom1, c.geom2} & self.pads and self.obj_geom in (c.geom1, c.geom2):
                mujoco.mj_contactForce(self.model, d, i, f); total += abs(f[0])
        return total

    def _info(self):
        d = self.data
        return {'object_pose': [float(x) for x in np.concatenate([d.xpos[self.obj_body], d.xquat[self.obj_body]])],
                'grip_normal_force': self._grip_force(), 'actuator_force': [float(x) for x in d.actuator_force],
                'mechanical_power': [float(x) for x in d.actuator_force * d.actuator_velocity]}

    def _outcome(self):
        d = self.data; lift = d.xpos[self.obj_body][2] - self.rest_z; self.lifted_max = max(self.lifted_max, lift)
        w, x, y, z = d.xquat[self.obj_body]; tilt = math.degrees(math.acos(min(1.0, abs(1 - 2 * (x * x + y * y)))))
        if not (np.isfinite(d.qpos).all() and np.isfinite(d.qvel).all()): return 'invalid_non_finite'
        if d.ncon and min(d.contact[i].dist for i in range(d.ncon)) < -TASK['quarantine_rules']['max_penetration_m']: return 'invalid_penetration'
        self.hold = self.hold + 1 if lift >= TASK['success']['lift_m'] else 0
        if self.hold * self.dt >= TASK['success']['hold_s']: return 'success'
        if tilt > 30: return 'collision'
        self.gripped |= self._grip_force() > TASK['failure_thresholds']['gripped_force_N']
        jaws_shut = d.qpos[self.joints[2]] < 0.002
        if lift < 0.003 and ((self.lifted_max >= 0.01) or (jaws_shut and self.gripped)): return 'slip'
        if jaws_shut and not self.gripped and lift < 0.003: return 'miss'
        return None

    def step(self, action):
        a = np.clip(np.asarray(action, dtype=float), self.lower, self.upper); self.data.ctrl[:] = a
        for _ in range(self.decimation):
            mujoco.mj_step(self.model, self.data)
            self.energy += np.maximum(self.data.actuator_force * self.data.actuator_velocity, 0) * self.model.opt.timestep
        self.t += 1; outcome = self._outcome()
        terminated = outcome is not None; truncated = not terminated and self.t >= self.horizon
        reward = 1.0 if outcome == 'success' else 0.0
        info = self._info(); info['outcome'] = outcome or ('timeout' if truncated else 'ongoing'); info['positive_work_J'] = [float(x) for x in self.energy]
        return self._obs(), reward, terminated, truncated, info
