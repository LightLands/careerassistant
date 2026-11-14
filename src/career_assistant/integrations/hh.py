"""Клиент hh.ru: поиск вакансий через публичный API.

Нужно: зарегистрировать приложение на https://dev.hh.ru и указать в .env
HH_USER_AGENT="Название/1.0 (ваш@email)". Если hh.ru потребует токен для
поиска, добавьте HH_TOKEN. Актуальные правила сверяйте с документацией hh.ru.
Зарплата в поиске задаётся в рублях за месяц.
"""
import asyncio
import logging
import re
from typing import Optional

import aiohttp

from ..models import SearchParams, Vacancy
from .base import SourceError

logger = logging.getLogger(__name__)

RUSSIA_ID = 113

# Запасной список на случай, если справочник /areas не загрузится.
FALLBACK_AREAS = {
    "россия": (113, "Россия"),
    "москва": (1, "Москва"),
    "санкт-петербург": (2, "Санкт-Петербург"),
    "спб": (2, "Санкт-Петербург"),
    "питер": (2, "Санкт-Петербург"),
    "екатеринбург": (3, "Екатеринбург"),
    "новосибирск": (4, "Новосибирск"),
    "казань": (88, "Казань"),
    "нижний новгород": (66, "Нижний Новгород"),
    "краснодар": (53, "Краснодар"),
    "минск": (1002, "Минск"),
    "алматы": (160, "Алматы"),
}

CURRENCY_SIGNS = {"RUR": "₽", "RUB": "₽", "USD": "$", "EUR": "€", "KZT": "₸", "BYR": "Br", "BYN": "Br"}
REMOTE_WORDS = {"удалёнка", "удаленка", "удалённо", "удаленно", "удалённая работа", "удаленная работа", "remote"}


def is_remote_word(text: Optional[str]) -> bool:
    return (text or "").strip().lower() in REMOTE_WORDS


class HHClient:
    name = "hh"
    BASE_URL = "https://api.hh.ru"

    def __init__(
        self,
        user_agent: str,
        token: Optional[str] = None,
        session: Optional[aiohttp.ClientSession] = None,
        min_interval: float = 0.35,
    ):
        self._user_agent = user_agent
        self._token = token
        self._session = session
        self._own_session = session is None
        self._min_interval = min_interval  # пауза между запросами
        self._lock = asyncio.Lock()
        self._areas: Optional[dict[str, tuple[int, str]]] = None

    @property
    def session(self) -> aiohttp.ClientSession:
        if self._session is None:
            headers = {"User-Agent": self._user_agent, "HH-User-Agent": self._user_agent}
            if self._token:
                headers["Authorization"] = f"Bearer {self._token}"
            self._session = aiohttp.ClientSession(
                headers=headers, timeout=aiohttp.ClientTimeout(total=15)
            )
        return self._session

    # ---------- поиск ----------
    async def search(self, params: SearchParams, limit: int = 20) -> list[Vacancy]:
        query: dict = {
            "text": params.tech,
            "per_page": min(limit, 50),
            "page": 0,
            "order_by": "publication_time",
            "period": 7,
        }

        if is_remote_word(params.location):
            query["schedule"] = "remote"
            query["area"] = RUSSIA_ID
        else:
            area = await self._find_area(params.location) if params.location else None
            query["area"] = area[0] if area else RUSSIA_ID

        if params.salary:
            query["salary"] = params.salary
            query["currency"] = "RUR"
            query["only_with_salary"] = "true"

        data = await self._get("/vacancies", query)
        return [self._parse(item) for item in data.get("items", [])][:limit]

    async def get_full_description(self, vacancy_id: str) -> str:
        """Полное описание вакансии (в поиске приходит только сниппет)."""
        data = await self._get(f"/vacancies/{vacancy_id.removeprefix('hh_')}")
        return self._clean(data.get("description", ""), max_length=3000)

    # ---------- регионы ----------
    async def validate_location(self, text: str) -> Optional[str]:
        """Возвращает нормальное название города или None, если не нашли."""
        if is_remote_word(text):
            return "удалёнка"
        area = await self._find_area(text)
        return area[1] if area else None

    async def _find_area(self, text: Optional[str]) -> Optional[tuple[int, str]]:
        key = (text or "").strip().lower().replace("ё", "е")
        if not key:
            return None
        areas = await self._load_areas()
        return areas.get(key)

    async def _load_areas(self) -> dict[str, tuple[int, str]]:
        if self._areas is not None:
            return self._areas
        areas = {k.replace("ё", "е"): v for k, v in FALLBACK_AREAS.items()}
        try:
            tree = await self._get("/areas")
            if isinstance(tree, list):
                self._flatten(tree, areas)
        except SourceError as e:
            logger.warning("Не удалось загрузить справочник регионов hh.ru: %s", e)
            return areas  # не кэшируем, попробуем в следующий раз
        self._areas = areas
        return areas

    def _flatten(self, nodes: list, out: dict) -> None:
        for n in nodes:
            try:
                name = n["name"]
                key = name.strip().lower().replace("ё", "е")
                # при совпадении имён оставляем первый (страны идут раньше городов)
                out.setdefault(key, (int(n["id"]), name))
            except (KeyError, TypeError, ValueError):
                continue
            self._flatten(n.get("areas") or [], out)

    # ---------- HTTP ----------
    async def _get(self, path: str, params: Optional[dict] = None):
        async with self._lock:
            last_error = "неизвестная ошибка"
            for attempt in range(3):
                await asyncio.sleep(self._min_interval)
                try:
                    async with self.session.get(self.BASE_URL + path, params=params) as r:
                        if r.status == 200:
                            return await r.json()
                        body = (await r.text())[:300]
                        if r.status in (429, 500, 502, 503, 504):
                            last_error = f"HTTP {r.status}"
                            await asyncio.sleep(2 ** attempt)
                            continue
                        if r.status in (401, 403):
                            raise SourceError(
                                f"hh.ru отклонил запрос (HTTP {r.status}). Проверьте "
                                f"HH_USER_AGENT и HH_TOKEN. Ответ: {body}"
                            )
                        raise SourceError(f"hh.ru ответил HTTP {r.status}: {body}")
                except SourceError:
                    raise
                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    last_error = str(e) or type(e).__name__
                    await asyncio.sleep(2 ** attempt)
            raise SourceError(f"hh.ru недоступен: {last_error}")

    # ---------- разбор ----------
    def _parse(self, d: dict) -> Vacancy:
        salary_d = d.get("salary") or {}
        s_from, s_to = salary_d.get("from"), salary_d.get("to")
        cur = salary_d.get("currency") or ""
        sign = CURRENCY_SIGNS.get(cur, cur)
        gross = " до вычета налогов" if salary_d.get("gross") else ""
        if s_from and s_to:
            salary = f"{s_from:,} — {s_to:,} {sign}{gross}"
        elif s_from:
            salary = f"от {s_from:,} {sign}{gross}"
        elif s_to:
            salary = f"до {s_to:,} {sign}{gross}"
        else:
            salary = "Не указана"
        salary = salary.replace(",", " ")

        snippet = d.get("snippet") or {}
        parts = [snippet.get("requirement"), snippet.get("responsibility")]
        description = self._clean(" ".join(p for p in parts if p)) or "Описание — по ссылке"

        tags = []
        for key in ("schedule", "experience"):
            name = (d.get(key) or {}).get("name")
            if name:
                tags.append(name)

        return Vacancy(
            id=f"hh_{d.get('id', '')}",  # префикс, чтобы id не пересекались с другими сайтами
            title=d.get("name") or "Без названия",
            company=(d.get("employer") or {}).get("name") or "Не указана",
            salary=salary,
            location=(d.get("area") or {}).get("name") or "",
            url=d.get("alternate_url") or "https://hh.ru",
            description=description,
            tags=tags,
            date=(d.get("published_at") or "")[:10] or None,
            salary_min=s_from,
            salary_max=s_to,
        )

    @staticmethod
    def _clean(text: str, max_length: int = 700) -> str:
        # hh подсвечивает совпадения тегами <highlighttext>, описание приходит в HTML
        text = re.sub(r"<[^>]+>", "", text or "")
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) > max_length:
            text = text[:max_length].rsplit(" ", 1)[0] + "..."
        return text

    async def close(self) -> None:
        if self._own_session and self._session:
            await self._session.close()
