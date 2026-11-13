# MySQL Lab validation

## 1.1 depth iteration — 2026-11-14 (Asia/Shanghai)

The audit in `learning/AUDIT.md` identifies four evidence-backed gaps and selects business invariants as the implementation priority. Original accepted records are retained unchanged.

### Official learning resources

Selected CMU 15-445/645 Intro to Database Systems and MIT 6.5830/6.5831 Database Systems, both Spring 2026. `learning/resources.json` records school, accurate number/name, term, prerequisites, material access versus institutional enrollment/costs, exact lecture/reading locations and verification date. Six units have runnable commands, predictions, evidence to inspect and limits. The units are independently authored, not BusTub/GoDB assignment answers. The catalog is searchable both in the browser and offline.

Actually fetched 18 official public course/documentation URLs without credentials, checked HTTP 200 and PDF signatures, and retained status/type/body hashes in `records/course-verification.json`. No course document body is bundled. CMU Fall 2026 exists; its November 16 MVCC lecture is future-scheduled at verification and has no linked notes/slides. The completed Spring notes are used instead. Public reading does not confer registration, credit, staff support, graded access or rights to redistribute textbooks.

### Measured concurrency loop

Ran `python scripts/verify_oncall.py` on the existing dedicated MySQL 8.4.13 Colima profile and its existing volume, at loopback port 13316. This is not a fresh-volume claim. The script actually executes the documented start/run/stop/start/repeat steps, equivalent SQL rewrite, missing-lock negative control, original-suite regression and final scoped stop. It checks the Compose project and actual loopback mapping before SQL.

The business rule is at least one of two fixed doctors remains on call. An independent pure-Python specification enumerates both serial withdrawal orders; only `(0,1)` and `(1,0)` are legal terminal states. An independent autocommit observer reads actual final rows after both participants finish. It checks IDs and flags, not just a count or the runner's asserted verdict. This is a terminal-state oracle for this rule, not a general history-serializability checker.

Observed in every repetition and after stop/start:

| Strategy | READ COMMITTED | REPEATABLE READ | What the evidence establishes |
| --- | --- | --- | --- |
| unguarded | 0 remain | 0 remain | Both real reads returned 2 before either distinct-row conditional update; both commit, but the terminal state violates the invariant and serial specification. |
| late_guard | 1 remains | 0 remain | Real B→A exclusive guard wait precedes A's commit. RR's earlier snapshot persists; acquiring the lock did not make its next plain count current. |
| guard_first | 1 remains | 1 remains | No consistent read precedes the guard. The waiting follower's first count after the leader commits returns 1. |
| locking_roster | 1 remains | 1 remains | Real PRIMARY record-lock wait, followed by a current locking read returning one active doctor; only one withdrawal is approved. |

Each saved run contains three repetitions, swapping doctor identities in repetition 2. First/repeat decisions, final rows and oracle verdicts match exactly. Every case has two commits; approval is separately recorded. Successful runs left zero Lab locks and joined/closed all workers/sessions. Lock modes are observed values, not fixed expected modes or performance claims. Saved records are `records/oncall-clean.json` and `records/oncall-repeat.json`; hashes and lifecycle evidence are in `records/oncall-verification.json`.

Changed count SQL to `SELECT COALESCE(SUM(on_call),0) AS n FROM oncall_roster WHERE shift_id=1` and actually reran the complete matrix with `--sql-file`; semantics matched. Removed `FOR UPDATE` from the guard in a separate local copy: the observer rejected the absent real wait within its deadline, the process exited 1, no success JSON appeared, and a subsequent independent check found zero locks. This negative control establishes failure of the required scheduling premise, not a new final-state theorem.

The original deadlock/read-view/error/index suite was actually rerun. All original semantic assertions passed; dataset and result hashes matched the accepted baseline. No old success capability was replaced with a fixture. The nine original and thirteen new regression/adversarial checks pass, including fabricated oracle success, changed final rows, wrong doctor bindings, missing waits/WAITING locks, missing repetitions and incomplete cleanup.

### Reading export and browser acceptance

The independently named export allowlist checks exact files, SHA-256, source/catalog equality, measured-record hashes, recomputed invariant verdicts, privacy, links, anchors and bilingual metadata. New course and concurrency entries are reachable from both language navigations and the existing workbench/runbook. Existing record switching and workbench assets remain available.

Actual Chrome acceptance: English `guard` search returns the two corresponding units; an absent query returns zero; clearing restores all eight course/unit entries. Chinese `索引` search works. Chinese RR late-guard and locking-roster details show real terminal states, approvals, PRIMARY locks and executed parameterized SQL. At 390 CSS pixels both new Chinese pages have `document.scrollWidth=390`, with wide tables/SQL scrolling internally. Public deployment status is recorded separately after Pages and live verification; a source commit alone is not a deployment claim.

### Reproduce and boundaries

```sh
python scripts/verify_oncall.py
python -m unittest discover -s tests -v
python scripts/validate_oncall.py records/oncall-clean.json records/oncall-repeat.json
python scripts/curriculum.py MVCC
python scripts/build_site.py
python scripts/check_site.py
```

Use the dedicated Docker context when applicable, as in the README. No API key or private dataset is required. Guard-first RR assumes no earlier consistent read and all writers follow the guard protocol. Fixed membership, one shift, no insert/delete/phantom proof, no arbitrary snapshot repair, no throughput or timing comparison. The original run's query timings remain warm-buffer observations with their original limits.

## 1.0 validation (retained history)

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
