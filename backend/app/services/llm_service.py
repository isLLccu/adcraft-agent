from typing import Dict, List, Optional
import httpx
from app.core.config import settings
from app.core.logging import logger


class LLMService:
    """LLM 服务 - 用于生成广告文案和图片 Prompt"""

    def __init__(self):
        self.api_key = settings.LLM_API_KEY
        self.api_base = settings.LLM_API_BASE
        self.model = settings.LLM_MODEL

    async def generate_ad_copy(
        self,
        product_name: str,
        product_description: str,
        selling_points: List[str],
        platform: str,
        ad_type: str,
        style: Optional[str] = None,
        target_audience: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        生成广告文案

        Args:
            product_name: 商品名称
            product_description: 商品描述
            selling_points: 卖点列表
            platform: 投放平台（淘宝/京东/抖音等）
            ad_type: 广告类型（banner/feed/story等）
            style: 文案风格（可选）
            target_audience: 目标受众（可选）

        Returns:
            包含 title, body, slogan 的字典
        """
        # 构建 prompt
        prompt = self._build_ad_copy_prompt(
            product_name=product_name,
            product_description=product_description,
            selling_points=selling_points,
            platform=platform,
            ad_type=ad_type,
            style=style,
            target_audience=target_audience,
        )

        # 调用 LLM API
        response = await self._call_llm(prompt)

        # 解析响应
        return self._parse_ad_copy_response(response)

    async def generate_image_prompt(
        self,
        product_name: str,
        product_description: str,
        ad_copy: Dict[str, str],
        style: Optional[str] = None,
        platform: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        生成图片 Prompt

        Args:
            product_name: 商品名称
            product_description: 商品描述
            ad_copy: 广告文案
            style: 图片风格（可选）
            platform: 投放平台（可选）

        Returns:
            包含 prompt 和 negative_prompt 的字典
        """
        # 构建 prompt
        prompt = self._build_image_prompt_prompt(
            product_name=product_name,
            product_description=product_description,
            ad_copy=ad_copy,
            style=style,
            platform=platform,
        )

        # 调用 LLM API
        response = await self._call_llm(prompt)

        # 解析响应
        return self._parse_image_prompt_response(response)

    def _build_ad_copy_prompt(
        self,
        product_name: str,
        product_description: str,
        selling_points: List[str],
        platform: str,
        ad_type: str,
        style: Optional[str],
        target_audience: Optional[str],
    ) -> str:
        """构建广告文案生成的 prompt"""
        selling_points_text = "\n".join([f"- {point}" for point in selling_points])

        prompt = f"""你是一位专业的电商广告文案撰写专家。请根据以下信息生成广告文案：

商品信息：
- 商品名称：{product_name}
- 商品描述：{product_description}
- 核心卖点：
{selling_points_text}

投放信息：
- 投放平台：{platform}
- 广告类型：{ad_type}
"""

        if style:
            prompt += f"- 文案风格：{style}\n"

        if target_audience:
            prompt += f"- 目标受众：{target_audience}\n"

        prompt += """
请生成以下内容（以 JSON 格式返回）：
1. title: 广告标题（15-30字，吸引眼球）
2. body: 广告正文（50-100字，突出卖点）
3. slogan: 广告口号（8-15字，朗朗上口）

要求：
- 文案要符合平台特点和用户习惯
- 突出商品核心卖点
- 语言生动、有感染力
- 避免夸大宣传和违禁词

请直接返回 JSON 格式，不要包含其他内容：
{"title": "...", "body": "...", "slogan": "..."}
"""
        return prompt

    def _build_image_prompt_prompt(
        self,
        product_name: str,
        product_description: str,
        ad_copy: Dict[str, str],
        style: Optional[str],
        platform: Optional[str],
    ) -> str:
        """构建图片 Prompt 生成的 prompt"""
        prompt = f"""你是一位专业的 AI 绘画 Prompt 工程师。请根据以下信息生成图片生成 Prompt：

商品信息：
- 商品名称：{product_name}
- 商品描述：{product_description}

广告文案：
- 标题：{ad_copy.get('title', '')}
- 正文：{ad_copy.get('body', '')}
- 口号：{ad_copy.get('slogan', '')}
"""

        if style:
            prompt += f"\n图片风格：{style}"

        if platform:
            prompt += f"\n投放平台：{platform}"

        prompt += """

请生成以下内容（以 JSON 格式返回）：
1. prompt: 正向提示词（英文，详细描述画面内容、构图、光影、色彩等）
2. negative_prompt: 负向提示词（英文，描述不希望出现的元素）

要求：
- Prompt 要详细、具体，包含商品特征
- 符合电商广告的视觉风格
- 画面要吸引人、有冲击力
- 避免版权问题和敏感内容

请直接返回 JSON 格式，不要包含其他内容：
{"prompt": "...", "negative_prompt": "..."}
"""
        return prompt

    async def _call_llm(self, prompt: str) -> str:
        """调用 LLM API"""
        import time

        max_retries = 3
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                logger.info(f"LLM API call attempt {attempt + 1}/{max_retries}")
                logger.info(f"API Base: {self.api_base}")
                logger.info(f"Model: {self.model}")

                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(120.0, connect=10.0),
                    follow_redirects=True,
                    verify=True,
                ) as client:
                    response = await client.post(
                        f"{self.api_base}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": self.model,
                            "messages": [
                                {"role": "user", "content": prompt}
                            ],
                            "temperature": 0.7,
                            "max_tokens": 2000,
                        },
                    )

                    logger.info(f"LLM API response status: {response.status_code}")
                    response.raise_for_status()
                    result = response.json()
                    logger.info(f"LLM API response: {result}")

                    content = result["choices"][0]["message"]["content"]
                    logger.info(f"LLM response content: {content}")
                    return content

            except httpx.ConnectError as e:
                logger.error(f"Connection error on attempt {attempt + 1}: {str(e)}")
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    logger.error("Max retries reached, giving up")
                    raise
            except httpx.ReadTimeout as e:
                logger.error(f"Read timeout on attempt {attempt + 1}: {str(e)}")
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    logger.error("Max retries reached, giving up")
                    raise
            except Exception as e:
                logger.error(f"LLM API call failed: {type(e).__name__}: {str(e)}")
                raise

    def _parse_ad_copy_response(self, response: str) -> Dict[str, str]:
        """解析广告文案响应"""
        import json
        import re

        logger.info(f"Original response length: {len(response)}")
        logger.info(f"Original response: {response}")

        # 移除 Markdown 代码块标记
        cleaned = response.strip()
        if cleaned.startswith("```"):
            # 移除开头的 ```json 或 ```
            cleaned = re.sub(r'^```(?:json)?\s*\n?', '', cleaned)
            # 移除结尾的 ```
            cleaned = re.sub(r'\n?```\s*$', '', cleaned)

        logger.info(f"Cleaned response: {cleaned}")

        try:
            # 尝试直接解析 JSON
            result = json.loads(cleaned)
            logger.info(f"Successfully parsed JSON: {result}")
            return result
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")

            # 尝试修复不完整的 JSON（补全缺失的引号和括号）
            fixed = cleaned
            # 如果字符串未闭合，尝试补全
            if not fixed.endswith('}'):
                # 找到最后一个完整的字段
                if '"slogan":' in fixed:
                    # 补全 slogan 字段
                    fixed = re.sub(r'"slogan":\s*"[^"]*$', '"slogan": "品质优选"}', fixed)
                if not fixed.endswith('}'):
                    fixed += '}'

            logger.info(f"Attempting to parse fixed JSON: {fixed}")
            try:
                result = json.loads(fixed)
                logger.warning(f"Successfully parsed fixed JSON: {result}")
                return result
            except json.JSONDecodeError:
                # 如果修复失败，尝试提取 JSON 部分
                json_match = re.search(r'\{[^}]*"title"[^}]*"body"[^}]*\}', cleaned, re.DOTALL)
                if json_match:
                    extracted = json_match.group()
                    logger.info(f"Extracted JSON: {extracted}")
                    return json.loads(extracted)
                else:
                    logger.error(f"Failed to parse ad copy response: {response}")
                    raise ValueError("Invalid response format")

    def _parse_image_prompt_response(self, response: str) -> Dict[str, str]:
        """解析图片 Prompt 响应"""
        import json
        import re

        logger.info(f"Original prompt response length: {len(response)}")
        logger.info(f"Original prompt response: {response}")

        # 移除 Markdown 代码块标记
        cleaned = response.strip()
        if cleaned.startswith("```"):
            # 移除开头的 ```json 或 ```
            cleaned = re.sub(r'^```(?:json)?\s*\n?', '', cleaned)
            # 移除结尾的 ```
            cleaned = re.sub(r'\n?```\s*$', '', cleaned)

        logger.info(f"Cleaned prompt response: {cleaned}")

        try:
            # 尝试直接解析 JSON
            result = json.loads(cleaned)
            logger.info(f"Successfully parsed prompt JSON: {result}")
            return result
        except json.JSONDecodeError as e:
            logger.error(f"Prompt JSON decode error: {e}")

            # 尝试修复不完整的 JSON
            fixed = cleaned
            # 如果字符串未闭合，尝试补全
            if not fixed.endswith('}'):
                # 找到最后一个完整的字段
                if '"negative_prompt":' in fixed:
                    # 补全 negative_prompt 字段
                    fixed = re.sub(r'"negative_prompt":\s*"[^"]*$', '"negative_prompt": "low quality, blurry"}', fixed)
                if not fixed.endswith('}'):
                    fixed += '}'

            logger.info(f"Attempting to parse fixed prompt JSON: {fixed}")
            try:
                result = json.loads(fixed)
                logger.warning(f"Successfully parsed fixed prompt JSON: {result}")
                return result
            except json.JSONDecodeError:
                # 如果修复失败，尝试提取 JSON 部分
                json_match = re.search(r'\{[^}]*"prompt"[^}]*\}', cleaned, re.DOTALL)
                if json_match:
                    extracted = json_match.group()
                    logger.info(f"Extracted prompt JSON: {extracted}")
                    return json.loads(extracted)
                else:
                    logger.error(f"Failed to parse image prompt response: {response}")
                    raise ValueError("Invalid response format")


# 创建全局实例
llm_service = LLMService()
