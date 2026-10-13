from typing import Dict, List
import re
from app.core.logging import logger


class ContentAuditService:
    """内容审核服务 - 检查广告文案和图片是否合规"""

    # 违禁词列表（示例）
    FORBIDDEN_WORDS = [
        "最好", "最优", "最佳", "第一", "唯一", "顶级", "极致",
        "国家级", "世界级", "全球领先", "史无前例",
        "100%", "完全", "彻底",
        "治愈", "根治", "药到病除",
    ]

    # 敏感词列表（示例）
    SENSITIVE_WORDS = [
        "暴力", "色情", "赌博", "毒品",
        "政治", "宗教", "歧视",
    ]

    def audit_text(self, text: str) -> Dict:
        """
        审核文本内容

        Args:
            text: 待审核的文本

        Returns:
            审核结果字典
        """
        issues = []
        risk_level = "low"

        # 检查违禁词
        forbidden_found = []
        for word in self.FORBIDDEN_WORDS:
            if word in text:
                forbidden_found.append(word)

        if forbidden_found:
            issues.append({
                "type": "forbidden_words",
                "severity": "high",
                "description": f"包含违禁词: {', '.join(forbidden_found)}",
                "words": forbidden_found,
            })
            risk_level = "high"

        # 检查敏感词
        sensitive_found = []
        for word in self.SENSITIVE_WORDS:
            if word in text:
                sensitive_found.append(word)

        if sensitive_found:
            issues.append({
                "type": "sensitive_words",
                "severity": "medium",
                "description": f"包含敏感词: {', '.join(sensitive_found)}",
                "words": sensitive_found,
            })
            if risk_level == "low":
                risk_level = "medium"

        # 检查文本长度
        if len(text) > 500:
            issues.append({
                "type": "length",
                "severity": "low",
                "description": f"文本过长 ({len(text)} 字符)",
            })

        # 检查是否包含联系方式
        if self._contains_contact_info(text):
            issues.append({
                "type": "contact_info",
                "severity": "medium",
                "description": "包含联系方式（电话/微信/QQ等）",
            })
            if risk_level == "low":
                risk_level = "medium"

        # 生成建议
        suggestions = self._generate_suggestions(issues)

        # 判断是否通过
        passed = risk_level != "high"

        return {
            "passed": passed,
            "risk_level": risk_level,
            "issues": issues,
            "suggestions": suggestions,
        }

    def audit_ad_copy(
        self,
        title: str,
        body: str,
        slogan: str,
    ) -> Dict:
        """
        审核广告文案

        Args:
            title: 标题
            body: 正文
            slogan: 口号

        Returns:
            审核结果字典
        """
        # 合并所有文本进行审核
        full_text = f"{title}\n{body}\n{slogan}"
        result = self.audit_text(full_text)

        # 添加文案特定的检查
        issues = result["issues"]

        # 检查标题长度
        if len(title) > 50:
            issues.append({
                "type": "title_length",
                "severity": "low",
                "description": f"标题过长 ({len(title)} 字符，建议 15-30 字符)",
            })

        # 检查口号长度
        if len(slogan) > 30:
            issues.append({
                "type": "slogan_length",
                "severity": "low",
                "description": f"口号过长 ({len(slogan)} 字符，建议 8-15 字符)",
            })

        result["issues"] = issues
        result["suggestions"] = self._generate_suggestions(issues)

        return result

    def _contains_contact_info(self, text: str) -> bool:
        """检查是否包含联系方式"""
        # 检查手机号
        phone_pattern = r'1[3-9]\d{9}'
        if re.search(phone_pattern, text):
            return True

        # 检查 QQ 号
        qq_pattern = r'[Qq]{2}[:：\s]*\d{5,}'
        if re.search(qq_pattern, text):
            return True

        # 检查微信
        wechat_keywords = ['微信', 'WeChat', 'wx', 'vx']
        for keyword in wechat_keywords:
            if keyword in text:
                return True

        return False

    def _generate_suggestions(self, issues: List[Dict]) -> List[str]:
        """根据问题生成修改建议"""
        suggestions = []

        for issue in issues:
            if issue["type"] == "forbidden_words":
                suggestions.append(
                    f"请移除违禁词: {', '.join(issue['words'])}，"
                    "可使用更客观的描述方式"
                )
            elif issue["type"] == "sensitive_words":
                suggestions.append(
                    f"请移除敏感词: {', '.join(issue['words'])}，"
                    "避免引起争议"
                )
            elif issue["type"] == "contact_info":
                suggestions.append(
                    "请移除联系方式，电商平台通常不允许在广告中直接展示联系方式"
                )
            elif issue["type"] == "length":
                suggestions.append("建议精简文案，使其更简洁有力")
            elif issue["type"] == "title_length":
                suggestions.append("建议缩短标题至 15-30 字符")
            elif issue["type"] == "slogan_length":
                suggestions.append("建议缩短口号至 8-15 字符")

        if not suggestions:
            suggestions.append("内容审核通过，无需修改")

        return suggestions

    async def audit_image(self, image_data: bytes) -> Dict:
        """
        审核图片内容（预留接口）

        在实际项目中，这里应该调用图片审核 API（如阿里云、腾讯云的内容安全服务）

        Args:
            image_data: 图片二进制数据

        Returns:
            审核结果字典
        """
        # TODO: 集成真实的图片审核 API
        logger.info("Image audit called (mock implementation)")

        # 模拟审核结果
        return {
            "passed": True,
            "risk_level": "low",
            "issues": [],
            "suggestions": ["图片审核通过"],
        }


# 创建全局实例
audit_service = ContentAuditService()
