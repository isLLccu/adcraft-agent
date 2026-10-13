"""Inspectable RAG retrieval: character chunking, BM25, optional API vectors.

Chinese lexical tokens are adjacent character bigrams (a single character for
one-character runs); English/numeric tokens are words. This is a pragmatic
lexical baseline, not a Chinese word segmenter or a semantic embedding model.
Hybrid mode uses actual embedding API output plus reciprocal rank fusion.
"""

from __future__ import annotations

import asyncio
import hashlib
import math
import re
import unicodedata
from collections import Counter, OrderedDict
from typing import TYPE_CHECKING

from .provider import ModelError

if TYPE_CHECKING:
    from .config import AISettings
    from .provider import ModelClient


def tokenize(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    runs = re.findall(r"[\u3400-\u9fff]+|[a-z0-9]+(?:[._-][a-z0-9]+)*", normalized)
    result: list[str] = []
    for run in runs:
        if "\u3400" <= run[0] <= "\u9fff":
            result.extend([run] if len(run) == 1 else [run[i:i + 2] for i in range(len(run) - 1)])
        else:
            result.append(run)
    return result


def chunk_documents(documents: list[dict], chunk_size: int, chunk_overlap: int) -> list[dict]:
    """Split by Unicode characters, preferring a nearby paragraph/sentence end.

    Metadata and original content remain attached to each stable chunk ID.
    Overlap must be smaller than size, guaranteeing progress for long texts.
    """
    if chunk_size < 2 or chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_size 必须至少为 2，且 0 <= chunk_overlap < chunk_size。")
    chunks: list[dict] = []
    for document in documents:
        content = str(document.get("content") or "").strip()
        if not content:
            continue
        document_id = str(document["id"])
        version = str(document.get("version", "1"))
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:10]
        start = 0
        index = 0
        while start < len(content):
            end = min(start + chunk_size, len(content))
            if end < len(content):
                lower = start + max(chunk_size // 2, chunk_overlap + 1)
                boundary = max(content.rfind(mark, lower, end) for mark in ("\n", "。", "！", "？", ";"))
                if boundary >= lower:
                    end = boundary + 1
            text = content[start:end].strip()
            if text:
                chunks.append({
                    "id": f"{document_id}:{version}:{index}:{digest}",
                    "document_id": document_id,
                    "title": str(document.get("title", "Untitled")),
                    "text": text,
                    "score": 0.0,
                    "source": str(document.get("source", "manual")),
                    "version": document.get("version", "1"),
                    "chunk_index": index,
                    "brand_id": str(document.get("brand_id", "")),
                })
                index += 1
            if end == len(content):
                break
            start = end - chunk_overlap
    return chunks


def _bm25(chunks: list[dict], query: str) -> dict[str, float]:
    """Okapi BM25, k1=1.5 and b=0.75, with nonnegative Robertson IDF."""
    query_terms = set(tokenize(query))
    if not query_terms or not chunks:
        return {}
    # Title participates in retrieval but evidence.text remains the source body.
    term_counts = [Counter(tokenize(f"{chunk['title']}\n{chunk['text']}")) for chunk in chunks]
    lengths = [sum(counts.values()) for counts in term_counts]
    average_length = sum(lengths) / len(lengths) or 1.0
    document_frequency = Counter(term for counts in term_counts for term in counts)
    scores: dict[str, float] = {}
    k1, b, n = 1.5, 0.75, len(chunks)
    for chunk, counts, length in zip(chunks, term_counts, lengths):
        score = 0.0
        for term in query_terms:
            frequency = counts.get(term, 0)
            if not frequency:
                continue
            df = document_frequency[term]
            idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
            score += idf * frequency * (k1 + 1) / (
                frequency + k1 * (1 - b + b * length / average_length)
            )
        if score > 0:
            scores[chunk["id"]] = score
    return scores


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        raise ModelError("Embedding 向量维度不一致。", code="invalid_response")
    denominator = math.sqrt(sum(value * value for value in left)) * math.sqrt(
        sum(value * value for value in right)
    )
    if not denominator or not math.isfinite(denominator):
        raise ModelError("Embedding 向量数值无效。", code="invalid_response")
    return sum(a * b for a, b in zip(left, right)) / denominator


class Retriever:
    def __init__(self, settings: AISettings, client: ModelClient) -> None:
        self.settings = settings
        self.client = client
        self._embedding_cache: OrderedDict[tuple[str, str, str], list[float]] = OrderedDict()
        self._cache_lock = asyncio.Lock()
        self._cache_capacity = 4096
        self.last_mode = "lexical"

    @property
    def embedding_enabled(self) -> bool:
        return bool(
            self.settings.mode == "live"
            and self.settings.embedding_api_base
            and self.settings.embedding_api_key
            and self.settings.embedding_model
        )

    def _cache_key(self, text: str) -> tuple[str, str, str]:
        return (
            str(self.settings.embedding_api_base).rstrip("/"),
            str(self.settings.embedding_model),
            hashlib.sha256(text.encode("utf-8")).hexdigest(),
        )

    async def _vectors(self, texts: list[str]) -> list[list[float]]:
        # A shared retriever keeps a bounded LRU cache across searches. The lock
        # prevents concurrent identical misses from causing duplicate API calls.
        keys = [self._cache_key(text) for text in texts]
        async with self._cache_lock:
            missing: dict[tuple[str, str, str], str] = {}
            for key, text in zip(keys, texts):
                if key not in self._embedding_cache:
                    missing[key] = text
            newly_received: dict[tuple[str, str, str], list[float]] = {}
            missing_items = list(missing.items())
            for offset in range(0, len(missing_items), 64):
                batch = missing_items[offset:offset + 64]
                vectors = await self.client.embed([text for _, text in batch])
                if len(vectors) != len(batch):
                    raise ModelError("Embedding 数量与输入不符。", code="invalid_response")
                for (key, _), vector in zip(batch, vectors):
                    if not vector or not all(math.isfinite(value) for value in vector) or not any(vector):
                        raise ModelError("Embedding 向量数值无效。", code="invalid_response")
                    newly_received[key] = vector
            # Keep local vectors too: a corpus larger than cache_capacity must
            # still produce a complete result after older entries are evicted.
            available = dict(self._embedding_cache)
            available.update(newly_received)
            result = [available[key] for key in keys]
            if len({len(vector) for vector in result}) != 1:
                raise ModelError("Embedding 向量维度不一致。", code="invalid_response")
            self._embedding_cache.update(newly_received)
            for key in keys:
                if key in self._embedding_cache:
                    self._embedding_cache.move_to_end(key)
            while len(self._embedding_cache) > self._cache_capacity:
                self._embedding_cache.popitem(last=False)
            return result

    async def search(
        self, documents: list[dict], query: str, brand_id: str, top_k: int | None = None
    ) -> list[dict]:
        self.last_mode = "hybrid" if self.embedding_enabled else "lexical"
        if not query.strip():
            return []
        # Apply scope before BOTH lexical scoring and embedding API calls.
        scoped = [document for document in documents if str(document.get("brand_id", "")) == str(brand_id)]
        chunks = chunk_documents(scoped, self.settings.chunk_size, self.settings.chunk_overlap)
        if not chunks:
            return []
        limit = min(max(int(top_k if top_k is not None else self.settings.top_k), 0), 50)
        if limit == 0:
            return []
        scores = _bm25(chunks, query)
        lexical = sorted(scores, key=lambda chunk_id: (-scores[chunk_id], chunk_id))
        if self.embedding_enabled:
            # Do not fabricate vectors or silently call lexical results hybrid
            # when the configured embedding API fails: surface the safe error.
            vectors = await self._vectors([query] + [f"{chunk['title']}\n{chunk['text']}" for chunk in chunks])
            semantic_scores = {
                chunk["id"]: _cosine(vectors[0], vector)
                for chunk, vector in zip(chunks, vectors[1:])
            }
            semantic = sorted(semantic_scores, key=lambda chunk_id: (-semantic_scores[chunk_id], chunk_id))
            fused: dict[str, float] = {}
            # Rank fusion avoids treating BM25 and cosine as comparable scales.
            # Use candidate lists of at most 50 to avoid rewarding every chunk.
            for ranked in (lexical[:50], semantic[:50]):
                for rank, chunk_id in enumerate(ranked, start=1):
                    fused[chunk_id] = fused.get(chunk_id, 0.0) + 1 / (60 + rank)
            scores = fused
        ranked = sorted(scores, key=lambda chunk_id: (-scores[chunk_id], chunk_id))[:limit]
        by_id = {chunk["id"]: chunk for chunk in chunks}
        return [
            {**{key: value for key, value in by_id[chunk_id].items() if key != "brand_id"}, "score": round(scores[chunk_id], 8)}
            for chunk_id in ranked
        ]
