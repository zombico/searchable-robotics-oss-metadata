"""Optional MuJoCo runtime check. Requires: pip install -r requirements-sim.txt
Runs in the `engine` CI job; tests/test_engine.py holds the fuller engine checks.
"""
import pathlib
import mujoco
import numpy as np
p=pathlib.Path(__file__).resolve().parent
m=mujoco.MjModel.from_xml_path(str(p/'example.mjcf.xml'));d=mujoco.MjData(m)
mujoco.mj_resetDataKeyframe(m,d,0)
for step in range(2000):
    d.ctrl[0]=-5 if step<1000 else 5
    mujoco.mj_step(m,d)
    assert np.isfinite(d.qpos).all() and np.isfinite(d.qvel).all()
    assert abs(d.qpos[0]-d.qpos[1])<0.0002
    assert np.all(d.qpos>=-0.001) and np.all(d.qpos<=0.026)
    if step==999: assert d.qpos.max()<0.0005,'jaws did not close'
assert d.qpos.min()>0.0245,'jaws did not reopen'
print(f'PASS: mujoco {mujoco.__version__}; full-effort close/open, finite state, coupling <0.2 mm, stops within 1 mm for 2 s. Not physical validation.')
