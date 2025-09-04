from sentence_transformers import SentenceTransformer
from app.config import settings


_model = SentenceTransformer(settings.embeddings_model, device=settings.embeddings_device)


def embed(texts: list[str]) -> list[list[float]]:
    if isinstance(texts, str):
        texts = [texts]
    return _model.encode(texts, normalize_embeddings=True).tolist()