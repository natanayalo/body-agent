from app.tools.embeddings import embed


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
