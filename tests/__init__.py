"""Подготовка окружения для тестов.

Если сторонних библиотек (aiogram, aiohttp, pydantic) нет, подставляем
минимальные заглушки, чтобы логика проекта тестировалась без установки.
С настоящими библиотеками заглушки не включаются.
"""
import os
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
os.environ.setdefault("BOT_TOKEN", "123:test")


def _missing(name: str) -> bool:
    try:
        __import__(name)
        return False
    except ImportError:
        return True


class _Obj:
    def __init__(self, *a, **k):
        self.__dict__.update(k)
        self.args = a


class _Dummy:
    def __init__(self, *a, **k): ...
    def __call__(self, *a, **k): return _Dummy()
    def __getattr__(self, n): return _Dummy()
    def __invert__(self): return _Dummy()
    def __eq__(self, o): return _Dummy()
    def __and__(self, o): return _Dummy()
    def __or__(self, o): return _Dummy()
    __hash__ = object.__hash__


class _Mod(types.ModuleType):
    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        cls = type(name, (_Obj,), {})
        setattr(self, name, cls)
        return cls


def _install_aiogram() -> None:
    class Router:
        def __init__(self, *a, **k): ...
        def _deco(self, *a, **k): return lambda f: f
        message = callback_query = _deco

    class BaseMiddleware: ...
    class State:
        def __init__(self, *a): ...
    class StatesGroup: ...
    class TelegramForbiddenError(Exception): ...
    class TelegramBadRequest(Exception): ...

    names = ["aiogram", "aiogram.filters", "aiogram.fsm", "aiogram.fsm.context",
             "aiogram.fsm.state", "aiogram.types", "aiogram.exceptions",
             "aiogram.client", "aiogram.client.session", "aiogram.client.session.aiohttp"]
    mods = {n: _Mod(n) for n in names}
    for n, m in mods.items():
        sys.modules[n] = m
    a = mods["aiogram"]
    a.F, a.Router, a.BaseMiddleware = _Dummy(), Router, BaseMiddleware
    a.Bot = a.Dispatcher = _Obj
    a.types = mods["aiogram.types"]
    mods["aiogram.filters"].Command = _Dummy()
    mods["aiogram.fsm.state"].State, mods["aiogram.fsm.state"].StatesGroup = State, StatesGroup
    mods["aiogram.exceptions"].TelegramForbiddenError = TelegramForbiddenError
    mods["aiogram.exceptions"].TelegramBadRequest = TelegramBadRequest


def _install_aiohttp() -> None:
    m = types.ModuleType("aiohttp")
    class ClientError(Exception): ...
    m.ClientError, m.ClientSession, m.ClientTimeout = ClientError, _Obj, _Obj
    sys.modules["aiohttp"] = m


def _install_pydantic() -> None:
    p = types.ModuleType("pydantic")
    class ValidationError(Exception): ...
    p.ValidationError = ValidationError
    ps = types.ModuleType("pydantic_settings")

    class BaseSettings:
        def __init__(self):
            for name in self.__class__.__annotations__:
                env = os.environ.get(name.upper())
                if env is not None:
                    default = getattr(type(self), name, None)
                    setattr(self, name, int(env) if isinstance(default, int) else env)
                elif hasattr(type(self), name):
                    setattr(self, name, getattr(type(self), name))
                else:
                    raise ValidationError(name)
    ps.BaseSettings, ps.SettingsConfigDict = BaseSettings, dict
    sys.modules["pydantic"], sys.modules["pydantic_settings"] = p, ps


if _missing("aiogram"):
    _install_aiogram()
if _missing("aiohttp"):
    _install_aiohttp()
if _missing("pydantic_settings"):
    _install_pydantic()
