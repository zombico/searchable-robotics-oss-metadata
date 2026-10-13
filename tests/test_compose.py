"""Composer v0: requirement model and static screening (standard library), plus a composed-design engine check."""
import math,os,pathlib,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'compose')]
import pick_gripper as P
REQ,SCREENED=P.screen_all();BY={s['name']:s for s in SCREENED}
def failed(name): return {c['check'] for c in BY[name]['checks'] if c['result']=='fail'}
def unknown(name): return {c['check'] for c in BY[name]['checks'] if c['result']=='unknown'}

class Requirements(unittest.TestCase):
    def test_grip_requirement_formula(self):
        r=P.TASK['object_randomization'];a=P.ASSUMPTIONS
        pad=a['safety_factor']*r['mass_kg'][1]*(9.81+a['lift_accel_m_s2'])/(2*r['friction'][0])
        self.assertAlmostEqual(REQ['pad_normal_force_N']['value'],pad);self.assertAlmostEqual(REQ['jaw_drive_force_N']['value'],2*pad)
    def test_widest_box_fits(self): self.assertGreaterEqual(REQ['jaw_opening_m']['available'],REQ['jaw_opening_m']['value'])

class Screening(unittest.TestCase):
    def test_example_drive_is_too_weak(self): self.assertEqual(failed('baseline_example_drive'),{'jaw_drive_force_N'})
    def test_small_pinion_is_too_slow_and_flagged(self):
        self.assertEqual(failed('E01_z12'),{'full_stroke_close_s'});self.assertTrue(any('undercut' in w for w in BY['E01_z12']['warnings']))
    def test_xm430_designs_feasible(self):
        for z in (20,30,40): self.assertEqual(BY[f'E01_z{z}']['status'],'feasible')
    def test_74v_servo_rejected_on_12v_rail(self):
        self.assertIn('supply_voltage_V',failed('E03_z20'));self.assertEqual(BY['E03_z20']['status'],'rejected')
    def test_unpublished_mass_is_undetermined_not_feasible(self):
        self.assertEqual(BY['E04_z20']['status'],'undetermined');self.assertEqual(unknown('E04_z20'),{'z_payload_N'})
        self.assertTrue(any('search-snippet' in w for w in BY['E04_z20']['warnings']))
    def test_force_and_speed_follow_pinion_radius(self):
        a,b=BY['E01_z20']['drive'],BY['E01_z40']['drive']
        self.assertAlmostEqual(a['effort_limit_N']/b['effort_limit_N'],2);self.assertAlmostEqual(b['no_load_speed_m_s']/a['no_load_speed_m_s'],2)
        self.assertAlmostEqual(a['effort_limit_N'],0.9*4.1/0.01)
    def test_bom_names_catalog_parts(self):
        bom={b['item']:b['part'] for b in BY['E01_z40']['bill_of_materials']}
        self.assertTrue(bom['jaw servo'].startswith('E01'));self.assertTrue(bom['bus adapter'].startswith('E20'));self.assertTrue(bom['supply'].startswith('E72'))

try:
    import mujoco
except ImportError:
    mujoco=None
if mujoco is None and os.environ.get('REQUIRE_ENGINE')=='1': raise RuntimeError('REQUIRE_ENGINE=1 but mujoco is not installed')

@unittest.skipIf(mujoco is None,'mujoco not installed; pip install -r requirements-sim.txt')
class ComposedDesign(unittest.TestCase):
    def test_composed_servo_holds_box_the_example_drive_drops(self):
        import tempfile;from generate import run;from env import PickEnv;from scripted import ScriptedPicker;import scene
        heavy={'width_m':0.03,'depth_m':0.03,'height_m':0.04,'x_m':0.02,'mass_kg':0.3,'friction':0.3}
        self.assertEqual(run(PickEnv(),0,heavy)['summary']['outcome'],'slip')
        d=BY['E01_z40']['drive'];servo={'stall_force_N':d['effort_limit_N'],'no_load_speed_m_s':d['no_load_speed_m_s'],
            'force_limit_N':REQ['jaw_drive_force_N']['value'],'armature_kg':1e-8*(353.5/d['pinion_radius_m'])**2}
        with tempfile.TemporaryDirectory() as tmp:
            env=PickEnv(scene.build({'model':'t','jaw_servo':servo,'z_extra_mass_kg':d['servo_mass_kg']},pathlib.Path(tmp)/'t.xml'))
            ep=run(env,0,heavy,policy=ScriptedPicker(jaw_command=d['no_load_speed_m_s'],extra_mass_kg=d['servo_mass_kg']))
        self.assertEqual(ep['summary']['outcome'],'success')
if __name__=='__main__':unittest.main()
