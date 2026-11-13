#!/usr/bin/env python3
"""Scoped local lifecycle. Credentials stay in ignored .local/, never in reports."""
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
LOCAL = ROOT / '.local'
PROJECT = 'lynn-mysql-lab'


def compose(*args, capture=False):
    command = ['docker', 'compose']
    if subprocess.run(command + ['version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
        command = [shutil.which('docker-compose') or 'docker-compose']
    return subprocess.run(command + ['--project-name', PROJECT, '--env-file', str(LOCAL / 'compose.env'), '-f', str(ROOT / 'compose.yaml'), *args], cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE if capture else None)


def config(create=False, port=13316):
    path = LOCAL / 'config.json'
    if not path.exists():
        if not create:
            raise RuntimeError('No local configuration; run start first.')
        if not 1024 <= port <= 65535:
            raise ValueError('Choose a nonprivileged local TCP port.')
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', port))
        LOCAL.mkdir(exist_ok=True, mode=0o700)
        c = {'port': port, 'password': secrets.token_hex(24), 'root_password': secrets.token_hex(24)}
        path.write_text(json.dumps(c))
        path.chmod(0o600)
        env = LOCAL / 'compose.env'
        env.write_text(f"LAB_PORT={port}\nMYSQL_PASSWORD={c['password']}\nMYSQL_ROOT_PASSWORD={c['root_password']}\n")
        env.chmod(0o600)
    return json.loads(path.read_text())


def connect():
    import pymysql
    c = config()
    return pymysql.connect(host='127.0.0.1', port=c['port'], user='lab_runner', password=c['password'], database='mysql_lab', autocommit=True, connect_timeout=3, read_timeout=15, write_timeout=15, cursorclass=pymysql.cursors.DictCursor)


def doctor():
    checks = {}
    for name, cmd in [('docker', ['docker', 'info', '--format', '{{.ServerVersion}}']), ('compose', ['docker-compose', 'version'])]:
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=12)
            checks[name] = {'ok': p.returncode == 0, 'version': p.stdout.strip() if p.returncode == 0 else 'unavailable; start your local Docker engine'}
        except (OSError, subprocess.TimeoutExpired):
            checks[name] = {'ok': False, 'version': 'unavailable'}
    # A Compose v2 CLI plugin is also accepted.
    if not checks['compose']['ok']:
        p = subprocess.run(['docker', 'compose', 'version'], capture_output=True, text=True)
        checks['compose'] = {'ok': p.returncode == 0, 'version': p.stdout.strip()}
    try:
        checks['driver'] = {'ok': True, 'version': importlib.metadata.version('PyMySQL')}
    except importlib.metadata.PackageNotFoundError:
        checks['driver'] = {'ok': False, 'version': 'install requirements.txt'}
    checks['disk'] = {'ok': shutil.disk_usage(ROOT).free > 2 * 1024**3, 'minimum_free_gib': 2}
    print(json.dumps(checks, indent=2))
    return all(c['ok'] for c in checks.values())


def start(port):
    config(True, port)
    compose('up', '-d', '--wait', '--wait-timeout', '180')
    c = connect()
    try:
        with c.cursor() as cur:
            cur.execute('SELECT VERSION() AS version')
            print('Ready:', cur.fetchone()['version'], '| loopback port', config()['port'])
    finally:
        c.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['doctor', 'start', 'run', 'oncall', 'stop', 'destroy'])
    p.add_argument('--port', type=int, default=13316, help='Only used on first start')
    p.add_argument('--output', type=Path, help='Sanitized JSON output (default: ignored .local/runs/)')
    p.add_argument('--confirm', help='destroy requires the exact Compose project name')
    p.add_argument('--repeats', type=int, default=3, help='oncall: 2–5 bounded repetitions')
    p.add_argument('--sql-file', type=Path, help='oncall: editable SQL JSON (local synthetic experiment only)')
    a = p.parse_args()
    try:
        if a.command == 'doctor':
            return 0 if doctor() else 1
        if a.command == 'start':
            start(a.port)
        elif a.command == 'run':
            from scripts.experiments import run
            out = a.output or LOCAL / 'runs' / time.strftime('%Y%m%dT%H%M%S') / 'run.json'
            run(connect, out)
            print('PASS: all measured semantic assertions; sanitized result saved.')
        elif a.command == 'oncall':
            from scripts.oncall import run
            out = a.output or LOCAL / 'runs' / time.strftime('%Y%m%dT%H%M%S') / 'oncall.json'
            run(connect, out, repeats=a.repeats, sql_file=a.sql_file)
            print('PASS: measured concurrency counterexamples and locking controls; independent final-state oracle checked.')
        elif a.command == 'stop':
            config()
            compose('stop', '--timeout', '20')
            print('Stopped this Lab only; its named data volume is retained.')
        elif a.command == 'destroy':
            if a.confirm != PROJECT:
                raise ValueError(f'Destructive operation: pass --confirm {PROJECT} to remove only this Lab container/network/data volume.')
            config()
            compose('down', '--volumes', '--remove-orphans', '--timeout', '20')
            print('Removed only this Lab Compose resources. Local credentials and reports retained.')
    except Exception as e:
        # Do not print connection exceptions: they may contain local configuration.
        print(f'FAILED ({type(e).__name__}): ' + (str(e) if isinstance(e, (ValueError, AssertionError, RuntimeError)) else 'operation failed; check local engine, dependencies and port; no success result was produced.'), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
