# MySQL Lab

本轮新增[课程路线与六个可运行单元](https://lynnlee1229.github.io/mysql-lab/zh/learn/)和[并发撤岗业务不变量练习](https://lynnlee1229.github.io/mysql-lab/zh/oncall/)。[结构化资源清单](learning/resources.json)记录 CMU 15-445/645、MIT 6.5830/6.5831 的准确名称、2026 春季版本、先修、公开材料、具体讲次和核验日期。离线运行 `python scripts/curriculum.py 索引` 或 `python scripts/curriculum.py MVCC` 即可检索。公开阅读与学校注册、学分、收费教材及评分支持分开说明；练习是独立编写的 SQL 实验，不是大学作业解答。

## 新练习：双方提交，却无人值班

固定两名医生各申请撤岗，业务规则是“至少留一人”：`SUM(on_call) >= 1`。独立 Python 规格模型枚举两种串行请求顺序，合法终值只有 `(0,1)`、`(1,0)`。两方提交后，另一个自动提交观察者读取 MySQL 实际终值；模型不读取作者预制结果。它只检查这个规则的终态，不是通用可串行化验证器。

沿用下方隔离环境；使用专用 profile 时每条命令都保留 `DOCKER_CONTEXT=colima-mysql-lab`：

```sh
python lab.py start
python lab.py oncall --output .local/oncall-first.json
python lab.py stop
python lab.py start
python lab.py oncall --output .local/oncall-repeat.json
python scripts/validate_oncall.py .local/oncall-first.json .local/oncall-repeat.json
python lab.py stop
```

`oncall` 只重置专用合成 schema 内的 `oncall_guard`、`oncall_roster`，不修改全局隔离级别或死锁检测设置。默认每份结果运行四种策略 × 两个隔离级别 × 三轮；第二轮交换医生 ID。双方都成功提交，是否批准撤岗与是否满足业务规则分别记录。

| 策略 | RC | RR | 应检查的证据 |
| --- | --- | --- | --- |
| `unguarded` | 两人均撤岗 | 两人均撤岗 | 写入前两次计数均已返回 2；单行 `AND on_call=1` 条件不能保护跨行规则。 |
| `late_guard` | 留一人 | 两人均撤岗 | 真实独占守卫锁等待存在，但 RR 先前已建立的读视图没有被刷新。 |
| `guard_first` | 留一人 | 留一人 | 取得守卫锁前没有一致性读；等待方首次计数读到 1。 |
| `locking_roster` | 留一人 | 留一人 | 当前锁定读等待后只返回一名值班医生，并保存实际 PRIMARY 锁。 |

先预测，再运行，再解释锁与终值。保存基线后复制 `sql/oncall.json` 为 `.local/oncall-sql.json`，将 `count` 改为 `SELECT COALESCE(SUM(on_call),0) AS n FROM oncall_roster WHERE shift_id=1`，先 `python lab.py start`，再用 `python lab.py oncall --sql-file .local/oncall-sql.json --output .local/oncall-edited.json` 复跑，解释为什么固定名单下语义相同；完成后 `python lab.py stop`。

负对照：从本地副本的 `guard` 查询删除 `FOR UPDATE`。运行器应在观察期限内拒绝缺失的 B→A 等待边，且不产生成功 JSON；这验证的是调度前提失效，不是新的终值结论。恢复 SQL 后再试。

所有写入者必须遵守守卫协议，guard_first 的 RR 事务也不能更早建立一致性读快照。当前实验只有固定成员、一个班次，不推广到成员插入、删除、范围谓词或吞吐性能；不需要 API key、模型或数据库插件。完整[分步练习与真实证据](https://lynnlee1229.github.io/mysql-lab/zh/oncall/)含参数绑定、时间线、锁表、独立模型判断及具体课程映射。

新增离线验证：`python scripts/validate_oncall.py records/oncall-clean.json records/oncall-repeat.json`。`python scripts/verify_resources.py` 可选地重新核验公开官方资料，只保存状态、类型与哈希，不保存课程正文；普通实验及验证无需此联网步骤。

真实 MySQL 事务、锁证据与查询计划。[双语网页](https://lynnlee1229.github.io/mysql-lab/zh/)的 MIT 配套实验仓库。网页用于阅读保存记录，浏览器不连接数据库。下载源码后可修改 SQL、开发编排器及调试真实并发；主页整体源码保持私有。

## 本地运行

要求 Python 3.11+、Docker Engine、Compose v2 或独立 `docker-compose`，以及可用的 2 核 / 2 GiB 引擎内存、至少 2 GiB 磁盘。MySQL 容器限制为 2 核 / 1 GiB，缓冲池 128 MiB。`image-lock.json` 与 `compose.yaml` 固定实际可用的 MySQL 8.4 补丁镜像和 digest。

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python lab.py doctor
python lab.py start --port 13316
python lab.py run
python lab.py stop
```

macOS 可按需建立独立运行环境，避免与其他实验共享引擎：

```sh
colima start --profile mysql-lab --cpu 2 --memory 2 --disk 12 --activate=false
export DOCKER_CONTEXT=colima-mysql-lab
```

使用该 profile 时，所有 Lab 命令都应保留 `DOCKER_CONTEXT`。否则使用当前 Docker context。磁盘不足时不要清理其他实验资源。

`start` 在忽略提交的 `.local/` 内生成随机密码，并限制配置文件权限。仅创建 `lynn-mysql-lab` 项目及其网络、命名数据卷，端口只绑定 `127.0.0.1:13316`。首次启动可选择其他空闲端口。实验用户仅拥有合成 schema 和诊断所需的 Performance Schema/事务读取权限。

`run` 会删除并重建专用 `mysql_lab` 中的 `a`、`b`、`events` 实验表，切勿改成业务数据库连接。成功时在 `.local/runs/<时间戳>/run.json` 保存筛选后的结果；原始死锁段落留在 `raw-local-only/`，仅供本地调试。失败返回非零状态，不会生成成功报告。公开记录不含密码、路径、主机标识或连接行。

## 三个实验

1. **反向加锁死锁与同顺序对照**：两边先各锁一张表；A 的第二次更新发出后，观察者必须在真实 `data_lock_waits` 看到 A → B 才放行 B 的冲突更新。自动死锁检测始终开启。成环前的锁快照、最近死锁摘录、1213 错误、事务结果和最终数值共同建立证据。同顺序对照仍会等待，但双方提交。
2. **隔离级别与读取**：A 普通读 100，B 提交 200，A 再普通读、锁定读、普通读。A 不写入。RC 后续普通读看到 200，RR 保留 100；两种隔离级别的锁定读都看到 200，并阻塞 B 后续改为 300 的更新，直至 A 提交。范围仅限已存在唯一行，不涵盖间隙、幻读或 DML 读取。
3. **索引与实际执行**：种子 20261113 生成 60,000 行。比较全表扫描与联合索引非覆盖查询的相同哈希，再比较覆盖范围查询与 `DATE_FORMAT` 改写的相同哈希。保存 `EXPLAIN FORMAT=JSON`、`EXPLAIN ANALYZE`、全部返回行及每种查询 1 次预热、7 次耗时采样。暖缓存和固定顺序是明确限制，不代表生产容量。

另外实际执行错误 SQL（1064）、真实锁等待超时（1205）和连接拒绝（2003）。结束后所有工作线程退出、会话关闭、未完成事务回滚，Lab 锁数归零。执行次序由完成条件或真实锁边控制，不靠猜测 sleep 时间。连接、查询、观察与线程等待均有超时。

## 停止、复跑与销毁

```sh
python lab.py stop       # 保留数据卷与密码
python lab.py start      # 复用相同卷
python lab.py run        # 只重置合成实验表

# 显式破坏性操作：仅删除本 Lab 的容器、网络和命名卷
python lab.py destroy --confirm lynn-mysql-lab
```

保留数据卷时不要删除本地密码文件。`stop` 不停止 Docker 引擎；如使用独立 Colima profile，可随后执行 `colima stop --profile mysql-lab`。流程不使用全局 prune。

## 验证与网页导出

```sh
python -m unittest discover -s tests -v
python scripts/validate.py records/run-clean.json records/run-repeat.json
python scripts/build_site.py
python scripts/check_site.py
python -m http.server 18911 --bind 127.0.0.1 --directory dist
```

浏览 `http://127.0.0.1:18911/mysql-lab/zh/`。导出器只读取三份指定公开记录与四个指定资产，绝不复制 `.local/`、原始日志、配置或编写源码。静态 manifest 为每个文件保存哈希。主页 CI 只依赖已提交的静态导出，无本机绝对目录依赖。

CI 会真实启动固定 MySQL、在干净卷执行实验、停止/重启后复跑、检查实测结果、反例回归测试及静态导出；只保留筛选后的 JSON，最后显式删除自己的资源。发布验证见 `VALIDATION.md` 与 `records/verification.json`。

时间线是实际执行偏移，死锁受害者可能变化。自动检测会立即解除完整环，因此锁表采集成环前快照，完整环由死锁摘录证明。线程 ID 映射为 A/B，不公开内存地址锁 ID。查询耗时没有冷缓存控制、随机交叉、并发负载或生产容量含义；覆盖投影省略了 `amount_cents`，只能和相同投影比较完整哈希。

参考：[死锁示例](https://dev.mysql.com/doc/refman/8.4/en/innodb-deadlock-example.html)、[锁等待表](https://dev.mysql.com/doc/refman/8.4/en/performance-schema-data-lock-waits-table.html)、[事务隔离](https://dev.mysql.com/doc/refman/8.4/en/innodb-transaction-isolation-levels.html)、[EXPLAIN](https://dev.mysql.com/doc/refman/8.4/en/explain.html)。仓库仅链接官方资料，不打包文档原文。
