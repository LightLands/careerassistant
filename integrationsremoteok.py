import logging
import re
from typing import Optional

import aiohttp
from bs4 import BeautifulSoup

from ..models import SearchParams, Vacancy

logger = logging.getLogger(__name__)


class RemoteOKClient:
    BASE_URL = "https://remoteok.com/api"

    def __init__(self, user_agent: str, session: Optional[aiohttp.ClientSession] = None):
        self._user_agent = user_agent
        self._session = session
        self._own_session = session is None

    @property
    def session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession(
                headers={"User-Agent": self._user_agent}
            )
        return self._session

    async def search(self, params: SearchParams, limit: int = 20) -> list[Vacancy]:
        query = {"tag": params.tech}
        if params.salary:
            query["compensation"] = str(params.salary)

        headers = {"User-Agent": self._user_agent, "Accept": "application/json"}

        try:
            async with self.session.get(self.BASE_URL, params=query, headers=headers) as r:
                if r.status != 200:
                    logger.error("RemoteOK HTTP %s", r.status)
                    return []
                if "application/json" not in (r.content_type or ""):
                    logger.error("RemoteOK unexpected content-type: %s", r.content_type)
                    return []
                data = await r.json()
        except Exception as e:
            logger.exception("RemoteOK request failed: %s", e)
            return []

        if not isinstance(data, list) or len(data) < 2:
            return []

        parsed = [self._parse(v) for v in data[1:limit + 1] if v]
        filtered = self._filter(parsed, params)
        return filtered[:limit]

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
            title=d.get("position", "Без названия"),
            company=d.get("company", "Неизвестная компания"),
            salary=salary,
            salary_min=sal_min,
            salary_max=sal_max,
            location=d.get("location", "Worldwide"),
            url=d.get("url", "https://remoteok.com"),
            description=self._clean_description(d.get("description", "")),
            tags=d.get("tags", []) or [],
            date=d.get("date", "")[:10] if d.get("date") else None,
        )

    def _filter(self, vacancies: list[Vacancy], params: SearchParams) -> list[Vacancy]:
        result = vacancies
        if params.salary:
            result = [v for v in result
                      if (v.salary_max and v.salary_max >= params.salary)
                      or (v.salary_min and v.salary_min >= params.salary)]
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

    async def close(self) -> None:
        if self._own_session and self._session:
            await self._session.close()