"""Pick task artifacts without an engine: committed scene matches the builder, samples pass the contract (standard library only)."""
import copy,hashlib,json,pathlib,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tasks/pick')]
from verify_release import validate_episode,validate_split_groups
import scene
SAMPLES=sorted((ROOT/'tasks/pick/sample').glob('pick-*.json'))
class PickContract(unittest.TestCase):
    def test_committed_scene_matches_builder(self):
        committed=scene.SCENE.read_bytes();scene.build()
        self.assertEqual(scene.SCENE.read_bytes(),committed,'run python tasks/pick/scene.py and commit the result')
    def test_samples_validate_and_match_scene(self):
        digest=hashlib.sha256(scene.SCENE.read_bytes()).hexdigest();self.assertTrue(SAMPLES)
        for p in SAMPLES:
            e=json.loads(p.read_text());validate_episode(e)
            self.assertEqual(e['manifest']['asset_sha256'],digest,f'{p.name}: regenerate samples after changing the scene')
    def test_privileged_channels_stay_out_of_observations(self):
        for p in SAMPLES:
            e=json.loads(p.read_text());priv=set(e['manifest']['observation_contract']['privileged_channels'])
            for t in e['transitions']: self.assertFalse(priv&set(t['observation']))
    def test_multi_axis_action_bounds_enforced(self):
        e=json.loads(SAMPLES[0].read_text());e['transitions'][0]['action'][1]=e['manifest']['action_contract']['upper'][1]+1
        with self.assertRaisesRegex(ValueError,'action outside'): validate_episode(e)
    def test_action_dimension_enforced(self):
        e=json.loads(SAMPLES[0].read_text());e['transitions'][0]['action']=e['transitions'][0]['action'][:2]
        with self.assertRaisesRegex(ValueError,'action outside'): validate_episode(e)
    def test_channel_dimension_enforced(self):
        e=json.loads(SAMPLES[0].read_text());e['transitions'][0]['observation']['joint_pos']['value'].append(0.0)
        with self.assertRaisesRegex(ValueError,'joint_pos'): validate_episode(e)
    def test_undeclared_channel_rejected(self):
        e=json.loads(SAMPLES[0].read_text());e['transitions'][0]['observation']['object_pose']=copy.deepcopy(e['transitions'][0]['observation']['joint_pos'])
        with self.assertRaisesRegex(ValueError,'privileged'): validate_episode(e)
    def test_samples_respect_group_splits(self):
        validate_split_groups([json.loads(p.read_text()) for p in SAMPLES])
if __name__=='__main__':unittest.main()
