"""Opt-in check that the patched embedding stack preserves the pinned baseline."""

import json
import os
from pathlib import Path

import pytest


@pytest.mark.skipif(
    os.getenv("LANGCONFIG_TEST_EMBEDDINGS") != "1",
    reason="Opt-in CPU model check; downloads the pinned MiniLM revision if absent",
)
def test_pinned_minilm_direct_and_llamaindex_match_preserved_baseline():
    import numpy as np
    from llama_index.embeddings.huggingface import HuggingFaceEmbedding
    from sentence_transformers import SentenceTransformer

    fixture = json.loads(
        (Path(__file__).parent / "fixtures/minilm_embedding_baseline.json").read_text()
    )
    baseline = np.asarray(fixture["vectors"])
    cache = os.getenv("LANGCONFIG_EMBEDDING_CACHE")
    model = SentenceTransformer(
        fixture["model"], revision=fixture["revision"], device="cpu", cache_folder=cache,
    )
    actual = model.encode(
        fixture["texts"], normalize_embeddings=True, show_progress_bar=False,
    )
    adapter = HuggingFaceEmbedding(
        model_name=fixture["model"], revision=fixture["revision"], device="cpu",
        normalize=True, cache_folder=cache,
    )
    adapted = np.asarray(adapter.get_text_embedding_batch(fixture["texts"]))
    assert actual.shape == adapted.shape == baseline.shape == (4, 384)
    np.testing.assert_allclose(actual, baseline, rtol=0, atol=fixture["absolute_tolerance"])
    np.testing.assert_allclose(adapted, baseline, rtol=0, atol=fixture["absolute_tolerance"])
