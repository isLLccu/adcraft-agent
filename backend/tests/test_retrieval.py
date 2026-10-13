"""Offline ranking, evidence scope, chunking, and real-vector integration tests."""

import asyncio
from types import SimpleNamespace

import pytest

from app.ai.provider import ModelError
from app.ai.retrieval import Retriever, chunk_documents, tokenize


def settings(**overrides):
    values = dict(
        mode="demo", embedding_api_base="", embedding_api_key="", embedding_model="",
        top_k=3, chunk_size=120, chunk_overlap=20,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def doc(identifier, text, brand="a", **overrides):
    values = {"id": identifier, "content": text, "title": identifier, "brand_id": brand, "source": "manual", "version": "1"}
    values.update(overrides)
    return values


class NoEmbedding:
    async def embed(self, texts):
        pytest.fail("Lexical and demo retrieval must not call embedding APIs")


class FakeEmbedding:
    def __init__(self):
        self.calls = []

    async def embed(self, texts):
        self.calls.append(list(texts))
        # The test manually labels these vectors. Production uses API output;
        # this fake is not exported as a semantic retrieval implementation.
        return [[1.0, 0.01] if ("warm" in text or "保温" in text) else [0.01, 1.0] for text in texts]


def test_tokenizer_normalizes_cjk_bigrams_and_english():
    assert tokenize("品牌语气 Cup ４００ml") == ["品牌", "牌语", "语气", "cup", "400ml"]
    assert tokenize("红") == ["红"]


def test_chunking_is_bounded_overlapping_and_metadata_preserved():
    text = "甲乙丙丁戊己庚辛壬癸" * 8
    chunks = chunk_documents([doc("d1", text, version="2")], 25, 5)
    assert all(len(chunk["text"]) <= 25 for chunk in chunks)
    assert chunks[0]["text"][-5:] == chunks[1]["text"][:5]
    assert chunks[-1]["text"].endswith(text[-5:])
    assert chunks[0]["source"] == "manual"
    assert chunks[0]["version"] == "2"
    assert chunk_documents([doc("d1", text, version="2")], 25, 5)[0]["id"] == chunks[0]["id"]
    assert chunk_documents([doc("d1", text + "新", version="2")], 25, 5)[0]["id"] != chunks[0]["id"]


@pytest.mark.parametrize("size,overlap", [(1, 0), (20, -1), (20, 20), (20, 21)])
def test_invalid_chunk_configuration_cannot_loop_forever(size, overlap):
    with pytest.raises(ValueError):
        chunk_documents([doc("d", "内容")], size, overlap)


def test_bm25_matches_chinese_and_excludes_other_brand_before_ranking():
    documents = [
        doc("relevant", "品牌文案使用温和语气，避免夸张承诺。"),
        doc("irrelevant", "配送范围支持大陆地区。"),
        doc("outside", "温和语气 温和语气 温和语气", brand="b"),
    ]
    result = asyncio.run(Retriever(settings(), NoEmbedding()).search(documents, "温和语气", "a"))
    assert [item["document_id"] for item in result] == ["relevant"]
    assert result[0]["score"] > 0
    assert "brand_id" not in result[0]
    assert set(result[0]) == {"id", "document_id", "title", "text", "score", "source", "version", "chunk_index"}


def test_no_lexical_match_returns_no_fabricated_evidence():
    retriever = Retriever(settings(), NoEmbedding())
    assert asyncio.run(retriever.search([doc("d", "配送说明")], "机器人", "a")) == []
    assert asyncio.run(retriever.search([doc("d", "配送说明")], " ", "a")) == []


def test_demo_ignores_embedding_configuration_and_top_k_zero():
    retriever = Retriever(settings(embedding_api_base="https://fake", embedding_api_key="secret", embedding_model="real"), NoEmbedding())
    assert not retriever.embedding_enabled
    assert asyncio.run(retriever.search([doc("d", "品牌语气")], "品牌", "a", 0)) == []


def test_hybrid_rrf_combines_rankings_and_filters_before_embedding():
    client = FakeEmbedding()
    retriever = Retriever(settings(mode="live", embedding_api_base="https://fake", embedding_api_key="secret", embedding_model="real"), client)
    documents = [doc("semantic", "保持饮品温度，保温杯。"), doc("lexical", "warm 的英语文案要求。"), doc("outside", "outside-secret warm", brand="b")]
    result = asyncio.run(retriever.search(documents, "warm", "a", 2))
    assert retriever.last_mode == "hybrid"
    assert result[0]["document_id"] == "lexical"  # both lexical + semantic support
    assert {item["document_id"] for item in result} == {"lexical", "semantic"}
    assert result[0]["score"] > result[1]["score"]
    assert all("outside-secret" not in text for call in client.calls for text in call)


def test_embeddings_cache_invalidates_on_content_model_and_endpoint():
    async def exercise():
        client = FakeEmbedding()
        config = settings(mode="live", embedding_api_base="https://fake", embedding_api_key="secret", embedding_model="real")
        retriever = Retriever(config, client)
        documents = [doc("d", "保温温度")]
        await retriever.search(documents, "warm", "a")
        assert len(client.calls) == 1
        await retriever.search(documents, "warm", "a")
        assert len(client.calls) == 1
        documents[0]["content"] = "保温温度新版"
        await retriever.search(documents, "warm", "a")
        assert len(client.calls) == 2
        assert client.calls[-1] == ["d\n保温温度新版"]
        config.embedding_model = "other"
        await retriever.search(documents, "warm", "a")
        assert len(client.calls) == 3
        config.embedding_api_base = "https://other"
        await retriever.search(documents, "warm", "a")
        assert len(client.calls) == 4

    asyncio.run(exercise())


def test_concurrent_identical_searches_share_cached_embeddings():
    async def exercise():
        client = FakeEmbedding()
        retriever = Retriever(settings(mode="live", embedding_api_base="https://fake", embedding_api_key="secret", embedding_model="real"), client)
        results = await asyncio.gather(*(retriever.search([doc("d", "保温说明")], "warm", "a") for _ in range(4)))
        assert len(client.calls) == 1
        assert results[0] == results[3]

    asyncio.run(exercise())


def test_embedding_failure_is_explicit_instead_of_silent_fake_hybrid():
    class FailedEmbedding:
        async def embed(self, texts):
            raise ModelError("Embedding service unavailable", code="upstream_unavailable")

    retriever = Retriever(settings(mode="live", embedding_api_base="https://fake", embedding_api_key="secret", embedding_model="real"), FailedEmbedding())
    with pytest.raises(ModelError) as captured:
        asyncio.run(retriever.search([doc("d", "品牌语气")], "品牌", "a"))
    assert captured.value.code == "upstream_unavailable"


def test_lru_bound_does_not_drop_vectors_needed_for_current_result():
    async def exercise():
        retriever = Retriever(settings(mode="live", embedding_api_base="https://fake", embedding_api_key="secret", embedding_model="real"), FakeEmbedding())
        retriever._cache_capacity = 1
        result = await retriever.search([doc("d1", "保温内容"), doc("d2", "配送内容")], "warm", "a")
        assert len(result) == 2
        assert len(retriever._embedding_cache) == 1

    asyncio.run(exercise())
