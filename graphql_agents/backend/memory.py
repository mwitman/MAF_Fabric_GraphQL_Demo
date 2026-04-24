"""Mem0 memory layer — persists conversation context across sessions.

Uses Azure OpenAI for both the LLM (memory extraction) and the embedder.
Qdrant runs in-memory by default; swap to a file path or remote URL for
persistence across restarts.

Required env vars (loaded from graphql_agents/.env):
    AOAI_ENDPOINT                  — Azure OpenAI endpoint
    AOAI_KEY                       — Azure OpenAI API key
    AZURE_OPENAI_DEPLOYMENT_NAME   — LLM deployment (e.g. gpt-5.4)
    AOAI_EMBEDDING_DEPLOYMENT_NAME — Embedding deployment (e.g. text-embedding-3-small)
    AOAI_EMBEDDING_API_VERSION     — Embedding API version (e.g. 2024-06-01)
"""

import logging
import os

from mem0 import Memory

logger = logging.getLogger(__name__)


def _build_config() -> dict:
    endpoint = os.environ["AOAI_ENDPOINT"]
    api_key = os.environ["AOAI_KEY"]
    llm_deployment = os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"]
    embed_deployment = os.environ["AOAI_EMBEDDING_DEPLOYMENT_NAME"]
    embed_api_version = os.environ.get("AOAI_EMBEDDING_API_VERSION", "2024-06-01")

    return {
        "llm": {
            "provider": "azure_openai",
            "config": {
                "model": llm_deployment,
                "temperature": 0.1,
                "max_tokens": 2000,
                "azure_kwargs": {
                    "azure_deployment": llm_deployment,
                    "azure_endpoint": endpoint,
                    "api_key": api_key,
                    "api_version": "2024-06-01",
                },
            },
        },
        "embedder": {
            "provider": "azure_openai",
            "config": {
                "model": embed_deployment,
                "azure_kwargs": {
                    "azure_deployment": embed_deployment,
                    "azure_endpoint": endpoint,
                    "api_key": api_key,
                    "api_version": embed_api_version,
                },
            },
        },
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "collection_name": "fabric_agent_memories",
                "embedding_model_dims": 1536,
            },
        },
    }


def create_memory() -> Memory:
    config = _build_config()
    logger.info("Initializing Mem0 with Azure OpenAI (LLM=%s, Embed=%s)",
                config["llm"]["config"]["model"],
                config["embedder"]["config"]["model"])
    return Memory.from_config(config)
