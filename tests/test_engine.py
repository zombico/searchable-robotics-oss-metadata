"""MuJoCo runtime checks for example.mjcf.xml (L1-style engine evidence, not physical validation).
Skipped when mujoco is unavailable unless REQUIRE_ENGINE=1, which turns the skip into a failure.
"""
import os,pathlib,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
try:
    import mujoco,numpy as np
except ImportError:
    mujoco=None
if mujoco is None and os.environ.get('REQUIRE_ENGINE')=='1': raise RuntimeError('REQUIRE_ENGINE=1 but mujoco is not installed')
TRAVEL=0.025;EFFORT=5.0

def sweep(force,dt=0.001):
    """Close for 1 s then open for 1 s at constant joint force; returns the qpos trace sampled every 0.1 s and extremes."""
    m=mujoco.MjModel.from_xml_path(str(ROOT/'example.mjcf.xml'));m.opt.timestep=dt;d=mujoco.MjData(m)
    mujoco.mj_resetDataKeyframe(m,d,0);n=int(round(1/dt));trace=[];lo=hi=d.qpos[0];couple=0.0;speed=0.0
    for step in range(2*n):
        d.ctrl[0]=-force if step<n else force;mujoco.mj_step(m,d)
        if not (np.isfinite(d.qpos).all() and np.isfinite(d.qvel).all()): raise AssertionError(f'non-finite state at step {step}')
        lo=min(lo,d.qpos.min());hi=max(hi,d.qpos.max());couple=max(couple,abs(d.qpos[0]-d.qpos[1]));speed=max(speed,abs(d.qvel).max())
        if (step+1)%(n//10)==0: trace.append(d.qpos.copy())
        if step==n-1: closed=d.qpos.copy()
    return {'trace':np.array(trace),'lo':lo,'hi':hi,'couple':couple,'closed':closed,'open':d.qpos.copy(),'speed':speed}

@unittest.skipIf(mujoco is None,'mujoco not installed; pip install -r requirements-sim.txt')
class EngineTests(unittest.TestCase):
    def test_model_matches_compiler_contract(self):
        m=mujoco.MjModel.from_xml_path(str(ROOT/'example.mjcf.xml'))
        self.assertEqual((m.nq,m.nu,m.neq),(2,1,1))
        self.assertAlmostEqual(m.opt.timestep,0.001)
        np.testing.assert_allclose(m.jnt_range,[[0,TRAVEL]]*2)
        np.testing.assert_allclose(m.actuator_ctrlrange,[[-EFFORT,EFFORT]])
    def test_full_effort_sweep_reaches_and_respects_stops(self):
        r=sweep(EFFORT)
        self.assertLess(r['closed'].max(),0.0005,'jaws did not close')
        self.assertGreater(r['open'].min(),TRAVEL-0.0005,'jaws did not reopen')
        # Soft limits allow some transient penetration; 1 mm is the declared engine-check tolerance.
        self.assertGreater(r['lo'],-0.001);self.assertLess(r['hi'],TRAVEL+0.001)
        self.assertLess(r['couple'],0.0002)
    def test_drive_respects_declared_no_load_speed(self):
        # Linear force-speed drive: full command cannot exceed the 0.1 m/s no-load speed declared in example.json.
        self.assertLess(sweep(EFFORT)['speed'],0.1)
    def test_low_effort_sweep_is_tight(self):
        r=sweep(0.5)
        self.assertGreater(r['lo'],-0.0002);self.assertLess(r['hi'],TRAVEL+0.0002);self.assertLess(r['couple'],0.00005)
    def test_timestep_halving_changes_trajectory_little(self):
        for force in (0.5,EFFORT):
            err=np.abs(sweep(force)['trace']-sweep(force,0.0005)['trace']).max()
            self.assertLess(err,0.00005,f'timestep sensitivity {err:.2e} m at {force} N')
    def test_repeat_run_is_bitwise_identical_in_process(self):
        # Same build/process only; cross-platform bitwise reproducibility is not claimed.
        np.testing.assert_array_equal(sweep(EFFORT)['trace'],sweep(EFFORT)['trace'])
if __name__=='__main__':unittest.main()
