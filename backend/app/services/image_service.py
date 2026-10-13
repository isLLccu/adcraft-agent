"""图片生成服务

支持:
- dashscope: 阿里云通义万相 (推荐, 文生图 + 图生图)
- openai:    OpenAI DALL-E 3 (仅文生图)
- mock:      本地占位图 (测试)

通过 settings.IMAGE_PROVIDER 切换。
"""
from typing import Optional
import asyncio
import base64
import httpx
from io import BytesIO

from app.core.config import settings
from app.core.logging import logger


class ImageGenerationService:
    def __init__(self):
        self.provider = (settings.IMAGE_PROVIDER or "mock").lower()
        self.api_key = settings.IMAGE_API_KEY
        self.api_base = settings.IMAGE_API_BASE.rstrip("/")
        self.model = settings.IMAGE_MODEL

    async def generate_image(
        self,
        prompt: str,
        negative_prompt: Optional[str] = None,
        width: int = 1024,
        height: int = 1024,
        reference_image_url: Optional[str] = None,
    ) -> bytes:
        """统一入口：根据 provider 分发，无 key 时自动降级到 mock。"""
        if not self.api_key or self.provider == "mock":
            logger.warning(
                f"IMAGE_API_KEY missing or provider=mock, falling back to mock image"
            )
            return await self.generate_image_mock(prompt, negative_prompt, width, height)

        if self.provider == "dashscope":
            return await self._generate_dashscope(
                prompt, negative_prompt, width, height, reference_image_url
            )
        if self.provider == "openai":
            return await self._generate_openai(prompt, width, height)

        raise ValueError(f"Unknown IMAGE_PROVIDER: {self.provider}")

    # ----- DashScope (通义万相) -----
    async def _generate_dashscope(
        self,
        prompt: str,
        negative_prompt: Optional[str],
        width: int,
        height: int,
        reference_image_url: Optional[str],
    ) -> bytes:
        """DashScope 万相 文生图 (text2image) 异步流程

        步骤: POST 提交 → 轮询 GET → 下载图片
        参考: https://help.aliyun.com/zh/model-studio/text-to-image

        注: 当 reference_image_url 存在时, 通过 prompt 注入「参考商品视觉特征」
        (而非走 image-edit 接口) — 因为 image-edit 要求图片 URL 公网可达,
        而本地 docker 部署时 MinIO 仅 localhost 可达。
        生产部署到云上 + OSS 时再切换到背景重绘接口。
        """
        size_str = self._dashscope_size(width, height)
        endpoint = f"{self.api_base}/services/aigc/text2image/image-synthesis"

        full_prompt = prompt
        if reference_image_url:
            full_prompt = f"参考商品图: {reference_image_url[:80]}. {prompt}"

        body: dict = {
            "model": self.model,
            "input": {"prompt": full_prompt[:500]},
            "parameters": {"size": size_str, "n": 1},
        }
        if negative_prompt:
            body["input"]["negative_prompt"] = negative_prompt[:500]

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",
        }

        async with httpx.AsyncClient(timeout=httpx.Timeout(settings.IMAGE_TIMEOUT)) as client:
            # 1. 提交
            r = await client.post(endpoint, headers=headers, json=body)
            r.raise_for_status()
            data = r.json()
            task_id = data.get("output", {}).get("task_id")
            if not task_id:
                raise RuntimeError(f"DashScope returned no task_id: {data}")
            logger.info(f"DashScope task submitted: {task_id}")

            # 2. 轮询
            poll_url = f"{self.api_base}/tasks/{task_id}"
            poll_headers = {"Authorization": f"Bearer {self.api_key}"}
            for attempt in range(60):  # 最多 60 次, 每次 3s = 3 分钟
                await asyncio.sleep(3)
                pr = await client.get(poll_url, headers=poll_headers)
                pr.raise_for_status()
                pdata = pr.json()
                status = pdata.get("output", {}).get("task_status")
                logger.info(f"DashScope task {task_id} status: {status} (attempt {attempt + 1})")
                if status == "SUCCEEDED":
                    results = pdata.get("output", {}).get("results", [])
                    if not results:
                        raise RuntimeError(f"DashScope SUCCEEDED but no results: {pdata}")
                    img_url = results[0].get("url")
                    if not img_url:
                        raise RuntimeError(f"DashScope no image url in result: {pdata}")
                    # 3. 下载图片
                    ir = await client.get(img_url)
                    ir.raise_for_status()
                    return ir.content
                if status in {"FAILED", "UNKNOWN"}:
                    raise RuntimeError(f"DashScope task {task_id} failed: {pdata}")
            raise RuntimeError(f"DashScope task {task_id} timed out after 3 min")

    @staticmethod
    def _dashscope_size(width: int, height: int) -> str:
        """万相支持: 1024*1024, 720*1280, 1280*720, 768*1152, 1152*768"""
        ratio = width / height
        if abs(ratio - 1.0) < 0.05:
            return "1024*1024"
        if ratio < 0.7:
            return "720*1280"
        if ratio > 1.4:
            return "1280*720"
        if ratio < 1.0:
            return "768*1152"
        return "1152*768"

    # ----- OpenAI DALL-E -----
    async def _generate_openai(self, prompt: str, width: int, height: int) -> bytes:
        size = "1024x1024"
        if width > height * 1.4:
            size = "1792x1024"
        elif height > width * 1.4:
            size = "1024x1792"
        async with httpx.AsyncClient(timeout=httpx.Timeout(settings.IMAGE_TIMEOUT)) as client:
            r = await client.post(
                f"{self.api_base}/images/generations",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={"model": self.model, "prompt": prompt, "size": size, "n": 1, "response_format": "b64_json"},
            )
            r.raise_for_status()
            data = r.json()
            b64 = data["data"][0]["b64_json"]
            return base64.b64decode(b64)

    # ----- Mock -----
    async def generate_image_mock(
        self,
        prompt: str,
        negative_prompt: Optional[str] = None,
        width: int = 1024,
        height: int = 1024,
    ) -> bytes:
        """生成占位图，方便无 key 时也能跑通端到端。"""
        try:
            from PIL import Image, ImageDraw, ImageFont

            img = Image.new("RGB", (width, height), color="#fafafa")
            draw = ImageDraw.Draw(img)
            try:
                font = ImageFont.truetype("arial.ttf", 32)
                small = ImageFont.truetype("arial.ttf", 18)
            except Exception:
                font = ImageFont.load_default()
                small = font

            title = "AdCraft Mock Image"
            bbox = draw.textbbox((0, 0), title, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            draw.text(((width - tw) // 2, (height - th) // 2 - 20), title, fill="#333", font=font)

            line = (prompt or "")[:80]
            draw.text((20, height - 40), f"prompt: {line}", fill="#888", font=small)

            buf = BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()
        except Exception as e:
            logger.error(f"Mock image generation failed: {e}")
            raise


image_service = ImageGenerationService()
