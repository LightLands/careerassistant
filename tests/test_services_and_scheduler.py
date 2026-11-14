import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from career_assistant.integrations.base import SourceError
from career_assistant.models import SearchParams, Vacancy
from career_assistant.repositories import Database, SQLiteRepository, UserProfileRepository
from career_assistant.scheduler import notify_due_subscriptions
from career_assistant.services.cover_letters import CoverLetterService, detect_language
from career_assistant.services.vacancies import VacancyService
from aiogram.exceptions import TelegramForbiddenError


def vac(i, title="Dev"):
    return Vacancy(f"hh_{i}", f"{title} {i}", "Co", "100", "Москва", f"https://x/{i}", "d")


class FakeSource:
    def __init__(self, result=None, error=None):
        self.result, self.error, self.calls, self.validate = result or [], error, 0, None

    async def search(self, params, limit=20):
        self.calls += 1
        if self.error:
            raise self.error
        return self.result[:limit]

    async def validate_location(self, text):
        if isinstance(self.validate, Exception):
            raise self.validate
        return text.title()

    async def close(self): ...


class FakeBot:
    def __init__(self, fail_for=None):
        self.sent, self.fail_for = [], fail_for

    async def send_message(self, chat_id, text, **kw):
        if chat_id == self.fail_for:
            raise TelegramForbiddenError()
        self.sent.append((chat_id, text))


class Base(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db = Database(str(Path(self.tmp.name) / "t.db"))
        self.repo, self.profiles = SQLiteRepository(db), UserProfileRepository(db)

    def tearDown(self):
        self.tmp.cleanup()


class VacancyServiceTests(Base):
    async def test_find_caches_and_save_results(self):
        src = FakeSource([vac(1)])
        svc = VacancyService({"hh": src}, self.repo)
        found = await svc.find_and_cache(SearchParams("py", source="hh"))
        self.assertEqual(len(found), 1)
        self.assertEqual(svc.save_for_user(1, "hh_1"), "saved")
        self.assertEqual(svc.save_for_user(1, "hh_1"), "exists")
        self.assertEqual(svc.save_for_user(1, "hh_999"), "expired")

    async def test_unknown_source_and_errors(self):
        svc = VacancyService({"hh": FakeSource(error=SourceError("down"))}, self.repo)
        with self.assertRaises(SourceError):
            await svc.find_and_cache(SearchParams("py", source="hh"))
        with self.assertRaises(SourceError):
            await svc.find_and_cache(SearchParams("py", source="nope"))
        with self.assertRaises(ValueError):
            VacancyService({}, self.repo)

    async def test_validate_location_tolerates_outage(self):
        src = FakeSource()
        svc = VacancyService({"hh": src}, self.repo)
        self.assertEqual(await svc.validate_location("hh", "тула"), "Тула")
        src.validate = SourceError("down")
        self.assertEqual(await svc.validate_location("hh", " тула "), "тула")


class CoverLetterTests(unittest.IsolatedAsyncioTestCase):
    def test_language_detection(self):
        self.assertEqual(detect_language("Ищем Python разработчика, опыт от 3 лет"), "ru")
        self.assertEqual(detect_language("We are hiring a senior Python engineer"), "en")

    async def test_fallback_without_ai(self):
        svc = CoverLetterService(None, "m")
        self.assertFalse(svc.ai_enabled)
        ru = await svc.generate("Требуется разработчик", "3 года Python")
        en = await svc.generate("Hiring a developer", "3 years Python")
        self.assertTrue(ru.startswith("Здравствуйте"))
        self.assertTrue(en.startswith("Dear Hiring Manager"))
        self.assertIn("3 года Python", ru)


class SchedulerTests(Base):
    def setUp(self):
        super().setUp()
        self.src = FakeSource([vac(i) for i in range(1, 9)])
        self.svc = VacancyService({"hh": self.src}, self.repo)

    async def run_at(self, hour, bot):
        await notify_due_subscriptions(bot, self.repo, self.profiles, self.svc,
                                       now=datetime(2026, 11, 14, hour, 0))

    async def test_sends_only_at_users_hour_and_never_twice(self):
        self.repo.add_subscription(1, "python", None, None, "hh")
        bot = FakeBot()
        await self.run_at(11, bot)
        self.assertEqual(bot.sent, [])                 # не его час (по умолчанию 10)
        await self.run_at(10, bot)
        self.assertEqual(len(bot.sent), 1 + 5 + 1)     # заголовок + 5 карточек + «и ещё 3»
        bot.sent.clear()
        await self.run_at(10, bot)
        self.assertEqual(len(bot.sent), 1 + 3)         # остальные 3, и без повторов
        bot.sent.clear()
        await self.run_at(10, bot)
        self.assertEqual(bot.sent, [])

    async def test_custom_hour(self):
        self.repo.add_subscription(1, "python", None, None, "hh")
        self.profiles.set_notify_hour(1, 7)
        bot = FakeBot()
        await self.run_at(10, bot)
        self.assertEqual(bot.sent, [])
        await self.run_at(7, bot)
        self.assertTrue(bot.sent)

    async def test_same_query_searched_once(self):
        self.repo.add_subscription(1, "python", None, None, "hh")
        self.repo.add_subscription(2, "python", None, None, "hh")
        bot = FakeBot()
        await self.run_at(10, bot)
        self.assertEqual(self.src.calls, 1)
        self.assertEqual({c for c, _ in bot.sent}, {1, 2})

    async def test_blocked_user_subscriptions_removed(self):
        self.repo.add_subscription(1, "python", None, None, "hh")
        self.repo.add_subscription(2, "python", None, None, "hh")
        bot = FakeBot(fail_for=1)
        await self.run_at(10, bot)
        self.assertEqual(self.repo.get_user_subscriptions(1), [])
        self.assertEqual(len(self.repo.get_user_subscriptions(2)), 1)
        self.assertTrue(any(c == 2 for c, _ in bot.sent))   # остальным всё равно пришло

    async def test_source_outage_does_not_crash(self):
        self.src.error = SourceError("down")
        self.repo.add_subscription(1, "python", None, None, "hh")
        bot = FakeBot()
        await self.run_at(10, bot)
        self.assertEqual(bot.sent, [])


if __name__ == "__main__":
    unittest.main()
