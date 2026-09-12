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

    # LLM — choose "ollama" (local) or "huggingface" (online) per deployment/development
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "ollama")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gemma4:4b")
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.7"))
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "4096"))

    # Embeddings (for RAG) — choose "ollama" (local) or "huggingface" (online)
    EMBEDDING_PROVIDER: str = os.getenv("EMBEDDING_PROVIDER", "ollama")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
    EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", "768"))

    # Qdrant
    QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")

    # Ollama (local)
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    # Hugging Face (online, development-only)
    HF_TOKEN: str | None = os.getenv("HF_TOKEN")
    HF_BASE_URL: str = os.getenv("HF_BASE_URL", "https://api-inference.huggingface.co")
    HF_LLM_MODEL: str = os.getenv("HF_LLM_MODEL", "google/gemma-4-e4b")
    HF_EMBEDDING_MODEL: str = os.getenv("HF_EMBEDDING_MODEL", "nomic-ai/nomic-embed-text-v1.5")


settings = Settings()
