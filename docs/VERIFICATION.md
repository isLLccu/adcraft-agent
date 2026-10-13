# 本版验证记录

## 自动测试

Python 3.12 + backend/requirements-dev.txt，执行 `python -m pytest -q`：**133 项通过**，app.ai 行覆盖率 90%。覆盖 HTTP 分类错误与重试（含退避抖动边界）、工具循环/停止条件、无依据承诺与数值单位、品牌检索隔离、schema 与有限修复、历史草稿、SQLite 并发幂等与分页、SSE、图片确认/透明 PNG 合成/替换删旧文件/部分失败、反馈与重启状态、会话锁弱引用回收、结构化日志白名单、prompt 与配置一致性。全部测试离线，任何外呼都会失败。

本地门禁 `scripts/ci.ps1` / `scripts/ci.sh` 在本机实际跑通：ruff、pytest、前端 lint 与 build 全绿。

## 离线评测

执行 `python scripts/evaluate.py`：**24/24 通过**（6 条检索、10 条校验、8 条 demo 工作流）。结果在 `data/evaluation_report.json`；不是模型效果准确率或优化收益。

## 真实模型联调（2026-10-13）

配置 deepseek-chat（`AI_MODE=auto` + `.env` 密钥，Embedding 未配置 → 全程 BM25 词法检索，图片保持 demo）：

- 手工 3 次运行：生成（completed，3 次调用，校验通过）、同会话修改“再短一点，不提价格”（revise，claims 5→4，校验通过）、无依据承诺“保温24小时”（needs_clarification，拒绝编造并引用品牌手册）。
- 付费评测 `scripts/evaluate.py --live --confirm-paid --limit 2`：**2/2 通过**（小红书生成、淘宝生成+品牌隔离），每例 3 次模型调用。
- 记录：`data/live_report.json`（评测报告）与 `data/runtime/live_test_records.md`（配置、run_id、token、时延、失败样例口径）；结构化日志在 `data/runtime/logs`。
- 边界：样本极小（3+2 例），未做人工质量评阅、真实图片联调、embedding 联调与并发实测。

## 前端与浏览器

npm run lint 与 npm run build 通过，TypeScript 开启 strict。浏览器访问单 Python 服务提供的预构建网页，验证生成文案、连续修改/不提价格/删除口号、未知保温时长澄清、确认生成演示图片、刷新恢复图片、反馈、24 例评测窗口；未发现页面运行错误，1440px 桌面与 390px 手机无横向溢出。

## Docker

后端与前端两个镜像均已在本机成功构建（backend 含 SQLite 探测 healthcheck 与自动重启配置）。构建后本机 Docker 引擎不可用，`docker compose up` 运行态未实测。

## 未执行的验证与口径

图片提供方（dashscope/openai）未进行付费联调；embedding 混合检索未联调。规则只覆盖有限可枚举错误，不证明所有语义正确；固定样例通过率不能外推到真实用户请求。生产级多租户、持久队列、预算与限流不在本版验证范围。
