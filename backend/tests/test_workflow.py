import copy
import json
import unittest
from types import SimpleNamespace
from app.ai.workflow import AIWorkflow

PRODUCT = {
    "id": "p-cup", "brand_id": "northcup", "name": "北岸随行杯",
    "description": "日常用品", "selling_points": ["轻便随行", "旋拧杯盖"],
    "facts": [
        {"id": "f-capacity", "label": "容量", "value": "400mL"},
        {"id": "f-material", "label": "材质", "value": "304不锈钢"},
        {"id": "f-weight", "label": "重量", "value": "260g"},
        {"id": "f-price", "label": "售价", "value": "99元"},
    ],
}
DOCUMENTS = [
    {"id": "doc-cup", "brand_id": "northcup", "title": "品牌规则", "content": "简洁真实", "source": "manual", "version": 1},
    {"id": "doc-other", "brand_id": "other", "title": "其他品牌", "content": "禁止使用", "source": "manual", "version": 1},
]
EVIDENCE = [{"id": "doc-cup:0", "document_id": "doc-cup", "title": "品牌规则", "text": "简洁真实", "score": 0.8, "source": "manual", "version": 1, "chunk_index": 0}]


def good_draft():
    return {
        "title": "北岸随行杯", "body": "容量400mL。", "slogan": "日常随行",
        "selling_points": ["容量400mL"], "claims": [{"text": "容量400mL", "fact_ids": ["f-capacity"]}],
        "evidence_ids": ["doc-cup:0"],
        "image_prompts": [{"label": "场景", "prompt": "保留原始商品外观，明亮背景", "negative_prompt": "不修改比例"}],
        "platform": "xiaohongshu",
    }


def tool(name, arguments=None, id=None):
    return {"id": id or name, "type": "function", "function": {"name": name, "arguments": json.dumps(arguments or {}, ensure_ascii=False)}}


def reply(content="", tools=None):
    return {"content": content, "tool_calls": tools or [], "usage": {"input_tokens": 10, "output_tokens": 5}}


class Client:
    def __init__(self, replies=()):
        self.replies = list(replies)
        self.calls = []

    async def chat(self, messages, tools=None, json_mode=False):
        self.calls.append({"messages": copy.deepcopy(messages), "tools": tools, "json_mode": json_mode})
        if not self.replies:
            raise AssertionError("unexpected model call")
        return self.replies.pop(0)


class Retriever:
    def __init__(self, poisoned=False):
        self.calls = []
        self.poisoned = poisoned

    async def search(self, documents, query, brand_id, top_k=None):
        self.calls.append((documents, query, brand_id, top_k))
        result = copy.deepcopy(EVIDENCE)
        if self.poisoned:
            result.append({**EVIDENCE[0], "id": "foreign:0", "document_id": "doc-other", "brand_id": "other"})
        return result


class FakeLogger:
    def __init__(self):
        self.entries = []

    def write(self, fields):
        self.entries.append(fields)


class WorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def run_flow(self, mode="demo", message="生成文案", history=None, client=None, max_steps=6, repairs=1,
                       retriever=None, run_id=None, logger=None):
        events = []

        async def emit(type_, stage, message, data):
            events.append({"type": type_, "stage": stage, "message": message, "data": data})
        client = client or Client()
        retriever = retriever or Retriever()
        settings = SimpleNamespace(mode=mode, max_agent_steps=max_steps, max_repair_attempts=repairs)
        result = await AIWorkflow(settings, client, retriever).run(PRODUCT, DOCUMENTS, message, "xiaohongshu",
                                                                   history or [], emit, run_id=run_id, logger=logger)
        return result, events, client, retriever

    async def test_finish_logs_whitelisted_summary(self):
        from app.ai.observability import RUN_FIELDS

        logger = FakeLogger()
        result, _, _, _ = await self.run_flow(run_id="run-1", logger=logger)
        assert result["status"] == "completed"
        assert len(logger.entries) == 1
        entry = logger.entries[0]
        assert entry["event"] == "run_finished"
        assert entry["run_id"] == "run-1"
        assert entry["mode"] == "demo"
        assert entry["intent"] == "generate"
        assert entry["status"] == "completed"
        assert entry["input_tokens"] == 0 and entry["output_tokens"] == 0
        assert entry["latency_ms"] >= 0
        assert set(entry) <= RUN_FIELDS

    async def test_failed_run_logs_error_code(self):
        class Broken(Retriever):
            async def search(self, documents, query, brand_id, top_k=None):
                raise RuntimeError("boom")

        logger = FakeLogger()
        result, _, _, _ = await self.run_flow(run_id="run-2", logger=logger, retriever=Broken())
        assert result["status"] == "failed"
        assert len(logger.entries) == 1
        assert logger.entries[0]["error_code"] == "internal_error"

    def live_script(self, draft=None):
        return [
            reply(tools=[tool("get_product"), tool("search_knowledge", {"query": "品牌表达"})]),
            reply(json.dumps({"intent": "generate", "answer": "生成"})),
            reply(json.dumps(good_draft() if draft is None else draft, ensure_ascii=False)),
        ]

    async def test_demo_no_model_calls_real_retrieval(self):
        result, events, client, retriever = await self.run_flow()
        self.assertEqual("completed", result["status"])
        self.assertEqual(0, result["usage"]["total_calls"])
        self.assertEqual([], client.calls)
        self.assertEqual(["northcup"], [c[2] for c in retriever.calls])
        self.assertEqual(1, len(retriever.calls[0][0]))
        self.assertTrue(result["validation"]["passed"])
        self.assertIn("demo", {e["data"].get("mode") for e in events})

    async def test_demo_image_prompts_describe_background_only(self):
        result, *_ = await self.run_flow()
        for image in result["draft"]["image_prompts"]:
            self.assertIn("纯背景", image["prompt"])
            self.assertIn("不生成商品", image["prompt"])
            self.assertIn("不绘制文字和Logo", image["prompt"])
            self.assertNotIn("商品照片为主体", image["prompt"])

    async def test_demo_unknown_request_refused(self):
        result, *_ = await self.run_flow(message="请生成保温24小时、食品级、防漏的文案")
        self.assertEqual("needs_clarification", result["status"])
        self.assertIsNone(result["draft"])
        self.assertFalse(result["validation"]["passed"])

    async def test_demo_negative_instruction_supported(self):
        result, *_ = await self.run_flow(message="生成文案，不要写保温24小时")
        self.assertEqual("completed", result["status"])
        self.assertNotIn("24", json.dumps(result["draft"], ensure_ascii=False))

    async def test_example_message_completes_and_keeps_negative_scope(self):
        result, *_ = await self.run_flow(message="生成一版自然简洁的小红书文案，不添加未知保温时长。")
        self.assertEqual("completed", result["status"])
        self.assertNotIn("保温", json.dumps(result["draft"], ensure_ascii=False))
        positive, *_ = await self.run_flow(message="生成文案，不添加虚假材质，但强调保温24小时。")
        self.assertEqual("needs_clarification", positive["status"])
        self.assertIsNone(positive["draft"])

    async def test_explanation_not_advertisement(self):
        result, *_ = await self.run_flow(message="什么是RAG？")
        self.assertEqual("completed", result["status"])
        self.assertIsNone(result["draft"])
        self.assertIn("检索", result["answer"])

    async def test_actual_previous_draft_and_recent_constraint(self):
        first, *_ = await self.run_flow(message="生成文案，不要提售价")
        history = [{"message": "生成文案，不要提售价", "draft": first["draft"], "status": "completed", "answer": first["answer"]}]
        second, *_ = await self.run_flow(message="更简短，口语一点", history=history)
        self.assertEqual("completed", second["status"])
        self.assertNotIn("99", json.dumps(second["draft"], ensure_ascii=False))
        self.assertLess(len(second["draft"]["body"]), len(first["draft"]["body"]))
        third, *_ = await self.run_flow(message="只修改标题，更简短", history=history)
        self.assertEqual(first["draft"]["body"], third["draft"]["body"])
        self.assertNotEqual(first["draft"]["title"], third["draft"]["title"])

    async def test_latest_style_override_and_price_synonym(self):
        first, *_ = await self.run_flow(message="生成口语文案，不要提价格")
        history = [{"message": "生成口语文案，不要提价格", "draft": first["draft"], "status": "completed"}]
        next_run, *_ = await self.run_flow(message="改正式一点，内容详细些", history=history)
        self.assertEqual("completed", next_run["status"])
        self.assertNotIn("99", json.dumps(next_run["draft"], ensure_ascii=False))
        self.assertNotIn("今天出门", next_run["draft"]["body"])

    async def test_retriever_cross_brand_output_filtered(self):
        result, *_ = await self.run_flow(retriever=Retriever(poisoned=True))
        self.assertEqual(["doc-cup:0"], [e["id"] for e in result["evidence"]])

    async def test_live_executes_model_tools_then_generator(self):
        client = Client(self.live_script())
        result, events, *_ = await self.run_flow(mode="live", client=client)
        self.assertEqual("completed", result["status"])
        self.assertEqual(3, result["usage"]["total_calls"])
        self.assertEqual(30, result["usage"]["input_tokens"])
        self.assertTrue(client.calls[0]["tools"])
        self.assertTrue(client.calls[2]["json_mode"])
        self.assertIn("tool", [m["role"] for m in client.calls[1]["messages"]])
        self.assertFalse(any("reasoning" in e["data"] for e in events))

    async def test_live_bad_json_shape_can_repair(self):
        client = Client(self.live_script(draft={"title": "broken"}) + [reply(json.dumps(good_draft()))])
        result, events, *_ = await self.run_flow(mode="live", client=client)
        self.assertEqual("completed", result["status"])
        self.assertEqual(4, len(client.calls))
        self.assertEqual(1, sum(e["type"] == "repair" for e in events))

    async def test_live_persistent_invalid_not_success(self):
        bad = good_draft()
        bad["body"] += "保温24小时。"
        client = Client(self.live_script(bad) + [reply(json.dumps(bad))])
        result, *_ = await self.run_flow(mode="live", client=client)
        self.assertEqual("needs_clarification", result["status"])
        self.assertIsNone(result["draft"])
        self.assertFalse(result["validation"]["passed"])
        self.assertEqual(4, len(client.calls))

    async def test_live_max_steps_prevents_unbounded_loop(self):
        client = Client([reply(tools=[tool("get_product")])] * 3)
        result, *_ = await self.run_flow(mode="live", client=client, max_steps=3)
        self.assertEqual("failed", result["status"])
        self.assertEqual(3, len(client.calls))

    async def test_invalid_tool_arguments_cannot_change_scope(self):
        client = Client([
            reply(tools=[tool("search_knowledge", {"query": "规则", "brand_id": "other"})]),
            *self.live_script(),
        ])
        result, events, _, retriever = await self.run_flow(mode="live", client=client)
        self.assertEqual("completed", result["status"])
        self.assertEqual(1, len(retriever.calls))
        self.assertEqual("northcup", retriever.calls[0][2])
        self.assertTrue(any(e["type"] == "tool_error" for e in events))

    async def test_unallowed_tool_rejected(self):
        client = Client([reply(tools=[tool("delete_all_products")]), *self.live_script()])
        result, events, *_ = await self.run_flow(mode="live", client=client)
        self.assertEqual("completed", result["status"])
        self.assertTrue(any(e["type"] == "tool_error" and e["data"]["tool"] == "unknown" for e in events))

    async def test_live_explanation_single_call(self):
        client = Client([reply(json.dumps({"intent": "explain", "answer": "RAG先检索，再生成。"}))])
        result, *_ = await self.run_flow(mode="live", message="解释RAG", client=client)
        self.assertEqual("completed", result["status"])
        self.assertIsNone(result["draft"])
        self.assertEqual(1, len(client.calls))

    async def test_recent_history_bounded_and_previous_passed(self):
        old = [{"message": "旧约束" + str(i), "status": "completed", "draft": good_draft(), "answer": "old"} for i in range(8)]
        client = Client([
            reply(tools=[tool("get_product"), tool("search_knowledge", {"query": "规则"}), tool("inspect_previous_draft")]),
            reply(json.dumps({"intent": "revise", "answer": "修改"})),
            reply(json.dumps(good_draft())),
        ])
        result, *_ = await self.run_flow(mode="live", message="简短一点", history=old, client=client)
        self.assertEqual("completed", result["status"])
        context = json.loads(client.calls[2]["messages"][1]["content"])
        self.assertEqual(6, len(context["recent_turns"]))
        self.assertEqual(good_draft(), context["previous_draft"])

    async def test_slogan_can_be_deleted_without_changing_body(self):
        first, *_ = await self.run_flow()
        history = [{"message": "生成文案", "draft": first["draft"], "status": "completed"}]
        result, *_ = await self.run_flow(message="删除口号", history=history)
        self.assertEqual("completed", result["status"])
        self.assertEqual("", result["draft"]["slogan"])
        self.assertEqual(first["draft"]["body"], result["draft"]["body"])

    async def test_model_error_safe_metadata_and_specific_message(self):
        from app.ai.provider import ModelError
        class ErrorClient:
            async def chat(self, *args, **kwargs):
                raise ModelError("private payload secret-value", code="authentication", status_code=401)
        result, events, *_ = await self.run_flow(mode="live", client=ErrorClient())
        self.assertEqual("failed", result["status"])
        self.assertIn("认证", result["answer"])
        event = next(e for e in events if e["type"] == "error")
        self.assertEqual("authentication", event["data"]["code"])
        self.assertEqual(401, event["data"]["status_code"])
        self.assertNotIn("secret-value", json.dumps([result, events]))

    async def test_factual_explanation_reads_product_first(self):
        client = Client([
            reply(json.dumps({"intent": "explain", "answer": "容量400mL。"})),
            reply(tools=[tool("get_product")]),
            reply(json.dumps({"intent": "explain", "answer": "容量400mL。"})),
        ])
        result, *_ = await self.run_flow(mode="live", message="这个商品容量多少？", client=client)
        self.assertEqual("completed", result["status"])
        self.assertEqual(3, len(client.calls))
        self.assertIsNone(result["draft"])

    async def test_explanation_cannot_deliver_unknown_performance(self):
        client = Client([
            reply(tools=[tool("get_product")]),
            reply(json.dumps({"intent": "explain", "answer": "这款杯子保温24小时。"})),
        ])
        result, *_ = await self.run_flow(mode="live", message="保温时长多少？", client=client)
        self.assertEqual("needs_clarification", result["status"])
        self.assertFalse(result["validation"]["passed"])
        self.assertNotIn("这款杯子保温24小时", result["answer"])

    async def test_failures_never_expose_exception_secrets(self):
        class SecretErrorClient:
            async def chat(self, *args, **kwargs):
                raise RuntimeError("Bearer secret-test-value")
        result, events, *_ = await self.run_flow(mode="live", client=SecretErrorClient())
        self.assertEqual("failed", result["status"])
        self.assertNotIn("secret-test-value", json.dumps([result, events]))


if __name__ == "__main__":
    unittest.main()
