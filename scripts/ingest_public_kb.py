import os, glob
from elasticsearch import Elasticsearch
from datetime import datetime
from sentence_transformers import SentenceTransformer


ES = os.getenv("ES_HOST", "http://localhost:9200")
INDEX = os.getenv("ES_PUBLIC_INDEX", "public_medical_kb")
MODEL = os.getenv("EMBEDDINGS_MODEL", "sentence-transformers/all-MiniLM-L6-v2")


es = Elasticsearch(ES)
model = SentenceTransformer(MODEL)


for path in glob.glob("seeds/public_medical_kb/*.md"):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    title = os.path.basename(path).replace(".md", "").replace("_", " ")
    doc = {
        "title": title.title(),
        "section": "general" if "home" in path else ("interactions" if "warfarin" in path else "warnings" if "ibuprofen" in path else "general"),
        "language": "en",
        "jurisdiction": "generic",
        "source_url": f"file://{path}",
        "updated_on": datetime.utcnow().isoformat(),
        "text": text,
    }
    vec = model.encode([doc["title"] + "\n" + doc["text"]], normalize_embeddings=True)[0].tolist()
    doc["embedding"] = vec
    es.index(index=INDEX, document=doc)
    print("Indexed", path)
