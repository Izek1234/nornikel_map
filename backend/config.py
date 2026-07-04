import logging
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    # App Settings
    app_name: str = "Nornickel Knowledge Map API"
    environment: str = Field(default="production", alias="ENVIRONMENT")
    debug: bool = Field(default=False, alias="DEBUG")
    
    # Neo4j Settings
    neo4j_uri: str = Field(default="neo4j://localhost:7687", alias="NEO4J_URI")
    neo4j_user: str = Field(default="neo4j", alias="NEO4J_USERNAME")
    neo4j_password: str = Field(default="", alias="NEO4J_PASSWORD")
    
    # LLM Settings
    llm_provider: str = Field(default="yandex", alias="LLM_PROVIDER")
    
    # Yandex Settings
    yandex_api_key: str = Field(default="", alias="YANDEX_API_KEY")
    yandex_folder_id: str = Field(default="", alias="YANDEX_FOLDER_ID")
    yandex_model: str = Field(default="yandexgpt/latest", alias="YANDEX_MODEL")
    yandex_max_concurrent: int = Field(default=3, alias="YANDEX_MAX_CONCURRENT")
    yandex_rps_limit: float = Field(default=8.0, alias="YANDEX_RPS_LIMIT")
    yandex_hourly_limit: int = Field(default=4500, alias="YANDEX_HOURLY_LIMIT")
    yandex_max_retries: int = Field(default=5, alias="YANDEX_MAX_RETRIES")
    
    # Ollama Settings
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="llama3.1:8b", alias="OLLAMA_MODEL")
    
    # Background Sync
    yandex_disk_token: str = Field(default="", alias="YANDEX_DISK_TOKEN")
    yandex_disk_public_url: str = Field(default="", alias="YANDEX_DISK_PUBLIC_URL")
    sync_on_startup: str = Field(default="true", alias="SYNC_ON_STARTUP")
    sync_max_files_per_run: int = Field(default=100, alias="SYNC_MAX_FILES_PER_RUN")
    sync_interval_seconds: int = Field(default=600, alias="SYNC_INTERVAL_SECONDS")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()

def setup_logging():
    level = logging.DEBUG if settings.debug else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[logging.StreamHandler()]
    )
