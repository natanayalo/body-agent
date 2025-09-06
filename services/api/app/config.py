from pydantic import BaseModel
import os


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
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")


settings = Settings()
