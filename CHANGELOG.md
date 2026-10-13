# AdCraft AI v2 修改记录

## v2.1：工程化基础与面试对齐（2026-10）

- 建立 git 分阶段历史与本地门禁（scripts/ci.sh、scripts/ci.ps1、GitHub Actions）：ruff + 133 个离线测试（覆盖率 90%）+ 前端 lint/build。
- 新增结构化 JSON 行日志（data/runtime/logs，12 个字段白名单，不含 prompt/响应/URL/密钥）与 /health 深度探测（SQLite 可读写，不拨测上游）。
- 修复：会话锁无限增长（弱引用回收）、provider 重试无抖动、repository.list 无分页、替换商品图不删旧文件、React StrictMode 会话双创建。
- 删除 v1 遗留后端与夹具约 3800 行（git 历史保留），前端依赖精简至 react/react-dom。
- 文档对齐 JavaGuide 面试方法：STAR 版介绍模板与量化矩阵、数据流与信任边界图、第六层设计讨论 8 题、四个排障剧本。
- 真实模型联调：deepseek-chat 生成/修改/澄清 3 次 + 付费评测 2/2（记录见 docs/VERIFICATION.md）；embedding 与图片未付费联调。
- 发布：公开仓库 https://github.com/isLLccu/adcraft-agent（v1 平台已被本版覆盖，旧历史保留在本地 git 与 v1 基线提交）；补 MIT LICENSE、预构建网页与 CI 徽章。

## 产品与代码

从表单式批量生图平台调整为对话式电商内容工作台。新的 AI 核心位于 backend/app/ai，可以脱离网页和基础设施独立运行。增加模型工具循环、严格输出schema、商品声明与资料引用、BM25和可选API向量混合检索、有限校验修复、多轮草稿、行动trace、离线评测。

默认使用SQLite与本地文件，仅启动Python服务即可体验预构建网页。v1 的 Celery/PostgreSQL/MinIO 链路与旧管理端页面已从代码库移除（保留在 git 历史），演进决策见下文 v2.1。

图片改为背景生成与商品原图合成；任务需人工确认，保留供应商任务ID，记录部分失败。上传非透明图或没有商品图时明确说明效果边界。

## 可靠性与学习

提供请求级事务幂等，前端未获响应的同参数重试复用key。新增后台状态与SSE进度接口，当前网页使用轮询；重启将中断任务标为failed。接入事实声明检查、trace数据查看、用户反馈与24项离线回归。

重写学习指南与面试材料，增加14个分级练习和45道项目追问。删除旧版未经复测的效果与价格宣传，以实际测试范围说明行为。

## 数据与配置

示例商品和品牌手册均为自建演示资料，不冒充平台官方规则或真实运营效果。真实密钥和原日志不进入交付包，按.env.example本地配置。报告和测试数据不混入运行数据库。
