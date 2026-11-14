# 🚀 Career Assistant Bot

Telegram-бот для поиска работы: ищет вакансии на **hh.ru** и **RemoteOK**, ведёт трекер откликов,
присылает новые вакансии по подписке и пишет черновики сопроводительных писем.

## Возможности

| Функция | Что делает |
| :--- | :--- |
| 🔍 `/search` | Поиск на hh.ru (рубли в месяц, города, удалёнка) или RemoteOK (доллары в год). |
| 📂 `/my_vacancies`, 📊 `/stats` | Трекер: сохранена → отклик → интервью → оффер / отказ, постраничный список, конверсия. |
| 🔔 `/subscribe` | Ежедневная рассылка только новых вакансий. Время выбирает пользователь: `/set_hour 9`. |
| ✉️ `/cover_letter` | Письмо на русском или английском (язык определяется по тексту вакансии). Без ключа ИИ — шаблон. |
| 👤 `/profile` | Компания, полезные ссылки, время уведомлений. |

## Запуск

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows;  на Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env          # Linux/macOS: cp .env.example .env
# впишите BOT_TOKEN (и при желании остальное) в .env
python run.py
```

Нужен Python 3.10+ (проверено на 3.12).

## Подключение hh.ru

1. Зарегистрируйте приложение на <https://dev.hh.ru>.
2. В `.env` задайте `HH_USER_AGENT="Название/1.0 (ваш@email)"`.
3. Если hh.ru отвечает 401/403, добавьте `HH_TOKEN`. В логе будет сообщение с подсказкой.

Важно:
* Используется только **публичный поиск вакансий**. Откликаться от имени пользователя бот не может:
  по сторонним описаниям hh.ru закрыл для этого API в декабре 2024. Отклик пользователь делает по ссылке,
  а статус отмечает в трекере. Актуальные правила смотрите в документации hh.ru.
* Запросы идут с паузами и повторами при 429/5xx. Не убирайте паузы: за агрессивные запросы могут заблокировать.

Чтобы добавить другой сайт, сделайте клиент по образцу `integrations/hh.py` (методы `search`,
`validate_location`, `close`, атрибут `name`) и подключите его в `main.py → build_sources()`.

## Структура

```
run.py                       точка входа
src/career_assistant/
  main.py                    сборка и запуск
  config.py                  настройки (.env)
  models.py                  Vacancy, SearchParams, Stats, ...
  scheduler.py               рассылка по часам, очистка, бэкап базы
  integrations/              hh.py, remoteok.py, base.py (SourceError)
  services/                  vacancies, analytics, cover_letters
  repositories/              SQLite: db (схема, миграции, бэкап), sqlite, user_profile
  bot/
    routers/                 common, search, subscriptions, applications, cover_letters, profile
    keyboards.py, formatting.py, flow.py, middlewares.py
tests/                       python -m unittest discover -s tests -t .
```

## База данных

SQLite, по умолчанию `data/career_bot.db`. Миграции применяются автоматически при запуске
(схема v2 добавила источник к подпискам; старые подписки считаются подписками на RemoteOK).
Раз в сутки в 03:30 делается копия в `data/backups/`.
Если у вас уже есть `career_bot.db` от прежней версии, положите его в `data/` или укажите путь в `DB_PATH`.

## Тесты

```bash
python -m unittest discover -s tests -t .
```

Тесты не ходят в сеть и не требуют токенов.

## Безопасность

* Никогда не отправляйте и не коммитьте `.env`. Токен бота можно перевыпустить в @BotFather командой `/revoke`.
* Бот хранит Telegram ID, username, имя, указанную компанию и ссылки, сохранённые вакансии и тексты сгенерированных
  писем. Если откроете бота для публики в России, учитывайте требования 152-ФЗ (согласие на обработку, хранение в РФ).
