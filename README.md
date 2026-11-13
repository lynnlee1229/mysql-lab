# MySQL Lab

Real MySQL transactions, lock evidence and query plans. A public MIT companion to [Lynn Lee's bilingual MySQL Lab](https://lynnlee1229.github.io/mysql-lab/en/). [中文指南](README.zh-CN.md).

The website reads saved executions. It never connects a browser to MySQL. Download this repository to change SQL, develop the runner and debug real concurrent sessions. It contains only synthetic data, audited records and Lab-specific code; the complete homepage source is private.

Start with the [course route and six runnable learning units](https://lynnlee1229.github.io/mysql-lab/en/learn/), then [the business-invariant exercise](https://lynnlee1229.github.io/mysql-lab/en/oncall/). The searchable [resource catalog](learning/resources.json) records exact course numbers, editions, prerequisites, public-access conditions, lecture locations and verification dates for CMU 15-445/645 and MIT 6.5830/6.5831 Spring 2026. `python scripts/curriculum.py MVCC` searches it offline. University reading access is separate from enrollment, credit, paid textbooks and graded submissions; these SQL exercises are independent of university assignments.

## Run locally

Requirements: Python 3.11+, a healthy Docker Engine, Compose v2 or standalone `docker-compose`, two CPU cores, 2 GiB available engine memory and 2 GiB free disk. MySQL itself is limited to two CPUs and 1 GiB, with a 128 MiB InnoDB buffer pool. The exact official MySQL 8.4 patch and multi-platform image digest are in `image-lock.json` and `compose.yaml`.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python lab.py doctor
python lab.py start --port 13316
python lab.py run
python lab.py stop
```

On macOS, an optional dedicated engine avoids sharing other experiments:

```sh
colima start --profile mysql-lab --cpu 2 --memory 2 --disk 12 --activate=false
export DOCKER_CONTEXT=colima-mysql-lab
```

Keep `DOCKER_CONTEXT` set for every Lab command when using this profile. The default Docker context is otherwise respected. Never prune unrelated resources to make room.

`start` generates random passwords in ignored, restricted-permission `.local/config.json` and `.local/compose.env`. It creates only the `lynn-mysql-lab` Compose project, its network and named volume. MySQL is published only at `127.0.0.1:13316`; choose a different free port on first start if needed. The laboratory user can access the synthetic schema and read Performance Schema/transaction diagnostics. It has no access to business databases.

`run` deliberately drops and recreates `a`, `b` and `events` in its dedicated `mysql_lab` schema. Do not adapt its connection to a real business database. A failed run exits nonzero and produces no success report. Successful sanitized reports are under `.local/runs/<timestamp>/run.json`; the raw deadlock section remains in `raw-local-only/` for local debugging. Public reports exclude credentials, host identifiers, paths and connection lines.

## Experiments

1. **Opposite-order deadlock and same-order control.** A and B lock separate tables. The coordinator submits A's second update, then waits for a real `data_lock_waits` edge before releasing B's conflicting update. The automatic detector stays enabled. A before-cycle `data_locks`/`data_lock_waits` snapshot, a latest-deadlock excerpt, error 1213, transaction outcomes and final values establish the result. A consistent lock order still waits, but both transactions commit.
2. **READ COMMITTED and REPEATABLE READ.** A reads 100; B commits 200; A repeats a plain read, a `FOR UPDATE` read, then another plain read. A never writes. RC plain reads advance to 200; RR plain reads retain 100; both locking reads see 200. A's locking read genuinely blocks B's later update to 300 until A commits. This tests an existing unique row, not range/gap/phantom/DML behavior.
3. **Indexes and actual execution.** Seed 20261113 generates 60,000 rows. Compare full scan and indexed noncovering reads with identical hashes, then covering range and `DATE_FORMAT` predicates with identical hashes. Every variant includes `EXPLAIN FORMAT=JSON`, `EXPLAIN ANALYZE`, complete returned rows, one warm-up and seven timed fetches. Fixed ordering and a warm shared buffer pool are explicit limitations; numbers are observations from one machine, not capacity claims.

The runner also executes bad SQL (1064), a real one-second lock timeout (1205), and a connection-refusal probe (2003). All worker sessions close, unfinished transactions roll back and zero Lab locks remain. Barriers are conditions on completed statements or observed locks; polling delays never decide transaction ordering. Hard connection, query, observation and worker timeouts bound failure paths.

## New exercise: both commit, nobody stays on call

Two doctors each withdraw only if another remains. The business invariant is `SUM(on_call) >= 1`. The independent pure-Python specification in `scripts/invariant_oracle.py` enumerates both serial request orders, allowing only `(0,1)` and `(1,0)`. A separate autocommit observer reads actual final rows after both workers finish. This is a final-state oracle for the fixed two-request rule, not a general serializability checker.

```sh
python lab.py start
python lab.py oncall --output .local/oncall-first.json
python lab.py stop
python lab.py start
python lab.py oncall --output .local/oncall-repeat.json
python scripts/validate_oncall.py .local/oncall-first.json .local/oncall-repeat.json
python lab.py stop
```

With the dedicated Colima profile, retain `DOCKER_CONTEXT=colima-mysql-lab` for every command, as in the setup above. `oncall` resets only `oncall_guard` and `oncall_roster` in the dedicated synthetic schema. It never changes server-global isolation or detector settings. Each default run executes four strategies × two isolation levels × three repetitions, swapping doctor identities in repetition 2:

| Strategy | RC | RR | Evidence to explain |
| --- | --- | --- | --- |
| `unguarded` | both leave | both leave | Both counts return 2 before any write; row-local conditional updates affect different doctors. |
| `late_guard` | one remains | both leave | A real exclusive guard wait occurs, but RR's earlier consistent-read snapshot persists. |
| `guard_first` | one remains | one remains | No consistent read precedes the guard. The waiting follower's first count reads 1. |
| `locking_roster` | one remains | one remains | The waiting current locking read returns one active doctor; inspect actual PRIMARY locks. |

All strategies deliberately produce two commits. Approval, business correctness and commit success are separate fields. An expected counterexample counts as evidence only when the independent final-state oracle actually rejects the observed state. No timing winner is prescribed. Guard-first requires all writers to cooperate and no previous consistent read in the transaction; the row-lock control tests fixed membership, not insert/delete/range protection.

Preserve the baseline, copy `sql/oncall.json` to `.local/oncall-sql.json` and modify that copy:

```sh
cp sql/oncall.json .local/oncall-sql.json
# Edit the count query to this equivalent fixed-roster formulation:
# SELECT COALESCE(SUM(on_call),0) AS n FROM oncall_roster WHERE shift_id=1
python lab.py start
python lab.py oncall --sql-file .local/oncall-sql.json --output .local/oncall-edited.json
python lab.py stop
```

Explain why the matrix stays the same. Then remove `FOR UPDATE` from the guard query in the local copy. The runner must reject the missing B→A edge within its deadline and write no success report. This negative control tests orchestration assumptions, not a new final-state claim. Restore SQL before retrying. The live [step-by-step exercise](https://lynnlee1229.github.io/mysql-lab/en/oncall/) includes real SQL bindings, timelines, lock snapshots, the oracle and lecture mapping.

## Stop, repeat and explicit destruction

```sh
python lab.py stop       # preserves the data volume and passwords
python lab.py start      # same volume
python lab.py run        # resets only synthetic Lab tables

# Explicitly destroys only this Lab's containers, network and named data volume:
python lab.py destroy --confirm lynn-mysql-lab
```

Do not delete local password files while retaining the volume: initialization passwords persist inside MySQL. `stop` does not stop Docker. If using a dedicated Colima profile, optionally stop it afterward with `colima stop --profile mysql-lab`. No global prune command is used.

## Validate and build the public reading export

```sh
python -m unittest discover -s tests -v
python scripts/validate.py records/run-clean.json records/run-repeat.json
python scripts/validate_oncall.py records/oncall-clean.json records/oncall-repeat.json
python scripts/build_site.py
python scripts/check_site.py
python -m http.server 18911 --bind 127.0.0.1 --directory dist
```

Open `http://127.0.0.1:18911/mysql-lab/en/` or `/mysql-lab/zh/`; `/learn/` and `/oncall/` are bilingual learning entries. The allowlist exporter consumes seven explicitly named sanitized records, `learning/resources.json` and five named site assets. It never copies `.local/`, raw logs, credentials or authoring source. The static manifest hashes every exported file. Homepage CI only needs the committed export, never a local absolute directory. `python scripts/verify_resources.py` optionally refreshes public official link status/type/hashes; it retains no course document bodies and is not needed for ordinary offline validation.

CI actually starts the pinned MySQL image on a clean volume, executes both runs across stop/start, validates measured reports, tests adversarial baseline regressions and checks the static export. It retains only sanitized JSON artifacts and explicitly removes its own resources. The local release history is in `VALIDATION.md`; the public lifecycle evidence is in `records/verification.json`.

## Reading results correctly

Timeline timestamps are measured offsets from each experiment, not simulated durations. The deadlock victim may change. A lock-table snapshot is taken before closing the cycle, because the detector resolves a complete cycle immediately; the saved latest-deadlock excerpt captures the cycle. Actor labels replace thread identifiers, while memory-address lock IDs are omitted.

The query benchmark has no cold-cache control, randomized crossover, concurrent workload or production sizing claim. Client samples include fetch and loopback overhead; `EXPLAIN ANALYZE` is a separate real server execution. Covering projection omits `amount_cents`, so compare its full hash only with the expression rewrite, not with the wider projection.

References: [InnoDB deadlock example](https://dev.mysql.com/doc/refman/8.4/en/innodb-deadlock-example.html), [lock waits](https://dev.mysql.com/doc/refman/8.4/en/performance-schema-data-lock-waits-table.html), [isolation levels](https://dev.mysql.com/doc/refman/8.4/en/innodb-transaction-isolation-levels.html), [EXPLAIN](https://dev.mysql.com/doc/refman/8.4/en/explain.html). No official text or documentation is bundled; the implementation and synthetic experiment are MIT licensed.
