import unittest
from pathlib import Path
from unittest.mock import patch

from src.ai.provider import NullProvider
from src import diagnostic as _diagnostic
from tests.fake_provider import FakeProvider


PROBLEMS_TEST = Path(__file__).resolve().parent.parent / "data" / "problems_diagcli_test.json"
NOTES_TEST = Path(__file__).resolve().parent.parent / "data" / "notes_diagcli_test.json"


def _clean():
    PROBLEMS_TEST.unlink(missing_ok=True)
    NOTES_TEST.unlink(missing_ok=True)


def _patch_files(fn):
    return fn


class _DiagCliBase(unittest.TestCase):

    def _make_problem(self):
        from src import problems
        from src.solve import start_investigation

        p = problems.create_problem(title="Тест", tags=[])
        start_investigation(p["id"])
        _diagnostic.open_diagnostic(p["id"])
        return problems.get_problem(p["id"])


# ── Вход в диагностику: пустое состояние ─────────────────────────

class TestDiagnosticEnter(unittest.TestCase):

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    def setUp(self):
        _clean()

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    def tearDown(self):
        _clean()

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    @patch("src.commands.input", side_effect=["0"])
    @patch("src.commands.print")
    def test_empty_state(self, mock_print, mock_input):
        from src import problems
        from src.solve import start_investigation

        p = problems.create_problem(title="Тест", tags=[])
        start_investigation(p["id"])

        from src.commands import _diagnostic_loop, _show_diagnostic_state
        result = _diagnostic_loop(problems.get_problem(p["id"]))

        self.assertIsNone(result)
        from src.problems import load_problems
        loaded = load_problems()
        self.assertEqual(loaded[0]["status"], "investigating")
        self.assertIn("diagnostic", loaded[0])

        printed = [str(a[0]) for a in mock_print.call_args_list]
        self.assertTrue(any("Гипотез нет." in v for v in printed))


# ── AI-гипотезы: принять все / выбрать / отказ ───────────────────

class TestDiagnosticAIHypotheses(_DiagCliBase):

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    def setUp(self):
        _clean()

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    def tearDown(self):
        _clean()

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    @patch("src.commands.input", side_effect=["y"])
    @patch("src.commands.print")
    def test_accept_all_ai(self, mock_print, mock_input):
        from src.commands import _diagnostic_add_hypotheses
        provider = FakeProvider()
        problem = self._make_problem()
        _diagnostic_add_hypotheses(problem, provider)

        from src.problems import load_problems
        session = load_problems()[0]["diagnostic"]
        self.assertEqual(len(session["hypotheses"]), 2)
        self.assertTrue(all(h["source"] == "ai" for h in session["hypotheses"]))

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    @patch("src.commands.input", side_effect=["1,2"])
    @patch("src.commands.print")
    def test_select_subset(self, mock_print, mock_input):
        from src.commands import _diagnostic_add_hypotheses
        provider = FakeProvider()
        problem = self._make_problem()
        _diagnostic_add_hypotheses(problem, provider)

        from src.problems import load_problems
        session = load_problems()[0]["diagnostic"]
        self.assertEqual(len(session["hypotheses"]), 2)
        self.assertEqual(
            [h["text"] for h in session["hypotheses"]],
            ["Проверь venv", "Посмотри установленные пакеты"],
        )

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    @patch("src.commands.input", side_effect=["n", "ручная гипотеза", ""])
    @patch("src.commands.print")
    def test_refuse_then_manual(self, mock_print, mock_input):
        from src.commands import _diagnostic_add_hypotheses
        provider = FakeProvider()
        problem = self._make_problem()
        _diagnostic_add_hypotheses(problem, provider)

        from src.problems import load_problems
        session = load_problems()[0]["diagnostic"]
        self.assertEqual(len(session["hypotheses"]), 1)
        self.assertEqual(session["hypotheses"][0]["text"], "ручная гипотеза")
        self.assertEqual(session["hypotheses"][0]["source"], "user")

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    @patch("src.commands.input", side_effect=["вручную", ""])
    @patch("src.commands.print")
    def test_null_provider_manual_fallback(self, mock_print, mock_input):
        from src.commands import _diagnostic_add_hypotheses
        provider = NullProvider()
        problem = self._make_problem()
        _diagnostic_add_hypotheses(problem, provider)

        from src.problems import load_problems
        session = load_problems()[0]["diagnostic"]
        self.assertEqual(session["hypotheses"][0]["text"], "вручную")

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    @patch("src.commands.input", side_effect=[""])
    @patch("src.commands.print")
    def test_empty_result_not_added(self, mock_print, mock_input):
        from src.commands import _diagnostic_add_hypotheses
        provider = NullProvider()
        problem = self._make_problem()
        _diagnostic_add_hypotheses(problem, provider)

        from src.problems import load_problems
        session = load_problems()[0]["diagnostic"]
        self.assertEqual(session["hypotheses"], [])
        printed = [str(a[0]) for a in mock_print.call_args_list]
        self.assertTrue(any("Гипотезы не добавлены" in v for v in printed))


# ── AI-шаг проверки ──────────────────────────────────────────────

class TestDiagnosticAICheck(_DiagCliBase):

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    def setUp(self):
        _clean()

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    def tearDown(self):
        _clean()

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    @patch("src.commands.input", side_effect=["y", "n"])
    @patch("src.commands.print")
    def test_accept_ai_step(self, mock_print, mock_input):
        from src.commands import _diagnostic_add_check
        provider = FakeProvider()
        problem = self._make_problem()
        _diagnostic_add_check(problem, provider)

        from src.problems import load_problems
        session = load_problems()[0]["diagnostic"]
        self.assertEqual(len(session["steps"]), 1)
        self.assertEqual(
            session["steps"][0]["description"],
            "Проверить активацию виртуального окружения",
        )

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    @patch("src.commands.input", side_effect=["n", "проверить вручную", "n"])
    @patch("src.commands.print")
    def test_reject_ai_step_manual(self, mock_print, mock_input):
        from src.commands import _diagnostic_add_check
        provider = FakeProvider()
        problem = self._make_problem()
        _diagnostic_add_check(problem, provider)

        from src.problems import load_problems
        session = load_problems()[0]["diagnostic"]
        self.assertEqual(session["steps"][0]["description"], "проверить вручную")

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    @patch("src.commands.input", side_effect=["проверить вручную", "n"])
    @patch("src.commands.print")
    def test_null_provider_step_manual(self, mock_print, mock_input):
        from src.commands import _diagnostic_add_check
        provider = NullProvider()
        problem = self._make_problem()
        _diagnostic_add_check(problem, provider)

        from src.problems import load_problems
        session = load_problems()[0]["diagnostic"]
        self.assertEqual(session["steps"][0]["description"], "проверить вручную")


# ── Завершение шага ──────────────────────────────────────────────

class TestDiagnosticCompleteStep(_DiagCliBase):

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    def setUp(self):
        _clean()

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    def tearDown(self):
        _clean()

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    @patch("src.commands.input", side_effect=["y", "y", "confirmed", "нашёл проблему"])
    @patch("src.commands.print")
    def test_add_and_immediately_complete(self, mock_print, mock_input):
        from src.commands import _diagnostic_add_check
        provider = FakeProvider()
        problem = self._make_problem()
        _diagnostic_add_check(problem, provider)

        from src.problems import load_problems
        session = load_problems()[0]["diagnostic"]
        self.assertEqual(len(session["steps"]), 1)
        self.assertEqual(session["steps"][0]["status"], "done")

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    @patch("src.commands.input", side_effect=["y", "n"])
    @patch("src.commands.print")
    def test_complete_existing_pending(self, mock_print, mock_input):
        from src.commands import _diagnostic_add_check
        provider = FakeProvider()
        problem = self._make_problem()
        _diagnostic_add_check(problem, provider)

        from src.problems import load_problems
        step_id = load_problems()[0]["diagnostic"]["steps"][0]["id"]

        from src.commands import _diagnostic_complete_step
        fresh = load_problems()[0]
        with patch("src.commands.input", side_effect=[step_id, "confirmed", "ок"]):
            _diagnostic_complete_step(fresh)

        from src.problems import load_problems
        session = load_problems()[0]["diagnostic"]
        self.assertEqual(session["steps"][0]["status"], "done")

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    @patch("src.commands.input", side_effect=["y", "n"])
    @patch("src.commands.print")
    def test_invalid_step_id(self, mock_print, mock_input):
        from src.commands import _diagnostic_add_check
        provider = FakeProvider()
        problem = self._make_problem()
        _diagnostic_add_check(problem, provider)

        from src.commands import _diagnostic_complete_step
        from src.problems import load_problems
        fresh = load_problems()[0]
        with patch("src.commands.input", side_effect=["bad-id"]):
            _diagnostic_complete_step(fresh)

        printed = [str(a[0]) for a in mock_print.call_args_list]
        self.assertTrue(any("Шаг не найден." in v for v in printed))

        session = load_problems()[0]["diagnostic"]
        self.assertEqual(session["steps"][0]["status"], "pending")


# ── Завершение диагностики → причина в solve ────────────────────

class TestDiagnosticFinish(unittest.TestCase):

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    def setUp(self):
        _clean()

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    def tearDown(self):
        _clean()

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    @patch("src.commands.input", side_effect=[
        "1",                   # new problem
        "Ошибка",              # title
        "",                    # description
        "",                    # context
        "",                    # error_message
        "",                    # tags
        "d",                   # investigate: diagnostic
        "4",                   # diag: confirm cause
        "причина",             # conclusion
        "",                    # cause prompt (Enter -> default)
        "",                    # solution
        "1",                   # helped: yes
        "2",                   # convert: no
    ])
    @patch("src.commands.print")
    def test_conclusion_prefills_cause(self, mock_print, mock_input):
        from src.commands import solve_flow
        solve_flow()

        from src.problems import load_problems
        problems = load_problems()
        self.assertEqual(problems[0]["status"], "solved")
        self.assertEqual(problems[0]["cause"], "причина")
        self.assertEqual(
            problems[0]["diagnostic"]["conclusion"],
            "причина",
        )


class TestDiagnosticSaveExit(unittest.TestCase):

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    def setUp(self):
        _clean()

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    def tearDown(self):
        _clean()

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    @patch("src.commands.input", side_effect=[
        "1",                   # new problem
        "Ошибка",              # title
        "",                    # description
        "",                    # context
        "",                    # error_message
        "",                    # tags
        "d",                   # investigate: diagnostic
        "1",                   # diag: add hypotheses
        "гипотеза А",          # manual hypothesis
        "",                    # end hypotheses
        "0",                   # diag: exit
    ])
    @patch("src.commands.print")
    def test_exit_preserves_progress(self, mock_print, mock_input):
        from src.commands import solve_flow
        solve_flow()

        from src.problems import load_problems
        problems = load_problems()
        self.assertEqual(problems[0]["status"], "investigating")
        session = problems[0]["diagnostic"]
        self.assertEqual(len(session["hypotheses"]), 1)
        self.assertTrue(_diagnostic.is_diagnostic_active(problems[0]))

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    @patch("src.commands.input", side_effect=["0"])
    @patch("src.commands.print")
    def test_second_entry_shows_state(self, mock_print, mock_input):
        from src import problems
        from src.solve import start_investigation
        p = problems.create_problem(title="Тест", tags=[])
        start_investigation(p["id"])
        _diagnostic.open_diagnostic(p["id"])
        _diagnostic.add_hypotheses(
            p["id"], [{"text": "гипотеза А", "source": "ai"}]
        )

        from src.commands import _diagnostic_loop
        _diagnostic_loop(problems.get_problem(p["id"]))

        printed = [str(a[0]) for a in mock_print.call_args_list]
        self.assertTrue(any("гипотеза А" in v for v in printed))


# ── Лимит гипотез ────────────────────────────────────────────────

class TestDiagnosticLimit(_DiagCliBase):

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    def setUp(self):
        _clean()

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    def tearDown(self):
        _clean()

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    @patch("src.commands.input", side_effect=["y"])
    @patch("src.commands.print")
    def test_limit_error_shown_no_crash(self, mock_print, mock_input):
        from src import problems
        from src.solve import start_investigation
        p = problems.create_problem(title="Тест", tags=[])
        start_investigation(p["id"])
        _diagnostic.open_diagnostic(p["id"])
        for i in range(_diagnostic.MAX_HYPOTHESES_PER_SESSION):
            _diagnostic.add_hypothesis(p["id"], f"гипотеза {i}")

        from src.commands import _diagnostic_add_hypotheses
        provider = FakeProvider()
        _diagnostic_add_hypotheses(problems.get_problem(p["id"]), provider)

        printed = [str(a[0]) for a in mock_print.call_args_list]
        self.assertTrue(any("Лимит диагностики превышен" in v for v in printed))


# ── Регресс: старые пункты меню investigate ─────────────────────

class TestDiagnosticRegression(unittest.TestCase):

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    def setUp(self):
        _clean()

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    def tearDown(self):
        _clean()

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    @patch("src.commands.input", side_effect=[
        "1",                   # new problem
        "Ошибка",              # title
        "",                    # description
        "",                    # context
        "",                    # error_message
        "",                    # tags
        "3",                   # investigate: save and exit
    ])
    @patch("src.commands.print")
    def test_old_choice_3_still_works(self, mock_print, mock_input):
        from src.commands import solve_flow
        solve_flow()

        from src.problems import load_problems
        problems = load_problems()
        self.assertEqual(problems[0]["status"], "investigating")

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    @patch("src.commands.input", side_effect=[
        "1",                   # new problem
        "Ошибка",              # title
        "",                    # description
        "",                    # context
        "",                    # error_message
        "",                    # tags
        "99",                  # invalid choice
    ])
    @patch("src.commands.print")
    def test_old_invalid_still_works(self, mock_print, mock_input):
        from src.commands import solve_flow
        solve_flow()

        from src.problems import load_problems
        problems = load_problems()
        self.assertEqual(problems[0]["status"], "investigating")


if __name__ == "__main__":
    unittest.main()
