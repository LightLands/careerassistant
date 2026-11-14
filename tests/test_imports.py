"""Страховка от опечаток: все модули импортируются, а в функциях нет
обращений к необъявленным именам (иначе ошибка вылезла бы только при нажатии кнопки)."""
import builtins
import dis
import importlib
import pkgutil
import types
import unittest

import career_assistant


def _walk_code(code):
    yield code
    for const in code.co_consts:
        if isinstance(const, types.CodeType):
            yield from _walk_code(const)


class ImportTests(unittest.TestCase):
    def test_all_modules_import_and_names_resolve(self):
        problems = []
        for info in pkgutil.walk_packages(career_assistant.__path__, "career_assistant."):
            if info.name.endswith("__main__"):
                continue
            module = importlib.import_module(info.name)
            with open(module.__file__, encoding="utf-8") as f:
                source_code = compile(f.read(), module.__file__, "exec")
            for code in _walk_code(source_code):
                for ins in dis.get_instructions(code):
                    if ins.opname == "LOAD_GLOBAL":
                        name = ins.argval
                        if name not in vars(module) and not hasattr(builtins, name):
                            problems.append(f"{info.name}: {code.co_name} → {name}")
        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
