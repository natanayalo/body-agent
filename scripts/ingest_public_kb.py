import os
import logging
import glob
import hashlib
from elasticsearch import Elasticsearch
from datetime import datetime
from sentence_transformers import SentenceTransformer
from app.config import settings


from typing import Any


logging.basicConfig(level=logging.INFO)

ES = os.getenv("ES_HOST", "http://localhost:9200")
INDEX = os.getenv("ES_PUBLIC_INDEX", "public_medical_kb")
MODEL = settings.embeddings_model
VEC_DIMS = 384
es = Elasticsearch(ES)

if MODEL == "__stub__":

    def get_embedding(texts: list[str]) -> list[list[float]]:
        if isinstance(texts, str):
            texts = [texts]
        return [[0.0] * VEC_DIMS for _ in texts]  # deterministic small vector

else:
    model = SentenceTransformer(MODEL)

    def get_embedding(texts: list[str]) -> list[list[float]]:
        return model.encode(texts, normalize_embeddings=True)[0].tolist()


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
    vec = get_embedding([doc["title"] + "\n" + doc["text"]])[0]
    doc["embedding"] = vec
    doc_id = hashlib.sha1((source_url + "|" + section).encode("utf-8")).hexdigest()
    es.index(index=INDEX, id=doc_id, document=doc)
    logging.info(f"Indexed {path}")
logging.info("Done indexing public medical knowledge base.")
