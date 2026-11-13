#!/usr/bin/env python3
"""Explicit clean-volume acceptance. Destroys only this Lab when confirmed."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from lab import PROJECT
from scripts.validate import validate


def command(*args):
    subprocess.run([sys.executable,str(ROOT/'lab.py'),*args],cwd=ROOT,check=True)


def volume_created():
    return subprocess.check_output(['docker','volume','inspect',PROJECT+'_mysql-data','--format','{{.CreatedAt}}'],text=True).strip()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--confirm',required=True)
    a=p.parse_args()
    if a.confirm != PROJECT:raise SystemExit('Exact Lab project confirmation required')
    # Missing confirmation is also tested and must never remove the volume.
    refusal=subprocess.run([sys.executable,str(ROOT/'lab.py'),'destroy'],capture_output=True,text=True)
    assert refusal.returncode==1 and 'Destructive operation' in refusal.stderr
    command('destroy','--confirm',PROJECT)
    absent=subprocess.run(['docker','volume','inspect',PROJECT+'_mysql-data'],capture_output=True)
    assert absent.returncode!=0
    command('start')
    created=volume_created()
    outputs=[]
    batch=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
    for name in ('clean','repeat'):
        out=ROOT/'.local'/'verification'/batch/name/'run.json'
        command('run','--output',str(out))
        report=json.loads(out.read_text());validate(report)
        outputs.append(report)
        (ROOT/'records'/f'run-{name}.json').write_text(out.read_text())
        command('stop')
        assert volume_created()==created
        if name=='clean':command('start')
    assert outputs[0]['indexes']['dataset_sha256']==outputs[1]['indexes']['dataset_sha256']
    assert [v['result_sha256'] for v in outputs[0]['indexes']['variants']]==[v['result_sha256'] for v in outputs[1]['indexes']['variants']]
    ports=json.loads(subprocess.check_output(['docker','inspect',PROJECT+'-mysql-1','--format','{{json .HostConfig.PortBindings}}'],text=True))
    assert ports=={'3306/tcp':[{'HostIp':'127.0.0.1','HostPort':'13316'}]}
    status=subprocess.check_output(['docker','inspect',PROJECT+'-mysql-1','--format','{{.State.Status}}'],text=True).strip()
    assert status=='exited'
    record={'format':'mysql-lab-verification/v1','verified_at':datetime.now(timezone.utc).isoformat(),'result':'PASS','lifecycle':{'unconfirmed_destroy_refused':True,'explicit_scoped_destroy_executed':True,'volume_absent_after_destroy':True,'fresh_volume_created':True,'same_volume_retained_after_stop_start':True,'container_stopped_at_end':True,'loopback_only_port_verified':True},'runs':{name:{'sha256':hashlib.sha256((ROOT/'records'/f'run-{name}.json').read_bytes()).hexdigest(),'recorded_at':r['recorded_at'],'semantic_assertions_passed':r['assertions_passed'],'remaining_lab_locks':r['cleanup']['remaining_lab_locks']} for name,r in zip(('clean','repeat'),outputs)},'dataset_hashes_match':True,'query_result_hashes_match':True,'data_scope':'Synthetic data only; no raw logs, environment files, credentials, hostnames or local paths included.','limits':'Timing samples are local warm-buffer observations, not production benchmarks. Deadlock victim identity is not fixed.'}
    (ROOT/'records'/'verification.json').write_text(json.dumps(record,indent=2)+'\n')
    print('PASS: scoped destruction, fresh volume, real run, stop/start retention, repeated semantics and final stop.')


if __name__=='__main__':main()
