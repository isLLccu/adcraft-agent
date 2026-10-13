"""Preserving uploaded merchandise and making image demo/live failures explicit."""
import asyncio
from io import BytesIO

from PIL import Image
import pytest

from app.ai.config import AISettings
from app.ai.images import ImageError, ImageRenderer


PLAN = {"label": "商品细节", "prompt": "明亮干净的留白背景", "negative_prompt": "虚构功能"}


def test_missing_subject_has_explicit_background_only_warning(tmp_path):
    renderer = ImageRenderer(AISettings(data_dir=tmp_path, image_provider="demo", force_demo=True, llm_api_key=""))
    result = asyncio.run(renderer.render(PLAN, {"image_url": None}, "background.png"))
    assert result["mode"] == "demo"
    assert not result["product_preserved"]
    assert "背景方案" in result["warning"]
    assert Image.open(tmp_path / "assets" / "background.png").size == (1024, 1024)


def test_opaque_subject_keeps_original_background_and_warns_instead_of_claiming_cutout(tmp_path):
    renderer = ImageRenderer(AISettings(data_dir=tmp_path, image_provider="demo", force_demo=True, llm_api_key=""))
    Image.new("RGB", (50, 50), (20, 30, 40)).save(tmp_path / "assets" / "opaque.png")
    result = asyncio.run(renderer.render(PLAN, {"image_url": "/api/v1/ai/assets/opaque.png"}, "output.png"))
    assert result["product_preserved"]
    assert "不透明" in result["warning"]
    assert Image.open(tmp_path / "assets" / "output.png").getpixel((512, 582)) == (20, 30, 40)


def test_live_image_configuration_never_silently_falls_back_to_demo(tmp_path):
    renderer = ImageRenderer(AISettings(data_dir=tmp_path, image_provider="dashscope", image_api_key="", force_demo=True, llm_api_key=""))
    with pytest.raises(ImageError, match="IMAGE_API_KEY"):
        asyncio.run(renderer.render(PLAN, {}, "should-not-exist.png"))
    assert not (tmp_path / "assets" / "should-not-exist.png").exists()


def test_supplier_task_reference_is_retained_before_live_composition(tmp_path, monkeypatch):
    renderer = ImageRenderer(AISettings(data_dir=tmp_path, image_provider="dashscope", image_api_key="fake-only", force_demo=True, llm_api_key=""))
    recorded = []

    async def background(plan, callback):
        await callback("supplier-task-accepted")
        buffer = BytesIO()
        Image.new("RGBA", (100, 100), "white").save(buffer, "PNG")
        return buffer.getvalue()

    async def remember(task_id):
        recorded.append(task_id)

    monkeypatch.setattr(renderer, "_background", background)
    result = asyncio.run(renderer.render(PLAN, {}, "live-fake.png", remember))
    assert recorded == ["supplier-task-accepted"]
    assert result["mode"] == "live"


def test_non_https_vendor_download_is_rejected_before_network(tmp_path):
    renderer = ImageRenderer(AISettings(data_dir=tmp_path, image_provider="demo", force_demo=True, llm_api_key=""))
    with pytest.raises(ImageError, match="HTTPS"):
        asyncio.run(renderer._download(None, "http://unsafe.example/image.png"))
