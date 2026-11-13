"""Verify every allowlisted public export byte after Pages deployment (TLS on)."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--origin', default='https://lynnlee1229.github.io')
    p.add_argument('--output', type=Path, default=ROOT / '.local/release/live.json')
    a = p.parse_args()
    assert a.origin.startswith('https://'), 'Public verification requires HTTPS'
    export = ROOT / 'dist/mysql-lab'
    manifest = json.loads((export / 'manifest.json').read_text())['files']
    expected = {**manifest, 'manifest.json': hashlib.sha256((export / 'manifest.json').read_bytes()).hexdigest()}
    checks = []
    nonce = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
    for name, digest in sorted(expected.items()):
        url = a.origin.rstrip('/') + '/mysql-lab/' + quote(name) + '?verify=' + nonce
        response = subprocess.run(['curl', '--fail', '--silent', '--show-error', '--location', '--max-time', '30',
                                   '--retry', '2', '--retry-delay', '1', '--write-out', '\n%{http_code}', url], capture_output=True, check=True)
        body, status = response.stdout.rsplit(b'\n', 1)
        actual = hashlib.sha256(body).hexdigest()
        assert status == b'200' and actual == digest, 'Live export mismatch: ' + name
        checks.append({'path': '/mysql-lab/' + name, 'http_status': 200, 'sha256': actual})
    result = {'format': 'mysql-lab-live-check/v1', 'verified_at': datetime.now(timezone.utc).isoformat(),
              'result': 'PASS', 'origin': a.origin, 'files': checks,
              'scope': 'HTTPS GET with certificate verification; every published allowlisted byte equals the locally validated export.'}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2) + '\n')
    print('PASS: every public exported file has HTTP 200 and the expected SHA-256')


if __name__ == '__main__': main()
