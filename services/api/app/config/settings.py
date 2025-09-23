"""Settings for the API service."""

from pydantic import BaseModel
import os

_SYMPTOM_REGISTRY_DEFAULT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "registry", "symptoms.yml")
)


class Settings(BaseModel):
    app_env: str = os.getenv("APP_ENV", "dev")
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", 8000))

    es_host: str = os.getenv("ES_HOST", "http://localhost:9200")
    es_private_index: str = os.getenv("ES_PRIVATE_INDEX", "private_user_memory")
    es_public_index: str = os.getenv("ES_PUBLIC_INDEX", "public_medical_kb")
    es_places_index: str = os.getenv("ES_PLACES_INDEX", "providers_places")

    embeddings_model: str = os.getenv(
        "EMBEDDINGS_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
    )
    embeddings_device: str = os.getenv("EMBEDDINGS_DEVICE", "cpu")

    llm_provider: str = os.getenv("LLM_PROVIDER", "none")

    data_dir: str = os.getenv("APP_DATA_DIR", "/app/data")

    # Logging settings
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    log_file: str = os.getenv("LOG_FILE", "/var/log/body-agent/api.log")

    symptom_registry_path: str = os.getenv(
        "SYMPTOM_REGISTRY_PATH", _SYMPTOM_REGISTRY_DEFAULT
    )
