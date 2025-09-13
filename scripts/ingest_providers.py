import os
import logging
import json
import re
import hashlib
from elasticsearch import Elasticsearch
from sentence_transformers import SentenceTransformer
from app.config import settings


logging.basicConfig(level=logging.INFO)

ES = os.getenv("ES_HOST", "http://localhost:9200")
INDEX = os.getenv("ES_PLACES_INDEX", "providers_places")
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


with open("seeds/providers/tel_aviv_providers.json", "r", encoding="utf-8") as f:
    data = json.load(f)

logging.info(f"Indexing {len(data)} providers into {INDEX} using model {MODEL}.")
for p in data:
    text = f"{p['name']} {p.get('kind','')} {' '.join(p.get('services', []))} {p.get('hours','')}"
    vec = get_embedding([text])
    doc = p | {"embedding": vec}
    slug = re.sub(r"[^a-z0-9]+", "-", p["name"].lower()).strip("-")
    geokey = f"{p.get('geo',{}).get('lat','')},{p.get('geo',{}).get('lon','')}"
    doc_id = hashlib.sha1(f"{slug}|{geokey}".encode("utf-8")).hexdigest()
    es.index(index=INDEX, id=doc_id, document=doc)
logging.info("Done indexing providers.")
