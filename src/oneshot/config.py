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

    # LLM — choose "gemini" (online, default), "ollama" (local), or "huggingface" (online).
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "gemini")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gemma4:4b")
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.7"))
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "4096"))

    # Embeddings (for RAG) — choose "gemini" (online, default), "ollama" (local), or "huggingface" (online)
    EMBEDDING_PROVIDER: str = os.getenv("EMBEDDING_PROVIDER", "gemini")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")

    # Ollama (local)
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    # Gemini (online, default provider)
    GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemma-4-26b-a4b-it")
    GEMINI_EMBEDDING_MODEL: str = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-2")

    # Hugging Face (online, development-only; Inference Providers router)
    HF_TOKEN: str | None = os.getenv("HF_TOKEN")
    HF_BASE_URL: str = os.getenv("HF_BASE_URL", "https://router.huggingface.co")
    HF_LLM_MODEL: str = os.getenv("HF_LLM_MODEL", "google/gemma-3-4b-it")
    HF_EMBEDDING_MODEL: str = os.getenv("HF_EMBEDDING_MODEL", "BAAI/bge-base-en-v1.5")


settings = Settings()
