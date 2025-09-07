"""Settings for the API service."""

import os

# Elasticsearch settings
es_host = os.getenv("ES_HOST", "http://localhost:9200")
es_private_index = os.getenv("ES_PRIVATE_INDEX", "private_user_memory")
es_public_index = os.getenv("ES_PUBLIC_INDEX", "public_kb")
es_places_index = os.getenv("ES_PLACES_INDEX", "places")

# Embeddings settings
embeddings_model = os.getenv("EMBEDDINGS_MODEL", "all-MiniLM-L6-v2")
embeddings_device = os.getenv("EMBEDDINGS_DEVICE", "cpu")

# Logging settings
log_level = os.getenv("LOG_LEVEL", "INFO")
log_file = os.getenv("LOG_FILE", "/var/log/body-agent/api.log")
