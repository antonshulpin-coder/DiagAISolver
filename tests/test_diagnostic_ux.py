import unittest
from pathlib import Path
from unittest.mock import patch

from src.ai.provider import NullProvider
from src.ai.types import AIResponse
from src import diagnostic as _diagnostic
from tests.fake_provider import FakeProvider


PROBLEMS_TEST = Path(__file__).resolve().parent.parent / "data" / "problems_ux_test.json"
NOTES_TEST = Path(__file__).resolve().parent.parent / "data" / "notes_ux_test.json"


def _clean():
    PROBLEMS_TEST.unlink(missing_ok=True)
    NOTES_TEST.unlink(missing_ok=True)


def _make_diag_problem():
    from src import problems
    from src.solve import start_investigation

    p = problems.create_problem(title="Тест", tags=[])
    start_investigation(p["id"])
    _diagnostic.open_diagnostic(p["id"])
    return problems.get_problem(p["id"])


def _fresh(problem_id):
    from src import problems
    return problems.get_problem(problem_id)


def _add_confirmed(problem_id, text="гипотеза А"):
    sess = _diagnostic.add_hypothesis(problem_id, text)
    hyp_id = sess["hypotheses"][-1]["id"]
    sess2 = _diagnostic.add_check(problem_id, hyp_id, "проверить вариант")
    step_id = sess2["steps"][-1]["id"]
    _diagnostic.complete_check(problem_id, step_id, "воспроизводится", "confirmed")


class _UxBase(unittest.TestCase):

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    def setUp(self):
        _clean()

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    def tearDown(self):
        _clean()


# ── UX1: подтверждение причины одним нажатием ───────────────────

class TestUX1ConfirmCause(_UxBase):

    def _session_from(self, problem_id):
        from src import problems
        return problems.get_problem(problem_id)["diagnostic"]

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    @patch("src.commands.input", side_effect=[""])
    def test_one_confirmed_enter_accepts(self, mock_input):
        from src.commands import _confirm_cause
        problem = _make_diag_problem()
        _add_confirmed(problem["id"], "причина X")
        result = _confirm_cause(problem)
        self.assertEqual(result, "причина X")

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    @patch("src.commands.input", side_effect=["y"])
    def test_one_confirmed_y_accepts(self, mock_input):
        from src.commands import _confirm_cause
        problem = _make_diag_problem()
        _add_confirmed(problem["id"], "причина X")
        result = _confirm_cause(problem)
        self.assertEqual(result, "причина X")

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    @patch("src.commands.input", side_effect=["n", "ручная причина"])
    def test_one_confirmed_declined_manual(self, mock_input):
        from src.commands import _confirm_cause
        problem = _make_diag_problem()
        _add_confirmed(problem["id"], "причина X")
        result = _confirm_cause(problem)
        self.assertEqual(result, "ручная причина")

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    @patch("src.commands.input", side_effect=["2"])
    def test_multiple_confirmed_selection(self, mock_input):
        from src.commands import _confirm_cause
        problem = _make_diag_problem()
        _add_confirmed(problem["id"], "причина Один")
        _add_confirmed(problem["id"], "причина Два")
        result = _confirm_cause(problem)
        self.assertEqual(result, "причина Два")

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    @patch("src.commands.input", side_effect=["9", "фолбэк"])
    def test_multiple_confirmed_invalid_falls_back(self, mock_input):
        from src.commands import _confirm_cause
        problem = _make_diag_problem()
        _add_confirmed(problem["id"], "причина Один")
        _add_confirmed(problem["id"], "причина Два")
        result = _confirm_cause(problem)
        self.assertEqual(result, "фолбэк")

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    @patch("src.commands.input", side_effect=["введённая причина"])
    def test_no_confirmed_manual(self, mock_input):
        from src.commands import _confirm_cause
        problem = _make_diag_problem()
        _diagnostic.add_hypothesis(problem["id"], "гипотеза Б")
        result = _confirm_cause(problem)
        self.assertEqual(result, "введённая причина")

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    @patch("src.commands.input", side_effect=[""])
    def test_no_confirmed_uses_default(self, mock_input):
        from src.commands import _confirm_cause
        problem = _make_diag_problem()
        _diagnostic.finish_diagnostic(problem["id"], "дефолтная причина")
        result = _confirm_cause(problem)
        self.assertEqual(result, "дефолтная причина")

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    @patch("src.commands.input", side_effect=[""])
    def test_no_confirmed_empty_returns_none(self, mock_input):
        from src.commands import _confirm_cause
        problem = _make_diag_problem()
        result = _confirm_cause(problem)
        self.assertIsNone(result)

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    @patch("src.commands.input", side_effect=["4", ""])
    @patch("src.commands.print")
    def test_loop_item4_uses_confirmed(self, mock_print, mock_input):
        from src.commands import _diagnostic_loop
        from src import problems as _problems
        problem = _make_diag_problem()
        _add_confirmed(problem["id"], "готовая причина")
        fresh = _problems.get_problem(problem["id"])
        result = _diagnostic_loop(fresh)
        self.assertEqual(result, "готовая причина")
        from src.problems import load_problems
        self.assertEqual(
            load_problems()[0]["diagnostic"]["conclusion"],
            "готовая причина",
        )


# ── UX2: история расследования в состоянии ──────────────────────

class TestUX2History(_UxBase):

    def _printed(self, mock_print):
        return [str(a[0]) for a in mock_print.call_args_list]

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    @patch("src.commands.print")
    def test_history_done_steps_displayed(self, mock_print):
        from src.commands import _show_diagnostic_state
        problem = _make_diag_problem()
        _add_confirmed(problem["id"], "гипотеза А")
        _show_diagnostic_state(_fresh(problem["id"]))

        printed = self._printed(mock_print)
        joined = "\n".join(printed)
        self.assertIn("История проверок:", joined)
        self.assertIn("проверить вариант", joined)
        self.assertIn("гипотеза А", joined)
        self.assertIn("подтверждена", joined)

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    @patch("src.commands.print")
    def test_history_terminal_block_displayed(self, mock_print):
        from src.commands import _show_diagnostic_state
        problem = _make_diag_problem()
        _add_confirmed(problem["id"], "подтверждённая")
        _diagnostic.add_hypothesis(problem["id"], "обычная")
        _show_diagnostic_state(_fresh(problem["id"]))

        printed = self._printed(mock_print)
        joined = "\n".join(printed)
        self.assertIn("Проверено/Отклонено:", joined)
        self.assertIn("подтверждённая", joined)
        self.assertIn("подтверждена", joined)

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    @patch("src.commands.print")
    def test_empty_history_hidden(self, mock_print):
        from src.commands import _show_diagnostic_state
        problem = _make_diag_problem()
        _diagnostic.add_hypothesis(problem["id"], "гипотеза А")
        _show_diagnostic_state(_fresh(problem["id"]))

        printed = self._printed(mock_print)
        joined = "\n".join(printed)
        self.assertNotIn("История проверок:", joined)
        self.assertNotIn("Проверено/Отклонено:", joined)

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    @patch("src.commands.print")
    def test_history_truncated(self, mock_print):
        from src.commands import _show_diagnostic_state, _DIAG_HISTORY_LIMIT
        problem = _make_diag_problem()
        n = _DIAG_HISTORY_LIMIT + 3
        for i in range(n):
            _add_confirmed(problem["id"], f"гипотеза {i}")
        _show_diagnostic_state(_fresh(problem["id"]))

        printed = self._printed(mock_print)
        joined = "\n".join(printed)
        self.assertIn("и ещё", joined)
        # в блоке истории показывается не более лимита строк описаний
        hist_count = sum(
            1 for ln in joined.splitlines() if ln.strip().startswith("проверить вариант")
        )
        self.assertLessEqual(hist_count, _DIAG_HISTORY_LIMIT)

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    @patch("src.commands.print")
    def test_state_before_after_complete(self, mock_print):
        from src.commands import _show_diagnostic_state
        problem = _make_diag_problem()
        _diagnostic.add_hypothesis(problem["id"], "гипотеза А")
        _show_diagnostic_state(_fresh(problem["id"]))
        before = self._printed(mock_print)
        self.assertNotIn("История проверок:", "\n".join(before))

        mock_print.reset_mock()
        _add_confirmed(problem["id"], "другая")
        _show_diagnostic_state(_fresh(problem["id"]))
        after = self._printed(mock_print)
        self.assertIn("История проверок:", "\n".join(after))


# ── UX3: AI-подсказка «что дальше» ──────────────────────────────

class TestUX3Hint(_UxBase):

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    @patch("src.commands.input", side_effect=["y", "n"])
    @patch("src.commands.print")
    def test_hint_stuck_session_adds_check(self, mock_print, mock_input):
        from src.commands import _diagnostic_ai_hint
        provider = FakeProvider()
        problem = _make_diag_problem()
        _diagnostic.add_hypothesis(problem["id"], "гипотеза А")
        _diagnostic_ai_hint(_fresh(problem["id"]), provider)

        self.assertGreaterEqual(provider.call_count("suggest_next_check"), 1)
        from src.problems import load_problems
        session = load_problems()[0]["diagnostic"]
        self.assertEqual(len(session["steps"]), 1)
        self.assertEqual(
            session["steps"][0]["description"],
            "Проверить активацию виртуального окружения",
        )

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    @patch("src.commands.input", side_effect=["n"])
    @patch("src.commands.print")
    def test_hint_declined_no_add(self, mock_print, mock_input):
        from src.commands import _diagnostic_ai_hint
        provider = FakeProvider()
        problem = _make_diag_problem()
        _diagnostic.add_hypothesis(problem["id"], "гипотеза А")
        _diagnostic_ai_hint(_fresh(problem["id"]), provider)

        from src.problems import load_problems
        session = load_problems()[0]["diagnostic"]
        self.assertEqual(session["steps"], [])

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    @patch("src.commands.input", side_effect=["n"])
    @patch("src.commands.print")
    def test_hint_pending_ai_not_called(self, mock_print, mock_input):
        from src.commands import _diagnostic_ai_hint
        provider = FakeProvider()
        problem = _make_diag_problem()
        _diagnostic.add_hypothesis(problem["id"], "гипотеза А")
        fresh = _fresh(problem["id"])
        hyp_id = fresh["diagnostic"]["hypotheses"][0]["id"]
        _diagnostic.suggest_check(problem["id"], hyp_id)
        _diagnostic_ai_hint(_fresh(problem["id"]), provider)

        self.assertEqual(provider.call_count("suggest_next_check"), 0)
        printed = [str(a[0]) for a in mock_print.call_args_list]
        self.assertTrue(any("Подсказка недоступна" in v for v in printed))
        from src.problems import load_problems
        steps = load_problems()[0]["diagnostic"]["steps"]
        # существующий pending-шаг остаётся, новых не добавлено
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0]["status"], "pending")

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    @patch("src.commands.input", side_effect=["n"])
    @patch("src.commands.print")
    def test_hint_no_open_hyp_ai_not_called(self, mock_print, mock_input):
        from src.commands import _diagnostic_ai_hint
        provider = FakeProvider()
        problem = _make_diag_problem()
        _diagnostic_ai_hint(_fresh(problem["id"]), provider)

        self.assertEqual(provider.call_count("suggest_next_check"), 0)
        printed = [str(a[0]) for a in mock_print.call_args_list]
        self.assertTrue(any("Подсказка недоступна" in v for v in printed))

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    @patch("src.commands.print")
    def test_hint_success_false_message(self, mock_print):
        from src.commands import _diagnostic_ai_hint
        provider = FakeProvider(
            responses={"suggest_next_check": AIResponse(success=False, content="")}
        )
        problem = _make_diag_problem()
        _diagnostic.add_hypothesis(problem["id"], "гипотеза А")
        _diagnostic_ai_hint(_fresh(problem["id"]), provider)

        printed = [str(a[0]) for a in mock_print.call_args_list]
        self.assertTrue(any("Не удалось получить подсказку" in v for v in printed))
        from src.problems import load_problems
        self.assertEqual(load_problems()[0]["diagnostic"]["steps"], [])

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    @patch("src.commands.print")
    def test_hint_null_provider_no_ai(self, mock_print):
        from src.commands import _diagnostic_ai_hint
        provider = NullProvider()
        problem = _make_diag_problem()
        _diagnostic.add_hypothesis(problem["id"], "гипотеза А")
        _diagnostic_ai_hint(_fresh(problem["id"]), provider)

        printed = [str(a[0]) for a in mock_print.call_args_list]
        self.assertTrue(any("Подсказка недоступна" in v for v in printed))


if __name__ == "__main__":
    unittest.main()
