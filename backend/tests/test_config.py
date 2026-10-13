"""AISettings 的 env 解析、边界校验与模式推导。

config.py 模块导入时会执行 load_local_env()（只填充未设置的变量），
因此每个用例先清理相关环境变量，再构造 AISettings。
"""
import pytest

from app.ai.config import AISettings, _integer


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for key in (
        "AI_MODE", "LLM_API_KEY", "LLM_API_BASE", "LLM_MODEL", "LLM_TIMEOUT",
        "MAX_AGENT_STEPS", "MAX_REPAIR_ATTEMPTS", "RAG_TOP_K", "RAG_CHUNK_SIZE",
        "RAG_CHUNK_OVERLAP", "EMBEDDING_API_BASE", "EMBEDDING_API_KEY",
        "EMBEDDING_MODEL",
    ):
        monkeypatch.delenv(key, raising=False)


def test_integer_bounds_raise(monkeypatch):
    monkeypatch.setenv("LLM_TIMEOUT", "1000")
    with pytest.raises(ValueError):
        AISettings()


def test_mode_is_demo_when_forced(monkeypatch):
    monkeypatch.setenv("AI_MODE", "demo")
    monkeypatch.setenv("LLM_API_KEY", "sk-anything")
    assert AISettings().mode == "demo"


def test_mode_is_live_only_with_key(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-anything")
    assert AISettings().mode == "live"
    monkeypatch.delenv("LLM_API_KEY")
    assert AISettings().mode == "demo"


def test_embedding_enabled_requires_all_three(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-anything")
    monkeypatch.setenv("EMBEDDING_API_BASE", "https://example.test/v1")
    monkeypatch.setenv("EMBEDDING_API_KEY", "ek-anything")
    monkeypatch.setenv("EMBEDDING_MODEL", "text-embedding")
    assert AISettings().embedding_enabled is True

    monkeypatch.delenv("EMBEDDING_MODEL")
    assert AISettings().embedding_enabled is False


def test_integer_helper_reads_env_with_default():
    assert _integer("NOT_SET_ANYWHERE", 4, 1, 10) == 4
