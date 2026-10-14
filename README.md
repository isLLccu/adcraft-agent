# AdCraft AI 对话式电商内容工作台

[![CI](https://github.com/isLLccu/adcraft-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/isLLccu/adcraft-agent/actions/workflows/ci.yml)
仓库地址：https://github.com/isLLccu/adcraft-agent

AdCraft AI 将商品事实、品牌资料检索、模型工具调用、结构化文案和程序校验串成一条可观察的 AI 应用链路。你可以生成文案、追问依据、修改上一版，并在确认后生成广告背景或合成商品原图。

本版用于本地单工作区演示。核心模块可以脱离网页、数据库和任务队列运行，方便逐个阅读、调试与验证。Python 建议 3.11 或 3.12。

## 先启动并体验

项目包含已经构建好的网页。

```bash
python -m venv .venv
```

Windows PowerShell：

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
python scripts/dev.py --backend-only
```

macOS 或 Linux：

```bash
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
python scripts/dev.py --backend-only
```

打开 http://localhost:8000。接口文档位于 http://localhost:8000/docs。

第一次不需要密钥，默认使用确定性 Demo；网页会标注模式。Demo 会执行真实资料分块、BM25 检索、校验与任务管理，但文案来自固定模板，不代表大模型生成效果。切换 Live 后，工具决策和内容生成才由真实模型完成。

建议按顺序体验：

1. 选择北岸随行杯，生成一版自然的小红书上新文案。
2. 查看右侧的事实依据、检索片段和步骤记录。
3. 追问“把正文再短一点，不提价格”；确认上一版草稿被修改。
4. 请求“增加保温24小时的卖点”；观察缺少依据时的澄清。
5. 上传透明 PNG 商品原图，确认后生成素材；Demo 图明确标注模板背景。
6. 执行离线评测，查看具体通过和失败案例。

## 接入真实模型

将 `.env.example` 复制为项目根目录的 `.env`，然后设置以下值并重新启动服务：

```dotenv
AI_MODE=auto
LLM_API_BASE=https://api.deepseek.com/v1
LLM_API_KEY=你的密钥
LLM_MODEL=你的可用模型名
```

接口使用 OpenAI-compatible `/chat/completions`，模型需支持 `tools` 和 JSON 输出。API base 应为基础路径，例如 `/v1`，不能再次包含 `/chat/completions`。不同服务的模型名、地域、兼容字段和额度需要按该服务确认。文本链路已用 deepseek-chat 做过小样本联调（生成/修改/澄清各一次 + 付费评测 2 例，记录见 docs/VERIFICATION.md）；图片与 embedding 未付费联调，保留 MockTransport 与工具流程边界测试。

语义向量检索是可选项。配置 `EMBEDDING_API_BASE`、`EMBEDDING_API_KEY`、`EMBEDDING_MODEL` 后启用真实 Embedding + BM25 的 RRF 融合；默认仅使用 BM25。Embedding 服务需支持 `/embeddings`，不会隐式复用其他供应商密钥，也不会将字符哈希伪装成语义模型。

真实图片生成：设置 `IMAGE_PROVIDER=dashscope`，配置 `IMAGE_API_KEY` 和所在地域的 `IMAGE_API_BASE`。默认模型 `wanx2.1-t2i-turbo` 使用 text2image 异步协议；wan2.6 的新版协议不在当前适配器范围。`openai` 适配器保留兼容 images/generations 的接口，需自行配置支持当前 payload 的图像模型。未配置图片密钥时，真实模式显式报错，不自动冒充成功。

背景与商品主体分开处理：背景由供应商生成，上传的商品图由 Pillow 保持比例合成。没有商品原图时，只交付背景方案；非透明原图保留其原背景并给出提示。系统没有自动抠图、商品局部重绘或完整图像质量判断功能。

## 开发网页

只有修改前端时才需要 Node.js（建议 20 或 22）和 npm：

```bash
cd frontend
npm ci
npm run dev
```

另一个终端运行后端：

```bash
python scripts/dev.py --backend-only
```

开发网页 http://localhost:5173 将 `/api` 转发到 8000。`npm run build` 更新 `frontend/dist`，Python 服务会直接提供已构建网页。也可以在安装前后端依赖后运行 `python scripts/dev.py` 同时启动两个开发服务。

## AI 核心在哪里

| 文件 | 主要问题 |
|---|---|
| `backend/app/ai/workflow.py` | 模型何时调用工具，如何修改历史草稿，校验失败如何结束 |
| `backend/app/ai/prompts.py` | 规划、生成与修复分别需要什么指令与数据 |
| `backend/app/ai/schemas.py` | 模型输出和工具入参有哪些确定约束 |
| `backend/app/ai/provider.py` | HTTP 请求、工具调用格式、超时、分类重试和 token 记录 |
| `backend/app/ai/retrieval.py` | 中文分块、BM25、向量检索、RRF 和版本缓存 |
| `backend/app/ai/validation.py` | 字段、数值单位、事实引用和有限承诺检查 |
| `backend/app/ai/evaluation.py` | 怎样把期望行为写成可重复的回归案例 |
| `backend/app/ai/api.py` | HTTP 接口、进度 SSE、后台任务和人工确认 |
| `backend/app/ai/repository.py` | 本地持久化、事务幂等、重启状态处理 |
| `backend/app/ai/images.py` | 图片调用、供应商任务 ID 和原图合成 |

读取商品和品牌资料是受限工具。模型不能自行传入其他商品 ID、品牌 ID 或文件路径；执行端绑定当前商品并校验入参。Live 的工具循环有最大步数和调用量限制。Trace 记录真实执行动作与观察，未请求或展示模型隐藏思维链。

结构化结果包括 title、body、slogan、selling_points、claims、evidence_ids、image_prompts 与 platform。JSON 能解析不等于内容正确：Pydantic 校验字段，规则再检查已录入数值与单位、事实引用和部分无依据承诺。Live 有限修复后仍不通过时，不把草稿交付为成功。规则不能证明所有自然语言语义正确。

多轮上下文使用最近六轮和真实历史草稿，不是模型训练或永久记忆。切换商品时不把旧商品草稿当作新商品事实。超过窗口的早期约束可能遗失，适合作为后续改进与评测题。

## 独立运行与验证

从项目根目录执行：

```bash
python scripts/run_example.py
python -m pip install -r backend/requirements-dev.txt
python -m pytest -q
python scripts/evaluate.py
```

`run_example.py` 是最适合开始阅读的入口：没有 FastAPI、SQLite、前端或图片调用。它读取示例商品和资料，直接调用 AIWorkflow，并打印执行阶段与结果。若本地已启用 Live，它会调用你的真实模型；练习离线流程时把 `.env` 的 `AI_MODE` 设为 `demo`。

离线评测包含 24 条自建开发样例：6 条检索与品牌隔离、10 条结构与事实检查、8 条演示工作流。`data/evaluation_report.json` 保存实际报告。离线通过率不是 LLM 质量指标。网页评测始终强制离线，不静默产生模型费用。

真实模型评测须显式指定：

```bash
python scripts/evaluate.py --live --confirm-paid --limit 2 --output data/live_report.json
```

每条案例可能包含多次规划、生成、修复和 Embedding 调用。结果仍需人工审查；程序只覆盖明确断言。模型版本、配置、测试样例与失败结果应保留，以便事后审计与复现。Chat token 汇总不含 Embedding 和图片费用。

## 文档

| 文档 | 用途 |
|---|---|
| `docs/ARCHITECTURE.md` | 调用链、边界、数据流与设计取舍 |
| `docs/VERIFICATION.md` | 测试、离线评测与真实模型联调记录 |
| `docs/TROUBLESHOOTING.md` | 费用突增、限流、幻觉投诉、图片对账的排障路径 |
| `CHANGELOG.md` | 版本演进与取舍记录 |

## 部署与边界

`docker compose up --build` 提供后端 8000 和网页 3000 两个服务，默认绑定本机；后端配置了 SQLite 可读写探测的 healthcheck 与自动重启。两个镜像均已在本地成功构建，但引擎在构建后不可用，运行态未在本次实测。支持可选 `.env` 的 Compose 版本需 2.24 或以上。

本版没有生产级登录、多租户鉴权或持久任务队列。任务使用进程内 BackgroundTasks；启动时遗留 queued/running 会标记 failed，不会自动恢复模型请求。默认数据位于 `data/runtime`，不包含在交付包。结构化运行日志按天写入 `data/runtime/logs`，只含白名单字段，不记录 prompt、响应正文、URL 与密钥。SQLite 事务防止本地重复创建，不能保证外部供应商只收费一次。图片任务保留上游 ID，超时后应先核对供应商状态。

v1 的批量内容生产流水线（Celery + PostgreSQL + Redis + MinIO）与旧管理端页面已从代码库移除，完整保留在 git 历史中（首个提交）；演进决策见 CHANGELOG。

官方接口参考：[DeepSeek 工具调用](https://api-docs.deepseek.com/zh-cn/guides/tool_calls/)、[DeepSeek JSON Output](https://api-docs.deepseek.com/zh-cn/guides/json_mode/)、[万相文生图 API](https://help.aliyun.com/zh/model-studio/text-to-image-v2-api-reference)、[FastAPI 后台任务](https://fastapi.tiangolo.com/tutorial/background-tasks/)。
