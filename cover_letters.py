import logging

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class CoverLetterService:
    def __init__(self, api_key: str | None, model: str):
        self._model = model
        self._client = (
            AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
            if api_key else None
        )

    async def generate(self, vacancy_text: str, user_profile: str) -> str:
        if self._client is None:
            return self._fallback(vacancy_text, user_profile)
        try:
            resp = await self._client.chat.completions.create(
                model=self._model,
                messages=[{
                    "role": "user",
                    "content": (
                        "Напиши профессиональное сопроводительное письмо на английском языке.\n\n"
                        f"Вакансия:\n{vacancy_text[:1500]}\n\n"
                        f"Мой опыт:\n{user_profile}\n\n"
                        "Требования: 3–4 абзаца, конкретно, свяжи опыт с требованиями. "
                        "Начни с 'Dear Hiring Manager,' и закончи 'Best regards, [My Name]'."
                    ),
                }],
                temperature=0.7,
                max_tokens=500,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            logger.exception("OpenRouter error: %s", e)
            return self._fallback(vacancy_text, user_profile)

    @staticmethod
    def _fallback(vacancy_text: str, user_profile: str) -> str:
        return (
            "Dear Hiring Manager,\n\n"
            f"I am writing to express my interest in your open position. "
            f"My background: {user_profile}.\n\n"
            "I would welcome the opportunity to discuss how my skills can benefit your team.\n\n"
            "Best regards,\n[My Name]"
        )