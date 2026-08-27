import unittest
from pathlib import Path
from unittest.mock import patch

from src import diagnostic as _diagnostic
from src.ai.context import MAX_SEARCH_RESULTS
from src.solve import _build_knowledge_text, _build_investigation_text


PROBLEMS_TEST = Path(__file__).resolve().parent.parent / "data" / "problems_diagctx_test.json"
NOTES_TEST = Path(__file__).resolve().parent.parent / "data" / "notes_diagctx_test.json"


def _clean():
    PROBLEMS_TEST.unlink(missing_ok=True)
    NOTES_TEST.unlink(missing_ok=True)


def _plain_problem():
    """Проблема без диагностики (обычный SOLVE)."""
    return {
        "id": "p1",
        "title": "Ошибка Python",
        "description": "Падает при запуске",
        "context": "Windows 11",
        "error_message": "ModuleNotFound",
        "cause": "venv сломан",
        "solution": "пересоздал venv",
        "helped": True,
        "status": "solved",
        "tags": ["python"],
    }


def _expected_plain_text(problem):
    parts = ["Статус: решена"]
    if problem.get("description"):
        parts.append(problem["description"])
    if problem.get("context"):
        parts.append(f"Контекст: {problem['context']}")
    if problem.get("error_message"):
        parts.append(f"Ошибка: {problem['error_message']}")
    if problem.get("cause"):
        parts.append(f"Причина: {problem['cause']}")
    if problem.get("solution"):
        parts.append(f"Решение: {problem['solution']}")
    if problem.get("helped") is not None:
        helped_label = "помогло" if problem["helped"] else "не помогло"
        parts.append(f"Результат: {helped_label}")
    return "\n\n".join(parts)


def _full_diagnostic_problem():
    """Проблема со статусом solved и полной сессией диагностики."""
    from src import problems
    from src.solve import start_investigation, start_solving, resolve_problem

    p = problems.create_problem(title="Ошибка", tags=["test"])
    start_investigation(p["id"])
    _diagnostic.open_diagnostic(p["id"])

    _diagnostic.add_hypothesis(p["id"], "сломан venv", source="ai")
    h1 = _diagnostic.get_diagnostic(p["id"])["hypotheses"][0]
    _diagnostic.add_hypothesis(p["id"], "нет пакета")
    h2 = _diagnostic.get_diagnostic(p["id"])["hypotheses"][1]

    s1 = _diagnostic.add_check(p["id"], h1["id"], "активировал venv")["steps"][-1]
    _diagnostic.complete_check(p["id"], s1["id"], "заработало", "confirmed")
    s2 = _diagnostic.add_check(p["id"], h2["id"], "pip install")["steps"][-1]
    _diagnostic.complete_check(p["id"], s2["id"], "ошибка", "rejected")

    _diagnostic.finish_diagnostic(p["id"], "venv сломан")

    start_solving(p["id"])
    resolve_problem(p["id"], cause="venv сломан", solution="пересоздал venv", helped=True)
    return problems.get_problem(p["id"])


class _FileTestCase(unittest.TestCase):

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    def setUp(self):
        _clean()

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    def tearDown(self):
        _clean()


# ── Нет диагностики: текст идентичен старому ────────────────────

class TestNoDiagnostic(_FileTestCase):

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    def test_byte_identical_without_diagnostic(self):
        problem = _plain_problem()
        self.assertEqual(_build_knowledge_text(problem), _expected_plain_text(problem))

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    def test_no_diagnostic_section_absent(self):
        problem = _plain_problem()
        self.assertNotIn("Расследование:", _build_knowledge_text(problem))

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    def test_empty_diagnostic_no_section(self):
        from src import problems
        from src.solve import start_investigation
        p = problems.create_problem(title="Тест", tags=[])
        start_investigation(p["id"])
        _diagnostic.open_diagnostic(p["id"])
        problem = problems.get_problem(p["id"])
        from src.problems import load_problems
        self.assertEqual(_build_investigation_text(problem), "")


# ── Диагностика активна ─────────────────────────────────────────

class TestActiveDiagnostic(_FileTestCase):

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    def test_section_present_with_hypotheses(self):
        problem = _full_diagnostic_problem()
        text = _build_knowledge_text(problem)
        self.assertIn("Расследование:", text)
        self.assertIn("Гипотезы:", text)

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    def test_hypotheses_with_source_and_status(self):
        problem = _full_diagnostic_problem()
        text = _build_knowledge_text(problem)
        self.assertIn("сломан venv", text)
        self.assertIn("нет пакета", text)
        self.assertIn("(AI)", text)
        self.assertIn("(вручную)", text)

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    def test_conclusion_present(self):
        problem = _full_diagnostic_problem()
        text = _build_knowledge_text(problem)
        self.assertIn("Вывод: venv сломан", text)


# ── Терминальные гипотезы ───────────────────────────────────────

class TestTerminalHypotheses(_FileTestCase):

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    def test_confirmed_and_rejected_shown(self):
        problem = _full_diagnostic_problem()
        text = _build_knowledge_text(problem)
        self.assertIn("подтверждена", text)
        self.assertIn("отклонена", text)

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    def test_steps_with_results_and_affected_hypotheses(self):
        problem = _full_diagnostic_problem()
        text = _build_knowledge_text(problem)
        self.assertIn("Проверки:", text)
        self.assertIn("активировал venv", text)
        self.assertIn("confirmed", text)
        self.assertIn("rejected", text)
        self.assertIn("pip install", text)


# ── Лимиты / приоритет ──────────────────────────────────────────

class TestLimits(_FileTestCase):

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    def test_truncation_keeps_conclusion_priority(self):
        hypotheses = [
            {"id": f"h{i}", "text": f"гипотеза {i}", "status": "open",
             "source": "ai", "confidence": 0.0}
            for i in range(30)
        ]
        steps = [
            {"id": f"s{i}", "hypothesis_id": "h0", "description": f"шаг {i}",
             "status": "done", "outcome": "ок", "result": "confirmed",
             "completed_at": ""}
            for i in range(40)
        ]
        problem = {
            "id": "p-limit",
            "title": "T",
            "description": "",
            "context": "",
            "error_message": "",
            "tags": [],
            "status": "solved",
            "cause": "причина",
            "solution": "решение",
            "helped": True,
            "diagnostic": {
                "started_at": "x",
                "hypotheses": hypotheses,
                "steps": steps,
                "conclusion": "корневая причина",
            },
        }
        text = _build_knowledge_text(problem)
        self.assertIn("Вывод: корневая причина", text)
        hypothesis_lines = [l for l in text.splitlines() if l.startswith("- [")]
        self.assertLessEqual(len(hypothesis_lines), MAX_SEARCH_RESULTS * 2)
        check_lines = [
            l for l in text.splitlines()
            if l.startswith("- ") and "→" in l and "шаг" in l
        ]
        self.assertLessEqual(len(check_lines), MAX_SEARCH_RESULTS)


# ── Readonly / изоляция ─────────────────────────────────────────

class TestIsolation(_FileTestCase):

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    def test_get_diagnostic_context_readonly(self):
        problem = _full_diagnostic_problem()
        session = problem["diagnostic"]
        snapshot = {
            k: list(v) if isinstance(v, list) else v
            for k, v in session.items()
        }
        _diagnostic.get_diagnostic_context(problem)
        self.assertEqual(problem["diagnostic"], snapshot)

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    def test_full_ai_response_not_written_to_problems_json(self):
        from src.solve import convert_to_knowledge
        problem = _full_diagnostic_problem()
        convert_to_knowledge(problem["id"])

        from src.problems import load_problems
        loaded = load_problems()[0]
        for s in loaded["diagnostic"].get("steps", []):
            self.assertNotIn("ai_response", s)
            self.assertNotIn("raw", s)

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    def test_convert_to_knowledge_includes_investigation(self):
        from src.solve import convert_to_knowledge
        problem = _full_diagnostic_problem()
        record = convert_to_knowledge(problem["id"])
        self.assertIn("Расследование:", record["text"])
        self.assertIn("venv сломан", record["text"])


# ── Сигнатурная совместимость ───────────────────────────────────

class TestSignature(_FileTestCase):

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    def test_call_without_new_param_works(self):
        problem = _full_diagnostic_problem()
        self.assertIn("Расследование:", _build_knowledge_text(problem))

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    def test_explicit_diagnostic_context_param(self):
        problem = _full_diagnostic_problem()
        session = problem["diagnostic"]
        text = _build_knowledge_text(problem, diagnostic_context=session)
        self.assertIn("Расследование:", text)

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    def test_non_dict_diagnostic_returns_plain(self):
        problem = _plain_problem()
        text = _build_knowledge_text(problem, diagnostic_context="not a dict")
        self.assertEqual(text, _expected_plain_text(problem))


if __name__ == "__main__":
    unittest.main()
