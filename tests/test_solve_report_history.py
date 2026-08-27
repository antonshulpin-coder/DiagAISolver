import unittest
from contextlib import redirect_stdout
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from src.commands import (
    _do_solve,
    _format_investigation_history,
    _show_investigation_history,
)


def _completed_problem():
    return {
        "id": "P1",
        "title": "Приложение падает",
        "status": "solved",
        "cause": "Пропал модуль x",
        "solution": "Установил модуль x",
        "diagnostic": {
            "started_at": "t0",
            "hypotheses": [
                {"id": "H1", "text": "Пропал модуль x", "status": "confirmed", "source": "ai"},
                {"id": "H2", "text": "Неверные права", "status": "rejected", "source": "manual"},
                {"id": "H3", "text": "Старая версия", "status": "rejected", "source": "manual"},
            ],
            "steps": [
                {"id": "S1", "hypothesis_id": "H2", "description": "Проверить права",
                 "status": "done", "outcome": "Файл читается", "result": "rejected"},
                {"id": "S2", "hypothesis_id": "H3", "description": "Сравнить версии",
                 "status": "done", "outcome": "Версия свежая", "result": "rejected"},
                {"id": "S3", "hypothesis_id": "H1", "description": "Проверить импорт",
                 "status": "done", "outcome": "Модуль отсутствует", "result": "confirmed"},
            ],
            "conclusion": "Пропал зависимый модуль",
        },
    }


class TestFormatInvestigationHistory(unittest.TestCase):

    def test_completed_full_report(self):
        lines = _format_investigation_history(_completed_problem())
        self.assertEqual(lines, [
            "\n--- Как расследовали ---",
            "Вывод: Пропал зависимый модуль",
            "Причина (подтверждена):",
            "  [H1] Пропал модуль x",
            "Выполненные шаги:",
            "  [S1] Проверить права → Файл читается → Неверные права (отклонена)",
            "  [S2] Сравнить версии → Версия свежая → Старая версия (отклонена)",
            "  [S3] Проверить импорт → Модуль отсутствует → Пропал модуль x (подтверждена)",
            "Отклонённые гипотезы:",
            "  [H2] Неверные права",
            "  [H3] Старая версия",
        ])

    def test_active_session_without_conclusion(self):
        problem = {
            "id": "P1",
            "diagnostic": {
                "hypotheses": [
                    {"id": "H1", "text": "Пропал модуль", "status": "tested", "source": "ai"},
                    {"id": "H2", "text": "Права", "status": "open", "source": "manual"},
                ],
                "steps": [
                    {"id": "S1", "hypothesis_id": "H1", "description": "Проверить импорт",
                     "status": "done", "outcome": "Не найден", "result": "unknown"},
                ],
                "conclusion": "",
            },
        }
        lines = _format_investigation_history(problem)
        self.assertNotIn("Вывод:", lines)
        self.assertNotIn("Причина (подтверждена):", lines)
        self.assertIn("Выполненные шаги:", lines)
        self.assertIn("  [S1] Проверить импорт → Не найден → Пропал модуль (проверена)", lines)

    def test_no_diagnostic_returns_empty(self):
        self.assertEqual(_format_investigation_history({"id": "P1"}), [])

    def test_diagnostic_non_dict_returns_empty(self):
        self.assertEqual(_format_investigation_history({"id": "P1", "diagnostic": None}), [])
        self.assertEqual(_format_investigation_history({"id": "P1", "diagnostic": "x"}), [])

    def test_empty_session_returns_empty(self):
        problem = {"id": "P1", "diagnostic": {"hypotheses": [], "steps": [], "conclusion": ""}}
        self.assertEqual(_format_investigation_history(problem), [])

    def test_only_conclusion(self):
        problem = {"id": "P1", "diagnostic": {"hypotheses": [], "steps": [], "conclusion": "Итог"}}
        lines = _format_investigation_history(problem)
        self.assertEqual(lines, ["\n--- Как расследовали ---", "Вывод: Итог"])

    def test_long_history_truncated(self):
        problem = {
            "id": "P1",
            "diagnostic": {
                "hypotheses": [
                    {"id": f"H{i}", "text": f"гипотеза {i}", "status": "rejected", "source": "manual"}
                    for i in range(1, 9)
                ],
                "steps": [
                    {"id": f"S{i}", "hypothesis_id": f"H{i}", "description": f"шаг {i}",
                     "status": "done", "outcome": "нет", "result": "rejected"}
                    for i in range(1, 9)
                ],
                "conclusion": "Итог",
            },
        }
        lines = _format_investigation_history(problem)
        step_count = sum(1 for l in lines if l.startswith("  [S"))
        self.assertEqual(step_count, 6)
        self.assertIn("  … и ещё 2 шаг(ов)", lines)
        rej_count = sum(1 for l in lines if l.startswith("  [H"))
        self.assertEqual(rej_count, 6)
        self.assertIn("  … и ещё 2 гипотез(ы)", lines)

    def test_step_without_hypothesis_link_and_without_outcome(self):
        problem = {
            "id": "P1",
            "diagnostic": {
                "hypotheses": [],
                "steps": [
                    {"id": "S1", "description": "Осмотр", "status": "done",
                     "outcome": "", "result": ""},
                ],
                "conclusion": "",
            },
        }
        lines = _format_investigation_history(problem)
        self.assertIn("  [S1] Осмотр", lines)

    def test_show_investigation_history_prints_lines(self):
        buf = StringIO()
        with redirect_stdout(buf):
            _show_investigation_history(_completed_problem())
        out = buf.getvalue()
        self.assertIn("--- Как расследовали ---", out)
        self.assertIn("Причина (подтверждена):", out)
        self.assertIn("  [H1] Пропал модуль x", out)


class TestDoSolveInvestigationSection(unittest.TestCase):

    def test_solve_end_to_end_shows_section(self):
        problem = _completed_problem()

        def fake_resolve(*args, **kwargs):
            return {"id": "P1", "title": "Приложение падает", "status": "solved",
                    "cause": "Пропал модуль x", "solution": "Установил модуль x"}

        buf = StringIO()
        with patch("src.commands.input", side_effect=["Причина", "Установил модуль x", "1"]), \
             patch("src.commands.resolve_problem", side_effect=fake_resolve), \
             patch("src.commands.ai_create_plan",
                   return_value=SimpleNamespace(success=False)), \
             patch("src.commands.ai_analyze_result",
                   return_value=SimpleNamespace(success=False)), \
             patch("src.commands._ask_convert") as mock_convert:
            with redirect_stdout(buf):
                _do_solve(problem, provider=None)
        out = buf.getvalue()
        self.assertIn("Как расследовали", out)
        self.assertIn("Вывод: Пропал зависимый модуль", out)
        self.assertIn("Причина (подтверждена):", out)
        self.assertIn("  [H1] Пропал модуль x", out)
        self.assertIn("Выполненные шаги:", out)
        self.assertIn("Отклонённые гипотезы:", out)
        mock_convert.assert_called_once()

    def test_no_diagnostic_output_has_no_history_byte_same(self):
        problem = {
            "id": "P9",
            "title": "Чистая задача",
            "status": "solved",
            "cause": "c",
            "solution": "s",
        }

        def fake_resolve(*args, **kwargs):
            return {"id": "P9", "title": "Чистая задача", "status": "solved",
                    "cause": "c", "solution": "s"}

        buf = StringIO()
        with patch("src.commands.input", side_effect=["c", "s", "1"]), \
             patch("src.commands.resolve_problem", side_effect=fake_resolve), \
             patch("src.commands.ai_create_plan",
                   return_value=SimpleNamespace(success=False)), \
             patch("src.commands.ai_analyze_result",
                   return_value=SimpleNamespace(success=False)), \
             patch("src.commands._ask_convert"):
            with redirect_stdout(buf):
                _do_solve(problem, provider=None)
        out = buf.getvalue()
        expected = "".join([
            "\n--- Решение ---\n",
            "\n",
            "\nПомогло ли решение?\n",
            "1. Да\n",
            "2. Нет\n",
            "3. Не знаю\n",
            "\n" + "=" * 50 + "\n",
            "SOLVE ЗАВЕРШЁН\n",
            "=" * 50 + "\n",
            "\nПроблема: Чистая задача\n",
            "Статус: РЕШЕНА\n",
            "Причина: c\n",
            "Решение: s\n",
            "\nID: P9\n",
        ])
        self.assertEqual(out, expected)


if __name__ == "__main__":
    unittest.main()
