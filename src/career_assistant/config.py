"""Настройки бота. Читаются из переменных окружения и файла .env."""
from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Telegram ---
    bot_token: str
    proxy_url: str | None = None  # например socks5://user:pass@host:1080

    # --- ИИ (любой OpenAI-совместимый API) ---
    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "google/gemini-2.0-flash-exp:free"

    # --- Источники вакансий ---
    enabled_sources: str = "hh,remoteok"  # через запятую
    hh_user_agent: str = "CareerAssistantBot/1.0 (your-email@example.com)"
    hh_token: str | None = None
    user_agent: str = "Mozilla/5.0 (compatible; CareerBot/1.0)"  # для RemoteOK

    # --- Общее ---
    log_level: str = "INFO"
    db_path: str = "data/career_bot.db"
    timezone: str = "Europe/Moscow"

    temp_vacancy_ttl_days: int = 7
    sent_vacancy_ttl_days: int = 60
    backup_dir: str = "data/backups"
    backup_keep_days: int = 14
    default_notify_hour: int = 10
    vacancies_page_size: int = 5
    search_limit: int = 5
    max_vacancies_per_notification: int = 5

    @property
    def sources_list(self) -> list[str]:
        return [s.strip().lower() for s in self.enabled_sources.split(",") if s.strip()]


try:
    settings = Settings()
except ValidationError as e:  # понятное сообщение вместо длинного traceback
    raise SystemExit(
        "❌ Не задан BOT_TOKEN.\n"
        "Скопируйте .env.example в .env и впишите токен от @BotFather."
    ) from e
