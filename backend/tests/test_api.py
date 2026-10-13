"""User-facing integration risks, with isolated data and no model network calls."""
from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from app.ai.api import PREFIX, create_app
from app.ai.config import AISettings
from app.ai.images import ImageError
from app.ai.provider import ModelClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    async def no_network(*args, **kwargs):
        pytest.fail("Demo integration must never call an external model")

    monkeypatch.setattr(ModelClient, "chat", no_network)
    monkeypatch.setattr(ModelClient, "embed", no_network)
    settings = AISettings(data_dir=tmp_path, force_demo=True, llm_api_key="", image_provider="demo")
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def session(client):
    response = client.post(f"{PREFIX}/sessions")
    assert response.status_code == 201
    return response.json()["id"]


def run(client, message="生成商品文案", *, session_id=None, product_id="p-cup", request_id="request-1"):
    response = client.post(f"{PREFIX}/runs", json={
        "session_id": session_id or session(client), "product_id": product_id,
        "message": message, "platform": "xiaohongshu", "request_id": request_id,
    })
    assert response.status_code == 202, response.text
    identifier = response.json()["id"]
    response = client.get(f"{PREFIX}/runs/{identifier}")
    assert response.status_code == 200
    return response.json()


def test_create_product_import_scoped_evidence_generate_and_follow_up(client):
    product_response = client.post(f"{PREFIX}/products", json={
        "name": "晴天随行杯", "brand_id": "integration-brand", "category": "生活用品",
        "facts": [{"id": "capacity", "label": "容量", "value": "400mL"},
                  {"id": "price", "label": "售价", "value": "99元"}],
    })
    assert product_response.status_code == 201
    product_id = product_response.json()["id"]
    imported = client.post(f"{PREFIX}/documents", json={
        "title": "晴天品牌写作手册", "brand_id": "integration-brand", "version": "2",
        "source": "用户提供的测试手册", "content": "晴天随行杯文案采用简洁温和语气，适合日常通勤，不编造商品性能。",
    })
    assert imported.status_code == 201
    foreign = client.post(f"{PREFIX}/documents", json={
        "title": "其他品牌手册", "brand_id": "other-brand",
        "content": "晴天随行杯 晴天随行杯 文案 品牌 绝密其他品牌资料。",
    })
    assert foreign.status_code == 201
    filtered = client.get(f"{PREFIX}/documents", params={"brand_id": "integration-brand"}).json()
    assert [d["id"] for d in filtered] == [imported.json()["id"]]
    sid = session(client)
    first = run(client, "生成晴天随行杯文案，不要提价格", session_id=sid, product_id=product_id)
    assert first["status"] == "completed", first
    assert first["validation"]["passed"]
    assert first["mode"] == "demo"
    assert first["usage"]["total_calls"] == 0
    assert first["evidence"]
    assert {e["document_id"] for e in first["evidence"]} == {imported.json()["id"]}
    assert first["evidence"][0]["version"] == "2"
    follow_up = run(client, "正文改得更口语一些", session_id=sid, product_id=product_id, request_id="follow-up")
    assert follow_up["status"] == "completed", follow_up
    assert "99元" not in follow_up["draft"]["body"]
    assert all("price" not in claim["fact_ids"] for claim in follow_up["draft"]["claims"])
    assert any(event["stage"] == "memory" for event in follow_up["trace"])
    history = client.get(f"{PREFIX}/sessions/{sid}/runs").json()
    assert [entry["id"] for entry in history] == [first["id"], follow_up["id"]]
    assert client.delete(f"{PREFIX}/documents/{imported.json()['id']}").status_code == 204


def test_same_request_reuses_run_and_different_content_conflicts(client):
    sid = session(client)
    payload = {"session_id": sid, "product_id": "p-cup", "message": "生成商品文案", "request_id": "same"}
    first = client.post(f"{PREFIX}/runs", json=payload)
    assert first.status_code == 202
    before = client.get(f"{PREFIX}/runs/{first.json()['id']}").json()
    duplicate = client.post(f"{PREFIX}/runs", json=payload)
    assert duplicate.status_code == 202
    assert duplicate.json()["id"] == first.json()["id"]
    assert duplicate.json()["trace"] == before["trace"]
    changed = client.post(f"{PREFIX}/runs", json={**payload, "message": "修改为简短文案"})
    assert changed.status_code == 409
    assert len(client.get(f"{PREFIX}/sessions/{sid}/runs").json()) == 1


def test_session_creation_is_idempotent_with_request_id(client):
    # React StrictMode 会双调用初始化 effect；同一 request_id 只应产生一条会话记录。
    first = client.post(f"{PREFIX}/sessions", json={"request_id": "init-1"})
    duplicate = client.post(f"{PREFIX}/sessions", json={"request_id": "init-1"})
    assert first.status_code == duplicate.status_code == 201
    assert first.json()["id"] == duplicate.json()["id"]
    # 会话存在且可用：能查询到空的历史列表。
    assert client.get(f"{PREFIX}/sessions/{first.json()['id']}/runs").status_code == 200


def test_session_creation_without_request_id_still_works(client):
    response = client.post(f"{PREFIX}/sessions")
    assert response.status_code == 201
    response = client.post(f"{PREFIX}/sessions", json={})
    assert response.status_code == 201


def test_completed_sse_replays_trace_and_honors_last_event_id(client):
    completed = run(client)
    response = client.get(f"{PREFIX}/runs/{completed['id']}/events")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: snapshot" in response.text
    assert "event: done" in response.text
    assert '"type": "completed"' in response.text
    assert "id: 1\nevent: trace" in response.text
    resumed = client.get(f"{PREFIX}/runs/{completed['id']}/events", headers={"Last-Event-ID": str(len(completed["trace"]))})
    assert "event: trace" not in resumed.text
    assert "event: done" in resumed.text


@pytest.mark.parametrize("route", ["runs/missing", "runs/missing/events", "sessions/missing/runs", "image-jobs/missing"])
def test_missing_objects_return_404(client, route):
    assert client.get(f"{PREFIX}/{route}").status_code == 404


def test_unknown_run_inputs_and_invalid_image_confirmation_are_rejected(client):
    sid = session(client)
    payload = {"session_id": "missing", "product_id": "p-cup", "message": "生成文案", "request_id": "bad"}
    assert client.post(f"{PREFIX}/runs", json=payload).status_code == 404
    assert client.post(f"{PREFIX}/runs", json={**payload, "session_id": sid, "product_id": "missing"}).status_code == 404
    completed = run(client, session_id=sid)
    url = f"{PREFIX}/runs/{completed['id']}/images"
    assert client.post(url, json={"indices": [0], "request_id": "no-confirm"}).status_code == 422
    assert client.post(url, json={"confirmed": False, "indices": [0], "request_id": "false-confirm"}).status_code == 422
    assert client.post(url, json={"confirmed": True, "indices": [99], "request_id": "bad-index"}).status_code == 422
    assert client.post(url, json={"confirmed": True, "indices": [0, 0], "request_id": "duplicate-index"}).status_code == 422


def test_unverified_promise_cannot_become_a_generatable_image(client):
    result = run(client, "生成广告文案，突出保温24小时")
    assert result["status"] == "needs_clarification"
    assert not result["validation"]["passed"]
    assert result["draft"] is None
    assert any(issue["code"] == "UNSUPPORTED_REQUEST" for issue in result["validation"]["issues"])
    assert client.post(f"{PREFIX}/runs/{result['id']}/images", json={
        "confirmed": True, "indices": [0], "request_id": "cannot-generate",
    }).status_code == 409


def test_transparent_product_upload_is_preserved_in_confirmed_image_and_asset_is_fetchable(client):
    png = BytesIO()
    subject = Image.new("RGBA", (80, 80), (0, 0, 0, 0))
    for x in range(20, 60):
        for y in range(20, 60):
            subject.putpixel((x, y), (255, 0, 0, 255))
    subject.save(png, "PNG")
    upload = client.post(f"{PREFIX}/products/p-cup/image", files={"file": ("subject.png", png.getvalue(), "image/png")})
    assert upload.status_code == 200
    assert client.get(upload.json()["image_url"]).status_code == 200
    completed = run(client)
    response = client.post(f"{PREFIX}/runs/{completed['id']}/images", json={
        "confirmed": True, "indices": [0], "request_id": "compose",
    })
    assert response.status_code == 202
    job = client.get(f"{PREFIX}/image-jobs/{response.json()['id']}").json()
    assert job["status"] == "completed"
    result = job["images"][0]
    assert result["product_preserved"] and result["warning"] is None
    asset = client.get(result["url"])
    assert asset.status_code == 200
    composed = Image.open(BytesIO(asset.content))
    assert composed.size == (1024, 1024)
    assert composed.getpixel((512, 582)) == (255, 0, 0)


def test_partial_image_failure_can_retry_only_selected_index_and_duplicate_is_local_idempotent(client, monkeypatch):
    calls = []
    failing_once = {1}

    async def render(plan, product, filename, on_provider_task):
        index = int(filename.rsplit("-", 1)[1].removesuffix(".png"))
        calls.append(index)
        await on_provider_task(f"fake-provider-task-{len(calls)}")
        if index in failing_once:
            failing_once.remove(index)
            raise ImageError("测试供应商暂时失败")
        return {"url": "test-result.png", "label": plan["label"], "mode": "demo", "product_preserved": False, "warning": "test"}

    monkeypatch.setattr(client.app.state.renderer, "render", render)
    completed = run(client)
    endpoint = f"{PREFIX}/runs/{completed['id']}/images"
    payload = {"confirmed": True, "indices": [0, 1], "request_id": "first-images"}
    first = client.post(endpoint, json=payload).json()
    job = client.get(f"{PREFIX}/image-jobs/{first['id']}").json()
    assert job["status"] == "partial"
    assert [image["index"] for image in job["images"]] == [0]
    assert [failure["index"] for failure in job["failures"]] == [1]
    assert len(job["provider_tasks"]) == 2
    duplicate = client.post(endpoint, json=payload)
    assert duplicate.json()["id"] == first["id"]
    assert calls == [0, 1]
    assert client.post(endpoint, json={**payload, "indices": [1]}).status_code == 409
    retry = client.post(endpoint, json={"confirmed": True, "indices": [1], "request_id": "retry-failed-index"})
    assert retry.status_code == 202
    retried = client.get(f"{PREFIX}/image-jobs/{retry.json()['id']}").json()
    assert retried["status"] == "completed"
    assert [image["index"] for image in retried["images"]] == [1]
    assert calls == [0, 1, 1]
    assert client.get(f"{PREFIX}/image-jobs/{first['id']}").json()["images"] == job["images"]


def test_feedback_persists_and_rating_is_validated(client):
    completed = run(client)
    endpoint = f"{PREFIX}/runs/{completed['id']}/feedback"
    assert client.post(endpoint, json={"rating": 6}).status_code == 422
    response = client.post(endpoint, json={"rating": 4, "accepted": True, "comment": "事实准确，需要进一步调整语气"})
    assert response.status_code == 200
    assert client.app.state.repo.get("feedback", completed["id"])["accepted"] is True
    assert client.post(f"{PREFIX}/runs/missing/feedback", json={"rating": 3}).status_code == 404


def test_real_evaluation_endpoint_creates_report_and_latest_returns_it(client):
    assert client.get(f"{PREFIX}/evaluations/latest").json() is None
    response = client.post(f"{PREFIX}/evaluations", json={"mode": "demo"})
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["id"]
    assert report["mode"] == "offline"
    assert report["cases_total"] > 0
    assert report["passed"] + report["failed"] == report["cases_total"]
    assert client.get(f"{PREFIX}/evaluations/latest").json() == report


def test_evaluation_route_stays_offline_even_when_live_credentials_are_configured(tmp_path, monkeypatch):
    async def no_network(*args, **kwargs):
        pytest.fail("Public evaluation route must not trigger paid model requests")

    monkeypatch.setattr(ModelClient, "chat", no_network)
    monkeypatch.setattr(ModelClient, "embed", no_network)
    settings = AISettings(data_dir=tmp_path, force_demo=False, llm_api_key="private-configured-key",
                          embedding_api_base="https://fake.invalid", embedding_api_key="private-embedding-key",
                          embedding_model="fake", image_provider="demo")
    with TestClient(create_app(settings)) as configured:
        assert configured.get(f"{PREFIX}/config").json()["mode"] == "live"
        response = configured.post(f"{PREFIX}/evaluations", json={"mode": "demo"})
        assert response.status_code == 200
        assert response.json()["mode"] == "offline"
        assert all(case["actual"].get("calls", 0) == 0 for case in response.json()["cases"])
        assert "private-configured-key" not in response.text
        assert "private-embedding-key" not in response.text


def test_changing_product_does_not_carry_previous_product_facts(client):
    sid = session(client)
    first = run(client, session_id=sid, product_id="p-cup")
    assert first["status"] == "completed"
    switched = run(client, "生成商品文案", session_id=sid, product_id="p-bag", request_id="switched-product")
    assert switched["status"] == "completed"
    serialized_draft = str(switched["draft"])
    assert "北岸随行杯" not in serialized_draft
    assert "f-capacity" not in serialized_draft
    assert "山径轻旅背包" in serialized_draft
    assert not any(event["stage"] == "memory" for event in switched["trace"])


def test_bad_image_upload_does_not_change_product_image(client):
    response = client.post(f"{PREFIX}/products/p-cup/image", files={"file": ("invalid.png", b"not an image", "image/png")})
    assert response.status_code == 422
    assert client.app.state.repo.get("products", "p-cup")["image_url"] is None
    assert client.post(f"{PREFIX}/products/missing/image", files={"file": ("invalid.png", b"bad", "image/png")}).status_code == 404


def test_app_restart_marks_interrupted_work_failed_without_losing_records(tmp_path):
    settings = AISettings(data_dir=tmp_path, force_demo=True, llm_api_key="", image_provider="demo")
    app = create_app(settings)
    app.state.repo.put("runs", {"id": "interrupted", "status": "running", "trace": [{"id": 1, "stage": "generation"}]})
    app.state.repo.put("image_jobs", {"id": "partial-on-restart", "status": "running", "images": [{"index": 0, "url": "kept.png"}],
                                     "provider_tasks": [{"index": 1, "task_id": "vendor-accepted"}]})
    with TestClient(create_app(settings)) as restarted:
        failed = restarted.get(f"{PREFIX}/runs/interrupted").json()
        image_job = restarted.get(f"{PREFIX}/image-jobs/partial-on-restart").json()
    assert failed["status"] == "failed" and failed["trace"]
    assert image_job["status"] == "failed"
    assert image_job["images"] == [{"index": 0, "url": "kept.png"}]
    assert image_job["provider_tasks"] == [{"index": 1, "task_id": "vendor-accepted"}]
