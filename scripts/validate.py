"""Validate measured public records. Invalid/empty input never counts as success."""
import hashlib
import json
from pathlib import Path


def snapshot(s):
    assert s['waits'] and s['locks']
    for w in s['waits']:
        assert any(x['actor']==w['waiting_actor'] and x['OBJECT_NAME']==w['table_name'] and x['LOCK_STATUS']=='WAITING' for x in s['locks'])
        assert any(x['actor']==w['blocking_actor'] and x['OBJECT_NAME']==w['table_name'] and x['LOCK_STATUS']=='GRANTED' for x in s['locks'])


def validate(r):
    assert r['format'] == 'mysql-lab-run/v1' and r['assertions_passed'] is True
    assert r['environment']['version'].startswith('8.4.')
    d = r['deadlock']
    assert sorted(x['status'] for x in d['outcomes'].values()) == ['committed','rolled_back']
    assert [x['errno'] for x in d['outcomes'].values() if 'errno' in x] == [1213]
    snapshot(d['snapshot_before_cycle'])
    assert d['final_values'] == {'a':101,'b':101}
    assert r['ordered_control']['final_values'] == {'a':102,'b':102}
    assert all(v == 'committed' for v in r['ordered_control']['outcomes'].values())
    snapshot(r['ordered_control']['snapshot'])
    for x in r['isolation']:
        expected = 200 if x['level'] == 'READ COMMITTED' else 100
        assert [x[k] for k in ['ordinary_first','ordinary_after_B_commit','locking_read','ordinary_after_locking_read','final_after_release']] == [100,expected,200,expected,300]
        snapshot(x['writer_wait_snapshot'])
    assert [x['level'] for x in r['isolation']] == ['READ COMMITTED','REPEATABLE READ']
    assert [r['errors'][k] for k in ['syntax_error','lock_wait_timeout','connection_failure']] == [1064,1205,2003]
    snapshot(r['errors']['timeout_snapshot'])
    for case in [d,r['ordered_control'],*r['isolation']]:
        events=case['timeline']
        assert [x['step'] for x in events]==list(range(1,len(events)+1))
        assert [x['elapsed_ms'] for x in events]==sorted(x['elapsed_ms'] for x in events)
    actions=[x['action'] for x in d['timeline']]
    assert actions.index('barrier: observed lock wait')<actions.index('barrier: close cycle only after observed A→B wait')
    idx = r['indexes']
    assert idx['row_count'] == 60000 and idx['seed'] == 20261113
    assert [v['id'] for v in idx['variants']] == ['full_scan','composite_noncover','composite_cover','expression_month']
    for v in idx['variants']:
        assert len(v['timings_ms']) == idx['repeats'] == 7 and v['result_rows'] > 0
        assert len(v['rows']) == v['result_rows'] and v['explain_json'] and 'actual time=' in v['explain_analyze']
        digest = hashlib.sha256(json.dumps(v['rows'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
        assert digest == v['result_sha256']
    assert idx['variants'][0]['result_sha256'] == idx['variants'][1]['result_sha256']
    assert idx['variants'][2]['result_sha256'] == idx['variants'][3]['result_sha256']
    assert r['cleanup'] == {'remaining_lab_locks':0,'workers_joined':True,'sessions_closed':True}
    return True


if __name__ == '__main__':
    import sys
    for name in sys.argv[1:]:
        validate(json.loads(Path(name).read_text()))
    print('PASS: measured record invariants')
