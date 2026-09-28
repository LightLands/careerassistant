from ..models import Stats
from ..repositories.sqlite import SQLiteRepository


class AnalyticsService:
    def __init__(self, repo: SQLiteRepository):
        self._repo = repo

    def get_stats(self, user_id: int) -> Stats:
        return self._repo.get_stats(user_id)