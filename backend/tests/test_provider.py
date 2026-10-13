"""Provider boundary tests: fake HTTP only, never an external model call."""

import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest

from app.ai.provider import ModelClient, ModelError


def settings(**overrides):
    values = dict(
        mode="live", llm_api_base="https://fake.example/v1", llm_api_key="private-test-key",
        llm_model="test-chat", llm_timeout=1, embedding_api_base="https://embed.example/v1",
        embedding_api_key="private-embedding-key", embedding_model="test-embedding", embedding_timeout=1,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def chat_response(**overrides):
    values = {
        "model": "test-chat", "choices": [{"message": {"content": "{\"title\":\"杯子\"}"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 12, "completion_tokens": 7},
    }
    values.update(overrides)
    return values


def test_chat_sends_tools_and_json_instruction_without_mutating_messages():
    received = []
    tool = {"type": "function", "function": {"name": "get_product", "parameters": {"type": "object"}}}
    tool_call = {"id": "call_1", "type": "function", "function": {"name": "get_product", "arguments": "{}"}}

    def handler(request):
        received.append(request)
        return httpx.Response(200, json=chat_response(choices=[{"message": {"content": None, "tool_calls": [tool_call]}, "finish_reason": "tool_calls"}]))

    messages = [{"role": "user", "content": "读取商品"}]
    result = asyncio.run(ModelClient(settings(), transport=httpx.MockTransport(handler)).chat(messages, [tool], True))
    payload = json.loads(received[0].content)
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["tools"] == [tool]
    assert payload["tool_choice"] == "auto"
    assert "JSON" in payload["messages"][0]["content"]
    assert received[0].url == "https://fake.example/v1/chat/completions"
    assert received[0].headers["authorization"] == "Bearer private-test-key"
    assert messages == [{"role": "user", "content": "读取商品"}]
    assert result["tool_calls"] == [tool_call]
    assert result["usage"] == {"input_tokens": 12, "output_tokens": 7}
    assert result["latency_ms"] >= 0


@pytest.mark.parametrize("status", [408, 429, 500, 503])
def test_retryable_http_failure_recovers_with_bounded_retry(status):
    count = 0

    def handler(request):
        nonlocal count
        count += 1
        return httpx.Response(status, json={"error": {"message": "do not expose me"}}) if count < 3 else httpx.Response(200, json=chat_response())

    result = asyncio.run(ModelClient(settings(), transport=httpx.MockTransport(handler), retry_delay=0).chat([{"role": "user", "content": "hi"}]))
    assert count == 3
    assert result["attempts"] == 3


def test_retry_backoff_applies_bounded_jitter(monkeypatch):
    count = 0

    def handler(request):
        nonlocal count
        count += 1
        return httpx.Response(503, json={"error": {"message": "retry"}}) if count < 3 else httpx.Response(200, json=chat_response())

    delays = []

    async def fake_sleep(delay):
        delays.append(delay)

    monkeypatch.setattr("app.ai.provider.asyncio.sleep", fake_sleep)
    result = asyncio.run(ModelClient(settings(), transport=httpx.MockTransport(handler), retry_delay=1.0).chat([{"role": "user", "content": "hi"}]))
    assert result["attempts"] == 3
    assert len(delays) == 2
    # 第一次退避 1.0s，第二次指数退避 2.0s 封顶；抖动在 ±50% 内且不越过上限。
    assert 0.5 <= delays[0] <= 1.5
    assert 1.0 <= delays[1] <= 2.0


@pytest.mark.parametrize("status,code", [(400, "invalid_request"), (401, "authentication"), (403, "authentication"), (404, "invalid_request")])
def test_permanent_failure_does_not_retry_or_leak_body(status, code, caplog):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, json={"error": {"message": "private-test-key confidential"}})

    with pytest.raises(ModelError) as captured:
        asyncio.run(ModelClient(settings(), transport=httpx.MockTransport(handler), retry_delay=0).chat([{"role": "user", "content": "hi"}]))
    assert len(calls) == 1
    assert captured.value.code == code
    assert "private-test-key" not in str(captured.value)
    assert "confidential" not in str(captured.value)
    assert "private-test-key" not in caplog.text


def test_quota_exhausted_429_is_not_retried():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(429, json={"error": {"code": "insufficient_quota"}})

    with pytest.raises(ModelError) as captured:
        asyncio.run(ModelClient(settings(), transport=httpx.MockTransport(handler), retry_delay=0).chat([{"role": "user", "content": "hi"}]))
    assert len(calls) == 1
    assert captured.value.code == "quota_exhausted"


def test_timeout_is_safe_and_retries_are_exhausted():
    count = 0

    def handler(request):
        nonlocal count
        count += 1
        raise httpx.ReadTimeout("timeout private-test-key", request=request)

    with pytest.raises(ModelError) as captured:
        asyncio.run(ModelClient(settings(), transport=httpx.MockTransport(handler), retry_delay=0).chat([{"role": "user", "content": "hi"}]))
    assert count == 3
    assert captured.value.code == "timeout"
    assert captured.value.attempts == 3
    assert "private-test-key" not in str(captured.value)


def test_demo_mode_prevents_even_an_accidental_request():
    def handler(request):
        pytest.fail("No external HTTP should be attempted in demo mode")

    with pytest.raises(ModelError) as captured:
        asyncio.run(ModelClient(settings(mode="demo"), transport=httpx.MockTransport(handler)).chat([{"role": "user", "content": "hi"}]))
    assert captured.value.code == "demo_mode"
    assert captured.value.attempts == 0


@pytest.mark.parametrize("body,code", [
    ({"choices": [{"message": None}]}, "invalid_response"),
    ({"choices": []}, "invalid_response"),
    ({"choices": [{"message": {"content": ""}}]}, "empty_response"),
    ({"choices": [{"message": {"content": "{"}, "finish_reason": "length"}]}, "truncated"),
    ({"choices": [{"message": {"content": ""}, "finish_reason": "content_filter"}]}, "refusal"),
])
def test_invalid_or_incomplete_chat_response_is_explicit(body, code):
    def handler(request):
        return httpx.Response(200, json=body)

    with pytest.raises(ModelError) as captured:
        asyncio.run(ModelClient(settings(), transport=httpx.MockTransport(handler)).chat([{"role": "user", "content": "hi"}]))
    assert captured.value.code == code


def test_embedding_order_follows_indices_and_uses_separate_key():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"data": [
            {"index": 1, "embedding": [0.1, 0.9]}, {"index": 0, "embedding": [0.9, 0.1]},
        ]})

    result = asyncio.run(ModelClient(settings(), transport=httpx.MockTransport(handler)).embed(["a", "b"]))
    assert result == [[0.9, 0.1], [0.1, 0.9]]
    assert requests[0].url == "https://embed.example/v1/embeddings"
    assert requests[0].headers["authorization"] == "Bearer private-embedding-key"
    assert json.loads(requests[0].content) == {"model": "test-embedding", "input": ["a", "b"], "encoding_format": "float"}


@pytest.mark.parametrize("data", [
    [{"index": 0, "embedding": [1, 0]}, {"index": 0, "embedding": [0, 1]}],
    [{"index": 0, "embedding": [1, 0]}, {"index": 1, "embedding": [1]}],
    [{"index": 0, "embedding": [0, 0]}, {"index": 1, "embedding": [1, 0]}],
    [{"index": 0, "embedding": ["secret", 0]}, {"index": 1, "embedding": [1, 0]}],
])
def test_malformed_embedding_response_is_rejected(data):
    def handler(request):
        return httpx.Response(200, json={"data": data})

    with pytest.raises(ModelError) as captured:
        asyncio.run(ModelClient(settings(), transport=httpx.MockTransport(handler)).embed(["a", "b"]))
    assert captured.value.code == "invalid_response"
