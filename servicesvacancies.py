import logging

from ..integrations.remoteok import RemoteOKClient
from ..models import SearchParams, Vacancy
from ..repositories.sqlite import SQLiteRepository

logger = logging.getLogger(__name__)


class VacancyService:
    """Сценарий поиска вакансий: API → фильтр → кэш → возврат."""

    def __init__(self, remoteok: RemoteOKClient, repo: SQLiteRepository):
        self._remoteok = remoteok
        self._repo = repo

    async def find_and_cache(self, params: SearchParams, limit: int = 5) -> list[Vacancy]:
        vacancies = await self._remoteok.search(params, limit=limit)
        for v in vacancies:
            self._repo.save_temp_vacancy(v)
        return vacancies

    def save_for_user(self, user_id: int, vacancy_id: str) -> bool:
        v = self._repo.get_temp_vacancy(vacancy_id)
        if not v:
            return False
        return self._repo.save_vacancy(user_id, v)

    def list_for_user(self, user_id: int) -> list[tuple]:
        return self._repo.get_user_vacancies(user_id)

    def change_status(self, user_id: int, db_id: int, new_status: str) -> bool:
        return self._repo.update_vacancy_status(user_id, db_id, new_status)

    def remove(self, user_id: int, db_id: int) -> bool:
        return self._repo.delete_vacancy(user_id, db_id)