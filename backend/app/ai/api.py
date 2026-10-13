"""对话工作台 HTTP 适配层；业务生成逻辑在 workflow.py。"""
import asyncio
from contextlib import asynccontextmanager
from io import BytesIO
import json
import time
from typing import Literal

from fastapi import BackgroundTasks, FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .config import AISettings, PROJECT_ROOT
from .images import ImageRenderer, ImageError
from .provider import ModelClient, ModelError
from .repository import Repository, IdempotencyConflict, fingerprint, new_id, now
from .retrieval import Retriever
from .workflow import AIWorkflow

PREFIX = "/api/v1/ai"


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FactInput(StrictInput):
    id: str | None = Field(None, max_length=80)
    label: str = Field(min_length=1, max_length=80)
    value: str = Field(min_length=1, max_length=200)


class ProductInput(StrictInput):
    name: str = Field(min_length=1, max_length=100)
    category: str = Field("其他", max_length=50)
    description: str = Field("", max_length=2000)
    brand_id: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")
    facts: list[FactInput] = Field(min_length=1, max_length=30)
    selling_points: list[str] = Field(default_factory=list, max_length=15)


class DocumentInput(StrictInput):
    title: str = Field(min_length=1, max_length=150)
    content: str = Field(min_length=10, max_length=30000)
    brand_id: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")
    source: str = Field("用户导入", max_length=300)
    version: str = Field("1", max_length=30)


class RunInput(StrictInput):
    session_id: str = Field(min_length=1, max_length=80)
    product_id: str = Field(min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=3000)
    platform: Literal["xiaohongshu", "taobao", "douyin"] = "xiaohongshu"
    request_id: str = Field(min_length=1, max_length=100)


class FeedbackInput(StrictInput):
    rating: int = Field(ge=1, le=5)
    comment: str = Field("", max_length=1000)
    accepted: bool = False


class ImageInput(StrictInput):
    confirmed: Literal[True]
    indices: list[int] = Field(min_length=1, max_length=3)
    request_id: str = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_indices(self):
        if len(set(self.indices)) != len(self.indices) or any(i < 0 for i in self.indices):
            raise ValueError("indices 应为不重复的非负序号")
        return self


class EvaluationInput(StrictInput):
    mode: Literal["demo"] = "demo"


def create_app(settings: AISettings | None = None) -> FastAPI:
    settings = settings or AISettings()
    assets = settings.data_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    repo = Repository(settings.data_dir)
    if not repo.get("meta", "seeded"):
        for kind, filename in (("products", "sample_products.json"), ("documents", "sample_documents.json")):
            for value in json.loads((PROJECT_ROOT / "data" / filename).read_text(encoding="utf-8")):
                repo.put(kind, value)
        repo.put("meta", {"id":"seeded", "at":now()})
    client = ModelClient(settings)
    retriever = Retriever(settings, client)
    workflow = AIWorkflow(settings, client, retriever)
    renderer = ImageRenderer(settings)
    session_locks: dict[str, asyncio.Lock] = {}
    concurrency = asyncio.Semaphore(settings.max_concurrent_runs)
    image_concurrency = asyncio.Semaphore(2)

    @asynccontextmanager
    async def lifespan(app):
        repo.recover_interrupted()
        yield

    app = FastAPI(title="AdCraft AI 对话工作台", version="2.0.0", lifespan=lifespan)
    app.state.repo = repo
    app.state.settings = settings
    app.state.workflow = workflow
    app.state.renderer = renderer
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"],
        allow_credentials=False, allow_methods=["GET","POST","DELETE"], allow_headers=["Content-Type","Last-Event-ID"])
    app.mount(f"{PREFIX}/assets", StaticFiles(directory=assets), name="assets")

    def required(kind, item_id):
        value = repo.get(kind, item_id)
        if value is None:
            raise HTTPException(404, "对象不存在")
        return value

    @app.get("/health")
    async def health():
        return {"status":"healthy", "version":"2.0.0"}

    @app.get(f"{PREFIX}/config")
    async def config():
        return {"mode":settings.mode,"model":settings.llm_model if settings.mode=="live" else "deterministic-demo",
                "embedding_mode":"hybrid" if settings.embedding_enabled else "lexical", "image_provider":settings.image_provider,
                "max_agent_steps":settings.max_agent_steps,"version":"2.0.0", "single_workspace":True}

    @app.get(f"{PREFIX}/products")
    async def products():
        return repo.list("products")

    @app.post(f"{PREFIX}/products", status_code=201)
    async def create_product(body: ProductInput):
        data = body.model_dump()
        data.update(id=new_id("p"), image_url=None)
        ids = set()
        for fact in data["facts"]:
            fact["id"] = fact["id"] or new_id("f")
            if fact["id"] in ids:
                raise HTTPException(422,"商品事实 ID 不得重复")
            ids.add(fact["id"])
        return repo.put("products", data)

    @app.post(f"{PREFIX}/products/{{product_id}}/image")
    async def upload_image(product_id: str, file: UploadFile = File(...)):
        required("products", product_id)
        raw = await file.read(10*1024*1024+1)
        if len(raw)>10*1024*1024:
            raise HTTPException(413,"商品图不得超过 10MB")
        try:
            image = Image.open(BytesIO(raw))
            if image.width*image.height > 20_000_000:
                raise HTTPException(413,"图片像素过多，请先缩小")
            if image.format not in {"PNG","JPEG","WEBP"}:
                raise HTTPException(415,"仅支持 PNG、JPEG、WebP")
            filename = f"{new_id('product')}.png"
            image.convert("RGBA").save(assets/filename,"PNG")
        except (UnidentifiedImageError,OSError,Image.DecompressionBombError):
            raise HTTPException(422,"无法读取图片") from None
        return repo.mutate("products",product_id,lambda item:item.update(image_url=f"{PREFIX}/assets/{filename}"))

    @app.get(f"{PREFIX}/documents")
    async def documents(brand_id: str | None = None):
        return [d for d in repo.list("documents") if brand_id is None or d["brand_id"]==brand_id]

    @app.post(f"{PREFIX}/documents",status_code=201)
    async def create_document(body: DocumentInput):
        return repo.put("documents", {"id":new_id("d"),**body.model_dump()})

    @app.delete(f"{PREFIX}/documents/{{document_id}}",status_code=204)
    async def delete_document(document_id: str):
        required("documents",document_id)
        repo.delete("documents",document_id)

    @app.post(f"{PREFIX}/sessions",status_code=201)
    async def create_session():
        return repo.put("sessions",{"id":new_id("s"),"created_at":now()})

    @app.get(f"{PREFIX}/sessions/{{session_id}}/runs")
    async def session_runs(session_id: str):
        required("sessions",session_id)
        return [r for r in repo.list("runs") if r["session_id"]==session_id]

    async def execute_run(run_id: str):
        run = required("runs",run_id)
        lock = session_locks.setdefault(run["session_id"],asyncio.Lock())
        async with lock, concurrency:
            begin = time.perf_counter()
            repo.mutate("runs",run_id,lambda item:item.update(status="running"))
            async def emit(event_type, stage, message, data=None):
                repo.add_trace(run_id,{"type":event_type,"stage":stage,"message":message,"data":data or {},
                    "elapsed_ms":round((time.perf_counter()-begin)*1000),"created_at":now()})
            try:
                product = required("products",run["product_id"])
                # 会话换商品时不把旧商品草稿作为本商品的事实来源。
                history = [r for r in repo.list("runs") if r["session_id"]==run["session_id"] and
                           r["product_id"]==run["product_id"] and r["id"]!=run_id and
                           r["status"] in {"completed","needs_clarification"}][-6:]
                result = await asyncio.wait_for(app.state.workflow.run(product=product,documents=repo.list("documents"),
                    message=run["message"],platform=run["platform"],history=history,emit=emit),timeout=360)
                repo.mutate("runs",run_id,lambda item:item.update(**result))
            except asyncio.TimeoutError:
                await emit("error","timeout","本次执行超过总时间预算。")
                repo.mutate("runs",run_id,lambda item:item.update(status="failed",error="执行超时，请查看步骤记录后重试。"))
            except Exception as exc:
                message = str(exc) if isinstance(exc,ModelError) else "执行失败，请检查配置和运行日志。"
                await emit("error","failed",message,{"error_type":type(exc).__name__})
                repo.mutate("runs",run_id,lambda item:item.update(status="failed",error=message))

    @app.post(f"{PREFIX}/runs",status_code=202)
    async def create_run(body: RunInput, background: BackgroundTasks):
        required("sessions",body.session_id)
        required("products",body.product_id)
        created = now()
        value = {"id":new_id("run"),**body.model_dump(exclude={"request_id"}),"status":"queued","mode":settings.mode,
                 "answer":"","draft":None,"evidence":[],"trace":[],"validation":{"passed":False,"issues":[]},
                 "usage":{"input_tokens":0,"output_tokens":0,"total_calls":0,"latency_ms":0},"error":None,
                 "created_at":created,"updated_at":created}
        try:
            run, fresh = repo.create_idempotent("runs",value,body.session_id,body.request_id,
                                               fingerprint(body.model_dump(exclude={"request_id"})))
        except IdempotencyConflict as exc:
            raise HTTPException(409,str(exc)) from None
        if fresh:
            background.add_task(execute_run,run["id"])
        return run

    @app.get(f"{PREFIX}/runs/{{run_id}}")
    async def get_run(run_id: str):
        return required("runs",run_id)

    @app.get(f"{PREFIX}/runs/{{run_id}}/events")
    async def events(run_id: str, request: Request, last_event_id: str | None = Header(None)):
        required("runs",run_id)
        try:
            cursor = max(0,int(last_event_id or "0"))
        except ValueError:
            cursor = 0
        async def stream():
            nonlocal cursor
            snapshot = required("runs",run_id)
            yield f"event: snapshot\ndata: {json.dumps(snapshot,ensure_ascii=False)}\n\n"
            while not await request.is_disconnected():
                current = required("runs",run_id)
                for event in current["trace"]:
                    if event["id"]>cursor:
                        cursor=event["id"]
                        yield f"id: {cursor}\nevent: trace\ndata: {json.dumps(event,ensure_ascii=False)}\n\n"
                if current["status"] not in {"queued","running"}:
                    yield f"event: done\ndata: {json.dumps(current,ensure_ascii=False)}\n\n"
                    return
                yield ": keepalive\n\n"
                await asyncio.sleep(0.4)
        return StreamingResponse(stream(),media_type="text/event-stream",headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})

    @app.post(f"{PREFIX}/runs/{{run_id}}/feedback")
    async def feedback(run_id: str, body: FeedbackInput):
        required("runs",run_id)
        return repo.put("feedback",{"id":run_id,"run_id":run_id,**body.model_dump(),"created_at":now()})

    async def execute_images(job_id: str):
        job = required("image_jobs",job_id)
        run = required("runs",job["run_id"])
        product = required("products",run["product_id"])
        repo.mutate("image_jobs",job_id,lambda j:j.update(status="running"))
        async def one(index):
            plan=run["draft"]["image_prompts"][index]
            async def persist_vendor(task_id):
                def update(j): j["provider_tasks"].append({"index":index,"task_id":task_id})
                repo.mutate("image_jobs",job_id,update)
            async with image_concurrency:
                try:
                    result=await app.state.renderer.render(plan,product,f"{job_id}-{index}.png",persist_vendor)
                    result["index"]=index
                    repo.mutate("image_jobs",job_id,lambda j:j["images"].append(result))
                except Exception as exc:
                    message=str(exc) if isinstance(exc,ImageError) else "图片生成失败"
                    repo.mutate("image_jobs",job_id,lambda j:j["failures"].append({"index":index,"error":message}))
        await asyncio.gather(*(one(i) for i in job["indices"]))
        def finish(j):
            j["images"].sort(key=lambda image:image["index"])
            j["status"]="completed" if not j["failures"] else ("partial" if j["images"] else "failed")
            j["error"]="；".join(f["error"] for f in j["failures"]) or None
        repo.mutate("image_jobs",job_id,finish)

    @app.post(f"{PREFIX}/runs/{{run_id}}/images",status_code=202)
    async def generate_images(run_id: str, body: ImageInput, background: BackgroundTasks):
        run=required("runs",run_id)
        if run["status"]!="completed" or not run["draft"] or not run["validation"]["passed"]:
            raise HTTPException(409,"请先取得通过校验的文案方案")
        if any(i>=len(run["draft"]["image_prompts"]) for i in body.indices):
            raise HTTPException(422,"图片方案序号不存在")
        value={"id":new_id("img"),"run_id":run_id,"indices":body.indices,"status":"queued","images":[],
               "failures":[],"provider_tasks":[],"error":None,"created_at":now(),"updated_at":now()}
        try:
            job,fresh=repo.create_idempotent("image_jobs",value,f"images:{run_id}",body.request_id,fingerprint({"indices":body.indices}))
        except IdempotencyConflict as exc:
            raise HTTPException(409,str(exc)) from None
        if fresh:
            background.add_task(execute_images,job["id"])
        return job

    @app.get(f"{PREFIX}/runs/{{run_id}}/images")
    async def run_image_jobs(run_id: str):
        required("runs",run_id)
        return [job for job in repo.list("image_jobs") if job["run_id"]==run_id]

    @app.get(f"{PREFIX}/image-jobs/{{job_id}}")
    async def get_image_job(job_id: str):
        return required("image_jobs",job_id)

    @app.get(f"{PREFIX}/evaluations/latest")
    async def latest_evaluation():
        reports=repo.list("evaluations")
        return reports[-1] if reports else None

    @app.post(f"{PREFIX}/evaluations")
    async def evaluate(body: EvaluationInput):
        from .evaluation import run_evaluation
        report=await run_evaluation(settings,repo.list("products"),repo.list("documents"))
        return repo.put("evaluations",report)

    # 交付包带预构建网页。开发模式则使用 Vite 的 /api 代理。
    frontend_dist = PROJECT_ROOT / "frontend" / "dist"
    if frontend_dist.is_dir():
        app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="workbench")
    return app
