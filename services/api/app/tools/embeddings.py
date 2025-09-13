import numpy as np
from sentence_transformers import SentenceTransformer
from app.config import settings

# Define a fixed dimension for stub embeddings
VEC_DIMS = 384

if settings.embeddings_model == "__stub__":

    def embed(texts: list[str]) -> list[list[float]]:
        if isinstance(texts, str):
            texts = [texts]
        return [[0.0] * VEC_DIMS for _ in texts]  # deterministic small vector

else:
    _model = SentenceTransformer(
        settings.embeddings_model, device=settings.embeddings_device
    )

    def embed(texts: list[str]) -> list[list[float]]:
        if isinstance(texts, str):
            texts = [texts]
        embeddings = _model.encode(texts, normalize_embeddings=True)
        return np.asarray(embeddings).tolist()
