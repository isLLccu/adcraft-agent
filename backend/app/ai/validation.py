"""Deterministic schema, citation and limited grounding checks.

These checks catch a useful class of errors; they do not prove every semantic claim.
Numeric facts use value AND unit, so 400 mL cannot authorize 400 g. Unknown
qualitative promises use an explicitly maintained keyword policy, not an LLM judge.
"""
import re
import unicodedata
from typing import Any
from pydantic import ValidationError
from .schemas import Draft

# Long units must precede short units in the regular expression.
_NUMBER = re.compile(
    r"(?<![\d.])(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>毫升|毫克|千克|公斤|公分|厘米|小时|小時|分钟|分鐘|个月|個月|瓦特|摄氏度|攝氏度|不锈钢|不鏽鋼|mm|cm|kg|ml|mL|ML|mAh|mah|小时|hrs?|years?|年|月|天|秒|元|块|塊|%|％|℃|度|g|W|w|L|l)?",
    re.IGNORECASE,
)
_UNIT_ALIASES = {
    "毫升": "ml", "l": "l", "毫克": "mg", "千克": "kg", "公斤": "kg",
    "公分": "cm", "厘米": "cm", "小时": "h", "小時": "h", "hr": "h", "hrs": "h",
    "分钟": "min", "分鐘": "min", "个月": "month", "個月": "month",
    "瓦特": "w", "摄氏度": "c", "攝氏度": "c", "℃": "c", "％": "%",
    "块": "元", "塊": "元", "不锈钢": "stainless", "不鏽鋼": "stainless",
    "years": "年", "year": "年",
}
_PROMISES = [
    ("保温", r"保温|保溫"),
    ("保温时长", r"(?:\d+|[一二三四五六七八九十]+)\s*(?:小时|小時|hrs?).{0,5}(?:保温|保溫)|(?:保温|保溫).{0,6}(?:\d+|[一二三四五六七八九十]+)\s*(?:小时|小時|hrs?)"),
    ("防漏", r"不漏水|零泄漏|零漏水|防漏|防水|滴水不漏"),
    ("食品安全认证", r"食品级|食品級|食品安全认证|食品安全認證|FDA|BPA[- ]?free|不含BPA|无BPA|無BPA"),
    ("抗菌", r"抗菌|杀菌|殺菌|除菌"),
    ("终身质保", r"终身质保|終身質保|永久保修|終身保固|终身保固"),
    ("健康功效", r"美白|治疗|治療|降血压|降血壓|改善睡眠|治愈|治癒"),
    ("绝对承诺", r"百分之百|百分百|绝对安全|絕對安全|保证有效|保證有效|永不损坏|永不損壞|全网第一|全網第一"),
    ("现货承诺", r"现货|現貨|保证当天发货|保證當天發貨"),
]
_NEGATION = re.compile(
    r"不要|不得(?:声称|聲稱)?|不能|禁止|不允许|不允許|避免|别写|別寫|不提|勿"
    r"|不添加|不写|不寫|不包含|不编造|不編造|不宣称|不宣稱|不声称|不聲稱"
    r"|没有|沒有|未提供|未经|未經|不承诺|不承諾|无法确认|無法確認"
)
# Negation applies to a local clause or a coordinated negative list. A comma,
# contrast, or an explicit new positive action ends its scope. The list separator
# '、' alone does not: '不要写防漏、保温24小时' negates both items.
_POSITIVE_ACTION = r"(?:突出|强调|強調|宣称|宣稱|声称|聲稱|写上|寫上|加入|添加|标注|標註|承诺|承諾|宣传|宣傳|主打)"
_CLAUSE_BREAK = re.compile(
    r"[。！？；;，,\n]|(?:但是|然而|不过|不過|而是|但)"
    r"|(?:并且|並且|同时|同時|然后|然後|另外|并|並)(?=\s*(?:请|請|要)?\s*" + _POSITIVE_ACTION + ")"
)


def normalized_text(text: Any) -> str:
    return unicodedata.normalize("NFKC", str(text)).lower()


def numeric_tokens(text: Any) -> set[tuple[str, str]]:
    """Keep magnitude and units; no automatic conversion or financial inference."""
    text = unicodedata.normalize("NFKC", str(text))
    tokens = set()
    for match in _NUMBER.finditer(text):
        number = match.group("value")
        number = number.rstrip("0").rstrip(".") if "." in number else number.lstrip("0") or "0"
        unit = (match.group("unit") or "").lower()
        tokens.add((number, _UNIT_ALIASES.get(unit, unit)))
    return tokens


def fact_map(product: dict) -> dict[str, dict]:
    facts = product.get("facts", []) if isinstance(product, dict) else []
    return {str(f["id"]): f for f in facts if isinstance(f, dict) and f.get("id")}


def fact_text(fact: dict) -> str:
    return f"{fact.get('label', '')} {fact.get('value', '')}"


def _segments(text: str):
    return _CLAUSE_BREAK.split(text)


def _positive(text: str, start: int) -> bool:
    # Fixed negation vocabulary deliberately excludes a generic '不': phrases
    # such as '不漏水' are positive performance promises. Scope resets before a
    # later positive action, so '不要写防漏，但强调保温24小时' is still blocked.
    prefix = text[:start]
    boundaries = list(_CLAUSE_BREAK.finditer(prefix))
    clause_start = boundaries[-1].end() if boundaries else 0
    return not _NEGATION.search(prefix[clause_start:])


def unsupported_promises(text: str, product: dict) -> list[str]:
    authoritative_parts = (
        [str(product.get("name", "")), str(product.get("description", ""))]
        + [fact_text(f) for f in fact_map(product).values()]
        + [str(s) for s in product.get("selling_points", [])]
    )
    # Negative source statements are not positive evidence for a capability.
    authority = normalized_text(" ".join(
        segment for part in authoritative_parts for segment in _segments(part)
        if not _NEGATION.search(segment)
    ))
    found = []
    for label, expression in _PROMISES:
        for match in re.finditer(expression, text, re.IGNORECASE):
            if not _positive(text, match.start()):
                continue
            # A keyword alone in a description is not a new certification:
            # the exact detected assertion must have a source in product data.
            if normalized_text(match.group()) not in authority and label not in found:
                found.append(label)
    return found


def unsupported_request(message: str, product: dict) -> list[str]:
    """Catch explicit new performance claims before demo/live generation.

    Counts ('生成2版'), negative instructions and questions are not numeric facts.
    A question containing an unknown specification is handled as clarification.
    """
    allowed = set()
    for fact in fact_map(product).values():
        allowed |= numeric_tokens(fact_text(fact))
    allowed |= numeric_tokens(product.get("name", ""))
    issues = unsupported_promises(message, product)
    for match in _NUMBER.finditer(unicodedata.normalize("NFKC", message)):
        unit = match.group("unit")
        if not unit or not _positive(message, match.start()):
            continue
        token = next(iter(numeric_tokens(match.group())), None)
        if token and token not in allowed:
            issues.append(f"未提供的商品数值：{match.group()}")
    return list(dict.fromkeys(issues))


def validate_draft(draft: Any, product: dict, evidence: list[dict], platform: str) -> dict:
    """Never raise on malformed model data; return actionable, bounded issues."""
    issues = []

    def issue(code: str, message: str, severity: str = "error"):
        value = {"code": code, "message": message[:400], "severity": severity}
        if value not in issues:
            issues.append(value)

    try:
        parsed = Draft.model_validate(draft)
    except (ValidationError, TypeError, ValueError) as exc:
        if isinstance(exc, ValidationError):
            for error in exc.errors()[:12]:
                path = ".".join(str(part) for part in error["loc"]) or "draft"
                issue("SCHEMA_INVALID", f"字段 {path} 不符合结构要求：{error['type']}")
        else:
            issue("SCHEMA_INVALID", "生成结果必须是符合 Draft 结构的对象")
        return {"passed": False, "issues": issues}

    data = parsed.model_dump()
    if data["platform"] != platform:
        issue("PLATFORM_MISMATCH", "生成内容的平台与用户选择不一致")
    facts = fact_map(product)
    allowed_numbers = numeric_tokens(product.get("name", ""))
    for fact in facts.values():
        allowed_numbers |= numeric_tokens(fact_text(fact))

    trusted_evidence = {}
    for item in evidence if isinstance(evidence, list) else []:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        if item.get("brand_id") and item["brand_id"] != product.get("brand_id"):
            issue("CROSS_BRAND_EVIDENCE", "证据包含其他品牌资料")
            continue
        trusted_evidence[item["id"]] = item
    for evidence_id in data["evidence_ids"]:
        if evidence_id not in trusted_evidence:
            issue("INVALID_EVIDENCE_ID", f"引用的资料 ID 不存在或不可用：{evidence_id}")

    claim_numbers = set()
    for index, claim in enumerate(data["claims"]):
        supported = set()
        for fact_id in claim["fact_ids"]:
            if fact_id not in facts:
                issue("INVALID_FACT_ID", f"第 {index + 1} 条商品声明引用了不存在的事实 ID：{fact_id}")
            else:
                supported |= numeric_tokens(fact_text(facts[fact_id]))
        numbers = numeric_tokens(claim["text"])
        if numbers - supported:
            issue("CLAIM_FACT_MISMATCH", f"第 {index + 1} 条商品声明的数值与引用事实不匹配")
        claim_numbers |= numbers & supported

    fields = [data["title"], data["body"], data["slogan"], *data["selling_points"], *[c["text"] for c in data["claims"]]]
    text = "\n".join(fields)
    unknown = numeric_tokens(text) - allowed_numbers
    if unknown:
        formatted = ", ".join(f"{v}{u}" for v, u in sorted(unknown))
        issue("UNSUPPORTED_NUMBER", f"生成内容出现未提供的商品数值：{formatted}")
    uncited = numeric_tokens(text) - claim_numbers - numeric_tokens(product.get("name", ""))
    if uncited - unknown:
        issue("UNCITED_NUMERIC_FACT", "正文中的商品数值没有对应的事实声明与引用")
    for promise in unsupported_promises(text, product):
        issue("UNSUPPORTED_PROMISE", f"生成内容包含没有依据的商品承诺：{promise}")

    # Descriptions of product specifications inside image prompts must also stay
    # grounded; composition counts are permitted, performance promises are not.
    for image in data["image_prompts"]:
        unknown_image_numbers = {token for token in numeric_tokens(image["prompt"]) if token[1]} - allowed_numbers
        if unknown_image_numbers:
            issue("UNSUPPORTED_IMAGE_NUMBER", "图片提示词包含未提供的商品数值或规格")
        for promise in unsupported_promises(image["prompt"], product):
            issue("UNSUPPORTED_IMAGE_PROMISE", f"图片提示词包含没有依据的商品承诺：{promise}")
    if trusted_evidence and not data["evidence_ids"]:
        issue("NO_EVIDENCE_CITATION", "当前草稿没有引用检索资料，请确认品牌要求是否使用", "warning")
    return {"passed": not any(i["severity"] == "error" for i in issues), "issues": issues}
