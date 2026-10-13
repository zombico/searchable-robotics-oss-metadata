"""Committed engine evidence must match the current model and pass the release verifier (standard library only).
Regenerate with: python engine_check.py
"""
import hashlib,json,pathlib,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from verify_release import validate_episode,validate_release
EVIDENCE=ROOT/'evidence/example_gripper'
class Evidence(unittest.TestCase):
    def setUp(self): self.release=json.loads((EVIDENCE/'release.json').read_text())
    def test_release_is_engine_checked_without_accuracy_claim(self):
        self.assertEqual(validate_release(self.release,EVIDENCE)['qualification'],'engine_checked');self.assertFalse(self.release['accuracy_claim'])
    def test_evidence_matches_current_model(self):
        current=hashlib.sha256((ROOT/'example.mjcf.xml').read_bytes()).hexdigest()
        self.assertEqual(self.release['asset_sha256'],current,'example.mjcf.xml changed: run python engine_check.py')
        for name in ['engine_report.json','replay_report.json','convergence_report.json']:
            self.assertEqual(json.loads((EVIDENCE/name).read_text())['asset_sha256'],current,name)
    def test_episode_is_valid_forward_simulation(self):
        e=json.loads((EVIDENCE/'episode.json').read_text())
        self.assertEqual(validate_episode(e)['origin'],'forward_simulation');self.assertEqual(e['manifest']['asset_sha256'],self.release['asset_sha256'])
    def test_reports_record_passing_metrics(self):
        for name in ['engine_report.json','replay_report.json','convergence_report.json']:
            r=json.loads((EVIDENCE/name).read_text())
            for k,limit in r['thresholds'].items():
                if k in r['metrics']: self.assertLessEqual(r['metrics'][k],limit,f'{name} {k}')
if __name__=='__main__':unittest.main()
