"""Build tasks/pick/pick_scene.mjcf.xml from example.json (gripper) and tasks/pick/task.json (carriage, object).
Standard library only. The object is nominal here; episodes override its size, mass, inertia, friction and pose.
"""
import json, pathlib, xml.etree.ElementTree as E

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCENE = HERE / 'pick_scene.mjcf.xml'

def vec(a): return ' '.join(f'{x:.10g}' for x in a)

def drive(parent, name, joint, effort, speed):
    """Linear force-speed drive, as in compile_example.py: force = ctrl - (effort/speed)*qvel, clipped."""
    limits = vec([-effort, effort])
    E.SubElement(parent, 'general', name=name, joint=joint, gear='1', ctrllimited='true', ctrlrange=limits, forcelimited='true',
                 forcerange=limits, gaintype='fixed', gainprm='1', biastype='affine', biasprm=vec([0, 0, -effort / speed]))

def build(overrides=None, path=SCENE):
    """overrides (composer): 'model' name; 'integrator'; 'z_extra_mass_kg'; and either 'jaw_drive' {'effort_limit_N',
    'no_load_speed_m_s'} (force-speed drive, command in N) or 'jaw_servo' {'stall_force_N', 'no_load_speed_m_s',
    'force_limit_N', 'armature_kg'} (current-limited servo, command = jaw speed in m/s; armature = reflected rotor inertia)."""
    o = overrides or {}
    g = json.loads((ROOT / 'example.json').read_text()); t = json.loads((HERE / 'task.json').read_text()); c = t['carriage']
    base = [v * .001 for v in g['base_size_mm']]; jaw = [v * .001 for v in g['jaw_size_mm']]
    travel = g['jaw_travel_mm'] * .001; offset = (g['closed_gap_mm'] * .001 + jaw[0]) / 2
    solref = vec([g['constraint_timeconst_s'], 1]); dt = t['clock']['physics_dt_s']
    mj = E.Element('mujoco', model=o.get('model', 'pick_box_v0'))
    E.SubElement(mj, 'compiler', angle='radian')
    E.SubElement(mj, 'option', timestep=str(dt), gravity='0 0 -9.81', **({'integrator': o['integrator']} if 'integrator' in o else {}))
    default = E.SubElement(mj, 'default')
    # Jaw pads carry zero friction so MuJoCo's max-combination makes the object's sampled friction govern the grasp.
    E.SubElement(default, 'geom', friction='1 0.005 0.0001', condim='4')
    world = E.SubElement(mj, 'worldbody')
    E.SubElement(world, 'geom', name='floor', type='plane', size='0.5 0.5 0.05', rgba='0.8 0.8 0.8 1')
    cx = E.SubElement(world, 'body', name='carriage_x', pos=vec([0, 0, c['home_height_m']]))
    E.SubElement(cx, 'joint', name='x_slide', type='slide', axis='1 0 0', range=vec(c['x_range_m']), limited='true',
                 damping=str(c['damping_N_s_m']), frictionloss=str(c['joint_friction_N']), solreflimit=solref)
    E.SubElement(cx, 'geom', type='box', size='0.02 0.02 0.02', pos='0 0 0.05', mass=str(c['x_mass_kg']), contype='0', conaffinity='0', rgba='0.4 0.4 0.4 1')
    cz = E.SubElement(cx, 'body', name='carriage_z')
    E.SubElement(cz, 'joint', name='z_slide', type='slide', axis='0 0 1', range=vec([-c['z_travel_m'], 0]), limited='true',
                 damping=str(c['damping_N_s_m']), frictionloss=str(c['joint_friction_N']), solreflimit=solref)
    E.SubElement(cz, 'geom', type='box', size='0.015 0.015 0.02', pos='0 0 0.03', mass=str(c['z_mass_kg'] + o.get('z_extra_mass_kg', 0)), contype='0', conaffinity='0', rgba='0.4 0.4 0.4 1')
    E.SubElement(cz, 'geom', name='base', type='box', size=vec([x / 2 for x in base]), mass=str(g['base_mass_kg']), rgba='0.2 0.3 0.5 1')
    jaw_z = -base[2] / 2 - jaw[2] / 2
    for side, sign in [('left', -1), ('right', 1)]:
        body = E.SubElement(cz, 'body', name=side, pos=vec([sign * offset, 0, jaw_z]))
        E.SubElement(body, 'joint', name=side + '_slide', type='slide', axis=vec([sign, 0, 0]), range=vec([0, travel]), limited='true',
                     damping=str(g['damping_N_s_m']), frictionloss=str(g['joint_friction_N']), solreflimit=solref)
        E.SubElement(body, 'geom', name=side + '_pad', type='box', size=vec([x / 2 for x in jaw]), mass=str(g['jaw_mass_kg']),
                     friction='0 0 0', rgba='0.3 0.65 0.9 1')
    obj = E.SubElement(world, 'body', name='object', pos='0 0 0.02')
    E.SubElement(obj, 'freejoint', name='object_free')
    E.SubElement(obj, 'geom', name='object', type='box', size='0.015 0.015 0.02', mass='0.1', friction='0.7 0.005 0.0001', rgba='0.9 0.5 0.2 1')
    eq = E.SubElement(mj, 'equality'); E.SubElement(eq, 'joint', joint1='right_slide', joint2='left_slide', polycoef='0 1 0 0 0', solref=solref)
    act = E.SubElement(mj, 'actuator')
    drive(act, 'x_drive', 'x_slide', c['x_drive']['effort_limit_N'], c['x_drive']['no_load_speed_m_s'])
    drive(act, 'z_drive', 'z_slide', c['z_drive']['effort_limit_N'], c['z_drive']['no_load_speed_m_s'])
    if 'jaw_servo' in o:
        # Current-limited geared servo: force = kv * (v_cmd - v) with kv = stall force / no-load speed (the torque-speed
        # line at full command), capped at the configured current limit. The reflected rotor inertia (armature) is what
        # makes this stiff line physical and numerically stable; without it the 40 g jaw diverges.
        s = o['jaw_servo']; kv = s['stall_force_N'] / s['no_load_speed_m_s']
        cz.find("./body[@name='left']/joint").set('armature', f"{s['armature_kg']:.10g}")
        E.SubElement(act, 'velocity', name='jaw_drive', joint='left_slide', kv=f'{kv:.10g}', ctrllimited='true',
                     ctrlrange=vec([-s['no_load_speed_m_s'], s['no_load_speed_m_s']]), forcelimited='true', forcerange=vec([-s['force_limit_N'], s['force_limit_N']]))
    else:
        jd = o.get('jaw_drive', {'effort_limit_N': g['effort_limit_N'], 'no_load_speed_m_s': g['velocity_limit_m_s']})
        drive(act, 'jaw_drive', 'left_slide', jd['effort_limit_N'], jd['no_load_speed_m_s'])
    E.indent(mj); E.ElementTree(mj).write(path, encoding='utf-8', xml_declaration=True)
    return path

if __name__ == '__main__': print('Wrote', build().relative_to(ROOT))
