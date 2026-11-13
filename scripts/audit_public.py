#!/usr/bin/env python3
"""Audit the exact Git index before a public push; never inspect private inputs."""
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]
names=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
names=[n for n in names if n]
assert names,'Stage an explicit reviewed file list before auditing.'
for name in names:
    p=ROOT/name
    assert not any(x in p.relative_to(ROOT).parts for x in ('.local','.venv','dist','raw-local-only','__pycache__'))
    if p.suffix in ('.ico','.jpeg'):continue
    s=subprocess.check_output(['git','show',':'+name],cwd=ROOT).decode()
    bad=re.compile(r'/Users/[A-Za-z0-9_.-]+/|/home/[A-Za-z0-9_.-]+/|sk-proj-[A-Za-z0-9]{8,}|gh[pousr]_[A-Za-z0-9]{12,}|-----BEGIN [A-Z ]*PRIVATE KEY|mysql://[A-Za-z0-9]+:')
    assert not bad.search(s),f'Forbidden public content: {name}'
    assert not re.search(r'(?i)(?:password|token)\s*[:=]\s*[\"\x27][A-Za-z0-9]{24,}',s),name
    if name.startswith('records/'):
        assert not any(x in s for x in ('localhost','127.0.0.1','lab_runner','raw-local-only')),name
print(f'PASS: exact public Git index audited ({len(names)} files), with no raw logs, credentials, local paths or private configuration.')
