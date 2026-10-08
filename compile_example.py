"""Small reference compiler, only for example.json (not a general catalog compiler).
Units: input lengths mm; emitted physics m/kg/s. No external dependencies.
"""
import json, math, pathlib, sys, xml.etree.ElementTree as E

HERE=pathlib.Path(__file__).resolve().parent
def vec(a):return ' '.join(f'{x:.10g}' for x in a)
def main():
    a=json.loads((HERE/'example.json').read_text())
    for key in ['base_size_mm','jaw_size_mm']:
        assert len(a[key])==3 and all(x>0 for x in a[key])
    assert 0 < a['closed_gap_mm'] < a['base_size_mm'][0]
    assert all(a[k]>0 for k in ['jaw_travel_mm','base_mass_kg','jaw_mass_kg','effort_limit_N','velocity_limit_m_s'])
    b=[v*.001 for v in a['base_size_mm']]; j=[v*.001 for v in a['jaw_size_mm']]
    travel=a['jaw_travel_mm']*.001; offset=(a['closed_gap_mm']*.001+j[0])/2
    height=b[2]+j[2]/2
    def inertia(m,d):return [m*(d[1]**2+d[2]**2)/12,m*(d[0]**2+d[2]**2)/12,m*(d[0]**2+d[1]**2)/12]
    robot=E.Element('robot',name='proposed_parallel_gripper')
    E.SubElement(robot,'link',name='world')
    def link(name,size,mass):
        l=E.SubElement(robot,'link',name=name); ine=E.SubElement(l,'inertial')
        E.SubElement(ine,'origin',xyz='0 0 0',rpy='0 0 0');E.SubElement(ine,'mass',value=str(mass))
        I=inertia(mass,size);E.SubElement(ine,'inertia',ixx=str(I[0]),iyy=str(I[1]),izz=str(I[2]),ixy='0',ixz='0',iyz='0')
        for tag in ['visual','collision']:
            el=E.SubElement(l,tag);g=E.SubElement(el,'geometry');E.SubElement(g,'box',size=vec(size))
    link('base',b,a['base_mass_kg'])
    fixed=E.SubElement(robot,'joint',name='mount',type='fixed');E.SubElement(fixed,'parent',link='world');E.SubElement(fixed,'child',link='base');E.SubElement(fixed,'origin',xyz=vec([0,0,b[2]/2]),rpy='0 0 0')
    for side,sign in [('left',-1),('right',1)]:
        link(side,j,a['jaw_mass_kg']); joint=E.SubElement(robot,'joint',name=side+'_slide',type='prismatic')
        E.SubElement(joint,'parent',link='base');E.SubElement(joint,'child',link=side)
        E.SubElement(joint,'origin',xyz=vec([sign*offset,0,height-b[2]/2]),rpy='0 0 0')
        E.SubElement(joint,'axis',xyz=vec([sign,0,0]))
        E.SubElement(joint,'limit',lower='0',upper=str(travel),effort=str(a['effort_limit_N']),velocity=str(a['velocity_limit_m_s']))
        E.SubElement(joint,'dynamics',damping=str(a['damping_N_s_m']),friction=str(a['joint_friction_N']))
        if side=='right':E.SubElement(joint,'mimic',joint='left_slide',multiplier='1',offset='0')
    # URDF mimic is an importer hint, not a portable enforced physics constraint.
    mj=E.Element('mujoco',model='proposed_parallel_gripper')
    E.SubElement(mj,'compiler',angle='radian');E.SubElement(mj,'option',timestep='0.001',gravity='0 0 -9.81')
    default=E.SubElement(mj,'default');E.SubElement(default,'geom',friction=vec([a['contact_friction'],0.005,0.0001]),condim='3')
    world=E.SubElement(mj,'worldbody');E.SubElement(world,'geom',name='floor',type='plane',size='1 1 0.1',rgba='0.8 0.8 0.8 1')
    E.SubElement(world,'geom',name='base',type='box',pos=vec([0,0,b[2]/2]),size=vec([x/2 for x in b]),rgba='0.2 0.3 0.5 1')
    for side,sign in [('left',-1),('right',1)]:
        body=E.SubElement(world,'body',name=side,pos=vec([sign*offset,0,height]))
        E.SubElement(body,'joint',name=side+'_slide',type='slide',axis=vec([sign,0,0]),range=vec([0,travel]),limited='true',damping=str(a['damping_N_s_m']),frictionloss=str(a['joint_friction_N']))
        E.SubElement(body,'geom',type='box',size=vec([x/2 for x in j]),mass=str(a['jaw_mass_kg']),rgba='0.3 0.65 0.9 1')
    eq=E.SubElement(mj,'equality');E.SubElement(eq,'joint',joint1='right_slide',joint2='left_slide',polycoef='0 1 0 0 0')
    act=E.SubElement(mj,'actuator');E.SubElement(act,'motor',name='jaw_drive',joint='left_slide',gear='1',ctrllimited='true',ctrlrange=vec([-a['effort_limit_N'],a['effort_limit_N']]))
    # Joint-space drive force is an assumed ideal actuator, not per-jaw rated grasp force.
    key=E.SubElement(mj,'keyframe');E.SubElement(key,'key',name='open',qpos=vec([travel,travel]))
    outputs={'example.urdf':robot,'example.mjcf.xml':mj}
    for name,root in outputs.items():
        E.indent(root);E.ElementTree(root).write(HERE/name,encoding='utf-8',xml_declaration=True)
    for I in [inertia(a['base_mass_kg'],b),inertia(a['jaw_mass_kg'],j)]:
        assert all(x>0 for x in I) and all(I[k]<=sum(I)-I[k]+1e-12 for k in range(3))
    print('Generated URDF and MJCF; checked positive dimensions and box inertia triangle inequalities.')
if __name__=='__main__':main()
