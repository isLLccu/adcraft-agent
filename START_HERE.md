# 从这里开始学习 AdCraft AI

这个项目的主线是 AI 应用链路。第一次学习按下面的顺序完成，不需要先学原项目的 PostgreSQL、Celery 或 MinIO。

## 第一次运行

按 README 安装 Python 依赖，执行 `python scripts/dev.py --backend-only`，打开 http://localhost:8000。交付包已带构建后的网页。先使用 Demo，不填写密钥也能观察流程。

依次尝试生成文案、修改上一版、查看依据、请求没有证据的保温时长、确认图片生成和离线评测。记下哪里进入 needs_clarification，哪里是完成。Demo 文案是固定模板；它的成功不能证明真实模型效果。

## 第一个代码任务

关闭网页也可以运行 `python scripts/run_example.py`。先读这个脚本，找到输入商品、品牌文档、用户消息和输出结果。跟进 `workflow.py` 的 run 函数，理解每一个 emit 事件对应什么实际行动。

完成三件事：把商品容量改为一个新值，观察输出变化；请求资料没有的保温时长，查看校验；把生成后的真实 draft 加到 history，再要求改短正文。保存输入、结果和你的解释。

## 再深入四个模块

1. `provider.py`：HTTP 请求的 headers/body/响应，async、timeout、有限重试，tools 与 usage。
2. `retrieval.py`：分块、BM25、品牌范围、top-k、可选真实 Embedding 和 RRF。
3. `schemas.py` 与 `validation.py`：JSON 对象、字段校验、数值单位、引用和误拦截。
4. `workflow.py` 与 `prompts.py`：Live 工具循环、停止条件、历史草稿、结构化生成和 repair。

每个模块先看输入输出，再运行对应的 `backend/tests/test_*.py`。不要从文件第一行开始逐行背诵。

## 必须亲手做的练习

先按 `docs/EXERCISES.md` 的 A 级练习操作；再做 B 级模块修改。每一次改动要记录“为什么改、改哪里、如何验证、还有什么问题”。做完后再阅读答案。

完成一次真实 Live 调用后，保存模型与配置、执行记录、输出和失败样例。只选少量任务进行联调；真实请求与图片会按供应商计费。不能把离线报告的 24/24 写成模型准确率。

## 面试准备

`docs/INTERVIEW_QUESTIONS.md` 提供 45 个分层问题；`RESUME_AND_PREP.md` 提供 3 分钟和 10 分钟讲解路径。先用自己的运行记录回答，再对照参考思路。

第一轮学习结束的标准：你能讲清一个生成请求的完整过程；独立修改一个模块；复现一次失败并修复；解释 RAG、工具调用、校验与评测的边界。随后再看 `api.py`、`repository.py` 和 `images.py`。
