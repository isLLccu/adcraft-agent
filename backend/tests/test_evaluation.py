import asyncio
import json

import pytest

from app.ai.config import AISettings, PROJECT_ROOT
from app.ai.evaluation import load_cases, run_evaluation, run_selected_evaluation
from app.ai.provider import ModelClient


def fixtures():
    products = json.loads((PROJECT_ROOT / "data" / "sample_products.json").read_text(encoding="utf-8"))
    documents = json.loads((PROJECT_ROOT / "data" / "sample_documents.json").read_text(encoding="utf-8"))
    return products, documents


def test_all_24_offline_cases_pass_and_never_touch_any_model(monkeypatch):
    async def forbidden(*args, **kwargs):
        pytest.fail("Offline evaluation must never call chat or embedding APIs")

    monkeypatch.setattr(ModelClient, "chat", forbidden)
    monkeypatch.setattr(ModelClient, "embed", forbidden)
    configured = AISettings(llm_api_key="private-llm-key", embedding_api_base="https://fake", embedding_api_key="private-embedding-key", embedding_model="real")
    products, documents = fixtures()
    report = asyncio.run(run_evaluation(configured, products, documents))
    assert report["mode"] == "offline"
    assert report["cases_total"] == 24
    assert report["passed"] == 24, [case for case in report["cases"] if not case["passed"]]
    assert report["failed"] == 0
    assert report["pass_rate"] == 1
    assert {metric["name"]: metric["total"] for metric in report["metrics"]} == {"retrieval": 6, "validation": 10, "workflow": 8}
    assert all(case["actual"].get("calls", 0) == 0 for case in report["cases"])
    serialized = json.dumps(report, ensure_ascii=False)
    assert "private-llm-key" not in serialized
    assert "private-embedding-key" not in serialized
    assert configured.llm_api_key == "private-llm-key"  # original settings unchanged


def test_fixture_ids_are_unique_and_results_are_reproducible():
    assert len({case["id"] for case in load_cases()}) == 24
    products, documents = fixtures()
    settings = AISettings(force_demo=True, llm_api_key="")
    first = asyncio.run(run_evaluation(settings, products, documents))
    second = asyncio.run(run_evaluation(settings, products, documents))
    assert first["cases"] == second["cases"]
    assert first["metrics"] == second["metrics"]


def test_missing_fixture_is_reported_as_failed_instead_of_invented_success():
    _, documents = fixtures()
    report = asyncio.run(run_evaluation(AISettings(force_demo=True, llm_api_key=""), [], documents))
    assert report["passed"] == 0
    assert report["failed"] == 24
    assert report["cases"][0]["actual"]["error"] == "评测样例商品不存在"


def test_cli_helper_requires_both_live_flags_before_model_call(monkeypatch):
    async def forbidden(*args, **kwargs):
        pytest.fail("Unconfirmed live evaluation must not call a model")

    monkeypatch.setattr(ModelClient, "chat", forbidden)
    products, documents = fixtures()
    with pytest.raises(ValueError, match="confirm-paid"):
        asyncio.run(run_selected_evaluation(AISettings(llm_api_key="private-key"), products, documents, live=True, confirm_paid=False))
    with pytest.raises(ValueError, match="LLM_API_KEY"):
        asyncio.run(run_selected_evaluation(AISettings(llm_api_key=""), products, documents, live=True, confirm_paid=True))


def test_offline_limit_and_invalid_limits():
    products, documents = fixtures()
    settings = AISettings(force_demo=True, llm_api_key="")
    report = asyncio.run(run_selected_evaluation(settings, products, documents, limit=3))
    assert report["cases_total"] == report["passed"] == 3
    for limit in (0, 25):
        with pytest.raises(ValueError, match="limit"):
            asyncio.run(run_selected_evaluation(settings, products, documents, limit=limit))
