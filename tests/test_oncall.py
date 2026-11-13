"""Measured-baseline adversarial checks; the baseline is produced by real MySQL."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.invariant_oracle import assess, serial_outcomes
from scripts.validate_oncall import validate
from scripts.curriculum import load


class OnCall(unittest.TestCase):
    def setUp(self):
        self.r = json.loads((ROOT / 'records/oncall-clean.json').read_text())

    def reject(self, mutate):
        mutate(self.r)
        with self.assertRaises(AssertionError):
            validate(self.r)

    def test_measured_runs(self):
        for name in ('oncall-clean.json', 'oncall-repeat.json'):
            self.assertTrue(validate(json.loads((ROOT / 'records' / name).read_text())))

    def test_independent_serial_spec(self):
        self.assertEqual(serial_outcomes(), [(0, 1), (1, 0)])
        self.assertFalse(assess([{'doctor_id': 1, 'on_call': 0}, {'doctor_id': 2, 'on_call': 0}])['serially_reachable'])

    def test_forged_success_verdict(self):
        self.reject(lambda r: r['cases'][0]['oracle'].update(invariant_holds=True, serially_reachable=True))

    def test_final_state_is_recomputed(self):
        self.reject(lambda r: r['cases'][0]['final_rows'][0].update(on_call=1))

    def test_row_identity_is_not_just_a_count(self):
        self.reject(lambda r: r['cases'][0]['final_rows'][0].update(doctor_id=2))

    def test_missing_wait_is_rejected(self):
        self.reject(lambda r: r['cases'][1]['lock_evidence']['snapshot'].update(waits=[]))

    def test_no_false_granted_lock_proof(self):
        c = self.r['cases'][1]
        c['lock_evidence']['snapshot']['locks'] = [x for x in c['lock_evidence']['snapshot']['locks'] if x['LOCK_STATUS'] != 'WAITING']
        with self.assertRaises(AssertionError): validate(self.r)

    def test_late_guard_rr_is_not_called_safe(self):
        c = next(c for c in self.r['cases'] if c['strategy'] == 'late_guard' and c['level'] == 'REPEATABLE READ')
        c['decisions']['B']['observed_count'] = 1
        with self.assertRaises(AssertionError): validate(self.r)

    def test_missing_read_barrier(self):
        self.reject(lambda r: r['cases'][0].update(initial_counts={}))

    def test_bind_parameter_identity(self):
        e = next(e for e in self.r['cases'][0]['timeline'] if e['action'] == 'returned' and 'parameters' in e)
        e['parameters'] = [999]
        with self.assertRaises(AssertionError): validate(self.r)

    def test_incomplete_matrix(self):
        self.reject(lambda r: r['cases'].pop())

    def test_cleanup(self):
        self.reject(lambda r: r['cleanup'].update(workers_joined=False))

    def test_course_links_and_exercises(self):
        data = load()
        self.assertEqual({c['school'] for c in data['courses']}, {'Carnegie Mellon University', 'Massachusetts Institute of Technology'})
        self.assertEqual({u['id'] for u in data['units']}, {'u1', 'u2', 'u3', 'u4', 'u5', 'u6'})


if __name__ == '__main__': unittest.main()
