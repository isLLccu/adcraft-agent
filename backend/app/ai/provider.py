"""A small, auditable OpenAI-compatible HTTP adapter.

No SDK, demo responses, prompts, response bodies, or secrets are logged here.
Retries are bounded transport recovery, not an exactly-once billing guarantee.
"""

from __future__ import annotations

import asyncio
import math
import time
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

import httpx

if TYPE_CHECKING:
    from .config import AISettings


class ModelError(Exception):
    """Safe public error: never includes request headers or provider bodies."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "model_error",
        status_code: int | None = None,
        retryable: bool = False,
        attempts: int = 1,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.retryable = retryable
        self.attempts = attempts


class ModelClient:
    """Non-streaming chat and embeddings; every operation is asynchronous.

    ``transport`` and ``retry_delay`` are optional test seams. The application
    uses ModelClient(settings). At most three attempts occur by default, with
    capped backoff. A timeout can happen after upstream execution; callers must
    not interpret these retries as a guarantee of no duplicated charges.
    """

    def __init__(
        self,
        settings: AISettings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        max_retries: int = 2,
        retry_delay: float = 0.25,
    ) -> None:
        self.settings = settings
        self._transport = transport
        self._max_retries = min(max(int(max_retries), 0), 3)
        self._retry_delay = max(float(retry_delay), 0.0)

    @staticmethod
    def _endpoint(base: str, route: str) -> str:
        try:
            parts = urlsplit(str(base))
        except ValueError:
            raise ModelError("模型 API 地址配置无效。", code="configuration", attempts=0) from None
        if (
            parts.scheme not in {"http", "https"}
            or not parts.hostname
            or parts.username
            or parts.password
            or parts.query
            or parts.fragment
        ):
            raise ModelError("模型 API 地址配置无效。", code="configuration", attempts=0)
        return str(base).rstrip("/") + "/" + route

    @staticmethod
    def _http_error(response: httpx.Response, attempts: int) -> ModelError:
        status = response.status_code
        if status in {401, 403}:
            return ModelError(
                "模型服务认证或权限失败，请检查配置。",
                code="authentication",
                status_code=status,
                attempts=attempts,
            )
        if status == 429:
            # Some compatible services use 429 for exhausted credit. Retrying
            # that would waste time; inspect only the fixed error-code field.
            quota_exhausted = False
            try:
                body = response.json()
                error = body.get("error", {}) if isinstance(body, dict) else {}
                quota_exhausted = isinstance(error, dict) and error.get("code") in {
                    "insufficient_quota", "quota_exceeded", "insufficient_balance"
                }
            except (ValueError, TypeError):
                pass
            return ModelError(
                "模型服务额度不足。" if quota_exhausted else "模型服务限流，请稍后重试。",
                code="quota_exhausted" if quota_exhausted else "rate_limit",
                status_code=status,
                retryable=not quota_exhausted,
                attempts=attempts,
            )
        if status == 408 or 500 <= status < 600:
            return ModelError(
                "模型服务暂时不可用。",
                code="upstream_unavailable",
                status_code=status,
                retryable=True,
                attempts=attempts,
            )
        return ModelError(
            "模型服务拒绝了请求，请检查模型、工具和输出格式配置。",
            code="invalid_request",
            status_code=status,
            attempts=attempts,
        )

    async def _post(
        self, *, base: str, key: str, route: str, payload: dict, timeout: float
    ) -> tuple[dict, int]:
        if self.settings.mode != "live":
            raise ModelError("演示模式禁止调用外部模型 API。", code="demo_mode", attempts=0)
        if not key:
            raise ModelError("模型 API Key 未配置。", code="configuration", attempts=0)
        url = self._endpoint(base, route)
        if not math.isfinite(float(timeout)) or float(timeout) <= 0:
            raise ModelError("模型超时配置无效。", code="configuration", attempts=0)
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        # A per-operation client is closed even after cancellation or failure.
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(float(timeout)),
            transport=self._transport,
            follow_redirects=False,
        ) as client:
            for attempt in range(1, self._max_retries + 2):
                response: httpx.Response | None = None
                try:
                    # httpx's timeout is per network phase. wait_for also bounds
                    # the complete attempt (including full response download).
                    response = await asyncio.wait_for(
                        client.post(url, json=payload, headers=headers),
                        timeout=float(timeout),
                    )
                except (httpx.TimeoutException, asyncio.TimeoutError):
                    error = ModelError(
                        "模型请求超时。", code="timeout", retryable=True, attempts=attempt
                    )
                except httpx.TransportError:
                    error = ModelError(
                        "无法连接模型服务。", code="network", retryable=True, attempts=attempt
                    )
                else:
                    if 200 <= response.status_code < 300:
                        try:
                            result = response.json()
                        except ValueError:
                            raise ModelError(
                                "模型服务返回了无效 JSON。",
                                code="invalid_response",
                                attempts=attempt,
                            ) from None
                        if not isinstance(result, dict):
                            raise ModelError(
                                "模型服务响应结构无效。",
                                code="invalid_response",
                                attempts=attempt,
                            )
                        return result, attempt
                    error = self._http_error(response, attempt)
                if not error.retryable or attempt > self._max_retries:
                    raise error from None
                delay = min(self._retry_delay * 2 ** (attempt - 1), 2.0)
                if response is not None:
                    try:
                        retry_after = float(response.headers.get("Retry-After", "0"))
                        if math.isfinite(retry_after):
                            delay = max(delay, min(max(retry_after, 0), 2.0))
                    except ValueError:
                        pass
                await asyncio.sleep(delay)
        raise ModelError("模型调用未完成。")  # defensive, loop always returns/raises

    async def chat(
        self, messages: list[dict], tools: list[dict] | None = None, json_mode: bool = False
    ) -> dict:
        started = time.perf_counter()
        if not isinstance(messages, list) or not messages:
            raise ModelError("模型消息不能为空。", code="invalid_request", attempts=0)
        sent_messages = list(messages)
        payload: dict[str, Any] = {"model": self.settings.llm_model, "messages": sent_messages}
        if tools:
            payload.update({"tools": tools, "tool_choice": "auto"})
        if json_mode:
            # JSON mode requires a JSON instruction, but does not validate the
            # application's schema or prove that generated facts are true.
            sent_messages.insert(0, {"role": "system", "content": "Return a valid JSON object."})
            payload["response_format"] = {"type": "json_object"}
        body, attempts = await self._post(
            base=self.settings.llm_api_base,
            key=self.settings.llm_api_key,
            route="chat/completions",
            payload=payload,
            timeout=self.settings.llm_timeout,
        )
        try:
            choices = body["choices"]
            if not isinstance(choices, list) or not choices:
                raise ValueError
            choice = choices[0]
            if not isinstance(choice, dict):
                raise ValueError
            message = choice["message"]
            if not isinstance(message, dict):
                raise ValueError
            content = message.get("content") or ""
            tool_calls = message.get("tool_calls") or []
            if not isinstance(content, str) or not isinstance(tool_calls, list):
                raise ValueError
            for call in tool_calls:
                if (
                    not isinstance(call, dict)
                    or not isinstance(call.get("id"), str)
                    or not isinstance(call.get("function"), dict)
                    or not isinstance(call["function"].get("name"), str)
                    or not isinstance(call["function"].get("arguments"), str)
                ):
                    raise ValueError
            if choice.get("finish_reason") == "length":
                raise ModelError("模型输出被截断。", code="truncated", attempts=attempts)
            if choice.get("finish_reason") == "content_filter" or message.get("refusal"):
                raise ModelError("模型服务未生成该内容。", code="refusal", attempts=attempts)
            if not content and not tool_calls:
                raise ModelError("模型返回空内容。", code="empty_response", attempts=attempts)
            usage = body.get("usage") or {}
            if not isinstance(usage, dict):
                raise ValueError
            input_tokens = int(usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0)
            output_tokens = int(usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0)
            if input_tokens < 0 or output_tokens < 0:
                raise ValueError
        except (KeyError, ValueError, TypeError, IndexError, OverflowError):
            raise ModelError(
                "模型服务响应结构无效。", code="invalid_response", attempts=attempts
            ) from None
        return {
            "content": content,
            "tool_calls": tool_calls,
            "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
            "model": body.get("model") or self.settings.llm_model,
            "latency_ms": round((time.perf_counter() - started) * 1000),
            "attempts": attempts,
        }

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not all(isinstance(text, str) and text.strip() for text in texts):
            raise ModelError("向量输入必须是非空文本。", code="invalid_request", attempts=0)
        if not self.settings.embedding_model:
            raise ModelError("Embedding 模型未配置。", code="configuration", attempts=0)
        body, attempts = await self._post(
            base=self.settings.embedding_api_base,
            key=self.settings.embedding_api_key,
            route="embeddings",
            payload={"model": self.settings.embedding_model, "input": texts, "encoding_format": "float"},
            timeout=self.settings.embedding_timeout,
        )
        try:
            data = body["data"]
            if not isinstance(data, list) or len(data) != len(texts):
                raise ValueError
            ordered: list[list[float] | None] = [None] * len(texts)
            dimension: int | None = None
            for item in data:
                index = item["index"]
                vector = item["embedding"]
                if (
                    not isinstance(index, int)
                    or isinstance(index, bool)
                    or not 0 <= index < len(texts)
                    or ordered[index] is not None
                    or not isinstance(vector, list)
                    or not vector
                    or any(not isinstance(v, (int, float)) or isinstance(v, bool) for v in vector)
                ):
                    raise ValueError
                converted = [float(v) for v in vector]
                if not all(math.isfinite(v) for v in converted):
                    raise ValueError
                dimension = dimension or len(converted)
                if len(converted) != dimension or not any(converted):
                    raise ValueError
                ordered[index] = converted
            if any(vector is None for vector in ordered):
                raise ValueError
        except (KeyError, ValueError, TypeError, OverflowError):
            raise ModelError(
                "Embedding 响应结构或向量维度无效。",
                code="invalid_response",
                attempts=attempts,
            ) from None
        return ordered  # type: ignore[return-value]
