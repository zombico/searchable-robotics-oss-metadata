"""Pick task with MuJoCo: determinism, randomization consistency, outcome semantics, replay of committed samples.
Skipped without mujoco unless REQUIRE_ENGINE=1."""
import os,pathlib,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tasks/pick')]
try:
    import mujoco,numpy as np
    from env import PickEnv,TASK
    from generate import run,replay
    from verify_release import validate_episode
except ImportError:
    mujoco=None
if mujoco is None and os.environ.get('REQUIRE_ENGINE')=='1': raise RuntimeError('REQUIRE_ENGINE=1 but mujoco is not installed')
BASE={'width_m':0.03,'depth_m':0.03,'height_m':0.04,'x_m':0.02}

@unittest.skipIf(mujoco is None,'mujoco not installed; pip install -r requirements-sim.txt')
class PickEngine(unittest.TestCase):
    def setUp(self): self.env=PickEnv()
    def test_same_seed_same_episode(self):
        a,b=run(self.env,7),run(self.env,7)
        self.assertEqual([t['action'] for t in a['transitions']],[t['action'] for t in b['transitions']])
        self.assertEqual(a['transitions'][-1]['next_observation'],b['transitions'][-1]['next_observation'])
    def test_randomized_body_is_consistent(self):
        self.env.reset(seed=3);p=self.env.params;m=self.env.model;b=self.env.obj_body
        self.assertAlmostEqual(m.body_mass[b],p['mass_kg'])
        w,d,h=p['width_m'],p['depth_m'],p['height_m']
        np.testing.assert_allclose(m.body_inertia[b],p['mass_kg']/12*np.array([d*d+h*h,w*w+h*h,w*w+d*d]))
        I=m.body_inertia[b];self.assertTrue(all(I[k]<=sum(I)-I[k] for k in range(3)))
    def test_enlarged_object_collides_with_jaws(self):
        # Resizing without updating geom_rbound/geom_aabb misses jaw contacts on boxes larger than nominal (penetration).
        e=run(self.env,0,{'width_m':0.045,'depth_m':0.04,'height_m':0.05,'x_m':0.02,'mass_kg':0.03,'friction':0.9})
        self.assertEqual(e['summary']['outcome'],'success');self.assertGreater(e['summary']['peak_grip_normal_force_N'],4)
    def test_light_grippy_box_is_picked(self):
        self.assertEqual(run(self.env,0,{**BASE,'mass_kg':0.03,'friction':0.9})['summary']['outcome'],'success')
    def test_heavy_slippery_box_slips(self):
        # ~2.5 N normal per pad at 5 N drive: 2*0.3*2.5 = 1.5 N friction capacity < 2.9 N weight.
        self.assertEqual(run(self.env,0,{**BASE,'mass_kg':0.3,'friction':0.3})['summary']['outcome'],'slip')
    def test_generated_episodes_validate(self):
        for seed in range(100,110):
            e=run(self.env,seed);validate_episode(e)
            self.assertIn(e['summary']['outcome'],{'success','slip','miss','collision','timeout'})
            self.assertTrue(all(w>=0 for w in e['summary']['positive_mechanical_work_J']))
    def test_committed_samples_replay(self):
        for p in sorted((ROOT/'tasks/pick/sample').glob('pick-*.json')): self.assertLessEqual(replay(p),1e-6,p.name)
if __name__=='__main__':unittest.main()
