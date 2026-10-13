"""Celery 任务定义

核心任务流程：
  generate_ad_materials(task_id)  ← 入口
       │
       ├─ 1. 生成文案 (LLM)
       ├─ 2. 内容审核
       ├─ 3. 生成图片 prompt (LLM)
       └─ 4. fan-out 6 个子任务 (Celery group)
             ├─ generate_one_material(主图  1:1)
             ├─ generate_one_material(详情图 3:4)
             ├─ generate_one_material(详情图 3:4 风格变体)
             ├─ generate_one_material(长图   9:16)
             ├─ generate_one_material(横图   16:9)
             └─ generate_one_material(海报   4:5)

每个子任务独立调图像 API、上传 MinIO、写一条 Material。
全部完成后 chord 回调把 ad_task 标 completed。
"""
import asyncio
from datetime import datetime
from typing import Optional

from celery import group, chord
from sqlalchemy.orm import Session

from app.workers.celery_app import celery_app
from app.db.session import SessionLocal
from app.core.logging import logger


# ---------- 6 张图的规格清单 ----------
MATERIAL_VARIANTS = [
    {"label": "主图",     "ratio": "1:1",  "style_hint": "干净背景，商品居中，电商主图风格"},
    {"label": "详情图A",  "ratio": "3:4",  "style_hint": "场景化使用，突出商品细节"},
    {"label": "详情图B",  "ratio": "3:4",  "style_hint": "高级杂志感，柔光氛围"},
    {"label": "竖版长图", "ratio": "9:16", "style_hint": "适合朋友圈/小红书首图，竖版构图"},
    {"label": "横版广告", "ratio": "16:9", "style_hint": "横向 banner，留白用于文字"},
    {"label": "活动海报", "ratio": "4:5",  "style_hint": "节日促销氛围，色彩鲜明"},
]


def _get_db() -> Session:
    return SessionLocal()


def _parse_ratio(ratio: str) -> tuple[int, int]:
    table = {
        "1:1": (1024, 1024),
        "3:4": (768, 1024),
        "4:3": (1024, 768),
        "4:5": (819, 1024),
        "5:4": (1024, 819),
        "9:16": (576, 1024),
        "16:9": (1024, 576),
    }
    return table.get(ratio, (1024, 1024))


# ============== 主任务（编排） ==============
@celery_app.task(bind=True, name="app.workers.tasks.generate_ad_materials")
def generate_ad_materials(self, task_id: int):
    """主任务：拆出 6 个子任务并发执行"""
    from app.models.ad_task import AdTask
    from app.models.product import Product
    from app.models.ad_copy import AdCopy
    from app.models.image_prompt import ImagePrompt
    from app.models.audit_result import AuditResult
    from app.services.llm_service import llm_service
    from app.services.audit_service import audit_service

    db = _get_db()
    try:
        ad_task = db.query(AdTask).filter(AdTask.id == task_id).first()
        if not ad_task:
            logger.error(f"Ad task {task_id} not found")
            return {"status": "error", "message": "Task not found"}

        ad_task.status = "processing"
        ad_task.started_at = datetime.utcnow()
        db.commit()

        product = db.query(Product).filter(Product.id == ad_task.product_id).first()
        if not product:
            raise ValueError("Product not found")

        # 1. 文案
        logger.info(f"[task {task_id}] Generating ad copy")
        copy_data = asyncio.run(llm_service.generate_ad_copy(
            product_name=product.name,
            product_description=product.description or "",
            selling_points=product.selling_points or [],
            platform=ad_task.platform,
            ad_type=ad_task.ad_type,
            style=ad_task.style,
            target_audience=product.target_audience,
        ))
        ad_copy = AdCopy(
            task_id=ad_task.id,
            title=copy_data.get("title", ""),
            body=copy_data.get("body", ""),
            slogan=copy_data.get("slogan", ""),
            platform=ad_task.platform,
            version=1,
        )
        db.add(ad_copy); db.commit(); db.refresh(ad_copy)

        # 2. 审核
        audit = audit_service.audit_ad_copy(
            title=ad_copy.title, body=ad_copy.body, slogan=ad_copy.slogan
        )
        db.add(AuditResult(
            task_id=ad_task.id,
            content_type="ad_copy",
            passed=audit["passed"],
            risk_level=audit["risk_level"],
            issues=audit["issues"],
            suggestions=audit["suggestions"],
        ))
        db.commit()
        if not audit["passed"]:
            ad_task.status = "failed"
            ad_task.error_message = "内容审核未通过：" + "; ".join(audit["suggestions"])
            ad_task.finished_at = datetime.utcnow()
            db.commit()
            return {"status": "failed", "message": "audit failed"}

        # 3. 图片 prompt（一次生成基础 prompt，子任务再加各自风格 hint）
        logger.info(f"[task {task_id}] Generating image prompt")
        prompt_data = asyncio.run(llm_service.generate_image_prompt(
            product_name=product.name,
            product_description=product.description or "",
            ad_copy=copy_data,
            style=ad_task.style,
            platform=ad_task.platform,
        ))
        base_prompt = prompt_data.get("prompt", "")
        negative_prompt = prompt_data.get("negative_prompt", "low quality, blurry, watermark")
        db.add(ImagePrompt(
            task_id=ad_task.id,
            prompt=base_prompt,
            negative_prompt=negative_prompt,
            style=ad_task.style,
            ratio=ad_task.image_ratio,
            version=1,
        ))
        db.commit()

        # 4. fan-out 6 张图
        reference_image_url = product.image_url  # 若商品有底图 → 图生图
        header = group(
            generate_one_material.s(
                task_id=task_id,
                product_id=product.id,
                variant_label=v["label"],
                ratio=v["ratio"],
                base_prompt=base_prompt,
                style_hint=v["style_hint"],
                negative_prompt=negative_prompt,
                reference_image_url=reference_image_url,
            )
            for v in MATERIAL_VARIANTS
        )
        callback = finalize_ad_task.s(task_id=task_id)
        chord(header)(callback)

        logger.info(f"[task {task_id}] dispatched {len(MATERIAL_VARIANTS)} subtasks")
        return {"status": "dispatched", "subtasks": len(MATERIAL_VARIANTS)}

    except Exception as e:
        logger.exception(f"[task {task_id}] failed in orchestrator")
        ad_task = db.query(AdTask).filter(AdTask.id == task_id).first()
        if ad_task:
            ad_task.status = "failed"
            ad_task.error_message = str(e)[:500]
            ad_task.retry_count = (ad_task.retry_count or 0) + 1
            ad_task.finished_at = datetime.utcnow()
            db.commit()
        raise
    finally:
        db.close()


# ============== 子任务（每张图） ==============
@celery_app.task(bind=True, name="app.workers.tasks.generate_one_material",
                 autoretry_for=(Exception,), retry_backoff=True, max_retries=2)
def generate_one_material(
    self,
    task_id: int,
    product_id: int,
    variant_label: str,
    ratio: str,
    base_prompt: str,
    style_hint: str,
    negative_prompt: str,
    reference_image_url: Optional[str] = None,
):
    """生成单张图片并落库 Material"""
    from app.models.material import Material
    from app.services.image_service import image_service
    from app.services.storage_service import storage_service

    db = _get_db()
    try:
        full_prompt = f"{base_prompt}. {style_hint}".strip()
        width, height = _parse_ratio(ratio)

        logger.info(f"[task {task_id}/{variant_label}] generating image {width}x{height}")
        image_bytes = asyncio.run(image_service.generate_image(
            prompt=full_prompt,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            reference_image_url=reference_image_url,
        ))

        filename = f"ad_materials/{task_id}_{variant_label}_{datetime.utcnow().timestamp()}.png"
        image_url = storage_service.upload_file(
            file_data=image_bytes,
            file_name=filename,
            content_type="image/png",
        )

        material = Material(
            task_id=task_id,
            product_id=product_id,
            image_url=image_url,
            status="active",
            is_favorite=False,
        )
        db.add(material); db.commit(); db.refresh(material)
        logger.info(f"[task {task_id}/{variant_label}] material {material.id} saved")
        return {"material_id": material.id, "label": variant_label, "url": image_url}
    finally:
        db.close()


# ============== chord 回调 ==============
@celery_app.task(name="app.workers.tasks.finalize_ad_task")
def finalize_ad_task(results, task_id: int):
    """所有子任务完成后调用，汇总状态"""
    from app.models.ad_task import AdTask
    db = _get_db()
    try:
        ad_task = db.query(AdTask).filter(AdTask.id == task_id).first()
        if not ad_task:
            return {"status": "error"}
        success_count = sum(1 for r in results if isinstance(r, dict) and r.get("material_id"))
        ad_task.status = "completed" if success_count > 0 else "failed"
        ad_task.finished_at = datetime.utcnow()
        if success_count == 0:
            ad_task.error_message = "所有图片生成均失败"
        db.commit()
        logger.info(f"[task {task_id}] finalized: {success_count}/{len(results)} succeeded")
        return {"status": ad_task.status, "succeeded": success_count, "total": len(results)}
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.test_task")
def test_task(message: str):
    logger.info(f"Test task received: {message}")
    return {"status": "success", "message": message}
