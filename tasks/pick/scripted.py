"""Scripted pick demonstrator. Uses only policy observations (joint_pos, joint_vel, object_x_measured),
so its demonstrations are learnable from the same inputs a policy would get. Gains are hand-tuned
demonstration choices, not an optimized controller.
"""
import numpy as np

GRASP_Z = -0.170          # jaw bottom ~10 mm above the floor at this carriage height
LIFT_Z = GRASP_Z + 0.06
GRAVITY_FF_N = 0.58 * 9.81  # carriage z + gripper base + jaws, from task.json/example.json masses

class ScriptedPicker:
    def __init__(self):
        self.phase, self.ticks, self.stall, self.x_est, self.n, self.z_int = 'align', 0, 0, 0.0, 0, 0.0

    def __call__(self, obs):
        x, z, jaw, _ = obs['joint_pos']; vx, vz, vjaw, _ = obs['joint_vel']
        self.n += 1; self.x_est += (obs['object_x_measured'][0] - self.x_est) / min(self.n, 25)  # running mean of noisy detections
        z_target, grip = 0.0, 5.0
        if self.phase == 'align' and abs(x - self.x_est) < 0.001 and abs(vx) < 0.005 and self.n > 10: self.phase, self.ticks = 'descend', 0
        if self.phase == 'descend':
            z_target = GRASP_Z
            if abs(z - GRASP_Z) < 0.005 and abs(vz) < 0.02: self.phase, self.ticks = 'close', 0
        if self.phase == 'close':
            z_target, grip = GRASP_Z, -5.0
            self.stall = self.stall + 1 if abs(vjaw) < 0.002 else 0
            if self.ticks > 5 and (self.stall >= 5 or jaw < 0.002): self.phase, self.ticks = 'lift', 0
        if self.phase in ('lift', 'hold'):
            z_target, grip = LIFT_Z, -5.0
            if self.phase == 'lift' and abs(z - LIFT_Z) < 0.003: self.phase = 'hold'
        self.ticks += 1
        self.z_int = float(np.clip(self.z_int + (z_target - z) * 0.02, -0.02, 0.02))
        fx = 1500 * (self.x_est - x) - 20 * vx
        fz = 3000 * (z_target - z) - 40 * vz + GRAVITY_FF_N + 500 * self.z_int
        return [float(fx), float(fz), grip]
