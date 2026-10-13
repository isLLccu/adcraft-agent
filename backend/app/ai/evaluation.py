"""Reproducible regression evaluation, with explicit offline/live boundaries.

Offline cases exercise real BM25, deterministic validation and demo behavior.
Passing them is not evidence of real model quality, autonomous agent ability,
marketing effectiveness, semantic retrieval quality or production reliability.
"""

from __future__ import annotations

import copy
import json
import uuid
from collections import Counter
from dataclasses import replace
from datetime import datetime, timezone

from .config import AISettings, PROJECT_ROOT
from .provider import ModelClient
from .retrieval import Retriever, chunk_documents
from .validation import fact_map, fact_text, validate_draft
from .workflow import AIWorkflow


def load_cases() -> list[dict]:
    return json.loads((PROJECT_ROOT / "data" / "evaluation_cases.json").read_text(encoding="utf-8"))


def _grounded_draft(product: dict, evidence: list[dict]) -> dict:
    facts = list(fact_map(product).values())
    points = [fact_text(fact) for fact in facts]
    return {
        "title": str(product["name"]),
        "body": "；".join(points),
        "slogan": "从真实商品信息出发",
        "selling_points": points,
        "claims": [{"text": fact_text(fact), "fact_ids": [str(fact["id"])]} for fact in facts],
        "evidence_ids": [item["id"] for item in evidence],
        "image_prompts": [{"label": "商品展示", "prompt": "保留原始商品主体，采用明亮简洁背景。", "negative_prompt": "不改变商品外观"}],
        "platform": "xiaohongshu",
    }


def _mutate(draft: dict, mutation: str) -> dict:
    draft = copy.deepcopy(draft)
    if mutation == "missing_body":
        draft.pop("body")
    elif mutation == "wrong_platform":
        draft["platform"] = "taobao"
    elif mutation == "unknown_number":
        draft["body"] += "。容量500mL。"
    elif mutation == "wrong_unit":
        draft["body"] += "。容量400g。"
    elif mutation == "invalid_fact":
        draft["claims"][0]["fact_ids"] = ["fact-does-not-exist"]
    elif mutation == "mismatched_fact":
        draft["claims"][0]["fact_ids"] = ["f-weight"]
    elif mutation == "uncited_number":
        draft["claims"] = []
    elif mutation == "invalid_evidence":
        draft["evidence_ids"] = ["evidence-does-not-exist"]
    elif mutation == "unsupported_promises":
        draft["body"] += "。产品防漏，滴水不漏。"
        draft["image_prompts"][0]["prompt"] += "添加防漏卖点。"
    elif mutation != "valid":
        raise ValueError("Unknown evaluation mutation")
    return draft


async def _evaluate_case(case: dict, products: dict, documents: list[dict], retriever: Retriever, workflow: AIWorkflow) -> dict:
    expected = copy.deepcopy(case["expected"])
    product = products.get(case["product_id"])
    item = {"id": case["id"], "category": case["category"], "input": case["input"], "expected": expected, "actual": {}, "passed": False}
    if product is None:
        item["actual"] = {"error": "评测样例商品不存在", "product_id": case["product_id"]}
        return item
    if case["category"] == "retrieval":
        hits = await retriever.search(documents, case["input"], product["brand_id"])
        document_ids = [hit["document_id"] for hit in hits]
        by_id = {doc["id"]: doc for doc in documents}
        scope_ok = all(by_id.get(identifier, {}).get("brand_id") == product["brand_id"] for identifier in document_ids)
        item["actual"] = {"document_ids": document_ids, "scores": [hit["score"] for hit in hits], "brand_scope_ok": scope_ok, "retrieval_mode": retriever.last_mode}
        checks = [scope_ok]
        if expected.get("contains_document"):
            checks.append(expected["contains_document"] in document_ids)
        if expected.get("empty"):
            checks.append(not hits)
        checks.append(not set(document_ids).intersection(expected.get("excludes_documents", [])))
        item["passed"] = all(checks)
    elif case["category"] == "validation":
        scoped = [doc for doc in documents if doc.get("brand_id") == product["brand_id"]]
        evidence = chunk_documents(scoped[:1], retriever.settings.chunk_size, retriever.settings.chunk_overlap)[:1]
        draft = _mutate(_grounded_draft(product, evidence), case["mutation"])
        result = validate_draft(draft, product, evidence, "xiaohongshu")
        codes = sorted({issue["code"] for issue in result["issues"]})
        item["actual"] = {"passed": result["passed"], "codes": codes}
        item["passed"] = result["passed"] == expected["passed"] and set(expected["codes"]).issubset(codes)
    elif case["category"] == "workflow":
        emitted = []

        async def emit(type_, stage, message, data=None):
            emitted.append({"type": type_, "stage": stage})

        history = []
        previous = None
        if case.get("preceding_message"):
            previous = await workflow.run(product, documents, case["preceding_message"], case["platform"], [], emit)
            history = [{**previous, "message": case["preceding_message"], "platform": case["platform"], "product_id": product["id"]}]
        result = await workflow.run(product, documents, case["input"], case["platform"], history, emit)
        draft = result.get("draft")
        actual = {"status": result.get("status"), "has_draft": isinstance(draft, dict), "validation_passed": result.get("validation", {}).get("passed", False), "calls": result.get("usage", {}).get("total_calls", 0) + (previous or {}).get("usage", {}).get("total_calls", 0), "stages": sorted({event["stage"] for event in emitted})}
        checks = [actual["status"] == expected["status"], actual["has_draft"] == expected["has_draft"]]
        if "validation_passed" in expected:
            checks.append(actual["validation_passed"] == expected["validation_passed"])
        if expected.get("evidence_brand"):
            by_id = {doc["id"]: doc for doc in documents}
            actual["evidence_brand_ok"] = bool(result.get("evidence")) and all(by_id.get(hit["document_id"], {}).get("brand_id") == expected["evidence_brand"] for hit in result.get("evidence", []))
            checks.append(actual["evidence_brand_ok"])
        if expected.get("shorter_body"):
            original_body = str((previous or {}).get("draft", {}).get("body", "")) if isinstance((previous or {}).get("draft"), dict) else ""
            new_body = str((draft or {}).get("body", ""))
            actual["previous_body_length"] = len(original_body)
            actual["body_length"] = len(new_body)
            checks.append(bool(new_body) and len(new_body) < len(original_body))
        if expected.get("omits_fact"):
            omitted = fact_map(product).get(expected["omits_fact"], {})
            serialized = json.dumps({k: (draft or {}).get(k) for k in ("title", "body", "slogan", "selling_points", "claims")}, ensure_ascii=False)
            actual["omitted_fact_absent"] = bool(omitted) and omitted.get("value", "") not in serialized and expected["omits_fact"] not in serialized
            checks.append(actual["omitted_fact_absent"])
        if expected.get("no_unsupported_claims"):
            codes = {issue["code"] for issue in result.get("validation", {}).get("issues", [])}
            actual["unsupported_claims_absent"] = not codes.intersection({"UNSUPPORTED_NUMBER", "UNSUPPORTED_PROMISE", "UNSUPPORTED_IMAGE_PROMISE"})
            checks.append(actual["unsupported_claims_absent"])
        if expected.get("nonempty_answer"):
            actual["nonempty_answer"] = bool(str(result.get("answer", "")).strip())
            checks.append(actual["nonempty_answer"])
        item["actual"] = actual
        item["passed"] = all(checks)
    else:
        item["actual"] = {"error": "未知评测类别"}
    return item


async def _run(settings: AISettings, products: list[dict], documents: list[dict], cases: list[dict], mode: str) -> dict:
    client = ModelClient(settings)
    retriever = Retriever(settings, client)
    workflow = AIWorkflow(settings, client, retriever)
    by_id = {product["id"]: product for product in products}
    results = []
    for case in cases:
        try:
            results.append(await _evaluate_case(case, by_id, documents, retriever, workflow))
        except Exception as exc:
            # Provider bodies/URLs/secrets must never enter a saved report.
            results.append({"id": case["id"], "category": case["category"], "input": case["input"], "expected": case["expected"], "actual": {"error": "评测执行失败", "error_type": type(exc).__name__}, "passed": False})
    totals = Counter(result["category"] for result in results)
    passed_by_category = Counter(result["category"] for result in results if result["passed"])
    passed = sum(result["passed"] for result in results)
    count = len(results)
    notes = [
        "样本来自自建演示资料，固定回归集规模有限，结果不能代表真实用户或业务收益。",
        "程序校验只覆盖 schema、数值/单位、引用和维护的承诺规则，不能证明所有语义声明正确。",
        "此报告不包含图片质量、真实投放、生产并发或供应商收费保证。",
    ]
    if mode == "offline":
        notes.insert(0, "离线评测：真实 BM25、程序校验与确定性演示工作流；未调用外部 LLM、Embedding 或图片 API。")
        notes.append("通过离线用例不证明真实模型生成质量或模型驱动 Agent 的效果；没有与旧版比较，也不提供提升百分比。")
    else:
        notes.insert(0, "Live 评测：用户通过 --live --confirm-paid 明确启用，可能产生模型和 Embedding 费用。")
        notes.append("Live 仅运行工作流样例并使用程序断言；需另行人工评阅自然度、品牌风格和语义依据。")
    return {
        "id": f"eval-{uuid.uuid4().hex[:12]}",
        "mode": mode,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "cases_total": count,
        "passed": passed,
        "failed": count - passed,
        "pass_rate": round(passed / count, 4) if count else 0,
        "metrics": [{"name": category, "value": round(passed_by_category[category] / total, 4), "total": total, "passed": passed_by_category[category]} for category, total in sorted(totals.items())],
        "cases": results,
        "notes": notes,
    }


async def run_evaluation(settings: AISettings, products: list[dict], documents: list[dict]) -> dict:
    """Public API evaluation: always offline, regardless of configured secrets."""
    offline = replace(settings, force_demo=True, llm_api_key="", embedding_api_key="", image_api_key="", image_provider="demo")
    return await _run(offline, products, documents, load_cases(), "offline")


async def run_selected_evaluation(settings: AISettings, products: list[dict], documents: list[dict], *, live: bool = False, confirm_paid: bool = False, limit: int | None = None) -> dict:
    """CLI boundary. API routes must use run_evaluation rather than this helper."""
    if live and not confirm_paid:
        raise ValueError("Live 评测必须同时提供 --live 和 --confirm-paid。")
    if live:
        if not settings.llm_api_key:
            raise ValueError("Live 评测需要配置 LLM_API_KEY。")
        config = replace(settings, force_demo=False)
        cases = [case for case in load_cases() if case["category"] == "workflow"]
        count = 2 if limit is None else limit
    else:
        config = replace(settings, force_demo=True, llm_api_key="", embedding_api_key="", image_api_key="", image_provider="demo")
        cases = load_cases()
        count = len(cases) if limit is None else limit
    if not 1 <= count <= len(cases):
        raise ValueError(f"limit 必须在 1 到 {len(cases)} 之间。")
    return await _run(config, products, documents, cases[:count], "live" if live else "offline")
