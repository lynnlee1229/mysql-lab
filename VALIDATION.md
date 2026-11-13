# MySQL Lab 1.0 validation

Date: 2026-11-13, Asia/Shanghai. Public data is entirely synthetic.

## Runtime and lifecycle actually executed

- Pulled the official MySQL 8.4.13 image and pinned its registry digest in image-lock.json. SELECT VERSION() returned 8.4.13 on Linux ARM64.
- The pre-existing Docker VM had insufficient disk. No volumes or containers from other projects were removed. A dedicated Colima profile with 2 CPUs, 2 GiB RAM and a separate 12 GiB data disk hosted this experiment. The MySQL container was limited to 2 CPUs / 1 GiB, with a 128 MiB buffer pool.
- Confirmed unqualified destruction is refused. Explicitly removed only the disposable lynn-mysql-lab project and volume; verified the volume was absent; initialized a new volume; ran all experiments; stopped MySQL; verified the volume was retained; restarted; repeated all experiments; verified matching dataset and result hashes; stopped the container again, retaining the data volume.
- Verified Docker's actual port mapping is only 127.0.0.1:13316. No public database is deployed.
- The first implementation smoke run exposed a date serialization error; it failed visibly without a success report. Conversion was fixed before the accepted clean/repeat runs. A later review tightened snapshot collection to read waits before locks while the coordinator holds the barrier, and both accepted runs were repeated from a fresh volume. Validation now requires a matching WAITING and GRANTED lock for every saved wait edge.

## Measured results

- Opposite-order updates: A committed, B was rolled back by real InnoDB deadlock detection with error 1213 in both accepted runs. Captured six lock rows, the real A → B wait edge, a latest-deadlock SQL/lock/victim excerpt and final values a=101, b=101. Victim identity is not guaranteed across runs.
- Same-order control: observed B → A wait; both committed; a=102, b=102.
- READ COMMITTED ordinary/locking reads: 100 → 200 → 200 → 200. REPEATABLE READ: 100 → 100 → 200 → 100. In both levels, A's FOR UPDATE blocked B's later update until commit; final value was 300.
- Fixed seed 20261113 generated 60,000 rows. All query variants returned the same 55 IDs/dates. Full scan and composite noncovering results had equal hashes; covering range and expression-month results had equal hashes. EXPLAIN ANALYZE observed 60,000 table rows for the scan, 55 range rows, and 608 tenant/status index candidates for the month expression.
- Actual failure paths: syntax error 1064; observed lock wait followed by timeout 1205; non-listening loopback connection refusal 2003. All workers joined and sessions closed. Zero remaining Lab locks after both runs.

Client wall-clock samples include fetch, with one warm-up and seven measured samples per variant. Clean-run measurements in ms:

| Variant | Rows | Median | p95 nearest rank |
| --- | ---: | ---: | ---: |
| full_scan | 55 | 15.407 | 16.409 |
| composite_noncover | 55 | 0.917 | 1.11 |
| composite_cover | 55 | 0.712 | 1.002 |
| expression_month | 55 | 1.006 | 2.678 |

These are local warm-buffer observations. Fixed variant ordering, no cold-cache controls, no randomized crossover, no production-capacity claim. Covering projection omits amount_cents; full hashes are compared only within matching projections.

## Tests and browser acceptance

- Nine regression/adversarial tests passed against the measured baselines, including forged timeout-as-deadlock, missing real waits/WAITING locks, wrong RR reads, altered result rows, missing samples and incomplete cleanup.
- Strict public-record validation, Python compilation and JavaScript syntax checks passed.
- Export built six prerendered EN/ZH pages and one English-default redirect. Exact export allowlist, SHA-256 manifest, local links/anchors, canonical/hreflang and privacy checks passed.
- In real Chrome, switched clean/repeat records, opposite/same-order/RC/RR timelines, timeline steps and index variants. Selected actual plans and real lock tables appeared. A copied deep link retained record/case/step/query selections across languages.
- Browser-downloaded JSON was independently checked byte-for-byte against the selected measured record. The downloaded CSV contained all 28 exact query samples and hashes.
- At 390 CSS pixels, English and Chinese workbenches and both Chinese guide/method pages had document scrollWidth=390; wide tables and SQL scroll internally. Saved screenshots remain in ignored local browser evidence.
- Temporarily removed a local selected record to test HTTP 404. The UI showed failure, disabled exports/inspection and cleared measurements; restored the file and verified recovery. Normal successful reads had no JavaScript runtime errors.

## Public boundary and CI

The exact staged Git index is audited by scripts/audit_public.py before its public push. No credentials, .local configuration, raw logs, host identifiers, absolute local paths, real contacts or business data are included. Only the independent MIT companion is public; the complete homepage source stays private.

GitHub Actions runs a real clean-volume MySQL experiment and stop/start repeat, validates their reports, runs the nine baseline tests, audits tracked source and builds/checks the static site. It uploads only sanitized JSON and explicitly destroys its own CI resources. Independent real Linux x86_64 CI run passed on companion commit b5dd61c: https://github.com/lynnlee1229/mysql-lab/actions/runs/43424390010 . Its downloaded clean/repeat artifacts independently passed validation and matched the local dataset hash. This validates semantics across these two tested machines, not timing equivalence. Current runs: https://github.com/lynnlee1229/mysql-lab/actions

The static homepage export is generated from these frozen, audited records. Publication commits, terminal Pages status and public URL/resource/browser acceptance are persisted separately in the workspace mysql-lab release record; a source push alone is not deployment evidence.

## Re-run

```sh
python lab.py doctor
python lab.py start
python lab.py run
python lab.py stop
python -m unittest discover -s tests -v
python scripts/validate.py records/run-clean.json records/run-repeat.json
python scripts/build_site.py
python scripts/check_site.py
```

To repeat destructive clean-volume acceptance explicitly:

```sh
python scripts/verify_lifecycle.py --confirm lynn-mysql-lab
```
