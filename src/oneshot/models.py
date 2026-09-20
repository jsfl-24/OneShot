"""Model definitions for the AI/RAG layer.

This module defines:
- Which LLM to use for shot generation
- Which embedding model to use for RAG
- Model parameters and abstraction interfaces
"""

import os
from enum import Enum

from pydantic import BaseModel


class Provider(str, Enum):
    GEMINI = "gemini"
    OLLAMA = "ollama"
    HUGGINGFACE = "huggingface"


class LLMConfig(BaseModel):
    provider: Provider = Provider(os.getenv("LLM_PROVIDER", "gemini"))
    model: str = os.getenv("LLM_MODEL", "gemma4:4b")
    temperature: float = 0.7
    max_tokens: int = 4096


class EmbeddingConfig(BaseModel):
    provider: Provider = Provider(os.getenv("EMBEDDING_PROVIDER", "gemini"))
    model: str = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")


llm_config = LLMConfig()
embedding_config = EmbeddingConfig()
