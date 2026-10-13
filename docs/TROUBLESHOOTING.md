# 排障剧本

四个高频故障的定位路径。所有命令在项目根目录执行；运行数据在 `data/runtime`（不进入交付包）。

可用的定位入口：

- **结构化日志**：`data/runtime/logs/run-YYYYMMDD.jsonl`，一行一个 JSON 对象，字段只有 `run_id/request_id/intent/mode/status/input_tokens/output_tokens/latency_ms/error_code` 等白名单字段，不含 prompt、响应正文、URL 与密钥。
- **运行记录**：SQLite `data/runtime/adcraft.sqlite3` 的 `objects` 表（kind=runs），每个 run 有完整 `trace`、`validation`、`usage` 与 `error`。
- **接口**：`GET /health`（本地存储探测）、`GET /api/v1/ai/config`（运行模式与检索/图片配置摘要）。
- **网页**：右侧面板的步骤记录、事实依据与检索片段。

---

## 剧本 1：费用突增

**现象**：模型账单上涨，或收到用量告警。

**定位**：

1. 确认当前模式：`GET /api/v1/ai/config` 的 `mode` 应为 `live`；demo 模式不会产生模型费用。
2. 统计日志里的 live 调用与 token 量：

   ```powershell
   Get-Content data\runtime\logs\run-*.jsonl | ForEach-Object {
       ($_ | ConvertFrom-Json) } | Where-Object { $_.mode -eq "live" } |
       Measure-Object input_tokens, output_tokens -Sum
   ```

3. 找出高消耗 run：按 `input_tokens` 排序，回查该 run 的 `trace`，看是否进入了多轮 repair 或工具循环接近步数上限（`max_agent_steps`/`max_repair_attempts`）。
4. 对照供应商控制台：日志口径不含 embedding 与图片费用，也不含供应商侧重试。

**处置**：

- 紧急止损：`.env` 设 `AI_MODE=demo` 并重启，服务仍可用但不再付费。
- 针对高消耗请求类型，收紧 `MAX_AGENT_STEPS`、`MAX_REPAIR_ATTEMPTS`、`RAG_TOP_K` 或缩短历史轮数（代码常量）。
- 修复后的回归：重放原请求，对比 token 与是否仍通过校验。

**预防**：当前没有 token 预算、熔断与告警——这是单工作区定位下的已知缺口。上生产前应加请求级与日级预算、费用仪表盘与超限自动降级（见 INTERVIEW_QUESTIONS 第六层）。

---

## 剧本 2：限流风暴

**现象**：大量 run 失败，答案提示“模型服务限流，请稍后重试”。

**定位**：

1. 日志里按 `error_code` 分组：

   ```powershell
   Get-Content data\runtime\logs\run-*.jsonl | ForEach-Object { ($_ | ConvertFrom-Json).error_code } |
       Group-Object | Select-Object Name, Count
   ```

2. `rate_limit` 是可重试的 429；`quota_exhausted` 也是 429 但**不可**重试（额度问题，重试只会浪费等待）。看单个 run 的 trace 里 ModelError 的 `code/status_code/retryable` 区分两者。
3. `upstream_unavailable`（408/5xx）高发说明上游整体不稳，不是本进程并发问题。

**处置**：

- 降并发：减少同时进行的会话（当前 `max_concurrent_runs` 是代码常量），或错峰重试——provider 已对退避加 ±50% 抖动并遵守 Retry-After 上限。
- 若是 `quota_exhausted`：停止重试，检查账户余额与套餐配额。
- 用户侧话术：明确告诉用户“本次是限流失败，稍后重试不会重复计费”与“超时可能已计费”的区别，不要混为一谈。

**预防**：限流预算应该显式化：并发令牌、每分钟请求数、429 退避观测（记录每次退避时长）三件事目前只有第一和第三件，且退避未落日志。上生产前把限流指标接入日志/监控。

---

## 剧本 3：幻觉投诉（文案数字或承诺与商品不符）

**现象**：用户指出草稿里的容量、保温时长或认证说法不对。

**定位**（先复现，再归因）：

1. 拿到该 run 的 `message`，在 demo/live 同参数重放，确认是否稳定复现。
2. 看 `validation.issues`：`UNSUPPORTED_NUMBER`/`UNSUPPORTED_PROMISE` 说明规则已拦下（未交付）；若草稿已交付，说明该错误不在当前规则覆盖内。
3. 看 `draft.claims` 与 `evidence_ids`：数字是否有对应 `fact_ids`；检索片段是否来自正确品牌（trace 里有 `tool_result` 的 evidence_count 与 ID）。
4. 区分三类原因：商品资料本身缺依据（应补资料）、规则词表没覆盖（应加规则+样例）、模型无视了已有依据（应加回归并看 repair 行为）。

**处置**：

- 交付侧的诚实表达：程序校验只覆盖“值+单位、引用存在、有限承诺词表”，不能证明任意自然语言语义正确——对投诉先承认边界，不把规则通过率说成正确率。
- 把该输入固化为 `scripts/evaluate.py` 的回归用例（或 backend/tests 的验证用例），防止复发。
- 若是词表缺口：加词表前先确认误伤率——词表越宽，把正常文案误判为承诺的概率越高。

**预防**：规则是确定性、可解释的防线，但覆盖面有限。语义级检查（如 claim-level entailment）需要标注集先评价它自己的误判，不能默认“上了模型检查就更好”。

---

## 剧本 4：图片任务丢失或需要核对

**现象**：图片任务卡在 `running`，或超时后想重试但担心重复收费。

**定位**：

1. `GET /api/v1/ai/image-jobs/{job_id}`：看 `status`、`images`、`failures` 与 `provider_tasks`（保存的供应商 task ID）。
2. 卡 `running`：服务重启后，启动逻辑会把遗留 queued/running 标为 failed——先确认是进程内卡住还是重启残留。
3. `failures` 非空而 `images` 也有内容 → `partial`：只有失败的 index 需要重试。

**处置**：

- **重试前必须先核对供应商侧任务状态**：用 `provider_tasks` 里的 task ID 查供应商控制台。上游可能已完成并计费，直接重提会再次计费；本项目没有供应商侧 exactly-once。
- 只重试失败 index：`POST /runs/{run_id}/images` 的 `indices` 只填失败序号（接口限制不重复且非负）。
- 未上传商品原图时交付的只是背景方案，不是“图片没生成完”。

**预防**：上游任务对账目前依赖人工。上生产前应把 task ID 轮询与恢复做成明确机制：启动后查询供应商状态、按结果回填或标记放弃，而不是只标 failed。

---

## 排障后要做的三件事

1. 把根因写进 run 的 `feedback`（或自己的复盘记录）：现象、输入、trace、根因、改动、验证。
2. 能固化的就固化：新回归用例 > 新日志字段 > 文档一句话。
3. 更新话术：面试被问“你遇到过什么线上问题”，用上面的剧本结构回答，而不是背故障名单。
