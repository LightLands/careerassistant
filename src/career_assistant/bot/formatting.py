"""Оформление сообщений. Всё, что пришло из внешних источников, экранируется:
иначе символы < > & в названии вакансии ломают HTML-разметку Telegram."""
from html import escape

from ..models import Stats, SearchParams, Subscription, Vacancy
from .keyboards import STATUS_NAMES

SOURCE_LABELS = {"hh": "hh.ru", "remoteok": "RemoteOK"}
SKIP_WORDS = {"пропустить", "skip", "не важно", "неважно", "-", "любой", "любая"}
MAX_MESSAGE = 4000


def esc(text) -> str:
    return escape(str(text if text is not None else ""), quote=True)


def money(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def salary_label(source: str, salary) -> str:
    if not salary:
        return "любая"
    return f"от {money(salary)} ₽/мес" if source == "hh" else f"от ${money(salary)}/год"


def _fit(text: str) -> str:
    return text if len(text) <= MAX_MESSAGE else text[: MAX_MESSAGE - 20] + "\n… (обрезано)"


def vacancy_card(v: Vacancy, idx: int | None = None) -> str:
    head = f"{idx}. {v.title}" if idx else v.title
    lines = [
        f"<b>{esc(head)}</b>",
        f"🏢 <b>Компания:</b> {esc(v.company)}",
        f"💰 <b>Зарплата:</b> {esc(v.salary)}",
        f"📍 <b>Локация:</b> {esc(v.location or '—')}",
    ]
    if v.tags:
        lines.append(f"🏷 <b>Теги:</b> {esc(', '.join(v.tags[:5]))}")
    lines.append(f"📅 <b>Опубликовано:</b> {esc(v.date or '—')}")
    lines.append(f"\n📋 <i>{esc(v.description[:1200])}</i>")
    lines.append(f"\n🔗 <a href=\"{esc(v.url)}\">Открыть вакансию</a>")
    return _fit("\n".join(lines))


def short_card(v: Vacancy) -> str:
    return _fit(
        f"<b>{esc(v.title)}</b>\n🏢 {esc(v.company)}\n💰 {esc(v.salary)}\n"
        f"📍 {esc(v.location or '—')}\n🔗 <a href=\"{esc(v.url)}\">Открыть</a>"
    )


def saved_card(row) -> str:
    status = STATUS_NAMES.get(row["status"], STATUS_NAMES["saved"])
    return _fit(
        f"<b>{esc(row['title'])}</b>\n🏢 {esc(row['company'])}\n💰 {esc(row['salary'])}\n"
        f"📍 {esc(row['location'] or '—')}\n📊 <b>Статус:</b> {status}\n"
        f"🔗 <a href=\"{esc(row['url'])}\">Открыть</a>"
    )


def subscription_card(sub: Subscription) -> str:
    return (
        f"🔍 <b>{esc(sub.tech)}</b>\n"
        f"🌐 Источник: {SOURCE_LABELS.get(sub.source, esc(sub.source))}\n"
        f"💰 Зарплата: {salary_label(sub.source, sub.salary)}\n"
        f"📍 Регион: {esc(sub.location) if sub.location else 'любой'}"
    )


def params_summary(p: SearchParams) -> str:
    return (
        f"• Источник: <b>{SOURCE_LABELS.get(p.source, esc(p.source))}</b>\n"
        f"• Запрос: <b>{esc(p.tech)}</b>\n"
        f"• Зарплата: <b>{salary_label(p.source, p.salary)}</b>\n"
        f"• Регион: <b>{esc(p.location) if p.location else 'любой'}</b>"
    )


def stats_text(s: Stats) -> str:
    rate = s.conversion_rate
    filled = max(0, min(10, rate // 10))
    bar = f"[{'█' * filled}{'░' * (10 - filled)}] {rate}%"
    return (
        "📊 <b>Твоя карьерная статистика</b>\n\n"
        f"📥 Всего в трекере: <b>{s.total}</b>\n"
        f"📤 Откликов отправлено: <b>{s.applied + s.interview + s.offer}</b>\n"
        f"✅ Приглашений на интервью: <b>{s.interview + s.offer}</b>\n"
        f"🏆 Получено офферов: <b>{s.offer}</b>\n"
        f"❌ Отказов: <b>{s.rejected}</b>\n\n"
        f"📈 <b>Конверсия отклик → интервью:</b>\n{bar}"
    )
