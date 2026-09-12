import os


class Settings:
    PROJECT_NAME: str = "OneShot"
    VERSION: str = "0.1.0"

    # LLM
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "ollama")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gemma4:4b")

    # Embeddings (for RAG)
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
    EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", "768"))

    # Qdrant
    QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")

    # Ollama
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


settings = Settings()
