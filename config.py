from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    bot_token: str
    openrouter_api_key: str | None = None
    openrouter_model: str = "google/gemini-2.0-flash-exp:free"
    log_level: str = "INFO"
    db_path: str = "data/career_bot.db"
    user_agent: str = "Mozilla/5.0 (compatible; CareerBot/1.0)"
    timezone: str = "Europe/Moscow"

    # Новые настройки
    temp_vacancy_ttl_days: int = 7
    sent_vacancy_ttl_days: int = 60
    backup_dir: str = "data/backups"
    backup_keep_days: int = 14
    default_notify_hour: int = 10
    vacancies_page_size: int = 5


settings = Settings()