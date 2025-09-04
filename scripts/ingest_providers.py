import os, json
from elasticsearch import Elasticsearch
from sentence_transformers import SentenceTransformer


ES = os.getenv("ES_HOST", "http://localhost:9200")
INDEX = os.getenv("ES_PLACES_INDEX", "providers_places")
MODEL = os.getenv("EMBEDDINGS_MODEL", "sentence-transformers/all-MiniLM-L6-v2")


es = Elasticsearch(ES)
model = SentenceTransformer(MODEL)


with open("seeds/providers/tel_aviv_providers.json", "r", encoding="utf-8") as f:
    data = json.load(f)


for p in data:
    text = f"{p['name']} {p.get('kind','')} {' '.join(p.get('services', []))} {p.get('hours','')}"
    vec = model.encode([text], normalize_embeddings=True)[0].tolist()
    doc = p | {"embedding": vec}
    es.index(index=INDEX, document=doc)
print("Indexed providers.")
