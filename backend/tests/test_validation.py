import copy
import unittest
from app.ai.validation import numeric_tokens, unsupported_request, validate_draft

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
EVIDENCE = [{"id": "doc-cup:0", "document_id": "doc-cup", "brand_id": "northcup", "title": "品牌规则", "text": "简洁真实", "score": 0.8, "source": "manual", "version": 1, "chunk_index": 0}]


def draft():
    return {
        "title": "北岸随行杯｜日常随行", "body": "容量400mL，材质304不锈钢。", "slogan": "轻松随行",
        "selling_points": ["容量400mL", "材质304不锈钢"],
        "claims": [
            {"text": "容量400mL", "fact_ids": ["f-capacity"]},
            {"text": "材质304不锈钢", "fact_ids": ["f-material"]},
        ],
        "evidence_ids": ["doc-cup:0"],
        "image_prompts": [{"label": "主图", "prompt": "保留原始商品主体，浅色背景", "negative_prompt": "不改变商品结构"}],
        "platform": "xiaohongshu",
    }


class ValidationTests(unittest.TestCase):
    def codes(self, value, evidence=EVIDENCE):
        return {i["code"] for i in validate_draft(value, PRODUCT, evidence, "xiaohongshu")["issues"]}

    def test_valid_schema_grounded(self):
        self.assertTrue(validate_draft(draft(), PRODUCT, EVIDENCE, "xiaohongshu")["passed"])

    def test_bad_shapes_never_raise(self):
        for value in (None, [], "", {"title": 3}, {"body": None}, {"claims": [None]}):
            with self.subTest(value=value):
                self.assertIn("SCHEMA_INVALID", self.codes(value))

    def test_numbers_adjacent_to_chinese_and_units(self):
        self.assertIn(("400", "ml"), numeric_tokens("容量400mL"))
        self.assertIn(("304", "stainless"), numeric_tokens("材质304不锈钢"))
        self.assertIn(("400", "ml"), numeric_tokens("容量400毫升"))
        self.assertNotEqual(numeric_tokens("400mL"), numeric_tokens("400g"))

    def test_numeric_conflict(self):
        value = draft()
        value["body"] += "容量500mL。"
        self.assertIn("UNSUPPORTED_NUMBER", self.codes(value))

    def test_unit_mismatch(self):
        value = draft()
        value["body"] += "重量400g。"
        self.assertIn("UNSUPPORTED_NUMBER", self.codes(value))

    def test_claim_wrong_fact(self):
        value = draft()
        value["claims"][0]["fact_ids"] = ["f-weight"]
        self.assertIn("CLAIM_FACT_MISMATCH", self.codes(value))

    def test_missing_and_forged_citations(self):
        value = draft()
        value["claims"][0]["fact_ids"] = ["fake"]
        value["evidence_ids"] = ["other-brand"]
        codes = self.codes(value)
        self.assertIn("INVALID_FACT_ID", codes)
        self.assertIn("INVALID_EVIDENCE_ID", codes)

    def test_cross_brand_evidence(self):
        evidence = copy.deepcopy(EVIDENCE)
        evidence[0]["brand_id"] = "foreign"
        self.assertIn("CROSS_BRAND_EVIDENCE", self.codes(draft(), evidence))

    def test_uncited_real_number(self):
        value = draft()
        value["body"] += "售价99元。"
        self.assertIn("UNCITED_NUMERIC_FACT", self.codes(value))

    def test_unknown_performance_promise(self):
        for text in ("保温24小时", "终身质保", "食品级安全认证", "百分百防漏", "抗菌", "保证有效"):
            value = draft()
            value["body"] += text
            with self.subTest(text=text):
                self.assertIn("UNSUPPORTED_PROMISE", self.codes(value))

    def test_no_silent_schema_extra(self):
        value = draft()
        value["reasoning"] = "private thinking"
        self.assertIn("SCHEMA_INVALID", self.codes(value))

    def test_negative_instructions_not_claims(self):
        self.assertEqual([], unsupported_request("生成文案，不要写保温24小时，不要宣称食品级", PRODUCT))
        self.assertEqual([], unsupported_request("生成2版文案，3张素材", PRODUCT))
        self.assertTrue(unsupported_request("帮我写保温24小时和终身质保的文案", PRODUCT))

    def test_common_negative_wording_is_not_a_performance_request(self):
        for message in (
            "生成一版自然简洁的小红书文案，不添加未知保温时长。",
            "生成文案，不写保温24小时。",
            "文案不包含保温24小时。",
            "不编造保温24小时，生成文案。",
            "不得声称保温24小时。",
            "不要写防漏、保温24小时、食品级认证。",
        ):
            with self.subTest(message=message):
                self.assertEqual([], unsupported_request(message, PRODUCT))

    def test_negative_scope_does_not_hide_later_positive_claim(self):
        for message in (
            "不要编造材质，但要突出保温24小时。",
            "不要写防漏，强调保温24小时。",
            "不添加保温时长，但主打终身质保。",
            "不要写防漏并突出保温24小时。",
            "不包含防漏，同时添加食品级认证。",
        ):
            with self.subTest(message=message):
                self.assertTrue(unsupported_request(message, PRODUCT))
        self.assertTrue(unsupported_request("突出不漏水性能。", PRODUCT))

    def test_no_evidence_warning_not_error(self):
        value = draft()
        value["evidence_ids"] = []
        result = validate_draft(value, PRODUCT, EVIDENCE, "xiaohongshu")
        self.assertTrue(result["passed"])
        self.assertIn("NO_EVIDENCE_CITATION", {i["code"] for i in result["issues"]})

    def test_image_specification_must_be_known(self):
        value = draft()
        value["image_prompts"][0]["prompt"] += "，杯子容量500mL"
        self.assertIn("UNSUPPORTED_IMAGE_NUMBER", self.codes(value))

    def test_negative_product_data_does_not_grant_promise(self):
        product = copy.deepcopy(PRODUCT)
        product["description"] = "不承诺保温性能。"
        value = draft()
        value["body"] += "长效保温。"
        result = validate_draft(value, product, EVIDENCE, "xiaohongshu")
        self.assertIn("UNSUPPORTED_PROMISE", {i["code"] for i in result["issues"]})

    def test_platform_mismatch(self):
        value = draft()
        value["platform"] = "douyin"
        self.assertIn("PLATFORM_MISMATCH", self.codes(value))


if __name__ == "__main__":
    unittest.main()
