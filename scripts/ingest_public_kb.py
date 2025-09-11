import os
import logging
import glob
import hashlib
from elasticsearch import Elasticsearch
from datetime import datetime
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO)

ES = os.getenv("ES_HOST", "http://localhost:9200")
INDEX = os.getenv("ES_PUBLIC_INDEX", "public_medical_kb")
MODEL = os.getenv("EMBEDDINGS_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

es = Elasticsearch(ES)
model = SentenceTransformer(MODEL)

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
    doc = {
        "title": title.title(),
        "section": section,
        "language": "en",
        "jurisdiction": "generic",
        "source_url": source_url,
        "updated_on": datetime.utcnow().isoformat(),
        "text": text,
    }
    vec = model.encode([doc["title"] + "\n" + doc["text"]], normalize_embeddings=True)[
        0
    ].tolist()
    doc["embedding"] = vec
    doc_id = hashlib.sha1((source_url + "|" + section).encode("utf-8")).hexdigest()
    es.index(index=INDEX, id=doc_id, document=doc)
    logging.info(f"Indexed {path}")
