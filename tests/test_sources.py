import asyncio
import unittest
from unittest.mock import AsyncMock, patch

import aiohttp

from career_assistant.integrations.base import SourceError
from career_assistant.integrations.hh import HHClient
from career_assistant.integrations.remoteok import RemoteOKClient
from career_assistant.models import SearchParams

HH_ITEM = {
    "id": "42", "name": "Python <dev>", "employer": {"name": "Яндекс"},
    "salary": {"from": 200000, "to": 300000, "currency": "RUR", "gross": True},
    "area": {"name": "Москва"}, "alternate_url": "https://hh.ru/vacancy/42",
    "snippet": {"requirement": "<highlighttext>Python</highlighttext>, SQL", "responsibility": None},
    "published_at": "2026-11-10T10:00:00+0300",
    "schedule": {"name": "Удаленная работа"}, "experience": {"name": "От 1 года до 3 лет"},
}
AREAS = [{"id": "113", "name": "Россия", "areas": [
    {"id": "1", "name": "Москва", "areas": []},
    {"id": "76", "name": "Тула", "areas": []},
    {"id": "1717", "name": "Республика Тыва", "areas": [{"id": "9", "name": "Кызыл", "areas": []}]},
]}]


class FakeResponse:
    def __init__(self, status, payload=None, text=""):
        self.status, self._payload, self._text = status, payload, text
    async def json(self): return self._payload
    async def text(self): return self._text
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False


class FakeSession:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), []
    def get(self, url, params=None, **kw):
        self.calls.append((url, params))
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class HHTests(unittest.IsolatedAsyncioTestCase):
    def test_parse(self):
        v = HHClient("ua")._parse(HH_ITEM)
        self.assertEqual(v.id, "hh_42")
        self.assertEqual(v.salary, "200 000 — 300 000 ₽ до вычета налогов")
        self.assertEqual(v.description, "Python, SQL")
        self.assertEqual(v.tags, ["Удаленная работа", "От 1 года до 3 лет"])
        self.assertEqual((v.date, v.salary_min), ("2026-11-10", 200000))

    def test_parse_handles_nulls(self):
        v = HHClient("ua")._parse({"id": "1", "name": None, "salary": None, "snippet": None})
        self.assertEqual((v.salary, v.company), ("Не указана", "Не указана"))

    async def test_search_builds_query(self):
        c = HHClient("ua", min_interval=0)
        calls = []

        async def fake_get(path, params=None):
            calls.append((path, params))
            return AREAS if path == "/areas" else {"items": [HH_ITEM]}
        c._get = fake_get
        res = await c.search(SearchParams("python", 150000, "Тула", "hh"), limit=5)
        self.assertEqual(len(res), 1)
        q = [p for path, p in calls if path == "/vacancies"][0]
        self.assertEqual((q["area"], q["salary"], q["currency"]), (76, 150000, "RUR"))
        self.assertEqual(q["only_with_salary"], "true")

        calls.clear()
        await c.search(SearchParams("python", None, "удалёнка", "hh"))
        q = calls[0][1]
        self.assertEqual((q["schedule"], q["area"]), ("remote", 113))
        self.assertNotIn("salary", q)

    async def test_validate_location(self):
        c = HHClient("ua", min_interval=0)
        c._get = AsyncMock(return_value=AREAS)
        self.assertEqual(await c.validate_location("тула"), "Тула")
        self.assertEqual(await c.validate_location("Кызыл"), "Кызыл")   # вложенный город
        self.assertEqual(await c.validate_location("Удаленка"), "удалёнка")
        self.assertIsNone(await c.validate_location("Атлантида"))

    async def test_areas_fallback_when_directory_unavailable(self):
        c = HHClient("ua", min_interval=0)
        c._get = AsyncMock(side_effect=SourceError("down"))
        self.assertEqual(await c.validate_location("Москва"), "Москва")  # из запасного списка

    async def test_retry_on_429_then_success(self):
        session = FakeSession([FakeResponse(429), FakeResponse(200, {"items": []})])
        c = HHClient("ua", session=session, min_interval=0)
        with patch("career_assistant.integrations.hh.asyncio.sleep", AsyncMock()):
            self.assertEqual(await c._get("/vacancies", {}), {"items": []})
        self.assertEqual(len(session.calls), 2)

    async def test_forbidden_raises_source_error_with_hint(self):
        c = HHClient("ua", session=FakeSession([FakeResponse(403, text="forbidden")]), min_interval=0)
        with patch("career_assistant.integrations.hh.asyncio.sleep", AsyncMock()):
            with self.assertRaises(SourceError) as ctx:
                await c._get("/vacancies")
        self.assertIn("HH_TOKEN", str(ctx.exception))

    async def test_network_errors_become_source_error(self):
        err = aiohttp.ClientError("boom")
        c = HHClient("ua", session=FakeSession([err, err, err]), min_interval=0)
        with patch("career_assistant.integrations.hh.asyncio.sleep", AsyncMock()):
            with self.assertRaises(SourceError):
                await c._get("/vacancies")


RO_DATA = [{"legal": "notice"}] + [
    {"id": i, "position": f"Job {i}", "company": "C", "location": "Europe" if i % 2 else "USA",
     "salary_min": 50000 + i * 1000, "salary_max": 90000 + i * 1000, "url": f"https://r/{i}",
     "description": "<p>Req</p><script>x</script>", "tags": ["python"], "date": "2026-11-01T00:00:00"}
    for i in range(1, 41)
]


class RemoteOKTests(unittest.IsolatedAsyncioTestCase):
    def _client(self, resp):
        class R(FakeResponse):
            content_type = "application/json"
        r = R(resp[0], resp[1])
        return RemoteOKClient("ua", session=FakeSession([r]))

    async def test_filter_happens_before_limit(self):
        c = self._client((200, RO_DATA))
        res = await c.search(SearchParams("python", None, "europe", "remoteok"), limit=5)
        self.assertEqual(len(res), 5)  # раньше после фильтра оставалось бы меньше
        self.assertTrue(all("europe" in v.location.lower() for v in res))

    async def test_http_error_is_source_error(self):
        c = self._client((503, None))
        with self.assertRaises(SourceError):
            await c.search(SearchParams("python"))

    def test_parse_cleans_html(self):
        v = RemoteOKClient("ua")._parse(RO_DATA[1])
        self.assertEqual(v.description, "Req")
        self.assertIn("/ год", v.salary)


if __name__ == "__main__":
    unittest.main()
