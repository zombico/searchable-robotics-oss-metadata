import copy,json,pathlib,sys,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from verify_release import validate_episode,validate_release,validate_split_groups
class Tests(unittest.TestCase):
    def setUp(self):
        self.e=json.loads((ROOT/'fixtures/episode.json').read_text());self.r=json.loads((ROOT/'fixtures/release.json').read_text())
    def test_contract_is_not_physics_validation(self): self.assertFalse(validate_episode(self.e)['physics_validated'])
    def test_future_sensor_rejected(self):
        self.e['transitions'][0]['observation']['qpos']['release_t_s']=0.02
        with self.assertRaisesRegex(ValueError,'future sensor'): validate_episode(self.e)
    def test_clock_rejected(self):
        self.e['manifest']['clock']['control_hz']=30
        with self.assertRaisesRegex(ValueError,'clock mismatch'): validate_episode(self.e)
    def test_privileged_input_rejected(self):
        self.e['transitions'][0]['observation']['true_material_parameters']=1
        with self.assertRaisesRegex(ValueError,'privileged'): validate_episode(self.e)
    def test_action_unit_rejected(self):
        self.e['manifest']['action_contract']['unit']='rad'
        with self.assertRaisesRegex(ValueError,'action semantics'): validate_episode(self.e)
    def test_nan_rejected(self):
        self.e['transitions'][0]['action']=[float('nan')]
        with self.assertRaisesRegex(ValueError,'action outside'): validate_episode(self.e)
    def test_terminal_rejected(self):
        self.e['transitions'][0]['terminated']=True
        with self.assertRaisesRegex(ValueError,'after terminal'): validate_episode(self.e)
    def test_split_leakage_rejected(self):
        b=copy.deepcopy(self.e);b['episode_id']='second';b['split']='test'
        with self.assertRaisesRegex(ValueError,'split leakage'): validate_split_groups([self.e,b])
    def test_accuracy_claim_rejected(self):
        self.r['accuracy_claim']=True
        with self.assertRaisesRegex(ValueError,'without calibration'): validate_release(self.r,ROOT/'fixtures')
    def test_engine_claim_rejected(self):
        self.r['qualification']='engine_checked'
        with self.assertRaisesRegex(ValueError,'missing engine'): validate_release(self.r,ROOT/'fixtures')
    def test_changed_evidence_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            p=pathlib.Path(folder);(p/'e.txt').write_text('test-only evidence')
            self.r['evidence']=[{'path':'e.txt','sha256':'0'*64,'kind':'engine_report'}]
            with self.assertRaisesRegex(ValueError,'hash mismatch'): validate_release(self.r,p)
    def test_release_is_not_authenticated(self): self.assertFalse(validate_release(self.r,ROOT/'fixtures')['experiment_authenticity_verified'])
    def test_fixture_cannot_be_relabelled_forward_simulation(self):
        self.e['origin']='forward_simulation'
        with self.assertRaisesRegex(ValueError,'needs engine'): validate_episode(self.e)
if __name__=='__main__':unittest.main()
