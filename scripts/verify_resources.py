"""Fetch public official links, save only status/type/hash; never bundle course PDFs."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.curriculum import load


def main():
    data = load()
    urls = {x['url'] for x in data['resources']}
    for c in data['courses']:
        urls.update(v for k, v in c.items() if k == 'url' or k.endswith('_url'))
    urls.update(x['url'] for x in data['edition_checks'])
    checks = []
    for url in sorted(urls):
        p = subprocess.run(['curl', '--fail', '--silent', '--show-error', '--location', '--max-time', '30',
                            '--write-out', '\n%{http_code}|%{content_type}', url], capture_output=True, check=True)
        body, meta = p.stdout.rsplit(b'\n', 1)
        code, content_type = meta.decode().split('|', 1)
        assert code == '200' and len(body) > 100
        if url.endswith('.pdf'):
            assert body.startswith(b'%PDF-'), 'Expected a PDF, not a login or error page'
        checks.append({'url': url, 'http_status': int(code), 'content_type': content_type,
                       'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()})
    out = ROOT / 'records/course-verification.json'
    out.write_text(json.dumps({'format': 'mysql-lab-resource-check/v1', 'verified_at': datetime.now(timezone.utc).isoformat(),
                              'scope': 'Public unauthenticated GET; PDF signatures checked. No enrollment, recording-access or future-publication claim.',
                              'checks': checks}, indent=2) + '\n')
    print(f'PASS: {len(checks)} official public resources, bodies not retained')


if __name__ == '__main__':
    main()
