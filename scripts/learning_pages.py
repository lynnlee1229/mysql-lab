"""Bilingual learning route and measured business-invariant reading page."""
from html import escape as e
import json
from pathlib import Path

from scripts.curriculum import load
from scripts.validate_oncall import validate

ROOT = Path(__file__).resolve().parents[1]
BASE = '/mysql-lab/'
REPO = 'https://github.com/lynnlee1229/mysql-lab'


def curriculum(lang, shell, block, table):
    t = lambda en, zh: zh if lang == 'zh' else en
    data = load()
    resources = {r['id']: r for r in data['resources']}
    body = f'''<article class="prose"><p class="eyebrow">LEARNING ROUTE / VERIFIED 2026-11-14</p><h1>{t('Read. Predict. Run. Explain.', '阅读、预测、运行、解释。')}</h1>
<p class="lead">{t('Two university courses, six original exercises, one real InnoDB engine. Start with the invariant, then connect general DBMS principles to measured MySQL behavior.', '两门大学课程、六个独立练习、一个真实 InnoDB 引擎。先写业务不变量，再将通用数据库原理与 MySQL 实测行为对应起来。')}</p>
<p>{t('The selected Spring 2026 courses and PDFs were checked on November 14, 2026. We link to the originals and do not redistribute their content or publish university assignment answers. These are current offerings of long-established DBMS ideas, not claims that transactions or MVCC were invented in 2026.', '所选 2026 年春季课程及 PDF 于 2026 年 11 月 14 日核验。本站链接原始资料，不转载课程内容、不发布大学作业答案。课程介绍的是长期发展的数据库原理，事务和 MVCC 并非 2026 年新发明。')}</p>
<p><a href="{BASE}learning/resources.json">{t('Download searchable resource catalog JSON', '下载可检索资源清单 JSON')}</a> · <a href="{BASE}records/course-verification.json">{t('Unauthenticated link checks & hashes', '公开访问核验与哈希')}</a></p>
<label for="learning-filter">{t('Search courses, lecture titles, SQL or learning units', '搜索课程、讲次、SQL 或学习单元')}</label><input type="search" id="learning-filter" placeholder="MVCC / MIT / guard / 索引"><output id="learning-count" aria-live="polite"></output>
<p class="subtle">{t('Search also works offline: python scripts/curriculum.py MVCC. Your query stays in this page.', '离线也可检索：python scripts/curriculum.py MVCC。检索内容仅保留在本页面。')}</p>'''
    for c in data['courses']:
        prereq = c['prerequisites'] if lang == 'en' else (
            '官方先修：CMU 15-213/513，能编写及调试 C++17。本站改编练习需要 SQL、Python、事务和索引基础，无需完成 BusTub。' if c['id'] == 'cmu-s26' else
            '2026 春季大纲期望 6.1210（原 6.006）或同等算法基础，了解计算机系统（如 6.1800/原 6.033），能调试较大型软件；不要求数据库先修，课程实验使用 Go。')
        access = c['public_access'] if lang == 'en' else '本次无需登录即可读取课程大纲、课表及下方指定 PDF。教材章节仅是阅读指引，不代表完整教材可免费取得；录像及第三方文章的访问条件可能不同。'
        enrollment = c['enrollment'] if lang == 'en' else '公开阅读与学校注册、学分、作业提交、助教支持及费用相互独立；这里不承诺免费学分或录取。MIT 明确禁止公开其实验及习题答案。本站提供独立 SQL 练习，不实现这些课程作业。'
        body += f'''<section class="panel learning-card" data-filter-card><h2>{e(c['school'])}</h2><h3>{e(c['number'])} · {e(c['name'])}</h3><p>{e(c['term'])} · {t('verified', '核验')} {c['verified_on']}</p><p><strong>{t('Prerequisites', '先修要求')}：</strong>{e(prereq)}</p><p><strong>{t('Public reading', '公开材料')}：</strong>{e(access)}</p><p><strong>{t('Enrollment / costs', '注册与费用')}：</strong>{e(enrollment)}</p><p><a href="{c['url']}">{t('Course', '课程主页')}</a> · <a href="{c['syllabus_url']}">{t('Syllabus', '大纲')}</a> · <a href="{c['schedule_url']}">{t('Schedule / readings', '课表与阅读')}</a></p></section>'''
    zh = {
        'u1': ('先枚举两种串行撤岗顺序。如果每次都至少留一人，终值 (0,0) 可能出现吗？', '运行独立 Python 规格模型，再运行 oncall。比较模型允许的 (0,1)/(1,0) 与观察者读取的 final_rows。', '模型只覆盖固定两名医生、各一次请求，不能证明任意 SQL 的可串行化。'),
        'u2': ('哪条第二次 UPDATE 闭合等待环？同顺序对照是否也会等待？', '运行原有完整实验，检查真实等待边、匹配的 WAITING/GRANTED 锁、1213、死锁摘录和表终值。保留基线后修改加锁顺序。', '成环前的锁快照不能独立证明完整死锁环；必须结合死锁摘录与回滚结果。'),
        'u3': ('RR 的 FOR UPDATE 会刷新下一次普通 SELECT 的读视图吗？先写出四次预期读值。', '运行完整实验，核对 RC 100/200/200/200 与 RR 100/100/200/100，并确认后续写入真实等待。', '通用 MVCC 与 InnoDB 具体语句规则需要分开理解；RR 不等于可串行化。'),
        'u4': ('两边先建立快照，再竞争同一守卫行：RR 下安全吗？RC 下有什么差别？', '运行 oncall，对比 unguarded、late_guard 与 guard_first。复制 sql/oncall.json 后修改 SQL，用 --sql-file 复跑。检查独立终值与真实 B→A 守卫锁等待。', '每个写入者都要遵守协议；guard_first 的 RR 事务不能更早建立一致性读快照。未测试成员插入、删除或吞吐量。'),
        'u5': ('为什么等待后的锁定读取会只返回一名医生？单行 AND on_call=1 能保护跨行计数吗？', '检查 locking_roster 实际返回的医生 ID、PRIMARY 锁和 unguarded 更新。锁定读取对照只批准一人撤岗，单行条件仍允许两人都撤岗。', '只有固定成员和一个班次。不把当前记录锁现象推广为对幻影、范围插入或绕过协议写入的保证。'),
        'u6': ('哪些谓词能缩小索引扫描？为什么只在相同投影内比较结果哈希？', '运行完整实验，比较两组等价查询的完整结果、JSON 计划与 EXPLAIN ANALYZE 实际迭代器行数，再看七次取回耗时。', '估计行数不是实测行数，索引也不保证更快。没有随机交叉顺序、冷缓存或生产容量结论。')
    }
    for u in data['units']:
        refs = ''.join(f'<li><a href="{resources[r]["url"]}">{e(resources[r]["title"])}</a><br><span class="subtle">{e(resources[r]["locator"])}</span></li>' for r in u['resources'])
        prediction, evidence, boundary = (u['prediction'], u['evidence'], u['boundary']) if lang == 'en' else zh[u['id']]
        body += f'''<section id="{u['id']}" class="learning-card" data-filter-card><h2>{u['id'].upper()} / {e(u['title_'+lang])}</h2><ul>{refs}</ul><p><strong>{t('Predict', '先预测')}：</strong>{e(prediction)}</p>{block(u['exercise'])}<p><strong>{t('Inspect / explain', '检查与解释')}：</strong>{e(evidence)}</p><p class="notice">{e(boundary)}</p></section>'''
    body += f'''<h2>{t('2026 publication status', '2026 资料发布状态')}</h2><p>{t('CMU Fall 2026 is real and its schedule was updated November 11. The November 16 MVCC lecture is still future-dated at this check and has no linked notes/slides. We use the completed Spring edition. Later publication is unknown here.', 'CMU Fall 2026 确实存在，课表更新于 11 月 11 日。本次核验时 11 月 16 日 MVCC 尚未到课期，也没有讲义或幻灯链接，因此使用已完成的春季版本。不推测之后是否发布。')} <a href="{data['edition_checks'][0]['url']}">{t('Official Fall schedule', '秋季官方课表')}</a></p><p><a class="button primary" href="{BASE}{lang}/oncall/">{t('Do the business-invariant exercise', '开始业务不变量练习')} →</a></p></article><script defer src="{BASE}assets/learning.js"></script>'''
    return shell(lang, 'learn', t('Course route & six runnable units', '课程路线与六个可运行单元'), t('Verified CMU and MIT materials mapped to original, runnable MySQL exercises.', '将已核验的 CMU、MIT 原始资料对应到独立可运行 MySQL 练习。'), body)


def oncall(lang, shell, block, table):
    t = lambda en, zh: zh if lang == 'zh' else en
    r = json.loads((ROOT / 'records/oncall-clean.json').read_text())
    validate(r)
    summaries = []
    for c in r['cases'][:8]:
        o = c['oracle']
        summaries.append([c['level'], c['strategy'], c['decisions']['A']['observed_count'], c['decisions']['B']['observed_count'], o['on_call_count'], t('yes','是') if o['serially_reachable'] else t('NO','否')])
    body = f'''<article class="prose"><p class="eyebrow">EXPERIMENT 04 / BUSINESS INVARIANT</p><h1>{t('Both committed. Nobody stayed.', '两边都提交了，却无人值班。')}</h1><p class="lead">{t('Two doctors each leave only if another remains. A transaction can commit successfully and still participate in a business-rule violation.', '两名医生各自在“还有别人值班”时才撤岗。事务成功提交，仍可能共同破坏业务规则。')}</p><p class="notice">{t('Saved real MySQL 8.4 execution. The browser does not run SQL. This fixed-roster example makes no claim about range inserts, arbitrary existing snapshots, or performance.', '这里展示真实 MySQL 8.4 运行记录；浏览器不执行 SQL。实验限于固定成员，不对范围插入、任意已有快照或性能作出保证。')}</p>
<p>{t('Invariant: SUM(on_call) ≥ 1. Initial state (1,1); two withdrawal requests. The independent Python oracle enumerates both serial request orders and allows only (0,1) or (1,0). MySQL final rows are read separately after both participants commit.', '不变量：SUM(on_call) ≥ 1。初始状态 (1,1)，各有一次撤岗请求。独立 Python 模型枚举两种串行请求顺序，只允许 (0,1) 或 (1,0)。两方提交后，另一个自动提交观察者独立读取 MySQL 终值。')}</p>
<p><a href="{BASE}records/oncall-clean.json">{t('Measured run JSON', '实测首跑 JSON')}</a> · <a href="{BASE}records/oncall-repeat.json">{t('Stop/start repeat JSON', '停止重启后复跑 JSON')}</a> · <a href="{BASE}records/oncall-verification.json">{t('Lifecycle & negative-control evidence', '生命周期与反例验收')}</a> · <a href="{REPO}/blob/main/sql/oncall.json">{t('Editable SQL', '可修改 SQL')}</a></p>
<h2>{t('Predict before reading the results', '先预测，再阅读结果')}</h2><ol><li>{t('Both counts finish before any write. Does a row-local AND on_call=1 condition protect the cross-row rule?', '双方先完成计数，再开始写入。单行 AND on_call=1 能否保护跨行规则？')}</li><li>{t('Both create an RR snapshot first, then take an exclusive guard. Will the next plain count be fresh?', '双方先建立 RR 快照，再竞争独占守卫锁。之后的普通计数会更新吗？')}</li><li>{t('Take the guard before the first consistent read, or read the roster FOR UPDATE. Which evidence must show B waited?', '在首次一致性读之前获取守卫锁，或直接 FOR UPDATE 读取名单。什么证据能证明 B 真正等待？')}</li></ol>
<h2 id="measured-outcomes">{t('Measured outcomes, first repetition', '首轮实测结果')}</h2>''' + table([t('Isolation','隔离级别'),'strategy',t('A count','A 计数'),t('B count','B 计数'),t('Remaining','剩余值班'),t('Serially reachable','串行可达')],summaries)
    body += f'''<p>{t('All rows above contain two successful commits. Approval is a separate decision. Each run repeats the matrix three times and swaps doctor IDs in repetition 2; the repeat follows a server stop/start. Timing is recorded only for ordering evidence, not a benchmark.', '上表每行都有两次成功提交；是否批准撤岗是另一个决策。每份记录重复三轮，第二轮交换医生 ID；第二份记录来自停止、重启后的复跑。时间只用于检查执行顺序，不作性能基准。')}</p>
<h2>{t('What changed, and why', '差异来自哪里')}</h2><ul><li><strong>unguarded：</strong>{t('Both read 2 before either writes. Distinct-row conditional updates both commit; (0,0) is a counterexample under RC and RR.', '双方在写入前都读到 2，更新不同的行并提交。RC 和 RR 都出现 (0,0) 反例。')}</li><li><strong>late_guard：</strong>{t('The lock really serializes access, but it cannot replace an existing RR read view. The follower still reads 2 under RR. Under RC its next statement reads 1 in this schedule.', '锁确实串行化了访问，但不会替换已有的 RR 读视图。RR 下后来的计数仍为 2；RC 下新的语句在这个调度中读到 1。')}</li><li><strong>guard_first：</strong>{t('No consistent read precedes the guard. B waits; its first count after A commits reads 1. Every writer must obey this protocol.', '守卫锁之前没有一致性读。B 等待 A 提交，之后首次计数读到 1。所有写入者都必须遵守协议。')}</li><li><strong>locking_roster：</strong>{t('A current locking read protects the rows used by the decision. B waits and then returns one active doctor. We test fixed membership, not all range/predicate cases.', '当前锁定读取保护决策使用的行。B 等待后只返回一名值班医生。这里验证固定成员，不推广到所有范围或谓词场景。')}</li></ul>
<h2>{t('Run, change SQL, rerun', '运行、修改 SQL、复跑')}</h2>'''
    body += block('python lab.py doctor\npython lab.py start\npython lab.py oncall --output .local/oncall-first.json\npython lab.py stop\npython lab.py start\npython lab.py oncall --output .local/oncall-repeat.json\npython scripts/validate_oncall.py .local/oncall-first.json .local/oncall-repeat.json\ncp sql/oncall.json .local/oncall-sql.json\n# Edit .local/oncall-sql.json, preserve the baseline\npython lab.py oncall --sql-file .local/oncall-sql.json --output .local/oncall-edited.json\npython lab.py stop')
    body += f'''<ol><li>{t('Baseline: explain the two disallowed terminal states before changing SQL. Read the bindings to confirm which doctor each actor changed.', '基线：修改前解释失败场景为何不在模型允许的串行终值内。检查参数绑定，确认每个会话实际修改了哪名医生。')}</li><li>{t('Equivalent rewrite: replace the count SQL with SELECT COALESCE(SUM(on_call),0) AS n FROM oncall_roster WHERE shift_id=1. Rerun the complete matrix; the semantics should match for the fixed roster.', '等价改写：将 count 改为 SELECT COALESCE(SUM(on_call),0) AS n FROM oncall_roster WHERE shift_id=1。复跑完整矩阵，固定名单下应保留相同语义。')}</li><li>{t('Negative control: remove FOR UPDATE from the guard query. The required B→A edge disappears and the runner must fail within its deadline without writing a success JSON. This rejects an invalid schedule assumption; it is not a new final-state proof.', '负对照：从 guard 查询中删除 FOR UPDATE。所需 B→A 等待边消失，运行器必须在期限内失败，且不能产生成功 JSON。这是在拒绝失效的调度前提，并非新的终值证明。')}</li><li>{t('Explain why moving a plain read above guard_first recreates late_guard. Use the existing late_guard RR record as the counterexample, then compare RC.', '解释把普通读取提前到 guard_first 之前，为何就变成 late_guard。用已有 late_guard RR 记录作为反例，再对比 RC。')}</li></ol>
<h2>{t('Inspect actual evidence', '检查实际证据')}</h2>'''
    for c in r['cases'][:8]:
        snap = c['lock_evidence']['snapshot']
        locks = table(['actor','table','index','mode','status'], [[x['actor'],x['OBJECT_NAME'],x['INDEX_NAME'],x['LOCK_MODE'],x['LOCK_STATUS']] for x in snap['locks']]) if snap else f'<p>{t("No lock wait is claimed here. Both completed reads form the barrier.","这里不声称观测到锁等待，屏障依据是双方已完成的读取。")}</p>'
        body += f'''<details id="{c['strategy']}-{'rc' if c['level']=='READ COMMITTED' else 'rr'}"><summary>{e(c['level'])} / {e(c['strategy'])} / {t('remaining','剩余')} {c['oracle']['on_call_count']}</summary><h3>{t('Independent final state / oracle','独立终值与模型判断')}</h3>{block(json.dumps({'final_rows':c['final_rows'],'oracle':c['oracle'],'decisions':c['decisions']},indent=2))}{locks}<h3>{t('Executed timeline, with SQL parameters','实际执行时间线，含 SQL 参数')}</h3>{block(json.dumps(c['timeline'],ensure_ascii=False,indent=2))}</details>'''
    body += f'''<h2>{t('Theory and implementation boundary', '理论与实现边界')}</h2><p>{t('CMU/MIT explain schedules, 2PL and multi-versioning. This experiment verifies specific MySQL 8.4 statements with autocommit disabled via explicit START TRANSACTION. It does not establish that all InnoDB reads follow strict 2PL or that every RR history is serializable. No API key, model, vector plugin or external database is involved.', 'CMU/MIT 用于理解调度、2PL 与多版本。本实验验证显式 START TRANSACTION 内的具体 MySQL 8.4 语句，不代表全部 InnoDB 读取都遵循严格 2PL，也不代表所有 RR 历史都可串行化。不需要 API key、模型、向量插件或外部数据库。')}</p><p><a href="{BASE}{lang}/learn/#u4">{t('Lecture and reading mapping', '具体讲次与阅读映射')} →</a> · <a href="https://dev.mysql.com/doc/refman/8.4/en/innodb-consistent-read.html">MySQL 8.4 consistent reads</a> · <a href="https://dev.mysql.com/doc/refman/8.4/en/innodb-locking-reads.html">MySQL 8.4 locking reads</a></p></article>'''
    return shell(lang, 'oncall', t('Concurrent withdrawals & business invariants', '并发撤岗与业务不变量'), t('Real write-skew counterexamples, flawed guard order and measured locking controls.', '真实写偏差反例、错误守卫顺序与锁策略对照。'), body)
