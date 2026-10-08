"""Optional MuJoCo runtime check. Requires user-installed mujoco and numpy.
This script was supplied but not run in the research environment.
"""
import pathlib
import mujoco
import numpy as np
p=pathlib.Path(__file__).resolve().parent
m=mujoco.MjModel.from_xml_path(str(p/'example.mjcf.xml'));d=mujoco.MjData(m)
mujoco.mj_resetDataKeyframe(m,d,0)
for step in range(2000):
    d.ctrl[0]=-0.5 if step<1000 else 0.5
    mujoco.mj_step(m,d)
    assert np.isfinite(d.qpos).all() and np.isfinite(d.qvel).all()
    assert abs(d.qpos[0]-d.qpos[1])<0.002
    assert np.all(d.qpos>=-0.002) and np.all(d.qpos<=0.027)
print('PASS: finite state, coupled jaw displacement, approximate limits for 2 s. Not physical validation.')
