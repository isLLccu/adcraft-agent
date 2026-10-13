"""Bounded, observable workflow with a deterministic offline demo.

Live planning uses actual model tool_calls. Demo is explicit deterministic code
and cannot demonstrate semantic model capability.
"""
import copy
import json
import re
import time
from pydantic import ValidationError
from .prompts import GENERATOR_PROMPT, PLANNER_PROMPT, REPAIR_PROMPT, TOOLS, PROMPT_VERSION, TOOL_VERSION
from .schemas import EmptyToolArgs, SearchKnowledgeArgs
from .provider import ModelError
from .validation import fact_map, fact_text, unsupported_request, validate_draft


def _json(text):
    if not isinstance(text, str):
        return None
    text = text.strip()
    fence = "\x60\x60\x60"
    if text.startswith(fence):
        text = re.sub(r"^" + fence + r"(?:json)?\s*|\s*" + fence + r"$", "", text, flags=re.IGNORECASE).strip()
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return None


def _intent(message, previous):
    if re.search(r"生成|写一|写个|写两|文案|广告|改写|改成|修改|重新写|简短|简洁|精简|更短|更口语|换.*标题|换.*口号", message):
        if re.search(r"为什么|為什麼|什么意思|什么是|解[释釋]|怎[么麼]验证|有什么依据", message) and not re.search(r"帮.*(?:修改|改写|生成)|请.*(?:修改|改写|生成)", message):
            return "explain"
        return "revise" if previous else "generate"
    if re.search(r"为什么|為什麼|什么|為何|怎么|如何|解释|解釋|介绍|区别|依据|靠谱吗|可靠|能不能|可以.*吗|吗[？?]?$|[？?]$", message):
        return "explain"
    return "revise" if previous else "generate"


class AIWorkflow:
    def __init__(self, settings, client, retriever):
        self.settings = settings
        self.client = client
        self.retriever = retriever

    async def run(self, product, documents, message, platform, history, emit):
        started = time.monotonic()
        usage = {"input_tokens": 0, "output_tokens": 0, "total_calls": 0, "latency_ms": 0}
        if not isinstance(product, dict) or not product.get("id") or not product.get("brand_id"):
            return {"status": "failed", "answer": "商品缺少必要标识或品牌信息。", "draft": None,
                    "evidence": [], "validation": {"passed": False, "issues": []}, "usage": usage}
        recent = [h for h in history if isinstance(h, dict) and (not h.get("product_id") or h["product_id"] == product.get("id"))][-6:]
        previous = next((h.get("draft") for h in reversed(recent) if isinstance(h.get("draft"), dict) and h.get("status", "completed") == "completed"), None)
        scoped_docs = [d for d in documents if isinstance(d, dict) and d.get("brand_id") == product.get("brand_id")]
        evidence = []
        mode = getattr(self.settings, "mode", "demo")
        intent = _intent(message, previous)

        async def event(type_, stage, text, data=None):
            await emit(type_, stage, text, data or {})

        def finish(status, answer, draft=None, validation=None):
            usage["latency_ms"] = round((time.monotonic() - started) * 1000)
            return {"status": status, "answer": answer, "draft": draft, "evidence": evidence,
                    "validation": validation or {"passed": status == "completed", "issues": []}, "usage": usage}

        await event("started", "understand", "读取本次需求与最近六轮约束", {
            "mode": mode, "history_turns": len(recent), "intent": intent,
            "prompt_version": PROMPT_VERSION, "tool_version": TOOL_VERSION,
        })
        if platform not in ("xiaohongshu", "taobao", "douyin"):
            return finish("failed", "平台参数不受支持。", validation={"passed": False, "issues": [{"code": "PLATFORM_INVALID", "message": "不支持的平台", "severity": "error"}]})

        async def search(query, top_k=None):
            retrieved = await self.retriever.search(scoped_docs, query, str(product["brand_id"]), top_k)
            document_ids = {d.get("id") for d in scoped_docs}
            safe = []
            for item in retrieved:
                if not isinstance(item, dict) or item.get("document_id") not in document_ids:
                    continue
                if item.get("brand_id") and item["brand_id"] != product["brand_id"]:
                    continue
                if item.get("id"):
                    safe.append(item)
            by_id = {e["id"]: e for e in evidence}
            by_id.update({e["id"]: e for e in safe})
            evidence[:] = list(by_id.values())
            return safe

        try:
            if mode == "demo":
                await event("tool_started", "tools", "读取当前商品事实", {"tool": "get_product"})
                await event("tool_result", "tools", "商品事实已读取", {"tool": "get_product", "fact_count": len(fact_map(product))})
                await event("tool_started", "retrieval", "按品牌范围检索资料", {"tool": "search_knowledge", "brand_id": product["brand_id"]})
                await search(f"{product.get('name', '')} {message}")
                await event("evidence", "retrieval", f"检索到 {len(evidence)} 条可用证据", {"evidence_ids": [e["id"] for e in evidence]})
                if previous:
                    await event("tool_result", "memory", "已读取会话中的真实历史草稿", {"tool": "inspect_previous_draft", "has_previous_draft": True})
                unknown = unsupported_request(message, product)
                if unknown and intent != "explain":
                    validation = {"passed": False, "issues": [{"code": "UNSUPPORTED_REQUEST", "message": text, "severity": "error"} for text in unknown]}
                    await event("validation", "validation", "请求包含未提供依据的商品承诺", validation)
                    return finish("needs_clarification", "商品资料没有这些承诺的依据：" + "、".join(unknown) + "。请补充已核实的规格或证明，或删除这些卖点。", validation=validation)
                if intent == "explain":
                    answer = self._demo_explain(message, product, previous, evidence, unknown)
                    await event("answer", "explain", "已根据可用资料完成解释", {"intent": "explain"})
                    return finish("completed", answer)
                await event("generation", "generation", "按确定性演示模板构建草稿", {"mode": "demo", "intent": intent})
                draft = self._demo_draft(product, evidence, message, platform, recent, previous)
            elif mode == "live":
                context = {
                    "selected_product": {k: product.get(k) for k in ("id", "name", "brand_id")},
                    "platform": platform, "has_brand_documents": bool(scoped_docs),
                    "recent_turns": [{k: h.get(k) for k in ("message", "answer", "platform", "status")} for h in recent],
                    "has_previous_draft": previous is not None, "request": message,
                }
                messages = [{"role": "system", "content": PLANNER_PROMPT},
                            {"role": "user", "content": json.dumps(context, ensure_ascii=False)}]
                called_tools = set()
                max_steps = max(1, min(int(getattr(self.settings, "max_agent_steps", 6)), 12))
                decision = None
                total_tools = 0
                for step in range(max_steps):
                    await event("model_started", "planning", "模型选择下一步操作", {"step": step + 1, "max_steps": max_steps})
                    reply = await self._chat(messages, usage, tools=TOOLS)
                    tool_calls = reply.get("tool_calls") or []
                    if tool_calls:
                        if not isinstance(tool_calls, list) or len(tool_calls) > 3 or total_tools + len(tool_calls) > max_steps * 3:
                            await event("limit", "planning", "工具调用超过单轮或总量限制", {})
                            return finish("failed", "工具调用超过限制，请缩小本次任务后重试。")
                        messages.append({"role": "assistant", "content": reply.get("content") or None, "tool_calls": tool_calls})
                        for position, call in enumerate(tool_calls):
                            total_tools += 1
                            call_id = call.get("id", f"step-{step}-{position}") if isinstance(call, dict) else f"step-{step}-{position}"
                            function = call.get("function", {}) if isinstance(call, dict) else {}
                            name = function.get("name", "") if isinstance(function, dict) else ""
                            raw_args = function.get("arguments", "{}") if isinstance(function, dict) else "{}"
                            safe_name = name if name in {"get_product", "search_knowledge", "inspect_previous_draft"} else "unknown"
                            await event("tool_started", "tools", "执行受限工具", {"tool": safe_name, "step": step + 1})
                            try:
                                if safe_name == "unknown":
                                    raise ValueError("未授权的工具")
                                if not isinstance(raw_args, str) or len(raw_args) > 5000:
                                    raise ValueError("工具参数必须是长度受限的 JSON 字符串")
                                args = _json(raw_args)
                                if name == "search_knowledge":
                                    args = SearchKnowledgeArgs.model_validate(args)
                                    result = {"evidence": await search(args.query, args.top_k)}
                                    await event("evidence", "retrieval", "检索到品牌范围内的资料", {"evidence_ids": [e["id"] for e in result["evidence"]]})
                                else:
                                    EmptyToolArgs.model_validate(args)
                                    result = product if name == "get_product" else {"draft": previous}
                                called_tools.add(name)
                                await event("tool_result", "tools", "工具执行完成", {"tool": name, "evidence_count": len(evidence) if name == "search_knowledge" else None})
                            except (ValidationError, ValueError, TypeError):
                                result = {"error": "工具未授权或参数无效；商品/品牌范围由服务端限定，请按工具 schema 重试。"}
                                await event("tool_error", "tools", "工具参数校验未通过", {"tool": safe_name})
                            messages.append({"role": "tool", "tool_call_id": call_id, "content": json.dumps(result, ensure_ascii=False)})
                        continue
                    parsed = _json(reply.get("content"))
                    if isinstance(parsed, dict) and parsed.get("intent") in ("generate", "revise", "explain", "clarify"):
                        decision = {"intent": parsed["intent"], "answer": parsed.get("answer") if isinstance(parsed.get("answer"), str) else ""}
                    else:
                        decision = {"intent": intent, "answer": str(reply.get("content") or "")}
                    chosen = decision["intent"]
                    required = {"get_product"}
                    if scoped_docs:
                        required.add("search_knowledge")
                    if chosen == "revise" and previous:
                        required.add("inspect_previous_draft")
                    if chosen == "explain" and re.search(r"商品|产品|杯|容量|材质|价格|售价|重量|保温|防漏|认证|文案|草稿|口号|标题|依据", message):
                        required = {"get_product"}
                        if previous and re.search(r"文案|草稿|口号|标题|为什么|依据", message):
                            required.add("inspect_previous_draft")
                        missing = required - called_tools
                    else:
                        missing = required - called_tools if chosen in ("generate", "revise") else set()
                    if missing:
                        messages.append({"role": "assistant", "content": reply.get("content") or ""})
                        messages.append({"role": "user", "content": "回答商品事实、生成或修改前仍需调用这些工具：" + ", ".join(sorted(missing)) + "。随后返回决策 JSON。"})
                        decision = None
                        continue
                    break
                if decision is None:
                    await event("limit", "planning", "模型未在最大步骤内完成决策", {"max_steps": max_steps})
                    return finish("failed", "已达到 Agent 步数限制，未生成可验收的结果。请缩小任务后重试。")
                intent = decision["intent"]
                if intent == "clarify":
                    return finish("needs_clarification", decision.get("answer") or "请补充商品事实或明确本次要求。")
                if intent == "explain":
                    answer = decision.get("answer")
                    if not isinstance(answer, str) or not answer.strip():
                        return finish("failed", "模型没有返回可用解释，请重试。")
                    # Conceptual Q&A needs no tool; factual explanations still obey
                    # the same limited promise and numeric authority checks.
                    unsupported = unsupported_request(answer, product)
                    if unsupported:
                        validation = {"passed": False, "issues": [{"code": "UNSUPPORTED_ANSWER", "message": value, "severity": "error"} for value in unsupported]}
                        await event("validation", "explain", "解释回答包含无依据的商品承诺", validation)
                        return finish("needs_clarification", "解释中出现无依据的商品承诺，未交付该回答。请补充商品资料或重试。", validation=validation)
                    await event("answer", "explain", "模型完成解释回答", {"intent": "explain"})
                    return finish("completed", answer)
                unknown = unsupported_request(message, product)
                if unknown:
                    validation = {"passed": False, "issues": [{"code": "UNSUPPORTED_REQUEST", "message": text, "severity": "error"} for text in unknown]}
                    await event("validation", "validation", "请求缺少商品承诺依据", validation)
                    return finish("needs_clarification", "资料未支持本次请求中的商品承诺，请补充核实资料或删除这些卖点：" + "、".join(unknown), validation=validation)
                generation_context = {
                    "product": product, "evidence": evidence, "platform": platform,
                    "previous_draft": previous, "recent_turns": [{k: h.get(k) for k in ("message", "answer", "platform")} for h in recent],
                    "request": message, "intent": intent,
                }
                generator_messages = [{"role": "system", "content": GENERATOR_PROMPT},
                                      {"role": "user", "content": json.dumps(generation_context, ensure_ascii=False)}]
                await event("generation", "generation", "模型生成结构化内容", {"intent": intent, "evidence_count": len(evidence)})
                reply = await self._chat(generator_messages, usage, json_mode=True)
                draft = _json(reply.get("content"))
            else:
                return finish("failed", "运行模式无效。")

            validation = validate_draft(draft, product, evidence, platform)
            await event("validation", "validation", "程序校验已完成", validation)
            repairs = max(0, min(int(getattr(self.settings, "max_repair_attempts", 1)), 3))
            if mode == "live":
                for attempt in range(repairs):
                    if validation["passed"]:
                        break
                    await event("repair", "repair", "根据校验问题有限修复草稿", {"attempt": attempt + 1, "max_attempts": repairs, "issues": validation["issues"]})
                    repair_messages = list(generator_messages) + [
                        {"role": "assistant", "content": json.dumps(draft, ensure_ascii=False)},
                        {"role": "user", "content": REPAIR_PROMPT + "\n" + json.dumps({"issues": validation["issues"]}, ensure_ascii=False)}]
                    reply = await self._chat(repair_messages, usage, json_mode=True)
                    draft = _json(reply.get("content"))
                    validation = validate_draft(draft, product, evidence, platform)
                    await event("validation", "validation", "修复后重新校验", {**validation, "attempt": attempt + 1})
            if not validation["passed"]:
                factual = {"UNSUPPORTED_NUMBER", "UNSUPPORTED_PROMISE", "UNSUPPORTED_IMAGE_PROMISE", "UNSUPPORTED_IMAGE_NUMBER", "CLAIM_FACT_MISMATCH", "UNCITED_NUMERIC_FACT", "INVALID_FACT_ID"}
                status = "needs_clarification" if any(i["code"] in factual for i in validation["issues"]) else "failed"
                return finish(status, "草稿未通过校验，未作为可用内容交付。请补充资料、调整要求或重试。", validation=validation)
            await event("completed", "complete", "草稿通过程序校验，可人工审阅", {"intent": intent, "mode": mode})
            return finish("completed", "已根据商品事实和品牌资料" + ("修改" if intent == "revise" else "生成") + "草稿。请确认表达和素材方案。" + ("当前为确定性演示模式。" if mode == "demo" else ""), draft, validation)
        except Exception as exc:
            # Never emit raw exceptions, provider bodies, URLs or secret headers.
            error_data = {"error_type": type(exc).__name__}
            public_message = "当前任务执行失败。请检查模型服务配置或稍后重试。"
            if isinstance(exc, ModelError):
                messages_by_code = {
                    "configuration": "模型服务配置无效，请检查服务地址、模型名称和 API Key。",
                    "authentication": "模型服务认证或权限失败，请检查 API Key 和账户权限。",
                    "quota_exhausted": "模型服务额度不足，请检查账户余额或配额。",
                    "rate_limit": "模型服务限流，请稍后重试。",
                    "upstream_unavailable": "模型服务暂时不可用，请稍后重试。",
                    "timeout": "模型调用超时；上游可能已接收请求，请注意重复调用可能计费。",
                    "network": "无法连接模型服务，请检查服务地址与网络。",
                    "truncated": "模型输出被截断，请缩短任务或检查输出长度配置。",
                    "refusal": "模型服务未生成该内容，请调整任务后重试。",
                    "empty_response": "模型服务返回空内容，请稍后重试。",
                    "invalid_response": "模型响应结构无效，请检查兼容接口配置。",
                    "invalid_request": "模型服务拒绝了请求参数，请检查接口兼容性。",
                    "demo_mode": "演示模式禁止调用外部模型，请检查运行模式。",
                }
                error_data.update({"code": exc.code, "retryable": exc.retryable, "status_code": exc.status_code})
                public_message = messages_by_code.get(exc.code, public_message)
            await event("error", "failed", "执行过程中发生错误", error_data)
            return finish("failed", public_message)

    async def _chat(self, messages, usage, tools=None, json_mode=False):
        usage["total_calls"] += 1
        response = await self.client.chat(messages, tools=tools, json_mode=json_mode)
        counts = response.get("usage") or {}
        usage["input_tokens"] += int(counts.get("input_tokens") or 0)
        usage["output_tokens"] += int(counts.get("output_tokens") or 0)
        return response

    @staticmethod
    def _demo_explain(message, product, previous, evidence, unknown):
        if re.search(r"RAG|检索增强|檢索增強", message, re.IGNORECASE):
            return "RAG 是先检索资料，再把命中的片段交给模型回答。本项目将商品事实与品牌知识分开：商品事实提供规格依据，品牌资料提供表达规则。检索结果保留来源 ID，但引用存在不代表语义必然正确，仍需校验与人工审阅。当前是确定性演示模式。"
        if re.search(r"agent|智能体|智能體|工具调用", message, re.IGNORECASE):
            return "Live 模式由模型决定调用 get_product、search_knowledge 或 inspect_previous_draft，服务端校验参数并限制品牌范围和步数，随后生成草稿并校验。Demo 模式按固定流程执行，不调用模型，也不能用于证明真实 Agent 效果。"
        if unknown or re.search(r"保温|保溫|认证|認證|质保|質保|依据|为什么", message):
            return "现有商品资料只支持这些事实：" + "；".join(fact_text(f) for f in fact_map(product).values()) + "。资料没有提供的性能、认证或保证不能作为卖点。品牌文档只决定表达规则，不能补足商品规格。" + ("已有草稿的 claims 和 evidence_ids 分别记录事实与资料引用。" if previous else "")
        if previous:
            return "当前草稿标题是“" + str(previous.get("title", "")) + "”。文案基于已录入的商品事实，资料引用用于追踪品牌要求。你可以指定修改标题、正文、口号或素材方案；修改时会保留此前有效约束。当前演示支持固定解释模板，接入 Live 模型后支持自由问答。"
        return "我可以根据当前商品资料生成或修改电商文案，也可以解释检索、工具调用和校验流程。当前商品是“" + product.get("name", "") + "”，已录入 " + str(len(fact_map(product))) + " 条事实。当前为确定性演示模式，请给出希望完成的具体任务。"

    @staticmethod
    def _demo_draft(product, evidence, message, platform, recent, previous):
        facts = list(fact_map(product).values())
        constraints = [str(h.get("message", "")) for h in recent] + [message]
        all_requests = "\n".join(constraints)
        # Demo supports a small, documented set of commands. Live semantics are
        # provided by the model; both modes share citation and grounding checks.
        banned_labels = set()
        for request in constraints:
            for fact in facts:
                label = str(fact.get("label", ""))
                aliases = {"售价": "售价|售價|价格|價格|价钱|價錢", "重量": "重量|克重", "材质": "材质|材質|材料"}.get(label, re.escape(label))
                if label and re.search(r"(?:不要|别|不提|省略|删除|去掉).{0,8}(?:" + aliases + ")", request):
                    banned_labels.add(label)
                if label and re.search(r"(?:恢复|重新加入|可以提|(?<!不)要提).{0,8}(?:" + aliases + ")", request):
                    banned_labels.discard(label)
        facts = [f for f in facts if f.get("label") not in banned_labels]
        claims = [{"text": f"{f.get('label', '')}：{f.get('value', '')}", "fact_ids": [str(f["id"])]} for f in facts]
        points = [c["text"] for c in claims][:6] or ["查看商品资料，选择适合自己的日常用品"]
        brief, tone = False, "简洁"
        for request in constraints:
            if re.search(r"详细|詳細|展开|展開|更完整|不要.{0,5}(?:简短|簡短|精简)", request):
                brief = False
            elif re.search(r"简短|简洁|精简|更短|短一点|少一点", request):
                brief = True
            if re.search(r"正式|专业|專業|不要.{0,5}(?:口语|口語|聊天)", request):
                tone = "简洁"
            elif re.search(r"口语|口語|聊天|朋友", request):
                tone = "口语"
        name = str(product.get("name", "商品"))
        title = name + ("，日常出门带上它" if tone == "口语" else "｜日常随行")
        body = ("今天出门，带上" if tone == "口语" else "认识") + name + "。\n" + "；".join(points) + "。"
        if not brief:
            body += "\n从真实商品信息出发，选一件适合日常的用品。"
        images = [
            {"label": "日常场景", "prompt": "生成明亮简洁的日常通勤环境纯背景，浅色桌面，柔和自然光线；中央预留商品合成空间，上方为文案排版留白。不生成商品或商品主体，不绘制文字和Logo。", "negative_prompt": "不要商品主体，不要文字或Logo，不要虚构认证标志"},
            {"label": "简洁棚拍", "prompt": "生成干净浅色棚拍纯背景，柔和照明与低对比阴影；中央与下方留出大片空白供后续本地商品合成，上方预留排版空间。不生成商品或商品主体，不绘制文字和Logo。", "negative_prompt": "不要商品主体，不要文字或Logo，不要多余物件"},
        ]
        draft = {"title": title, "body": body, "slogan": "让随行更从容", "selling_points": points,
                 "claims": claims, "evidence_ids": [e["id"] for e in evidence], "image_prompts": images, "platform": platform}
        if previous:
            draft = copy.deepcopy(previous)
            draft["platform"] = platform
            draft["evidence_ids"] = [e["id"] for e in evidence]
            draft["claims"] = claims
            draft["selling_points"] = points
            if re.search(r"标题|標題", message) and not re.search(r"正文|全部|整体|整體", message):
                draft["title"] = name if brief else title
            elif re.search(r"口号|口號|slogan", message, re.IGNORECASE) and not re.search(r"正文|全部|整体|整體", message):
                if re.search(r"(?:删除|刪除|去掉|不要|取消).{0,5}(?:口号|口號|slogan)", message, re.IGNORECASE):
                    draft["slogan"] = ""
                else:
                    draft["slogan"] = "随行，从这一刻开始" if tone == "口语" else "自在随行，每一程"
            elif re.search(r"背景|图片|圖片|素材", message):
                draft["image_prompts"] = images
                if re.search(r"第二|第2|2张", message):
                    draft["image_prompts"] = copy.deepcopy(previous.get("image_prompts", images))
                    if len(draft["image_prompts"]) > 1:
                        draft["image_prompts"][1]["prompt"] = images[1]["prompt"] + "采用明亮白色背景。"
            else:
                draft["title"] = name if brief else title
                draft["body"] = body
            # A persistent omitted fact cannot survive in preserved user-facing text.
            for fact in product.get("facts", []):
                if fact.get("label") in banned_labels:
                    for field in ("title", "body", "slogan"):
                        draft[field] = re.sub(r"[^。；;\n]*" + re.escape(str(fact.get("label", ""))) + r"[^。；;\n]*[。；;]?", "", str(draft.get(field, "")))
        if re.search(r"(?:删除|刪除|去掉|不要|取消).{0,5}(?:口号|口號|slogan)", message, re.IGNORECASE):
            draft["slogan"] = ""
        return draft
