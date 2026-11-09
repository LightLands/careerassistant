"""Точка входа. Запускает бота."""
import asyncio
from src.career_assistant.main import main

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass