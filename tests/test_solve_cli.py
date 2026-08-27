import unittest
from pathlib import Path
from unittest.mock import patch

from src.solve import SolveError


PROBLEMS_TEST = Path(__file__).resolve().parent.parent / "data" / "problems_cli_test.json"
NOTES_TEST = Path(__file__).resolve().parent.parent / "data" / "notes_cli_test.json"


def _clean():
    PROBLEMS_TEST.unlink(missing_ok=True)
    NOTES_TEST.unlink(missing_ok=True)


# ── solve() delegates to solve_flow() ─────────────────────────────

class TestSolveDelegation(unittest.TestCase):

    @patch("src.commands.solve_flow")
    def test_solve_calls_solve_flow(self, mock_flow):
        from src.commands import solve
        solve()
        mock_flow.assert_called_once()


# ── SOLVE menu: выход ────────────────────────────────────────────

class TestSolveMenuBack(unittest.TestCase):

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
    def test_choice_0_returns(self, mock_print, mock_input):
        from src.commands import solve_flow
        solve_flow()

        from src.problems import load_problems
        self.assertEqual(load_problems(), [])


# ── SOLVE menu: неверный выбор ───────────────────────────────────

class TestSolveMenuInvalid(unittest.TestCase):

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
    @patch("src.commands.input", side_effect=["99"])
    @patch("src.commands.print")
    def test_invalid_choice_returns(self, mock_print, mock_input):
        from src.commands import solve_flow
        solve_flow()

        from src.problems import load_problems
        self.assertEqual(load_problems(), [])


# ── Пустой заголовок ─────────────────────────────────────────────

class TestSolveFlowEmptyTitle(unittest.TestCase):

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
    @patch("src.commands.input", side_effect=["1", ""])
    @patch("src.commands.print")
    def test_empty_title_returns(self, mock_print, mock_input):
        from src.commands import solve_flow
        solve_flow()

        from src.problems import load_problems
        self.assertEqual(load_problems(), [])


# ── Выход из investigation (choice 3) ────────────────────────────

class TestSolveFlowExit(unittest.TestCase):

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
        "1",                   # SOLVE menu: new problem
        "Ошибка Python",       # title
        "При запуске падает",   # description
        "Windows 11",          # context
        "ModuleNotFound",      # error_message
        "python, flask",       # tags
        "3",                   # investigate menu: save and exit
    ])
    @patch("src.commands.print")
    def test_choice_3_saves_and_returns(self, mock_print, mock_input):
        from src.commands import solve_flow
        solve_flow()

        from src.problems import load_problems
        problems = load_problems()
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0]["status"], "investigating")


# ── Полный сценарий: helped=True → solved → convert ──────────────

class TestSolveFlowHappyPath(unittest.TestCase):

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
        "1",                   # SOLVE menu: new problem
        "Ошибка Python",       # title
        "При запуске падает",   # description
        "Windows 11",          # context
        "ModuleNotFound",      # error_message
        "python, flask",       # tags
        "2",                   # investigate menu: continue
        "venv не активирован", # cause
        "Активировал venv",   # solution
        "1",                   # helped: yes
        "1",                   # convert: yes
    ])
    @patch("src.commands.print")
    def test_full_happy_path(self, mock_print, mock_input):
        from src.commands import solve_flow
        solve_flow()

        from src.problems import load_problems
        problems = load_problems()
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0]["status"], "solved")
        self.assertEqual(problems[0]["cause"], "venv не активирован")
        self.assertEqual(problems[0]["solution"], "Активировал venv")
        self.assertTrue(problems[0]["helped"])
        self.assertIsNotNone(problems[0]["related_record_id"])

        from src.storage import load_notes
        notes = load_notes()
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["type"], "solution")


# ── helped=False → failed, без конвертации ────────────────────────

class TestSolveFlowHelpedNo(unittest.TestCase):

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
        "1",                   # SOLVE menu: new problem
        "Ошибка Python",       # title
        "Падает",              # description
        "",                    # context
        "",                    # error_message
        "",                    # tags
        "2",                   # investigate menu: continue
        "Причина",            # cause
        "Решение",            # solution
        "2",                   # helped: no
        "2",                   # convert: no
    ])
    @patch("src.commands.print")
    def test_helped_no_failed_no_convert(self, mock_print, mock_input):
        from src.commands import solve_flow
        solve_flow()

        from src.problems import load_problems
        problems = load_problems()
        self.assertEqual(problems[0]["status"], "failed")
        self.assertFalse(problems[0]["helped"])
        self.assertIsNone(problems[0]["related_record_id"])

        from src.storage import load_notes
        notes = load_notes()
        self.assertEqual(len(notes), 0)


# ── helped=None → solving, предложение повтора ────────────────────

class TestSolveFlowHelpedNone(unittest.TestCase):

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
        "1",                   # SOLVE menu: new problem
        "Ошибка",              # title
        "",                    # description
        "",                    # context
        "",                    # error_message
        "",                    # tags
        "2",                   # investigate menu: continue
        "Причина",            # cause
        "Решение",            # solution
        "3",                   # helped: don't know
        "2",                   # _ask_retry_or_continue: return to menu
    ])
    @patch("src.commands.print")
    def test_helped_none_keeps_solving(self, mock_print, mock_input):
        from src.commands import solve_flow
        solve_flow()

        from src.problems import load_problems
        problems = load_problems()
        self.assertEqual(problems[0]["status"], "solving")
        self.assertIsNone(problems[0]["helped"])


# ── helped=None → повтор решения ──────────────────────────────────

class TestSolveFlowHelpedNoneRetry(unittest.TestCase):

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
        "1",                   # SOLVE menu: new problem
        "Ошибка",              # title
        "",                    # description
        "",                    # context
        "",                    # error_message
        "",                    # tags
        "2",                   # investigate menu: continue
        "Причина 1",          # cause
        "Решение 1",          # solution
        "3",                   # helped: don't know
        "1",                   # _ask_retry_or_continue: continue solving
        "Причина 2",          # cause (retry)
        "Решение 2",          # solution (retry)
        "1",                   # helped: yes
        "2",                   # convert: no
    ])
    @patch("src.commands.print")
    def test_helped_none_retry_then_solved(self, mock_print, mock_input):
        from src.commands import solve_flow
        solve_flow()

        from src.problems import load_problems
        problems = load_problems()
        self.assertEqual(problems[0]["status"], "solved")
        self.assertTrue(problems[0]["helped"])


# ── Неверный выбор в investigate ──────────────────────────────────

class TestSolveFlowInvalidChoice(unittest.TestCase):

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
        "1",                   # SOLVE menu: new problem
        "Ошибка",              # title
        "",                    # description
        "",                    # context
        "",                    # error_message
        "",                    # tags
        "99",                  # invalid choice
    ])
    @patch("src.commands.print")
    def test_invalid_choice_keeps_investigating(self, mock_print, mock_input):
        from src.commands import solve_flow
        solve_flow()

        from src.problems import load_problems
        problems = load_problems()
        self.assertEqual(problems[0]["status"], "investigating")


# ── KeyboardInterrupt ─────────────────────────────────────────────

class TestSolveFlowInterrupt(unittest.TestCase):

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
    @patch("src.commands.input", side_effect=KeyboardInterrupt)
    @patch("src.commands.print")
    def test_keyboard_interrupt_handled(self, mock_print, mock_input):
        from src.commands import solve_flow
        solve_flow()

        printed_values = [str(args[0]) for args in mock_print.call_args_list]
        self.assertTrue(any("Возврат в главное меню" in v for v in printed_values))


# ── SolveError ────────────────────────────────────────────────────

class TestSolveFlowError(unittest.TestCase):

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
    @patch("src.commands.start_investigation", side_effect=SolveError("test error"))
    @patch("src.commands.input", side_effect=[
        "1",                   # SOLVE menu: new problem
        "Ошибка",              # title
        "",                    # description
        "",                    # context
        "",                    # error_message
        "",                    # tags
    ])
    @patch("src.commands.print")
    def test_solve_error_displayed(self, mock_print, mock_input, _mock_inv):
        from src.commands import solve_flow
        solve_flow()

        printed_values = [str(args[0]) for args in mock_print.call_args_list]
        self.assertTrue(any("Ошибка: test error" in v for v in printed_values))


# ── choice 1: использование найденного решения ─────────────────────

class TestSolveFlowUseExisting(unittest.TestCase):

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
    @patch("src.commands.find_similar")
    @patch("src.commands.input", side_effect=[
        "1",                   # SOLVE menu: new problem
        "Ошибка",              # title
        "",                    # description
        "",                    # context
        "",                    # error_message
        "python",              # tags
        "1",                   # investigate menu: use existing
        "1",                   # pick record
        "да",                  # try it
        "Причина",            # cause
        "Решение",            # solution
        "1",                   # helped: yes
        "2",                   # convert: no
    ])
    @patch("src.commands.print")
    def test_choice_1_use_existing(self, mock_print, mock_input, mock_find):
        mock_find.return_value = (
            [({"id": "abc", "title": "Guide", "type": "note",
              "text": "Use pip install", "tags": ["python"]}, 15.0)],
            [],
        )

        from src.commands import solve_flow
        solve_flow()

        from src.problems import load_problems
        problems = load_problems()
        self.assertEqual(problems[0]["status"], "solved")


# ── Продолжение существующей проблемы: investigating ─────────────

class TestContinueExistingInvestigating(unittest.TestCase):

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
    def _create_problem(self, status="investigating"):
        from src import problems
        p = problems.create_problem(title="Existing", tags=["test"])
        if status != "new":
            from src.solve import start_investigation
            start_investigation(p["id"])
        if status == "solving":
            from src.solve import start_solving
            start_solving(p["id"])
        if status == "failed":
            from src.solve import start_solving, resolve_problem
            start_solving(p["id"])
            resolve_problem(p["id"], cause="c", solution="s", helped=False)
        return p

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    @patch("src.commands.input", side_effect=[
        "2",                   # SOLVE menu: continue existing
        "1",                   # pick problem
        "3",                   # investigate: save and exit
    ])
    @patch("src.commands.print")
    def test_continue_investigating(self, mock_print, mock_input):
        self._create_problem("investigating")

        from src.commands import solve_flow
        solve_flow()

        from src.problems import load_problems
        problems = load_problems()
        self.assertEqual(problems[0]["status"], "investigating")


# ── Продолжение существующей проблемы: solving → пометить решённой ─

class TestContinueExistingSolvingSolved(unittest.TestCase):

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
    def _create_problem(self):
        from src import problems
        from src.solve import start_investigation, start_solving
        p = problems.create_problem(title="Active", tags=["test"])
        start_investigation(p["id"])
        start_solving(p["id"])
        return p

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    @patch("src.commands.input", side_effect=[
        "2",                   # SOLVE menu: continue existing
        "1",                   # pick problem
        "2",                   # solving: mark as solved
        "2",                   # convert: no
    ])
    @patch("src.commands.print")
    def test_solving_mark_solved(self, mock_print, mock_input):
        self._create_problem()

        from src.commands import solve_flow
        solve_flow()

        from src.problems import load_problems
        problems = load_problems()
        self.assertEqual(problems[0]["status"], "solved")


# ── Продолжение: solving → пометить нерешённой ───────────────────

class TestContinueExistingSolvingFailed(unittest.TestCase):

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
    def _create_problem(self):
        from src import problems
        from src.solve import start_investigation, start_solving
        p = problems.create_problem(title="Active", tags=["test"])
        start_investigation(p["id"])
        start_solving(p["id"])
        return p

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    @patch("src.commands.input", side_effect=[
        "2",                   # SOLVE menu: continue existing
        "1",                   # pick problem
        "3",                   # solving: mark as failed
        "2",                   # convert: no
    ])
    @patch("src.commands.print")
    def test_solving_mark_failed(self, mock_print, mock_input):
        self._create_problem()

        from src.commands import solve_flow
        solve_flow()

        from src.problems import load_problems
        problems = load_problems()
        self.assertEqual(problems[0]["status"], "failed")


# ── Продолжение: failed → повтор попытки ─────────────────────────

class TestContinueExistingFailedRetry(unittest.TestCase):

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
    def _create_problem(self):
        from src import problems
        from src.solve import start_investigation, start_solving, resolve_problem
        p = problems.create_problem(title="Failed", tags=["test"])
        start_investigation(p["id"])
        start_solving(p["id"])
        resolve_problem(p["id"], cause="c", solution="s", helped=False)
        return p

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    @patch("src.commands.input", side_effect=[
        "2",                   # SOLVE menu: continue existing
        "1",                   # pick problem
        "1",                   # failed: retry
        "Новая причина",       # cause
        "Новое решение",      # solution
        "1",                   # helped: yes
        "2",                   # convert: no
    ])
    @patch("src.commands.print")
    def test_failed_retry_then_solved(self, mock_print, mock_input):
        self._create_problem()

        from src.commands import solve_flow
        solve_flow()

        from src.problems import load_problems
        problems = load_problems()
        self.assertEqual(problems[0]["status"], "solved")
        self.assertEqual(problems[0]["cause"], "Новая причина")
        self.assertEqual(problems[0]["solution"], "Новое решение")


# ── Продолжение: failed → архивирование ──────────────────────────

class TestContinueExistingFailedArchive(unittest.TestCase):

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
    def _create_problem(self):
        from src import problems
        from src.solve import start_investigation, start_solving, resolve_problem
        p = problems.create_problem(title="Failed", tags=["test"])
        start_investigation(p["id"])
        start_solving(p["id"])
        resolve_problem(p["id"], cause="c", solution="s", helped=False)
        return p

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    @patch("src.commands.input", side_effect=[
        "2",                   # SOLVE menu: continue existing
        "1",                   # pick problem
        "2",                   # failed: archive
    ])
    @patch("src.commands.print")
    def test_failed_archive(self, mock_print, mock_input):
        self._create_problem()

        from src.commands import solve_flow
        solve_flow()

        from src.problems import load_problems
        problems = load_problems()
        self.assertEqual(problems[0]["status"], "archived")


# ── Продолжение: failed → конвертация в базу знаний ──────────────

class TestContinueExistingFailedConvert(unittest.TestCase):

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
    def _create_problem(self):
        from src import problems
        from src.solve import start_investigation, start_solving, resolve_problem
        p = problems.create_problem(title="Failed", tags=["test"])
        start_investigation(p["id"])
        start_solving(p["id"])
        resolve_problem(p["id"], cause="c", solution="s", helped=False)
        return p

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    @patch("src.commands.input", side_effect=[
        "2",                   # SOLVE menu: continue existing
        "1",                   # pick problem
        "3",                   # failed: convert to knowledge
    ])
    @patch("src.commands.print")
    def test_failed_convert(self, mock_print, mock_input):
        self._create_problem()

        from src.commands import solve_flow
        solve_flow()

        from src.storage import load_notes
        notes = load_notes()
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["type"], "solution")


# ── Продолжение: нет активных проблем ─────────────────────────────

class TestContinueExistingNoActive(unittest.TestCase):

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
        "2",                   # SOLVE menu: continue existing
    ])
    @patch("src.commands.print")
    def test_no_active_problems(self, mock_print, mock_input):
        from src.commands import solve_flow
        solve_flow()

        printed_values = [str(args[0]) for args in mock_print.call_args_list]
        self.assertTrue(any("Нет проблем для продолжения" in v for v in printed_values))


# ── Продолжение: отмена выбора ────────────────────────────────────

class TestContinueExistingCancel(unittest.TestCase):

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
        "2",                   # SOLVE menu: continue existing
        "1",                   # pick problem
        "",                    # empty = cancel in _handle_existing_problem? No...
    ])
    @patch("src.commands.print")
    def test_cancel_pick_returns(self, mock_print, mock_input):
        from src import problems
        from src.solve import start_investigation
        p = problems.create_problem(title="Test")
        start_investigation(p["id"])

        from src.commands import solve_flow
        solve_flow()

        from src.problems import load_problems
        all_problems = load_problems()
        self.assertEqual(all_problems[0]["status"], "investigating")


if __name__ == "__main__":
    unittest.main()
