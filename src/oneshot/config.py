import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class Settings:
    PROJECT_NAME: str = "OneShot"
    VERSION: str = "0.1.0"

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///oneshot.db")
    UPLOAD_DIR: Path = Path(os.getenv("UPLOAD_DIR", "uploads"))

    # LLM — LiteRT (on-device) is the only inference path; not env-configurable.
    LLM_PROVIDER: str = "litert"
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.7"))
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "4096"))
    # Read timeout for provider HTTP calls — on-device LiteRT decodes slowly, so
    # shot generation routinely needs minutes; 180s was too short (surfaced as a 502).
    LLM_TIMEOUT_SECONDS: int = int(os.getenv("LLM_TIMEOUT_SECONDS", "600"))
    # Output-token cap for shot-list generation — long shot lists otherwise run past
    # the read timeout on slow local providers.
    SHOT_MAX_TOKENS: int = int(os.getenv("SHOT_MAX_TOKENS", "3072"))

    # Embeddings (for RAG) — LiteRT (on-device) is the only inference path; not env-configurable.
    EMBEDDING_PROVIDER: str = "litert"

    # LiteRT (local) — Gemma 4 E2B via ai-edge-litert; embeddings via the EmbeddingGemma HTTP service
    LITERT_LLM_URL: str = os.getenv("LITERT_LLM_URL", "http://127.0.0.1:8101")
    LITERT_EMBEDDING_URL: str = os.getenv("LITERT_EMBEDDING_URL", "http://127.0.0.1:8100")
    LITERT_LLM_MODEL: str = os.getenv("LITERT_LLM_MODEL", "gemma-4-E2B-it")
    LITERT_EMBEDDING_MODEL: str = os.getenv("LITERT_EMBEDDING_MODEL", "embeddinggemma-300m")

    # EmbeddingGemma 300M via the LiteRT service returns 768 floats.
    EMBEDDING_SIGNATURE: str = f"litert/{LITERT_EMBEDDING_MODEL}"
    EMBEDDING_DIMENSION: int = int(os.getenv("EMBEDDING_DIMENSION", "768"))

    # RAG knowledge store (Phase 6) — Qdrant, local-file mode by default.
    RAG_QDRANT_MODE: str = os.getenv("RAG_QDRANT_MODE", "local")  # "local" | "http"
    RAG_QDRANT_PATH: Path = Path(os.getenv("RAG_QDRANT_PATH", "data/qdrant"))
    RAG_QDRANT_URL: str = os.getenv("RAG_QDRANT_URL", "http://127.0.0.1:6333")
    RAG_COLLECTION: str = os.getenv("RAG_COLLECTION", "oneshot_knowledge")
    # Embedding calls during corpus ingestion; the local LiteRT service serializes requests.
    RAG_EMBED_CONCURRENCY: int = int(os.getenv("RAG_EMBED_CONCURRENCY", "4"))
    # Seed the knowledge collection at startup when it is empty.
    RAG_AUTOSEED: bool = os.getenv("RAG_AUTOSEED", "true").strip().lower() not in {
        "0",
        "false",
        "no",
    }


settings = Settings()
