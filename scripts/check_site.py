#!/usr/bin/env python3
"""Independent export, manifest, privacy, local-link and language checks."""
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import urlparse, urljoin, unquote

ROOT=Path(__file__).resolve().parents[1]
DIST=ROOT/'dist'
OUT=DIST/'mysql-lab'


class Page(HTMLParser):
    def __init__(self):super().__init__();self.links=[];self.ids=set();self.h1=0;self.lang='';self.alt=set()
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='h1':self.h1+=1
        if tag=='html':self.lang=a.get('lang')
        if a.get('id'):self.ids.add(a['id'])
        if tag=='link' and a.get('rel')=='alternate':self.alt.add(a.get('hreflang'))
        for k in ('href','src'):
            if a.get(k):self.links.append(a[k])


def main():
    manifest=json.loads((OUT/'manifest.json').read_text())['files']
    actual={str(p.relative_to(OUT)) for p in OUT.rglob('*') if p.is_file()}
    assert actual == set(manifest)|{'manifest.json'}
    for name,digest in manifest.items():assert sha256((OUT/name).read_bytes()).hexdigest()==digest
    forbidden=re.compile(r'/Users/|/home/|localhost:[0-9]+|mysql://|sk-proj-|gh[pousr]_[A-Za-z0-9]|-----BEGIN|MYSQL_(?:ROOT_)?PASSWORD=.{16,}|raw-local-only/.*\.txt')
    for p in OUT.rglob('*'):
        if not p.is_file() or p.suffix in ('.ico','.jpeg'):continue
        assert not forbidden.search(p.read_text()),f'Forbidden public data in {p.name}'
    pages={}
    for p in OUT.rglob('*.html'):
        parser=Page();parser.feed(p.read_text());pages[p]=parser
        if p!=OUT/'index.html':
            assert parser.h1==1 and parser.lang in ('en','zh-CN')
            assert {'en','zh-CN','x-default'} <= parser.alt
    for p,parser in pages.items():
        for link in parser.links:
            u=urlparse(urljoin('https://lynnlee1229.github.io/'+str(p.relative_to(DIST)),link))
            if u.netloc!='lynnlee1229.github.io' or not u.path.startswith('/mysql-lab/'):continue
            target=DIST/unquote(u.path).lstrip('/')
            if target.is_dir():target/='index.html'
            assert target.exists(),f'Broken link {p.name}: {link}'
            if u.fragment and target in pages:assert unquote(u.fragment) in pages[target].ids
    print(f'PASS: {len(pages)} HTML pages; bilingual metadata, links, anchors, privacy, exact allowlist and hashes.')


if __name__=='__main__':main()
