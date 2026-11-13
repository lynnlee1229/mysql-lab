"""Run the documented on-call loop, SQL rewrite, negative control and old regression.

Uses the selected Docker context and the existing dedicated Lab volume; never
destroys a volume. Stops only the Lab container in finally. Course checks are offline.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lab import PROJECT, config, connect
from scripts.experiments import sql
from scripts.validate import validate as old_validate
from scripts.validate_oncall import validate


def command(*args):
    subprocess.run([sys.executable, str(ROOT / 'lab.py'), *args], cwd=ROOT, check=True)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def semantics(r):
    return [{k: c[k] for k in ('level', 'strategy', 'repetition', 'doctor_ids', 'decisions', 'final_rows', 'oracle')} for c in r['cases']]


def inspect(template):
    return subprocess.check_output(['docker', 'inspect', PROJECT + '-mysql-1', '--format', template], text=True).strip()


def main():
    batch = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
    work = ROOT / '.local/oncall-verification' / batch
    work.mkdir(parents=True)
    start = datetime.now(timezone.utc).isoformat()
    try:
        command('start')
        # Establish the exact Compose project and loopback mapping before running SQL.
        assert inspect('{{index .Config.Labels "com.docker.compose.project"}}') == PROJECT
        ports = json.loads(inspect('{{json .HostConfig.PortBindings}}'))
        assert ports == {'3306/tcp': [{'HostIp': '127.0.0.1', 'HostPort': str(config()['port'])}]}
        volume = subprocess.check_output(['docker', 'volume', 'inspect', PROJECT + '_mysql-data', '--format', '{{.CreatedAt}}'], text=True).strip()
        runs = []
        for name in ('clean', 'repeat'):
            path = work / (name + '.json')
            command('oncall', '--output', str(path))
            r = json.loads(path.read_text()); validate(r); runs.append(r)
            command('stop')
            same_volume = subprocess.check_output(['docker', 'volume', 'inspect', PROJECT + '_mysql-data', '--format', '{{.CreatedAt}}'], text=True).strip()
            assert same_volume == volume
            command('start')
        assert semantics(runs[0]) == semantics(runs[1])
        queries = json.loads((ROOT / 'sql/oncall.json').read_text())
        queries['count'] = 'SELECT COALESCE(SUM(on_call),0) AS n FROM oncall_roster WHERE shift_id=1'
        edited = work / 'equivalent-sql.json'; edited.write_text(json.dumps(queries))
        rewrite = work / 'rewrite.json'
        command('oncall', '--sql-file', str(edited), '--output', str(rewrite))
        assert semantics(json.loads(rewrite.read_text())) == semantics(runs[0])
        queries['guard'] = queries['guard'].replace(' FOR UPDATE', '')
        broken = work / 'missing-lock-sql.json'; broken.write_text(json.dumps(queries))
        missing = work / 'must-not-exist.json'
        negative = subprocess.run([sys.executable, str(ROOT / 'lab.py'), 'oncall', '--repeats', '2', '--sql-file', str(broken), '--output', str(missing)], cwd=ROOT, capture_output=True, text=True, timeout=30)
        assert negative.returncode == 1 and not missing.exists()
        assert 'Expected real lock wait was not observed before deadline' in negative.stderr
        observer = connect()
        try:
            remaining = sql(observer, "SELECT COUNT(*) AS n FROM performance_schema.data_locks WHERE OBJECT_SCHEMA='mysql_lab'")[0]['n']
            assert remaining == 0
        finally:
            observer.close()
        old = work / 'original-regression.json'
        command('run', '--output', str(old))
        original = json.loads(old.read_text()); old_validate(original)
        baseline = json.loads((ROOT / 'records/run-clean.json').read_text())
        assert original['indexes']['dataset_sha256'] == baseline['indexes']['dataset_sha256']
        assert [v['result_sha256'] for v in original['indexes']['variants']] == [v['result_sha256'] for v in baseline['indexes']['variants']]
        for name in ('clean', 'repeat'):
            (ROOT / 'records' / ('oncall-' + name + '.json')).write_bytes((work / (name + '.json')).read_bytes())
        record = {'format': 'mysql-lab-oncall-verification/v1', 'started_at': start,
                  'verified_at': datetime.now(timezone.utc).isoformat(), 'result': 'PASS',
                  'runtime': 'real MySQL 8.4; existing dedicated volume, not a new clean-volume claim',
                  'first_repeat_semantics_equal': True, 'same_volume_retained': True,
                  'loopback_only_project_mapping_checked': True,
                  'runs': {n: {'sha256': digest(work / (n + '.json')), 'cases': len(runs[i]['cases'])} for i, n in enumerate(('clean', 'repeat'))},
                  'equivalent_rewrite': {'sql': queries['count'], 'matrix_semantics_equal': True, 'sha256': digest(rewrite)},
                  'negative_control': {'change': 'guard FOR UPDATE removed', 'exit_code': negative.returncode,
                                       'success_report_absent': True, 'reason': 'Expected real lock wait was not observed before deadline',
                                       'remaining_lab_locks': remaining},
                  'original_regression': {'all_original_semantic_assertions_passed': True, 'dataset_and_result_hashes_equal_baseline': True,
                                          'sha256': digest(old), 'cleanup': original['cleanup']},
                  'limits': 'Fixed roster; all writers cooperate with a guard; guard-first RR has no earlier consistent read. Terminal-state oracle is not a general history checker. No performance comparison.'}
    finally:
        command('stop')
    assert inspect('{{.State.Status}}') == 'exited'
    record['container_stopped_at_end'] = True
    (ROOT / 'records/oncall-verification.json').write_text(json.dumps(record, indent=2) + '\n')
    print('PASS: documented first/repeat loop, editable SQL, missing-lock rejection, old regression and scoped stop')


if __name__ == '__main__': main()
