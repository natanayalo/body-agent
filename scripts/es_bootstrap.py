import os
from elasticsearch import Elasticsearch


ES = os.getenv("ES_HOST", "http://localhost:9200")
es = Elasticsearch(ES)


for idx in [
    os.getenv("ES_PRIVATE_INDEX", "private_user_memory"),
    os.getenv("ES_PUBLIC_INDEX", "public_medical_kb"),
    os.getenv("ES_PLACES_INDEX", "providers_places"),
]:
    if not es.indices.exists(index=idx):
        print(f"Index missing: {idx}. Start the API once to auto-create mappings.")
    else:
        print(f"OK {idx}")
