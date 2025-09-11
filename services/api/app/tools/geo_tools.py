from typing import Dict, Any
from app.config import settings
from app.tools.embeddings import embed


# Very simple provider search using semantic + optional geo bounding box


def search_providers(
    es_client,
    query: str,
    lat: float | None = None,
    lon: float | None = None,
    radius_km: float = 10.0,
) -> list[Dict[str, Any]]:
    es = es_client
    vector = embed([query])[0]
    knn = {
        "field": "embedding",
        "query_vector": vector,
        "k": 10,
        "num_candidates": 50,
    }
    must = []
    if lat is not None and lon is not None:
        must.append(
            {
                "geo_distance": {
                    "distance": f"{radius_km}km",
                    "geo": {"lat": lat, "lon": lon},
                }
            }
        )
    body = {
        "knn": knn,
        "query": {"bool": {"must": must}} if must else {"match_all": {}},
        "_source": {"excludes": ["embedding"]},
        "size": 10,
    }
    res = es.search(index=settings.es_places_index, body=body)
    return [hit["_source"] | {"_score": hit["_score"]} for hit in res["hits"]["hits"]]
