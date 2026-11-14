import unittest

from career_assistant.bot.flow import is_skip, parse_salary
from career_assistant.bot.formatting import esc, salary_label, saved_card, stats_text, vacancy_card
from career_assistant.models import Stats, Vacancy


class ParseSalaryTests(unittest.TestCase):
    def test_numbers(self):
        for text, expected in [("150000", 150000), ("150 000", 150000), ("150к", 150000),
                               ("150k", 150000), ("150.5к", 150500), ("80,000", 80000),
                               ("80000$", 80000), ("90 тыс", 90000)]:
            self.assertEqual(parse_salary(text), (True, expected), text)

    def test_skip_and_garbage(self):
        self.assertEqual(parse_salary("пропустить"), (True, None))
        self.assertEqual(parse_salary("-"), (True, None))
        self.assertEqual(parse_salary("abc"), (False, None))
        self.assertEqual(parse_salary("0"), (False, None))
        self.assertTrue(is_skip("  Не важно "))


class FormattingTests(unittest.TestCase):
    def test_html_is_escaped(self):
        v = Vacancy("1", "Dev <b>&</b>", "A&B <Co>", "100", "Msk", 'https://x.ru/?a=1&b="2"',
                    "<script>alert(1)</script>")
        text = vacancy_card(v, 1)
        self.assertNotIn("<script>", text)
        self.assertNotIn("<Co>", text)
        self.assertIn("&lt;Co&gt;", text)
        self.assertIn("&quot;", text)

    def test_saved_card_escapes_row(self):
        row = {"title": "<i>x</i>", "company": "c", "salary": "s", "location": None,
               "url": "https://x", "status": "applied"}
        self.assertIn("&lt;i&gt;", saved_card(row))

    def test_long_card_is_truncated(self):
        v = Vacancy("1", "T" * 3000, "C" * 3000, "s", "l", "https://x", "d")
        self.assertLessEqual(len(vacancy_card(v)), 4000)

    def test_stats_bar_never_overflows(self):
        for rate_stats in (Stats(), Stats(applied=1), Stats(interview=5, offer=5), Stats(applied=3, interview=1)):
            bar = stats_text(rate_stats).split("[")[1].split("]")[0]
            self.assertEqual(len(bar), 10)

    def test_salary_label(self):
        self.assertEqual(salary_label("hh", 150000), "от 150 000 ₽/мес")
        self.assertEqual(salary_label("remoteok", 80000), "от $80 000/год")
        self.assertEqual(salary_label("hh", None), "любая")
        self.assertEqual(esc(None), "")


class StatsTests(unittest.TestCase):
    def test_conversion(self):
        self.assertEqual(Stats().conversion_rate, 0)
        self.assertEqual(Stats(applied=3, interview=1).conversion_rate, 25)
        self.assertEqual(Stats(interview=2).conversion_rate, 100)
        self.assertEqual(Stats(saved=10, rejected=4).conversion_rate, 0)


if __name__ == "__main__":
    unittest.main()
