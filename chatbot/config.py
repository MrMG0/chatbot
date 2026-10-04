from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # LLM Settings
    llm_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    llm_api_key: str = ""
    llm_model: str = "gemini-flash-lite-latest"
    llm_temperature: float = 0.6
    llm_timeout: float = 60.0
    llm_max_retries: int = 2

    # Memory Settings
    memory_limit: int = 20
    recent_messages_count: int = 10
    max_active_users: int = 1000
    user_session_ttl_hours: int = 24
    redis_url: str = ""

    # API Settings
    cors_origins: list[str] = ["*"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
