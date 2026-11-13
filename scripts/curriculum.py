"""Search the official resource catalog without a network connection or API key."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load():
    data = json.loads((ROOT / 'learning/resources.json').read_text())
    assert data['format'] == 'mysql-lab-curriculum/v1'
    assert len(data['courses']) == 2 and len(data['units']) >= 6
    courses = {c['id'] for c in data['courses']}
    resources = {x['id'] for x in data['resources']}
    assert len(resources) == len(data['resources'])
    for c in data['courses']:
        assert all(c[k] for k in ('school', 'number', 'name', 'term', 'prerequisites', 'public_access', 'enrollment', 'url', 'verified_on'))
    for x in data['resources']:
        assert x['course'] in courses | {'mysql-8.4'}
        assert x['url'].startswith('https://') and x['locator'] and x['status'] == 'published'
    for u in data['units']:
        assert set(u['resources']) <= resources and u['resources']
        assert all(u[k] for k in ('exercise', 'prediction', 'evidence', 'boundary'))
    return data


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('query', nargs='?', default='', help='Full-text query, e.g. MVCC, MIT, guard, 索引')
    a = p.parse_args()
    data = load()
    matches = {k: [x for x in data[k] if a.query.casefold() in json.dumps(x, ensure_ascii=False).casefold()]
               for k in ('courses', 'resources', 'units')}
    print(json.dumps(matches, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
