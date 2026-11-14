import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

_CYR = re.compile(r"[а-яёА-ЯЁ]")
_LAT = re.compile(r"[a-zA-Z]")


def detect_language(text: str) -> str:
    """'ru', если в тексте вакансии больше кириллицы, иначе 'en'."""
    return "ru" if len(_CYR.findall(text)) > len(_LAT.findall(text)) else "en"


class CoverLetterService:
    def __init__(self, api_key: Optional[str], model: str,
                 base_url: str = "https://openrouter.ai/api/v1"):
        self._model = model
        self._client = None
        if api_key:
            from openai import AsyncOpenAI  # импорт здесь: без ключа пакет не нужен
            self._client = AsyncOpenAI(
                base_url=base_url, api_key=api_key, timeout=45, max_retries=1
            )

    @property
    def ai_enabled(self) -> bool:
        return self._client is not None

    async def generate(self, vacancy_text: str, user_profile: str,
                       lang: Optional[str] = None) -> str:
        lang = lang or detect_language(vacancy_text)
        if self._client is None:
            return self._fallback(user_profile, lang)
        try:
            resp = await self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": self._prompt(vacancy_text, user_profile, lang)}],
                temperature=0.7,
                max_tokens=900,
            )
            text = (resp.choices[0].message.content or "").strip()
            return text or self._fallback(user_profile, lang)
        except Exception as e:
            logger.exception("Ошибка ИИ-провайдера: %s", e)
            return self._fallback(user_profile, lang)

    @staticmethod
    def _prompt(vacancy_text: str, user_profile: str, lang: str) -> str:
        if lang == "ru":
            return (
                "Напиши сопроводительное письмо на русском языке.\n\n"
                f"Вакансия:\n{vacancy_text[:3000]}\n\n"
                f"Мой опыт:\n{user_profile[:1500]}\n\n"
                "Требования: 3–4 абзаца, конкретно, свяжи мой опыт с требованиями "
                "вакансии, без выдуманных фактов. Начни с «Здравствуйте!» и закончи "
                "«С уважением, [Ваше имя]». Выведи только текст письма."
            )
        return (
            "Write a professional cover letter in English.\n\n"
            f"Job posting:\n{vacancy_text[:3000]}\n\n"
            f"My experience:\n{user_profile[:1500]}\n\n"
            "Requirements: 3-4 paragraphs, specific, connect my experience to the "
            "requirements, do not invent facts. Start with 'Dear Hiring Manager,' and "
            "end with 'Best regards, [My Name]'. Output only the letter text."
        )

    @staticmethod
    def _fallback(user_profile: str, lang: str) -> str:
        if lang == "ru":
            return (
                "Здравствуйте!\n\n"
                "Меня заинтересовала ваша вакансия. "
                f"Коротко о моём опыте: {user_profile}.\n\n"
                "Буду рад обсудить, чем могу быть полезен вашей команде.\n\n"
                "С уважением,\n[Ваше имя]"
            )
        return (
            "Dear Hiring Manager,\n\n"
            "I am writing to express my interest in your open position. "
            f"My background: {user_profile}.\n\n"
            "I would welcome the opportunity to discuss how my skills can benefit your team.\n\n"
            "Best regards,\n[My Name]"
        )
