"""Measured write-skew counterexample and locking controls on a fixed two-row roster.

Both ordinary reads complete before either unguarded write. Guarded schedules
release A only after Performance Schema proves B is waiting. No sleep decides order.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from scripts.experiments import Sessions, sql, encode
from scripts.invariant_oracle import assess

ROOT = Path(__file__).resolve().parents[1]
LEVELS = ('READ COMMITTED', 'REPEATABLE READ')
STRATEGIES = ('unguarded', 'late_guard', 'guard_first', 'locking_roster')
DDL = [
    'CREATE TABLE IF NOT EXISTS oncall_guard (shift_id INT PRIMARY KEY) ENGINE=InnoDB',
    'CREATE TABLE IF NOT EXISTS oncall_roster (shift_id INT NOT NULL, doctor_id INT NOT NULL, on_call TINYINT NOT NULL, PRIMARY KEY(shift_id,doctor_id), CHECK(on_call IN (0,1))) ENGINE=InnoDB',
]
FINAL_SQL = 'SELECT doctor_id,on_call FROM oncall_roster WHERE shift_id=1 ORDER BY doctor_id'


def case(connect, observer, queries, level, strategy, repetition):
    sql(observer, 'DELETE FROM oncall_roster')
    sql(observer, 'DELETE FROM oncall_guard')
    sql(observer, 'INSERT INTO oncall_guard VALUES (1)')
    sql(observer, 'INSERT INTO oncall_roster VALUES (1,1,1),(1,2,1)')
    s = Sessions(connect)
    doctor_ids = {'A': 1, 'B': 2} if repetition % 2 else {'A': 2, 'B': 1}
    decisions, preliminary = {}, {}
    try:
        a, b = s.open('A'), s.open('B')
        for actor, c in [('A', a), ('B', b)]:
            s.execute(c, actor, f'SET SESSION TRANSACTION ISOLATION LEVEL {level}')
            s.execute(c, actor, 'START TRANSACTION')
        def count(c, actor):
            return int(s.execute(c, actor, queries['count'])[0]['n'])
        def finish(c, actor, observed):
            approved = observed > 1
            if approved:
                s.execute(c, actor, queries['leave'], (doctor_ids[actor],))
            s.execute(c, actor, 'COMMIT')
            decisions[actor] = {'doctor_id': doctor_ids[actor], 'observed_count': observed,
                                'approved': approved, 'outcome': 'committed'}
        # These early reads intentionally establish RR read views, including for
        # the flawed late-guard strategy. A later locking read cannot refresh them.
        if strategy in ('unguarded', 'late_guard'):
            preliminary = {'A': count(a, 'A'), 'B': count(b, 'B')}
            assert preliminary == {'A': 2, 'B': 2}
            s.event('coordinator', 'barrier: both initial counts completed before writes')
        if strategy == 'unguarded':
            t, result = s.worker(lambda: finish(b, 'B', preliminary['B']))
            finish(a, 'A', preliminary['A'])
            s.join(t, result)
            evidence = {'kind': 'completed-read barrier; distinct-row writes', 'snapshot': None}
        else:
            lock_query = queries['locking_roster'] if strategy == 'locking_roster' else queries['guard']
            first_rows = s.execute(a, 'A', lock_query)
            def follower():
                rows = s.execute(b, 'B', lock_query)
                n = len(rows) if strategy == 'locking_roster' else count(b, 'B')
                finish(b, 'B', n)
            t, result = s.worker(follower)
            snap = s.wait_for_edge(observer, 'B', 'A')
            s.event('coordinator', 'barrier: release A only after observed B→A wait')
            n = len(first_rows) if strategy == 'locking_roster' else count(a, 'A')
            finish(a, 'A', n)
            s.join(t, result)
            evidence = {'kind': 'real wait before leader commit', 'snapshot': snap}
        # Independent autocommit observer reads committed state after BOTH joins.
        rows = sql(observer, FINAL_SQL)
        verdict = assess(rows)
        return {'level': level, 'strategy': strategy, 'repetition': repetition,
                'doctor_ids': doctor_ids, 'initial_counts': preliminary,
                'decisions': decisions, 'final_rows': rows, 'oracle': verdict,
                'lock_evidence': evidence, 'timeline': s.events}
    finally:
        s.close()


def run(connect, output, repeats=3, sql_file=None):
    if not 2 <= repeats <= 5:
        raise ValueError('Use 2–5 bounded repetitions (both doctor orderings).')
    output = Path(output)
    if output.exists():
        raise ValueError('Output exists; preserve previous evidence and choose another path.')
    source = Path(sql_file) if sql_file else ROOT / 'sql/oncall.json'
    queries = json.loads(source.read_text())
    assert queries.pop('format') == 'mysql-lab-oncall-sql/v1'
    assert set(queries) == {'count', 'guard', 'locking_roster', 'leave'}
    observer = connect()
    try:
        env = sql(observer, 'SELECT VERSION() AS version, DATABASE() AS schema_name, @@performance_schema AS performance_schema, @@innodb_deadlock_detect AS deadlock_detect')[0]
        assert env['schema_name'] == 'mysql_lab' and env['version'].startswith('8.4.')
        assert env['performance_schema'] == 1 and env['deadlock_detect'] == 1
        for statement in DDL:
            sql(observer, statement)
        result = {'format': 'mysql-lab-oncall/v1', 'recorded_at': datetime.now(timezone.utc).isoformat(),
                  'environment': env, 'repeats': repeats, 'sql': queries, 'ddl': DDL,
                  'sql_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                  'final_observer_sql': FINAL_SQL, 'cases': []}
        for repetition in range(1, repeats + 1):
            for level in LEVELS:
                for strategy in STRATEGIES:
                    result['cases'].append(case(connect, observer, queries, level, strategy, repetition))
        n = sql(observer, "SELECT COUNT(*) AS n FROM performance_schema.data_locks WHERE OBJECT_SCHEMA='mysql_lab'")[0]['n']
        assert n == 0
        result['cleanup'] = {'remaining_lab_locks': n, 'workers_joined': True, 'sessions_closed': True}
        result = json.loads(json.dumps(result, default=encode))
        from scripts.validate_oncall import validate
        validate(result)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    finally:
        observer.close()
