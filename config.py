from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    bot_token: str
    openrouter_api_key: str | None = None
    openrouter_model: str = "google/gemini-2.0-flash-exp:free"
    log_level: str = "INFO"
    db_path: str = "career_bot.db"
    user_agent: str = "Mozilla/5.0 (compatible; CareerBot/1.0)"


settings = Settings()