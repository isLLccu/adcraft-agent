# 本版验证记录

本版使用明确的离线配置验证，未调用真实付费模型或图片服务。

## 自动测试

在 Python 3.12 环境安装 backend/requirements-dev.txt，执行 python -m pytest -q，105 项通过。测试覆盖 HTTP 分类错误与重试、工具循环/停止条件、无依据承诺与数值单位、品牌检索隔离、schema与有限修复、历史草稿、SQLite并发幂等、SSE、图片确认/透明PNG合成/部分失败、反馈与重启状态。

## 离线评测

执行 python scripts/evaluate.py，24/24 通过：6 条检索、10 条校验、8 条 demo 工作流。详细结果在 data/evaluation_report.json；不是模型效果准确率或优化收益。

## 前端与浏览器

npm run lint 与 npm run build 通过，TypeScript开启strict。浏览器真实访问单Python服务提供的预构建网页，验证生成文案、连续修改/不提价格/删除口号、未知保温时长澄清、确认生成演示图片、刷新恢复图片、反馈、24例评测窗口。未发现页面运行错误；1440px桌面与390px手机无横向溢出。

## 未执行的验证

真实LLM/Embedding/图片联调需使用你的接口配置；本次未发起付费调用。Docker配置提供但未构建镜像。规则只覆盖有限可枚举错误，不证明所有语义正确，也不能将固定样例的通过率外推到真实用户请求。
