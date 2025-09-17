from app.tools.embeddings import embed
from unittest.mock import patch


def test_embed_list_of_strings():
    texts = ["hello world", "how are you"]
    embeddings = embed(texts)
    assert isinstance(embeddings, list)
    assert len(embeddings) == 2
    assert isinstance(embeddings[0], list)
    assert isinstance(embeddings[0][0], float)


def test_embed_single_string():
    text = "hello world"
    embeddings = embed([text])
    assert isinstance(embeddings, list)
    assert len(embeddings) == 1
    assert isinstance(embeddings[0], list)
    assert isinstance(embeddings[0][0], float)


def test_embed_single_string_input():
    text = "hello world"
    embeddings = embed(text)  # Pass string directly
    assert isinstance(embeddings, list)
    assert len(embeddings) == 1
    assert isinstance(embeddings[0], list)
    assert isinstance(embeddings[0][0], float)


def test_embed_stub_mode(monkeypatch):
    monkeypatch.setenv("EMBEDDINGS_MODEL", "__stub__")
    # Reload the module to apply the new environment variable
    import importlib
    import app.tools.embeddings

    importlib.reload(app.tools.embeddings)
    from app.tools.embeddings import embed, VEC_DIMS

    texts = ["test text 1", "test text 2"]
    embeddings = embed(texts)

    assert isinstance(embeddings, list)
    assert len(embeddings) == len(texts)
    for emb in embeddings:
        assert isinstance(emb, list)
        assert len(emb) == VEC_DIMS
        # In stub mode, _one_hot creates a vector with one 1.0 and rest 0.0
        assert sum(emb) == 1.0
        assert emb.count(0.0) == VEC_DIMS - 1
        assert emb.count(1.0) == 1


def test_embed_fallback_mode(monkeypatch):
    monkeypatch.setenv("EMBEDDINGS_MODEL", "non_existent_model")
    # Mock SentenceTransformer to raise an exception during initialization
    with patch("app.tools.embeddings.SentenceTransformer") as mock_st:
        mock_st.side_effect = Exception("Failed to load model")

        # Reload the module to apply the mock and environment variable
        import importlib
        import app.tools.embeddings

        importlib.reload(app.tools.embeddings)
        from app.tools.embeddings import embed, VEC_DIMS

        texts = ["fallback test 1", "fallback test 2"]
        embeddings = embed(texts)

        assert isinstance(embeddings, list)
        assert len(embeddings) == len(texts)
        for emb in embeddings:
            assert isinstance(emb, list)
            assert len(emb) == VEC_DIMS
            # In fallback mode, _one_hot creates a vector with one 1.0 and rest 0.0
            assert sum(emb) == 1.0
            assert emb.count(0.0) == VEC_DIMS - 1
            assert emb.count(1.0) == 1
