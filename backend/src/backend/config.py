from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings. All secrets come from the local `.env` file only.

    Never write real keys into code, docs, or any shareable file.
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # GitHub API access. Leave empty to run unauthenticated (rate-limited).
    github_token: str = ""

    # OpenAI-compatible relay endpoint. Key stays in `.env`, but can be
    # overridden per-session via the settings API (frontend) — never logged.
    llm_api_key: str = ""
    llm_base_url: str = "https://api.a6api.com/v1"
    llm_model: str = "gpt-5.5"

    # Local embedding + vector store settings.
    embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2"
    vectorstore_dir: str = ".chroma"
    # Set USE_CHROMA=false (or 0) in tests/CI to force the hermetic in-memory
    # fallback and avoid downloading the embedding model.
    use_chroma: bool = True

    # Embedding dimension used by the hermetic hash fallback (when model absent).
    embedding_dim: int = 32

    # Request tuning.
    github_timeout_s: float = 15.0
    http_cache_ttl_s: int = 3600


@lru_cache
def get_settings() -> Settings:
    return Settings()
