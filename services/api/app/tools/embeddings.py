from __future__ import annotations

import os
import hashlib
from typing import Callable, List, Sequence, Union
import numpy as np

# Public constants
VEC_DIMS: int = 384

# Config
MODEL = os.getenv("EMBEDDINGS_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
DEVICE = os.getenv("EMBEDDINGS_DEVICE", "cpu")


def _one_hot(text: str, dims: int = VEC_DIMS) -> List[float]:
    """Deterministic non-zero stub vector for cosine similarity."""
    h = int(hashlib.sha1(text.encode("utf-8")).hexdigest(), 16)
    idx = h % dims
    v = [0.0] * dims
    v[idx] = 1.0
    return v


# Choose backend once, without redefining the public 'embed' symbol
_embed_impl: Callable[[Sequence[str]], List[List[float]]]

if MODEL == "__stub__":

    def _embed_stub(texts: Sequence[str]) -> List[List[float]]:
        return [_one_hot(t) for t in texts]

    _embed_impl = _embed_stub
else:
    try:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(MODEL, device=DEVICE)

        def _embed_real(texts: Sequence[str]) -> List[List[float]]:
            embeddings = _model.encode(list(texts), normalize_embeddings=True)
            return np.asarray(embeddings).tolist()

        _embed_impl = _embed_real
    except Exception:
        # Safe fallback: if model load fails in dev/CI, use stub
        def _embed_stub_fallback(texts: Sequence[str]) -> List[List[float]]:
            return [_one_hot(t) for t in texts]

        _embed_impl = _embed_stub_fallback


def embed(texts: Union[str, Sequence[str]]) -> List[List[float]]:
    """Public embedding API: returns List[List[float]] for str or Sequence[str]."""
    if isinstance(texts, str):
        texts = [texts]
    return _embed_impl(texts)


__all__ = ["embed", "VEC_DIMS"]
