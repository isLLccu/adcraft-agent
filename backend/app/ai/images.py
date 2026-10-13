"""背景生成与商品原图合成。此模块不把商品 URL 伪装成模型图像输入。"""
import asyncio
import base64
from io import BytesIO
from pathlib import Path
import time
from urllib.parse import urlparse

import httpx
from PIL import Image, ImageDraw, ImageOps

from .config import AISettings


class ImageError(RuntimeError):
    pass


class ImageRenderer:
    def __init__(self, settings: AISettings):
        self.settings = settings
        self.assets = settings.data_dir / "assets"
        self.assets.mkdir(parents=True, exist_ok=True)

    @property
    def mode(self) -> str:
        return "demo" if self.settings.image_provider in {"demo", "mock"} else "live"

    async def render(self, plan: dict, product: dict, filename: str, on_provider_task=None) -> dict:
        if self.mode == "demo":
            background = self._demo_background()
        else:
            if not self.settings.image_api_key:
                raise ImageError("真实图片模式缺少 IMAGE_API_KEY；请配置，或显式选择 demo。")
            background = Image.open(BytesIO(await self._background(plan, on_provider_task))).convert("RGBA")
            background = ImageOps.fit(background, (1024, 1024))
        preserved = False
        warning = "未上传商品原图：此图仅为背景方案，不是商品实物效果图。"
        image_url = product.get("image_url")
        if image_url:
            subject_path = self.assets / Path(image_url).name
            if subject_path.is_file():
                subject = Image.open(subject_path).convert("RGBA")
                has_transparency = subject.getchannel("A").getextrema()[0] < 255
                subject.thumbnail((640, 680), Image.Resampling.LANCZOS)
                background.alpha_composite(subject, ((1024-subject.width)//2, (1024-subject.height)//2+70))
                preserved = True
                warning = None if has_transparency else "原图不透明，已保留原图背景；请上传透明 PNG 获得更自然的合成。"
        if self.mode == "demo":
            ImageDraw.Draw(background).text((28, 980), "DEMO - template background", fill="#455d72")
        output = self.assets / filename
        background.convert("RGB").save(output, "PNG")
        return {"url": f"/api/v1/ai/assets/{filename}", "label": plan["label"], "mode": self.mode,
                "product_preserved": preserved, "warning": warning}

    def _demo_background(self) -> Image.Image:
        image = Image.new("RGBA", (1024, 1024), "#edf5f8")
        draw = ImageDraw.Draw(image)
        draw.ellipse((260, 300, 1250, 1250), fill="#d8edf0")
        draw.rounded_rectangle((110, 710, 915, 930), radius=45, fill="#ffffff")
        return image

    async def _download(self, client: httpx.AsyncClient, url: str) -> bytes:
        if urlparse(url).scheme != "https":
            raise ImageError("图片供应商返回了非 HTTPS 下载地址")
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            chunks, size = [], 0
            async for chunk in response.aiter_bytes():
                size += len(chunk)
                if size > 20 * 1024 * 1024:
                    raise ImageError("供应商返回图片超过 20MB")
                chunks.append(chunk)
            return b"".join(chunks)

    async def _background(self, plan: dict, on_provider_task) -> bytes:
        s = self.settings
        # 只生成背景：商品主体始终由本地原图合成。
        prompt = "Create only an empty advertising background, no product, no text, no logo. Leave the center empty. " + plan["prompt"]
        negative = "product, bottle, bag, lamp, text, letters, watermark, logo, " + plan.get("negative_prompt", "")
        async with httpx.AsyncClient(timeout=s.image_timeout, follow_redirects=True) as client:
            headers = {"Authorization": f"Bearer {s.image_api_key}"}
            try:
                if s.image_provider == "openai":
                    response = await client.post(f"{s.image_api_base}/images/generations", headers=headers,
                        json={"model":s.image_model,"prompt":prompt,"size":"1024x1024","n":1,"response_format":"b64_json"})
                    response.raise_for_status()
                    item = response.json()["data"][0]
                    if item.get("b64_json"):
                        return base64.b64decode(item["b64_json"])
                    return await self._download(client, item["url"])
                if s.image_provider != "dashscope":
                    raise ImageError("IMAGE_PROVIDER 只支持 demo、dashscope、openai")
                response = await client.post(f"{s.image_api_base}/services/aigc/text2image/image-synthesis",
                    headers={**headers,"X-DashScope-Async":"enable"},
                    json={"model":s.image_model,"input":{"prompt":prompt[:1500],"negative_prompt":negative[:500]},
                          "parameters":{"size":"1024*1024","n":1,"prompt_extend":False}})
                response.raise_for_status()
                task_id = response.json().get("output", {}).get("task_id")
                if not task_id:
                    raise ImageError("图片供应商没有返回任务 ID")
                if on_provider_task:
                    await on_provider_task(task_id)
                deadline = time.monotonic() + s.image_timeout
                while time.monotonic() < deadline:
                    await asyncio.sleep(3)
                    polled = await client.get(f"{s.image_api_base}/tasks/{task_id}", headers=headers)
                    polled.raise_for_status()
                    output = polled.json().get("output", {})
                    if output.get("task_status") == "SUCCEEDED":
                        return await self._download(client, output["results"][0]["url"])
                    if output.get("task_status") in {"FAILED", "UNKNOWN", "CANCELED"}:
                        raise ImageError("图片供应商任务失败；已保留任务 ID 供排查")
                raise ImageError("图片生成等待超时；已保留供应商任务 ID，请先查询，避免重复生成")
            except httpx.HTTPStatusError as exc:
                raise ImageError(f"图片供应商 HTTP {exc.response.status_code}；请检查模型、地域与配置") from exc
            except (httpx.RequestError, KeyError, ValueError) as exc:
                raise ImageError("图片调用或解析失败；请检查配置与供应商任务记录") from exc
