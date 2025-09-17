import os
import logging
import glob
import hashlib
from datetime import datetime
from typing import Any, List

from elasticsearch import Elasticsearch
from sentence_transformers import SentenceTransformer
from app.config import settings

logging.basicConfig(level=logging.INFO)

ES = os.getenv("ES_HOST", "http://localhost:9200")
INDEX = os.getenv("ES_PUBLIC_INDEX", "public_medical_kb")
MODEL = settings.embeddings_model
VEC_DIMS = 384
es = Elasticsearch(ES)

# init model lazily
_model = None
if MODEL != "__stub__":
    _model = SentenceTransformer(MODEL)


def embed_one(text: str) -> List[float]:
    """Return a single embedding vector (length VEC_DIMS)."""
    if MODEL == "__stub__" or _model is None:
        h = int(hashlib.sha1(text.encode("utf-8")).hexdigest(), 16)
        idx = h % VEC_DIMS
        v = [0.0] * VEC_DIMS
        v[idx] = 1.0
        return v
    return _model.encode([text], normalize_embeddings=True)[0].tolist()


logging.info(
    f"Indexing public medical knowledge base into {INDEX} using model {MODEL}."
)

for path in glob.glob("seeds/public_medical_kb/*.md"):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    title = os.path.basename(path).replace(".md", "").replace("_", " ")
    section = (
        "general"
        if "home" in path
        else (
            "interactions"
            if "warfarin" in path
            else "warnings" if "ibuprofen" in path else "general"
        )
    )
    source_url = f"file://{path}"

    doc: dict[str, Any] = {
        "title": title.title(),
        "section": section,
        "language": "en",
        "jurisdiction": "generic",
        "source_url": source_url,
        "updated_on": datetime.utcnow().isoformat(),
        "text": text,
    }

    vec = embed_one(doc["title"] + "\n" + doc["text"])  # <-- FLAT LIST
    # Guardrail to fail fast if shape is wrong
    assert (
        isinstance(vec, list)
        and len(vec) == VEC_DIMS
        and isinstance(vec[0], (int, float))
    ), f"Bad embedding shape/type: {type(vec)} len={getattr(vec, '__len__', None)}"

    doc["embedding"] = vec
    doc_id = hashlib.sha1((source_url + "|" + section).encode("utf-8")).hexdigest()
    es.index(index=INDEX, id=doc_id, document=doc)
    logging.info(f"Indexed {path}")

logging.info("Done indexing public medical knowledge base.")
