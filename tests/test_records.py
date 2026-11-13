"""Regression and adversarial record validation, against real measured baselines."""
import copy
import json
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.validate import validate


class Records(unittest.TestCase):
    def setUp(self):self.r=json.loads((ROOT/'records/run-clean.json').read_text())
    def test_real_baselines(self):
        for name in ('run-clean.json','run-repeat.json'):self.assertTrue(validate(json.loads((ROOT/'records'/name).read_text())))
    def test_missing_wait_is_not_deadlock_evidence(self):
        self.r['deadlock']['snapshot_before_cycle']['waits']=[]
        with self.assertRaises(AssertionError):validate(self.r)
    def test_wait_edge_requires_matching_waiting_lock(self):
        self.r['deadlock']['snapshot_before_cycle']['locks']=[x for x in self.r['deadlock']['snapshot_before_cycle']['locks'] if x['LOCK_STATUS']!='WAITING']
        with self.assertRaises(AssertionError):validate(self.r)
    def test_timeout_cannot_masquerade_as_deadlock(self):
        for x in self.r['deadlock']['outcomes'].values():
            if 'errno' in x:x['errno']=1205
        with self.assertRaises(AssertionError):validate(self.r)
    def test_rr_snapshot_regression_is_caught(self):
        self.r['isolation'][1]['ordinary_after_locking_read']=200
        with self.assertRaises(AssertionError):validate(self.r)
    def test_changed_query_rows_are_caught(self):
        self.r['indexes']['variants'][0]['rows'][0]['id']=-1
        with self.assertRaises(AssertionError):validate(self.r)
    def test_missing_samples_are_not_success(self):
        self.r['indexes']['variants'][0]['timings_ms']=[]
        with self.assertRaises(AssertionError):validate(self.r)
    def test_cleanup_regression_is_caught(self):
        self.r['cleanup']['remaining_lab_locks']=1
        with self.assertRaises(AssertionError):validate(self.r)
    def test_repeat_dataset_and_semantics(self):
        b=json.loads((ROOT/'records/run-repeat.json').read_text())
        self.assertEqual(self.r['indexes']['dataset_sha256'],b['indexes']['dataset_sha256'])
        self.assertEqual(self.r['deadlock']['final_values'],b['deadlock']['final_values'])
        self.assertEqual([v['result_sha256'] for v in self.r['indexes']['variants']],[v['result_sha256'] for v in b['indexes']['variants']])


if __name__=='__main__':unittest.main()
