import sqlite3
import tempfile
import unittest
from pathlib import Path

from career_assistant.models import SearchParams, Vacancy
from career_assistant.repositories import Database, SQLiteRepository, UserProfileRepository
from career_assistant.repositories.db import _SCHEMA_V1


def vac(i="hh_1", title="Python dev"):
    return Vacancy(i, title, "Co", "100", "Москва", f"https://x/{i}", "desc", ["a"], "2026-11-10", 1, 2)


class RepoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(str(Path(self.tmp.name) / "t.db"))
        self.repo = SQLiteRepository(self.db)
        self.profiles = UserProfileRepository(self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def test_temp_roundtrip_and_save(self):
        self.repo.save_temp_vacancies([vac()])
        got = self.repo.get_temp_vacancy("hh_1")
        self.assertEqual((got.title, got.tags, got.salary_max), ("Python dev", ["a"], 2))
        self.assertTrue(self.repo.save_vacancy(1, got))
        self.assertFalse(self.repo.save_vacancy(1, got))  # дубль
        self.assertEqual(self.repo.count_user_vacancies(1), 1)

    def test_status_flow(self):
        self.repo.save_vacancy(1, vac())
        db_id = self.repo.get_user_vacancies(1)[0]["id"]
        self.assertTrue(self.repo.update_vacancy_status(1, db_id, "applied"))
        self.assertFalse(self.repo.update_vacancy_status(1, db_id, "applied"))   # тот же статус
        self.assertFalse(self.repo.update_vacancy_status(1, db_id, "saved"))     # назад нельзя
        self.assertFalse(self.repo.update_vacancy_status(1, db_id, "nonsense"))
        self.assertTrue(self.repo.update_vacancy_status(1, db_id, "rejected"))
        self.assertTrue(self.repo.update_vacancy_status(1, db_id, "saved"))      # возврат из отказа
        self.assertFalse(self.repo.update_vacancy_status(2, db_id, "applied"))   # чужая вакансия
        stats = self.repo.get_stats(1)
        self.assertEqual((stats.saved, stats.total), (1, 1))

    def test_subscription_dedupe_with_nulls(self):
        self.assertTrue(self.repo.add_subscription(1, "python", None, None, "hh"))
        self.assertFalse(self.repo.add_subscription(1, "python", None, None, "hh"))  # NULL тоже дубль
        self.assertTrue(self.repo.add_subscription(1, "python", None, None, "remoteok"))
        self.assertTrue(self.repo.add_subscription(1, "python", 100000, "москва", "hh"))
        subs = self.repo.get_user_subscriptions(1)
        self.assertEqual(sorted(s.source for s in subs), ["hh", "hh", "remoteok"])
        self.assertEqual(self.repo.delete_user_subscriptions(1), 3)

    def test_sent_and_history_and_letters(self):
        self.repo.mark_vacancy_sent(1, "hh_1", 5)
        self.repo.mark_vacancy_sent(1, "hh_1", 5)  # повтор не падает
        self.assertEqual(self.repo.get_sent_vacancies(1), ["hh_1"])
        self.repo.add_search_history(1, SearchParams("python", 1, "x", "hh"))
        self.assertEqual(self.repo.get_recent_searches(1)[0]["source"], "hh")
        self.repo.save_cover_letter(1, "vac", "letter")

    def test_profile_and_settings(self):
        p = self.profiles.touch_user(7, "nick", "Имя")
        self.assertEqual(p.username, "nick")
        self.profiles.update_company(7, "Яндекс")
        self.profiles.add_link(7, "https://a.ru")
        self.assertEqual(len(self.profiles.get_links(7)), 1)
        self.assertEqual(self.profiles.get_settings(7, 10).notify_hour, 10)
        self.profiles.set_notify_hour(7, 99)
        self.assertEqual(self.profiles.get_settings(7, 10).notify_hour, 23)

    def test_backup(self):
        path = self.db.backup(str(Path(self.tmp.name) / "bk"), keep_days=14)
        self.assertTrue(Path(path).exists())


class MigrationTests(unittest.TestCase):
    def test_v1_database_is_migrated_and_keeps_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "old.db")
            c = sqlite3.connect(path)
            c.executescript(_SCHEMA_V1)
            c.execute("CREATE TABLE schema_version (v INTEGER NOT NULL)")
            c.execute("INSERT INTO schema_version VALUES (1)")
            c.execute("INSERT INTO job_subscriptions (user_id, tech) VALUES (1, 'python')")
            c.commit(); c.close()

            db = Database(path)
            subs = SQLiteRepository(db).get_user_subscriptions(1)
            self.assertEqual((subs[0].tech, subs[0].source), ("python", "remoteok"))
            Database(path)  # повторное открытие

    def test_legacy_monolith_database(self):
        """База от старого bot.py: есть часть таблиц и нет schema_version."""
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "legacy.db")
            c = sqlite3.connect(path)
            c.execute("""CREATE TABLE job_subscriptions (id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL, tech TEXT NOT NULL, salary INTEGER, location TEXT,
                is_active INTEGER DEFAULT 1, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
            c.execute("INSERT INTO job_subscriptions (user_id, tech) VALUES (1, 'go')")
            c.commit(); c.close()
            subs = SQLiteRepository(Database(path)).get_user_subscriptions(1)
            self.assertEqual((subs[0].tech, subs[0].source), ("go", "remoteok"))


if __name__ == "__main__":
    unittest.main()
