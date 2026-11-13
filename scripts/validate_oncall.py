"""Recompute the business oracle and audit measured scheduling/locking evidence."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.invariant_oracle import assess
from scripts.validate import snapshot


def validate(r):
    assert r['format'] == 'mysql-lab-oncall/v1'
    assert r['environment']['schema_name'] == 'mysql_lab'
    assert r['environment']['version'].startswith('8.4.')
    assert 2 <= r['repeats'] <= 5
    expected = {(i, l, s) for i in range(1, r['repeats'] + 1)
                for l in ('READ COMMITTED', 'REPEATABLE READ')
                for s in ('unguarded', 'late_guard', 'guard_first', 'locking_roster')}
    assert len(r['cases']) == len(expected)
    assert {(x['repetition'], x['level'], x['strategy']) for x in r['cases']} == expected
    for c in r['cases']:
        verdict = assess(c['final_rows'])
        assert verdict == c['oracle']
        unsafe = c['strategy'] == 'unguarded' or (c['strategy'] == 'late_guard' and c['level'] == 'REPEATABLE READ')
        assert verdict['invariant_holds'] is (not unsafe)
        assert verdict['serially_reachable'] is (not unsafe)
        doctors = {'A': 1, 'B': 2} if c['repetition'] % 2 else {'A': 2, 'B': 1}
        assert c['doctor_ids'] == doctors
        decisions = c['decisions']
        assert set(decisions) == {'A', 'B'}
        for actor, d in decisions.items():
            assert d['doctor_id'] == doctors[actor] and d['outcome'] == 'committed'
            assert d['approved'] is (d['observed_count'] > 1)
        assert decisions['A']['observed_count'] == 2
        assert decisions['B']['observed_count'] == (2 if unsafe else 1)
        expected_rows = [{'doctor_id': i, 'on_call': 0 if any(d['doctor_id'] == i and d['approved'] for d in decisions.values()) else 1} for i in (1, 2)]
        assert c['final_rows'] == expected_rows
        early = c['strategy'] in ('unguarded', 'late_guard')
        assert c['initial_counts'] == ({'A': 2, 'B': 2} if early else {})
        events = c['timeline']
        assert [e['step'] for e in events] == list(range(1, len(events) + 1))
        assert [e['elapsed_ms'] for e in events] == sorted(e['elapsed_ms'] for e in events)
        assert not any(e['action'] == 'mysql_error' for e in events)
        for actor, d in decisions.items():
            writes = [e for e in events if e['actor'] == actor and e['action'] == 'returned' and e.get('sql') == r['sql']['leave']]
            assert len(writes) == int(d['approved'])
            if writes:
                assert writes[0]['parameters'] == [d['doctor_id']]
            read_sql = r['sql']['locking_roster' if c['strategy'] == 'locking_roster' else 'count']
            reads = [e['rows'] for e in events if e['actor'] == actor and e['action'] == 'returned' and e.get('sql') == read_sql]
            assert reads
            actual_count = len(reads[-1]) if c['strategy'] == 'locking_roster' else int(reads[-1][0]['n'])
            assert actual_count == d['observed_count']
        for actor in ('A', 'B'):
            commits = [e for e in events if e['actor'] == actor and e['action'] == 'returned' and e.get('sql') == 'COMMIT']
            assert len(commits) == 1
        if early:
            barrier = next(e['step'] for e in events if e['action'] == 'barrier: both initial counts completed before writes')
            counts = [e for e in events if e['action'] == 'returned' and e.get('sql') == r['sql']['count'] and e['step'] < barrier]
            assert {e['actor'] for e in counts} == {'A', 'B'}
            assert all(e['step'] > barrier for e in events if e['action'] == 'submit' and e.get('sql') == r['sql']['leave'])
        if c['strategy'] == 'unguarded':
            assert c['lock_evidence']['snapshot'] is None
        else:
            snap = c['lock_evidence']['snapshot']
            snapshot(snap)
            target = 'oncall_roster' if c['strategy'] == 'locking_roster' else 'oncall_guard'
            assert any(w['waiting_actor'] == 'B' and w['blocking_actor'] == 'A' and w['table_name'] == target and w['index_name'] == 'PRIMARY' for w in snap['waits'])
            edge = next(e['step'] for e in events if e['action'] == 'barrier: observed lock wait')
            assert edge < next(e['step'] for e in events if e['actor'] == 'A' and e['action'] == 'submit' and e.get('sql') == 'COMMIT')
            lock_query = r['sql']['locking_roster' if c['strategy'] == 'locking_roster' else 'guard']
            acquired = next(e['step'] for e in events if e['actor'] == 'B' and e['action'] == 'returned' and e.get('sql') == lock_query)
            a_commit = next(e['step'] for e in events if e['actor'] == 'A' and e['action'] == 'submit' and e.get('sql') == 'COMMIT')
            assert acquired > a_commit
            if not early and c['strategy'] != 'locking_roster':
                for actor in ('A', 'B'):
                    locked = next(e['step'] for e in events if e['actor'] == actor and e['action'] == 'returned' and e.get('sql') == lock_query)
                    reads = [e['step'] for e in events if e['actor'] == actor and e.get('sql') == r['sql']['count']]
                    assert reads and min(reads) > locked
    assert r['cleanup'] == {'remaining_lab_locks': 0, 'workers_joined': True, 'sessions_closed': True}
    return True


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('records', nargs='+', type=Path)
    for name in parser.parse_args().records:
        validate(json.loads(name.read_text()))
    print('PASS: independent serial oracle, decisions, barriers, real waits and cleanup')
