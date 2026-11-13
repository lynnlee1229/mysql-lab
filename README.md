# MySQL Lab

Real MySQL transactions, lock evidence and query plans. A public MIT companion to [Lynn Lee's bilingual MySQL Lab](https://lynnlee1229.github.io/mysql-lab/en/). [中文指南](README.zh-CN.md).

The website reads saved executions. It never connects a browser to MySQL. Download this repository to change SQL, develop the runner and debug real concurrent sessions. It contains only synthetic data, audited records and Lab-specific code; the complete homepage source is private.

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
python scripts/build_site.py
python scripts/check_site.py
python -m http.server 18911 --bind 127.0.0.1 --directory dist
```

Open `http://127.0.0.1:18911/mysql-lab/en/` or `/mysql-lab/zh/`. The allowlist exporter consumes only `records/run-clean.json`, `records/run-repeat.json`, `records/verification.json` and four named site assets. It never copies `.local/`, raw logs, credentials or authoring source. The static manifest hashes every exported file. Homepage CI only needs the committed export, never a local absolute directory.

CI actually starts the pinned MySQL image on a clean volume, executes both runs across stop/start, validates measured reports, tests adversarial baseline regressions and checks the static export. It retains only sanitized JSON artifacts and explicitly removes its own resources. The local release history is in `VALIDATION.md`; the public lifecycle evidence is in `records/verification.json`.

## Reading results correctly

Timeline timestamps are measured offsets from each experiment, not simulated durations. The deadlock victim may change. A lock-table snapshot is taken before closing the cycle, because the detector resolves a complete cycle immediately; the saved latest-deadlock excerpt captures the cycle. Actor labels replace thread identifiers, while memory-address lock IDs are omitted.

The query benchmark has no cold-cache control, randomized crossover, concurrent workload or production sizing claim. Client samples include fetch and loopback overhead; `EXPLAIN ANALYZE` is a separate real server execution. Covering projection omits `amount_cents`, so compare its full hash only with the expression rewrite, not with the wider projection.

References: [InnoDB deadlock example](https://dev.mysql.com/doc/refman/8.4/en/innodb-deadlock-example.html), [lock waits](https://dev.mysql.com/doc/refman/8.4/en/performance-schema-data-lock-waits-table.html), [isolation levels](https://dev.mysql.com/doc/refman/8.4/en/innodb-transaction-isolation-levels.html), [EXPLAIN](https://dev.mysql.com/doc/refman/8.4/en/explain.html). No official text or documentation is bundled; the implementation and synthetic experiment are MIT licensed.
