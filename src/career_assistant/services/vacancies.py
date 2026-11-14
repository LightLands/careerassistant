import logging
from typing import Optional

from ..models import SearchParams, Vacancy
from ..integrations.base import SourceError
from ..repositories.sqlite import SQLiteRepository

logger = logging.getLogger(__name__)


class VacancyService:
    """Сценарий поиска вакансий: источник → кэш → возврат."""

    def __init__(self, sources: dict, repo: SQLiteRepository):
        if not sources:
            raise ValueError("Нужен хотя бы один источник вакансий")
        self._sources = sources
        self._repo = repo

    def available_sources(self) -> list[str]:
        return list(self._sources)

    def default_source(self) -> str:
        return next(iter(self._sources))

    def _source(self, name: str):
        src = self._sources.get(name)
        if src is None:
            raise SourceError(f"Источник «{name}» не подключён")
        return src

    async def find_and_cache(self, params: SearchParams, limit: int = 5) -> list[Vacancy]:
        vacancies = await self._source(params.source).search(params, limit=limit)
        if vacancies:
            self._repo.save_temp_vacancies(vacancies)
        return vacancies

    async def validate_location(self, source: str, text: str) -> Optional[str]:
        """Нормализованное название места или None, если такого не нашли.

        Если источник недоступен, не блокируем пользователя: принимаем как есть.
        """
        try:
            return await self._source(source).validate_location(text)
        except SourceError:
            return text.strip()

    # ---------- сохранённые вакансии ----------
    def save_for_user(self, user_id: int, vacancy_id: str) -> str:
        """'saved' | 'exists' | 'expired' (карточка устарела и удалена из кэша)."""
        v = self._repo.get_temp_vacancy(vacancy_id)
        if not v:
            return "expired"
        return "saved" if self._repo.save_vacancy(user_id, v) else "exists"

    def list_for_user(self, user_id: int, limit: int = 10, offset: int = 0) -> list:
        return self._repo.get_user_vacancies(user_id, limit=limit, offset=offset)

    def count_for_user(self, user_id: int) -> int:
        return self._repo.count_user_vacancies(user_id)

    def get_by_id(self, user_id: int, db_id: int):
        return self._repo.get_user_vacancy_by_id(user_id, db_id)

    def change_status(self, user_id: int, db_id: int, new_status: str) -> bool:
        return self._repo.update_vacancy_status(user_id, db_id, new_status)

    def remove(self, user_id: int, db_id: int) -> bool:
        return self._repo.delete_vacancy(user_id, db_id)
