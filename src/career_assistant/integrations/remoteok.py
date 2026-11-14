import logging
import re
from typing import Optional

import aiohttp
from bs4 import BeautifulSoup

from ..models import SearchParams, Vacancy
from .base import SourceError

logger = logging.getLogger(__name__)


class RemoteOKClient:
    """Зарубежная удалённая работа. Зарплата в USD за год."""

    name = "remoteok"
    BASE_URL = "https://remoteok.com/api"

    def __init__(self, user_agent: str, session: Optional[aiohttp.ClientSession] = None):
        self._user_agent = user_agent
        self._session = session
        self._own_session = session is None

    @property
    def session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession(
                headers={"User-Agent": self._user_agent},
                timeout=aiohttp.ClientTimeout(total=20),
            )
        return self._session

    async def search(self, params: SearchParams, limit: int = 20) -> list[Vacancy]:
        query = {"tag": params.tech}
        if params.salary:
            query["compensation"] = str(params.salary)

        try:
            async with self.session.get(
                self.BASE_URL, params=query, headers={"Accept": "application/json"}
            ) as r:
                if r.status != 200:
                    raise SourceError(f"RemoteOK ответил HTTP {r.status}")
                if "application/json" not in (r.content_type or ""):
                    raise SourceError(f"RemoteOK вернул {r.content_type}")
                data = await r.json()
        except SourceError:
            raise
        except Exception as e:  # сеть, таймаут, битый JSON
            raise SourceError(f"RemoteOK недоступен: {e}") from e

        if not isinstance(data, list) or len(data) < 2:
            return []

        # data[0] — служебная запись с правилами использования API.
        # Фильтруем ДО обрезки по limit, иначе после фильтра остаётся меньше.
        parsed = [self._parse(v) for v in data[1:] if isinstance(v, dict)]
        return self._filter(parsed, params)[:limit]

    def _parse(self, d: dict) -> Vacancy:
        sal_min, sal_max = d.get("salary_min"), d.get("salary_max")
        if sal_min and sal_max:
            salary = f"${sal_min:,} — ${sal_max:,} / год"
        elif sal_min:
            salary = f"от ${sal_min:,} / год"
        elif sal_max:
            salary = f"до ${sal_max:,} / год"
        else:
            salary = "Не указана"

        return Vacancy(
            id=str(d.get("id", "")),
            title=d.get("position") or "Без названия",
            company=d.get("company") or "Неизвестная компания",
            salary=salary,
            salary_min=sal_min or None,
            salary_max=sal_max or None,
            location=d.get("location") or "Worldwide",
            url=d.get("url") or "https://remoteok.com",
            description=self._clean_description(d.get("description", "")),
            tags=d.get("tags", []) or [],
            date=(d.get("date") or "")[:10] or None,
        )

    def _filter(self, vacancies: list[Vacancy], params: SearchParams) -> list[Vacancy]:
        result = vacancies
        if params.salary:
            result = [
                v for v in result
                if (v.salary_max and v.salary_max >= params.salary)
                or (v.salary_min and v.salary_min >= params.salary)
            ]
        if params.location and params.location.lower() != "worldwide":
            loc = params.location.lower()
            result = [v for v in result if v.location and loc in v.location.lower()]
        return result

    @staticmethod
    def _clean_description(html_text: str, max_length: int = 700) -> str:
        if not html_text:
            return "Требования не указаны"
        soup = BeautifulSoup(html_text, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = re.sub(r"\s+", " ", soup.get_text(separator=" ", strip=True)).strip()
        if len(text) > max_length:
            text = text[:max_length].rsplit(" ", 1)[0] + "..."
        return text or "Требования не указаны"

    async def validate_location(self, text: str) -> Optional[str]:
        return text

    async def close(self) -> None:
        if self._own_session and self._session:
            await self._session.close()
