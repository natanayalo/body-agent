import os
import logging
import json
import re
import hashlib
from elasticsearch import Elasticsearch, helpers
from sentence_transformers import SentenceTransformer
from app.config import settings


logging.basicConfig(level=logging.INFO)

ES = os.getenv("ES_HOST", "http://localhost:9200")
INDEX = os.getenv("ES_PLACES_INDEX", "providers_places")
MODEL = settings.embeddings_model
VEC_DIMS = 384
es = Elasticsearch(ES)

# Init model only if needed
_model = None
if MODEL != "__stub__":
    _model = SentenceTransformer(MODEL)


def embed_one(text: str) -> list[float]:
    if MODEL == "__stub__" or _model is None:
        h = int(hashlib.sha1(text.encode("utf-8")).hexdigest(), 16)
        idx = h % VEC_DIMS
        v = [0.0] * VEC_DIMS
        v[idx] = 1.0
        return v
    return _model.encode([text], normalize_embeddings=True)[0].tolist()


with open("seeds/providers/tel_aviv_providers.json", "r", encoding="utf-8") as f:
    data = json.load(f)

logging.info("Indexing %d providers into %s using model %s.", len(data), INDEX, MODEL)

actions = []
for p in data:
    text = f"{p['name']} {p.get('kind','')} {' '.join(p.get('services', []))} {p.get('hours','')}"
    vec = embed_one(text)  # <-- FLAT VECTOR
    assert isinstance(vec, list) and all(
        isinstance(x, (int, float)) for x in vec
    ), f"Bad embedding shape: {type(vec)}"

    doc = p | {"embedding": vec}
    slug = re.sub(r"[^a-z0-9]+", "-", p["name"].lower()).strip("-")
    geokey = f"{p.get('geo',{}).get('lat','')},{p.get('geo',{}).get('lon','')}"
    doc_id = hashlib.sha1(f"{slug}|{geokey}".encode("utf-8")).hexdigest()

    actions.append(
        {
            "_op_type": "update",
            "_index": INDEX,
            "_id": doc_id,
            "doc": doc,
            "doc_as_upsert": True,
        }
    )

helpers.bulk(es, actions)
logging.info("Upserted %d providers into %s", len(actions), INDEX)
