"""Real MySQL session orchestration. No fixture outputs and no sleep-based ordering."""
from collections import Counter
from datetime import date, datetime, timedelta, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import random
import re
import socket
import statistics
import threading
import time

import pymysql

SEED = 20261113
ROWS = 60000
REPEATS = 7
SCHEMA = '''CREATE TABLE a (id INT PRIMARY KEY, value INT NOT NULL) ENGINE=InnoDB;
CREATE TABLE b (id INT PRIMARY KEY, value INT NOT NULL) ENGINE=InnoDB;
CREATE TABLE events (id INT PRIMARY KEY, tenant_id INT NOT NULL, status VARCHAR(12) NOT NULL,
created_at DATE NOT NULL, amount_cents INT NOT NULL, payload VARCHAR(128) NOT NULL) ENGINE=InnoDB;'''
LOCK_SQL = '''SELECT THREAD_ID, OBJECT_NAME, INDEX_NAME, LOCK_TYPE, LOCK_MODE, LOCK_STATUS, LOCK_DATA
FROM performance_schema.data_locks WHERE OBJECT_SCHEMA='mysql_lab'
ORDER BY OBJECT_NAME, THREAD_ID, LOCK_TYPE, LOCK_STATUS'''
WAIT_SQL = '''SELECT r.THREAD_ID AS waiting_thread, b.THREAD_ID AS blocking_thread,
r.OBJECT_NAME AS table_name, r.INDEX_NAME AS index_name, r.LOCK_MODE AS requested_mode,
b.LOCK_MODE AS held_mode, r.LOCK_DATA AS lock_data
FROM performance_schema.data_lock_waits w
JOIN performance_schema.data_locks r ON r.ENGINE_LOCK_ID=w.REQUESTING_ENGINE_LOCK_ID
JOIN performance_schema.data_locks b ON b.ENGINE_LOCK_ID=w.BLOCKING_ENGINE_LOCK_ID
WHERE r.OBJECT_SCHEMA='mysql_lab' ORDER BY table_name, waiting_thread'''


def sql(c, query, args=None):
    with c.cursor() as cur:
        cur.execute(query, args)
        return cur.fetchall()


def encode(obj):
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    raise TypeError(type(obj).__name__)


def canonical(obj):
    return json.dumps(obj, default=encode, sort_keys=True, separators=(',', ':'))


class Sessions:
    def __init__(self, connect):
        self.connect = connect
        self.connections = []
        self.actors = {}
        self.events = []
        self.zero = time.perf_counter_ns()
        self.guard = threading.Lock()
        self.workers = []

    def open(self, actor):
        c = self.connect()
        self.connections.append(c)
        sql(c, 'SET SESSION innodb_lock_wait_timeout=4')
        tid = sql(c, 'SELECT THREAD_ID FROM performance_schema.threads WHERE PROCESSLIST_ID=CONNECTION_ID()')[0]['THREAD_ID']
        self.actors[tid] = actor
        return c

    def event(self, actor, action, **data):
        with self.guard:
            self.events.append({'step': len(self.events)+1, 'elapsed_ms': round((time.perf_counter_ns()-self.zero)/1e6, 3), 'actor': actor, 'action': action, **data})

    def execute(self, c, actor, query, args=None):
        self.event(actor, 'submit', sql=query)
        try:
            rows = sql(c, query, args)
            self.event(actor, 'returned', sql=query, rows=rows)
            return rows
        except pymysql.MySQLError as e:
            self.event(actor, 'mysql_error', sql=query, errno=e.args[0])
            raise

    def worker(self, fn):
        result = {}
        def wrapped():
            try:
                result['value'] = fn()
            except Exception as e:
                result['exception'] = e
        t = threading.Thread(target=wrapped, daemon=True)
        self.workers.append(t)
        t.start()
        return t, result

    def join(self, t, result, timeout=8):
        t.join(timeout)
        if t.is_alive():
            raise AssertionError('Worker exceeded hard orchestration deadline')
        if 'exception' in result:
            raise result['exception']
        return result.get('value')

    def snapshot(self, observer):
        # Read the wait first, then its locks while the coordinator still holds the barrier.
        waits = sql(observer, WAIT_SQL)
        locks = sql(observer, LOCK_SQL)
        for row in locks:
            row['actor'] = self.actors.get(row.pop('THREAD_ID'), 'other')
        for row in waits:
            row['waiting_actor'] = self.actors.get(row.pop('waiting_thread'), 'other')
            row['blocking_actor'] = self.actors.get(row.pop('blocking_thread'), 'other')
        return {'source': ['performance_schema.data_locks', 'performance_schema.data_lock_waits'], 'locks': locks, 'waits': waits}

    def wait_for_edge(self, observer, waiter, blocker, timeout=3):
        deadline = time.monotonic() + timeout
        # Observation polling only. The next SQL step is gated on a real edge, not on elapsed sleep.
        while time.monotonic() < deadline:
            snap = self.snapshot(observer)
            if any(w['waiting_actor'] == waiter and w['blocking_actor'] == blocker for w in snap['waits']):
                self.event('observer', 'barrier: observed lock wait', waiting=waiter, blocking=blocker)
                return snap
            threading.Event().wait(.02)
        raise AssertionError('Expected real lock wait was not observed before deadline')

    def close(self):
        for c in self.connections:
            try:
                c.close()  # disconnect rolls back unfinished transactions, including failures
            except Exception:
                pass
        for t in self.workers:
            t.join(16)
        if any(t.is_alive() for t in self.workers):
            raise AssertionError('Session cleanup left a worker running')


def reset(observer):
    for table in ('a', 'b'):
        sql(observer, f'DELETE FROM {table}')
        sql(observer, f'INSERT INTO {table} VALUES (1,100)')


def deadlock(connect, observer, raw_dir):
    reset(observer)
    s = Sessions(connect)
    try:
        a, b = s.open('A'), s.open('B')
        for actor, c, table in [('A', a, 'a'), ('B', b, 'b')]:
            s.execute(c, actor, 'START TRANSACTION')
            s.execute(c, actor, f'UPDATE {table} SET value=value+1 WHERE id=1')
        s.event('coordinator', 'barrier: both first updates completed')
        outcomes = {}
        def second(c, actor, table):
            try:
                s.execute(c, actor, f'UPDATE {table} SET value=value+1 WHERE id=1')
                s.execute(c, actor, 'COMMIT')
                outcomes[actor] = {'status': 'committed'}
            except pymysql.MySQLError as e:
                s.execute(c, actor, 'ROLLBACK')
                outcomes[actor] = {'status': 'rolled_back', 'errno': e.args[0]}
        t, result = s.worker(lambda: second(a, 'A', 'b'))
        snap = s.wait_for_edge(observer, 'A', 'B')
        s.event('coordinator', 'barrier: close cycle only after observed A→B wait')
        second(b, 'B', 'a')
        s.join(t, result)
        status = sql(observer, 'SHOW ENGINE INNODB STATUS')[0]['Status']
        section = status.split('LATEST DETECTED DEADLOCK', 1)[1].split('\nTRANSACTIONS', 1)[0]
        (raw_dir / 'innodb-deadlock.local.txt').write_text(section)
        # Public excerpt is an allowlist of SQL and lock/victim descriptions only.
        excerpt = [line.strip() for line in section.splitlines() if re.match(r'^(UPDATE [ab] |\*\*\* \([12]\)|\*\*\* WE ROLL BACK|RECORD LOCKS .* of table `mysql_lab`)', line)]
        assert len(outcomes) == 2 and sum(o['status']=='committed' for o in outcomes.values()) == 1
        assert [o['errno'] for o in outcomes.values() if o['status']=='rolled_back'] == [1213]
        assert any('ROLL BACK' in line for line in excerpt)
        final = {table: sql(observer, f'SELECT value FROM {table} WHERE id=1')[0]['value'] for table in ('a', 'b')}
        assert final == {'a': 101, 'b': 101}
        return {'outcomes': outcomes, 'snapshot_before_cycle': snap, 'deadlock_excerpt': excerpt, 'final_values': final, 'timeline': s.events, 'assertions_passed': True}
    finally:
        s.close()


def ordered_control(connect, observer):
    reset(observer)
    s = Sessions(connect)
    try:
        a, b = s.open('A'), s.open('B')
        s.execute(a, 'A', 'START TRANSACTION')
        s.execute(a, 'A', 'UPDATE a SET value=value+1 WHERE id=1')
        s.execute(b, 'B', 'START TRANSACTION')
        def work():
            s.execute(b, 'B', 'UPDATE a SET value=value+1 WHERE id=1')
            s.execute(b, 'B', 'UPDATE b SET value=value+1 WHERE id=1')
            s.execute(b, 'B', 'COMMIT')
        t, result = s.worker(work)
        snap = s.wait_for_edge(observer, 'B', 'A')
        s.execute(a, 'A', 'UPDATE b SET value=value+1 WHERE id=1')
        s.execute(a, 'A', 'COMMIT')
        s.join(t, result)
        final = {table: sql(observer, f'SELECT value FROM {table} WHERE id=1')[0]['value'] for table in ('a', 'b')}
        assert final == {'a':102, 'b':102}
        return {'outcomes': {'A':'committed', 'B':'committed'}, 'snapshot':snap, 'final_values':final, 'timeline':s.events, 'assertions_passed':True}
    finally:
        s.close()


def isolation(connect, observer, level):
    reset(observer)
    s = Sessions(connect)
    try:
        a, b = s.open('A'), s.open('B')
        s.execute(a, 'A', f'SET SESSION TRANSACTION ISOLATION LEVEL {level}')
        s.execute(b, 'B', f'SET SESSION TRANSACTION ISOLATION LEVEL {level}')
        s.execute(a, 'A', 'START TRANSACTION')
        read = 'SELECT value FROM a WHERE id=1'
        first = s.execute(a, 'A', read)[0]['value']
        s.execute(b, 'B', 'START TRANSACTION')
        s.execute(b, 'B', 'UPDATE a SET value=200 WHERE id=1')
        s.execute(b, 'B', 'COMMIT')
        second = s.execute(a, 'A', read)[0]['value']
        locking = s.execute(a, 'A', read + ' FOR UPDATE')[0]['value']
        third = s.execute(a, 'A', read)[0]['value']
        def writer():
            s.execute(b, 'B', 'START TRANSACTION')
            s.execute(b, 'B', 'UPDATE a SET value=300 WHERE id=1')
            s.execute(b, 'B', 'COMMIT')
        t, result = s.worker(writer)
        snap = s.wait_for_edge(observer, 'B', 'A')
        s.execute(a, 'A', 'COMMIT')
        s.join(t, result)
        final = sql(observer, read)[0]['value']
        expected = 200 if level == 'READ COMMITTED' else 100
        assert (first, second, locking, third, final) == (100, expected, 200, expected, 300)
        return {'level':level, 'ordinary_first':first, 'ordinary_after_B_commit':second, 'locking_read':locking, 'ordinary_after_locking_read':third, 'final_after_release':final, 'writer_wait_snapshot':snap, 'timeline':s.events, 'assertions_passed':True}
    finally:
        s.close()


def errors(connect, observer):
    s = Sessions(connect)
    try:
        a, b = s.open('A'), s.open('B')
        try:
            sql(a, 'SELEC broken')
            raise AssertionError('Bad SQL unexpectedly succeeded')
        except pymysql.MySQLError as e:
            syntax_errno = e.args[0]
        assert syntax_errno == 1064
        sql(a, 'START TRANSACTION')
        sql(a, 'SELECT value FROM a WHERE id=1 FOR UPDATE')
        sql(b, 'SET SESSION innodb_lock_wait_timeout=1')
        def timeout():
            sql(b, 'START TRANSACTION')
            try:
                sql(b, 'UPDATE a SET value=999 WHERE id=1')
                raise AssertionError('Expected lock timeout')
            except pymysql.MySQLError as e:
                return e.args[0]
            finally:
                sql(b, 'ROLLBACK')
        t, result = s.worker(timeout)
        snapshot = s.wait_for_edge(observer, 'B', 'A')
        timeout_errno = s.join(t, result)
        assert timeout_errno == 1205
        sql(a, 'ROLLBACK')
        # Reserve a loopback port without listening. No credentials are sent to any server.
        with socket.socket() as reserved:
            reserved.bind(('127.0.0.1', 0))
            port = reserved.getsockname()[1]
            try:
                pymysql.connect(host='127.0.0.1', port=port, user='unavailable_probe', connect_timeout=1)
                raise AssertionError('Connection failure probe unexpectedly succeeded')
            except pymysql.MySQLError as e:
                connection_errno = e.args[0]
        assert connection_errno == 2003
        return {'syntax_error':syntax_errno, 'lock_wait_timeout':timeout_errno, 'connection_failure':connection_errno, 'timeout_snapshot':snapshot, 'cleanup':'explicit rollback and all worker sessions closed', 'assertions_passed':True}
    finally:
        s.close()


def distribution(values):
    v = sorted(values)
    return {'min':min(v), 'median':statistics.median(v), 'p95_nearest_rank':v[__import__('math').ceil(.95*len(v))-1], 'max':max(v)}


def indexes(observer):
    sql(observer, 'TRUNCATE TABLE events')
    rng = random.Random(SEED)
    data = []
    for i in range(1, ROWS+1):
        data.append((i, rng.randrange(64), rng.choices(['paid','new','cancelled'], [7,2,1])[0], date(2026,1,1)+timedelta(days=rng.randrange(365)), rng.randrange(100,100000), 'synthetic-' + 'x'*80))
    digest = hashlib.sha256(canonical(data).encode()).hexdigest()
    with observer.cursor() as cur:
        for start in range(0,len(data),2000):
            cur.executemany('INSERT INTO events VALUES (%s,%s,%s,%s,%s,%s)', data[start:start+2000])
    full = "SELECT id,created_at,amount_cents FROM events WHERE tenant_id=7 AND status='paid' AND created_at>='2026-10-01' AND created_at<'2026-11-01' ORDER BY created_at,id"
    cover = full.replace('id,created_at,amount_cents', 'id,created_at')
    expression = "SELECT id,created_at FROM events WHERE tenant_id=7 AND status='paid' AND DATE_FORMAT(created_at,'%Y-%m')='2026-10' ORDER BY created_at,id"
    measurements = []
    def measure(name, query):
        sql(observer, query)  # one documented warm-up per variant
        times, outputs = [], []
        for _ in range(REPEATS):
            t = time.perf_counter_ns()
            result = sql(observer, query)
            times.append(round((time.perf_counter_ns()-t)/1e6, 3))
            outputs.append(hashlib.sha256(canonical(result).encode()).hexdigest())
        assert len(set(outputs)) == 1
        plan = json.loads(next(iter(sql(observer, 'EXPLAIN FORMAT=JSON '+query)[0].values())))
        analyze = next(iter(sql(observer, 'EXPLAIN ANALYZE '+query)[0].values()))
        measurements.append({'id':name,'sql':query,'explain_json':plan,'explain_analyze':analyze,'timings_ms':times,'distribution_ms':distribution(times),'result_rows':len(result),'result_sha256':outputs[0],'rows':result})
    sql(observer, 'ANALYZE TABLE events')
    measure('full_scan', full)
    sql(observer, 'CREATE INDEX idx_tenant_status_date ON events(tenant_id,status,created_at)')
    sql(observer, 'ANALYZE TABLE events')
    measure('composite_noncover', full)
    measure('composite_cover', cover)
    measure('expression_month', expression)
    assert measurements[0]['result_sha256'] == measurements[1]['result_sha256']
    assert measurements[2]['result_sha256'] == measurements[3]['result_sha256']
    assert [{'id':r['id'],'created_at':r['created_at']} for r in measurements[0]['rows']] == measurements[2]['rows']
    stats = sql(observer, 'SELECT status,COUNT(*) AS n FROM events GROUP BY status ORDER BY status')
    selected_tenant = sql(observer, "SELECT COUNT(*) AS n FROM events WHERE tenant_id=7 AND status='paid'")[0]['n']
    return {'seed':SEED,'row_count':ROWS,'dataset_sha256':digest,'status_distribution':stats,'tenant_7_paid_rows':selected_tenant,'index_ddl':'CREATE INDEX idx_tenant_status_date ON events(tenant_id,status,created_at)', 'cache_condition':'Warm process/buffer pool; one untimed execution per variant; no cache flush; sequential fixed variant order. Host client fetch included in seven wall-clock samples; EXPLAIN ANALYZE is a separate server execution.', 'warmups':1,'repeats':REPEATS,'variants':measurements,'assertions_passed':True}


def run(connect, output):
    output = Path(output)
    if output.exists():
        raise ValueError('Output already exists; choose a new report path to preserve the previous evidence.')
    output.parent.mkdir(parents=True, exist_ok=True)
    raw_dir = output.parent / 'raw-local-only'
    raw_dir.mkdir(exist_ok=True)
    observer = connect()
    try:
        version = sql(observer, 'SELECT VERSION() AS version, @@version_compile_machine AS arch, @@innodb_buffer_pool_size AS buffer_pool_bytes, @@innodb_deadlock_detect AS deadlock_detect, @@performance_schema AS performance_schema')[0]
        assert version['version'].startswith('8.4.') and version['deadlock_detect'] == 1 and version['performance_schema'] == 1
        for table in ('events', 'a', 'b'):
            sql(observer, f'DROP TABLE IF EXISTS {table}')
        for statement in SCHEMA.split(';'):
            if statement.strip():
                sql(observer, statement)
        result = {'format':'mysql-lab-run/v1', 'recorded_at':datetime.now(timezone.utc).isoformat(), 'provenance':'Executed against a real isolated MySQL server, not a simulation. Public fields are allowlisted; raw InnoDB text remains local.', 'environment':{**version,'driver':'PyMySQL '+importlib.metadata.version('PyMySQL'),'python':platform.python_version(),'runtime':'Docker / Linux ARM64' if version['arch']=='aarch64' else 'Docker / Linux '+version['arch'], 'image':json.loads((Path(__file__).resolve().parents[1]/'image-lock.json').read_text())['image'], 'mysql_memory_limit_mib':1024, 'mysql_cpu_limit':2}, 'schema_sql':SCHEMA, 'collector_sql':{'locks':LOCK_SQL, 'waits':WAIT_SQL}}
        result['deadlock'] = deadlock(connect, observer, raw_dir)
        result['ordered_control'] = ordered_control(connect, observer)
        result['isolation'] = [isolation(connect, observer, level) for level in ('READ COMMITTED', 'REPEATABLE READ')]
        result['errors'] = errors(connect, observer)
        result['indexes'] = indexes(observer)
        remaining = sql(observer, "SELECT COUNT(*) AS n FROM performance_schema.data_locks WHERE OBJECT_SCHEMA='mysql_lab'")[0]['n']
        assert remaining == 0
        result['cleanup'] = {'remaining_lab_locks':remaining, 'workers_joined':True, 'sessions_closed':True}
        result['assertions_passed'] = True
        result = json.loads(json.dumps(result, default=encode))
        from scripts.validate import validate
        validate(result)
        output.write_text(json.dumps(result, default=encode, ensure_ascii=False, indent=2)+'\n')
    finally:
        observer.close()
