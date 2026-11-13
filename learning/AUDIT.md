# Depth audit — 2026-11-14

The existing code and accepted real records were read before selecting this work.

| Gap | Existing evidence | Decision |
| --- | --- | --- |
| Isolation without a business invariant | `scripts/experiments.py:isolation` checks reads of one existing primary-key row, with no writes by the reader. It cannot reveal cross-row write skew. | Highest priority: add a fixed-roster withdrawal rule, independent serial specification, concurrent counterexample and locking controls. |
| No structured university learning route | The existing guides link MySQL reference documentation but have no school/course/term/lecture-to-exercise catalog. | Add two verified university course editions, six units and offline/browser search. |
| SQL changes lack a bounded exercise | The runner is public and editable, but learners must modify the entire original experiment module. | Add `sql/oncall.json`, `--sql-file`, an equivalent rewrite and a failing lock-removal control. |
| Successful statements can hide semantic failure | Existing validators check deadlocks, expected read values and matching query hashes. No independent business-state oracle exists. | Recompute legal serial terminal states and actual final rows; reject fabricated verdicts, missing waits, wrong doctor bindings and incomplete repetitions. |

Preserve the accepted deadlock, same-order, read-view, error-path and index baselines. The new exercise uses separate `oncall_guard` and `oncall_roster` tables in the existing synthetic schema. No new database, public SQL endpoint, model call or paid dependency is introduced.

The catalog links official materials. The roster scenario is a classic write-skew teaching pattern; this repository's SQL, orchestration, serial oracle and guided exercises are independently authored. They are not answers to CMU BusTub or MIT GoDB assignments. In particular, MIT's no-public-solutions rule is retained in the course-access notes.

The selected scope leaves skewed optimizer statistics, missing-key/range phantoms, dynamic roster membership, crash recovery and load/cold-cache benchmarking for future work. Terminal-state equality to the serial oracle is necessary evidence for this rule, not a general history-serializability checker.
