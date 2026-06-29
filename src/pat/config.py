from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    api_key: str = Field(default="dev-change-me", alias="PAT_API_KEY")
    database_path: str = Field(default="./data/pat.sqlite3", alias="PAT_DATABASE_PATH")
    ollama_base_url: str = Field(
        default="http://127.0.0.1:11434", alias="PAT_OLLAMA_BASE_URL"
    )
    ollama_model: str = Field(default="llama3.1:8b", alias="PAT_OLLAMA_MODEL")
    enable_ollama: bool = Field(default=True, alias="PAT_ENABLE_OLLAMA")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
