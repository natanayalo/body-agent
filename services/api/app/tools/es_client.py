from elasticsearch import Elasticsearch
from app.config import settings


es = Elasticsearch(settings.es_host)


def ensure_indices():
    # Called on startup by the API to ensure mappings exist
    from elasticsearch.exceptions import NotFoundError
    indices = es.indices


    def create_index(name: str, mapping: dict):
        if not indices.exists(index=name):
            indices.create(index=name, mappings=mapping)


    vec_dims = 384 # all-MiniLM-L6-v2


    private_mapping = {
    "properties": {
    "user_id": {"type": "keyword"},
    "entity": {"type": "keyword"},
    "name": {"type": "text"},
    "value": {"type": "text"},
    "normalized": {"type": "object", "enabled": True},
    "confidence": {"type": "float"},
    "ttl_days": {"type": "integer"},
    "updated_at": {"type": "date"},
    "embedding": {"type": "dense_vector", "dims": vec_dims, "index": True, "similarity": "cosine"}
    }
    }


    public_mapping = {
    "properties": {
    "title": {"type": "text"},
    "section": {"type": "keyword"},
    "language": {"type": "keyword"},
    "jurisdiction": {"type": "keyword"},
    "source_url": {"type": "keyword"},
    "updated_on": {"type": "date"},
    "text": {"type": "text"},
    "embedding": {"type": "dense_vector", "dims": vec_dims, "index": True, "similarity": "cosine"}
    }
    }


    places_mapping = {
    "properties": {
    "name": {"type": "text"},
    "kind": {"type": "keyword"},
    "services": {"type": "keyword"},
    "geo": {"type": "geo_point"},
    "hours": {"type": "text"},
    "book_url": {"type": "keyword"},
    "phone": {"type": "keyword"},
    "text": {"type": "text"},
    "embedding": {"type": "dense_vector", "dims": vec_dims, "index": True, "similarity": "cosine"}
    }
    }


    create_index(settings.es_private_index, private_mapping)
    create_index(settings.es_public_index, public_mapping)
    create_index(settings.es_places_index, places_mapping)