import unittest
from pathlib import Path
from unittest.mock import patch

from src.problems import create_problem, ProblemError
from src.solve import (
    build_search_query,
    find_similar,
    start_investigation,
    start_solving,
    resolve_problem,
    archive_problem,
    convert_to_knowledge,
    get_problem_summary,
    SolveError,
    _TRANSITIONS,
)


PROBLEMS_TEST = Path(__file__).resolve().parent.parent / "data" / "problems_solve_test.json"
NOTES_TEST = Path(__file__).resolve().parent.parent / "data" / "notes_solve_test.json"


def _clean():
    PROBLEMS_TEST.unlink(missing_ok=True)
    NOTES_TEST.unlink(missing_ok=True)


def _make_problem(**overrides):
    defaults = dict(
        title="Ошибка Python",
        description="При запуске падает",
        context="Windows 11",
        error_message="ModuleNotFoundError: No module named 'flask'",
        tags=["python", "flask"],
    )
    defaults.update(overrides)
    return create_problem(**defaults)


def _patchboth(fn):
    return patch("src.solve._problems.DATA_FILE", PROBLEMS_TEST)(
        patch("src.solve._storage.DATA_FILE", NOTES_TEST)(fn)
    )


# ── build_search_query ────────────────────────────────────────────

class TestBuildSearchQuery(unittest.TestCase):

    def test_title_only(self):
        q = build_search_query({"title": "Flask error"})
        self.assertEqual(q, "Flask error")

    def test_title_error_message(self):
        q = build_search_query({
            "title": "Flask",
            "error_message": "ModuleNotFound",
            "tags": [],
        })
        self.assertEqual(q, "Flask ModuleNotFound")

    def test_title_error_tags(self):
        q = build_search_query({
            "title": "Flask",
            "error_message": "ModuleNotFound",
            "tags": ["python", "vscode"],
        })
        self.assertEqual(q, "Flask ModuleNotFound python vscode")

    def test_empty_problem(self):
        q = build_search_query({"title": "", "error_message": "", "tags": []})
        self.assertEqual(q, "")

    def test_tags_only(self):
        q = build_search_query({"title": "", "error_message": "", "tags": ["a", "b"]})
        self.assertEqual(q, "a b")

    def test_missing_fields(self):
        q = build_search_query({})
        self.assertEqual(q, "")


# ── find_similar ──────────────────────────────────────────────────

class TestFindSimilar(unittest.TestCase):

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
    def test_finds_knowledge_records(self):
        from src.storage import create_record
        create_record(title="Flask guide", text="Use pip install flask", tags=["flask"])

        problem = _make_problem()
        kr, pr = find_similar(problem)
        titles = [r["title"] for r, _ in kr]
        self.assertIn("Flask guide", titles)

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    def test_finds_problems(self):
        _make_problem(title="Flask import error", error_message="ModuleNotFound", tags=["flask"])
        problem2 = _make_problem(title="Flask crash", error_message="RuntimeError", tags=["flask"])

        kr, pr = find_similar(problem2)
        problem_titles = [p["title"] for p, _ in pr]
        self.assertIn("Flask import error", problem_titles)

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    def test_returns_empty_when_no_match(self):
        problem = {"title": "kubernetes pod crash", "tags": ["k8s"],
                    "error_message": "", "description": ""}
        kr, pr = find_similar(problem)
        self.assertEqual(kr, [])
        self.assertEqual(pr, [])

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    def test_empty_query_returns_empty(self):
        problem = _make_problem(title="", error_message="", tags=[])
        kr, pr = find_similar(problem)
        self.assertEqual(kr, [])
        self.assertEqual(pr, [])

    @patch("src.problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.storage.DATA_FILE", NOTES_TEST)
    def test_scores_are_in_results(self):
        from src.storage import create_record
        create_record(title="Flask install", text="pip install flask", tags=["flask"])
        problem = _make_problem()

        kr, _ = find_similar(problem)
        self.assertTrue(len(kr) > 0)
        record, score = kr[0]
        self.assertIsInstance(score, float)
        self.assertGreater(score, 0)


# ── start_investigation ───────────────────────────────────────────

class TestStartInvestigation(unittest.TestCase):

    @patch("src.solve._problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.solve._storage.DATA_FILE", NOTES_TEST)
    def setUp(self):
        _clean()

    @patch("src.solve._problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.solve._storage.DATA_FILE", NOTES_TEST)
    def tearDown(self):
        _clean()

    @patch("src.solve._problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.solve._storage.DATA_FILE", NOTES_TEST)
    def test_new_to_investigating(self):
        problem = _make_problem()
        result = start_investigation(problem["id"])
        self.assertEqual(result["status"], "investigating")

    @patch("src.solve._problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.solve._storage.DATA_FILE", NOTES_TEST)
    def test_investigating_rejected(self):
        problem = _make_problem()
        start_investigation(problem["id"])
        with self.assertRaises(SolveError):
            start_investigation(problem["id"])


# ── start_solving ─────────────────────────────────────────────────

class TestStartSolving(unittest.TestCase):

    @patch("src.solve._problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.solve._storage.DATA_FILE", NOTES_TEST)
    def setUp(self):
        _clean()

    @patch("src.solve._problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.solve._storage.DATA_FILE", NOTES_TEST)
    def tearDown(self):
        _clean()

    @patch("src.solve._problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.solve._storage.DATA_FILE", NOTES_TEST)
    def test_investigating_to_solving(self):
        problem = _make_problem()
        start_investigation(problem["id"])
        result = start_solving(problem["id"])
        self.assertEqual(result["status"], "solving")

    @patch("src.solve._problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.solve._storage.DATA_FILE", NOTES_TEST)
    def test_new_rejected(self):
        problem = _make_problem()
        with self.assertRaises(SolveError):
            start_solving(problem["id"])


# ── resolve_problem ───────────────────────────────────────────────

class TestResolveProblem(unittest.TestCase):

    @patch("src.solve._problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.solve._storage.DATA_FILE", NOTES_TEST)
    def setUp(self):
        _clean()

    @patch("src.solve._problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.solve._storage.DATA_FILE", NOTES_TEST)
    def tearDown(self):
        _clean()

    @patch("src.solve._problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.solve._storage.DATA_FILE", NOTES_TEST)
    def test_resolve_helped_true(self):
        problem = _make_problem()
        start_investigation(problem["id"])
        start_solving(problem["id"])
        result = resolve_problem(
            problem["id"],
            cause="venv not activated",
            solution="activate venv",
            helped=True,
        )
        self.assertEqual(result["status"], "solved")
        self.assertEqual(result["cause"], "venv not activated")
        self.assertEqual(result["solution"], "activate venv")
        self.assertTrue(result["helped"])

    @patch("src.solve._problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.solve._storage.DATA_FILE", NOTES_TEST)
    def test_resolve_helped_false(self):
        problem = _make_problem()
        start_investigation(problem["id"])
        start_solving(problem["id"])
        result = resolve_problem(
            problem["id"],
            cause="unknown",
            solution="tried something",
            helped=False,
        )
        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["helped"])

    @patch("src.solve._problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.solve._storage.DATA_FILE", NOTES_TEST)
    def test_resolve_helped_none_keeps_status(self):
        problem = _make_problem()
        start_investigation(problem["id"])
        start_solving(problem["id"])
        result = resolve_problem(
            problem["id"],
            cause="partial cause",
            solution="partial solution",
            helped=None,
        )
        self.assertEqual(result["status"], "solving")
        self.assertIsNone(result["helped"])

    @patch("src.solve._problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.solve._storage.DATA_FILE", NOTES_TEST)
    def test_resolve_from_solving(self):
        problem = _make_problem()
        start_investigation(problem["id"])
        start_solving(problem["id"])
        result = resolve_problem(problem["id"], cause="c", solution="s", helped=True)
        self.assertEqual(result["status"], "solved")

    @patch("src.solve._problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.solve._storage.DATA_FILE", NOTES_TEST)
    def test_resolve_new_rejected(self):
        problem = _make_problem()
        with self.assertRaises(SolveError):
            resolve_problem(problem["id"], cause="", solution="", helped=True)

    @patch("src.solve._problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.solve._storage.DATA_FILE", NOTES_TEST)
    def test_resolve_missing_problem(self):
        with self.assertRaises(SolveError):
            resolve_problem("nonexistent", cause="", solution="", helped=True)


# ── Недопустимые переходы ────────────────────────────────────────

class TestInvalidTransitions(unittest.TestCase):

    @patch("src.solve._problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.solve._storage.DATA_FILE", NOTES_TEST)
    def setUp(self):
        _clean()

    @patch("src.solve._problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.solve._storage.DATA_FILE", NOTES_TEST)
    def tearDown(self):
        _clean()

    @patch("src.solve._problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.solve._storage.DATA_FILE", NOTES_TEST)
    def test_archived_has_no_transitions(self):
        problem = _make_problem()
        start_investigation(problem["id"])
        start_solving(problem["id"])
        resolve_problem(problem["id"], cause="c", solution="s", helped=True)
        archive_problem(problem["id"])
        with self.assertRaises(SolveError):
            start_investigation(problem["id"])

    @patch("src.solve._problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.solve._storage.DATA_FILE", NOTES_TEST)
    def test_solved_to_investigating_rejected(self):
        problem = _make_problem()
        start_investigation(problem["id"])
        start_solving(problem["id"])
        resolve_problem(problem["id"], cause="c", solution="s", helped=True)
        with self.assertRaises(SolveError):
            start_investigation(problem["id"])

    @patch("src.solve._problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.solve._storage.DATA_FILE", NOTES_TEST)
    def test_failed_to_new_rejected(self):
        problem = _make_problem()
        start_investigation(problem["id"])
        start_solving(problem["id"])
        resolve_problem(problem["id"], cause="c", solution="s", helped=False)
        with self.assertRaises(SolveError):
            start_investigation(problem["id"])

    @patch("src.solve._problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.solve._storage.DATA_FILE", NOTES_TEST)
    def test_failed_to_solving_allowed(self):
        problem = _make_problem()
        start_investigation(problem["id"])
        start_solving(problem["id"])
        resolve_problem(problem["id"], cause="c", solution="s", helped=False)
        result = start_solving(problem["id"])
        self.assertEqual(result["status"], "solving")

    @patch("src.solve._problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.solve._storage.DATA_FILE", NOTES_TEST)
    def test_missing_problem_raises(self):
        with self.assertRaises(SolveError):
            start_investigation("nonexistent")

    @patch("src.solve._problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.solve._storage.DATA_FILE", NOTES_TEST)
    def test_archive_new_rejected(self):
        problem = _make_problem()
        with self.assertRaises(SolveError):
            archive_problem(problem["id"])

    @patch("src.solve._problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.solve._storage.DATA_FILE", NOTES_TEST)
    def test_investigating_to_solved_rejected(self):
        problem = _make_problem()
        start_investigation(problem["id"])
        with self.assertRaises(SolveError):
            resolve_problem(problem["id"], cause="c", solution="s", helped=True)


# ── archive_problem ───────────────────────────────────────────────

class TestArchiveProblem(unittest.TestCase):

    @patch("src.solve._problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.solve._storage.DATA_FILE", NOTES_TEST)
    def setUp(self):
        _clean()

    @patch("src.solve._problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.solve._storage.DATA_FILE", NOTES_TEST)
    def tearDown(self):
        _clean()

    @patch("src.solve._problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.solve._storage.DATA_FILE", NOTES_TEST)
    def test_archive_solved(self):
        problem = _make_problem()
        start_investigation(problem["id"])
        start_solving(problem["id"])
        resolve_problem(problem["id"], cause="c", solution="s", helped=True)
        result = archive_problem(problem["id"])
        self.assertEqual(result["status"], "archived")

    @patch("src.solve._problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.solve._storage.DATA_FILE", NOTES_TEST)
    def test_archive_failed(self):
        problem = _make_problem()
        start_investigation(problem["id"])
        start_solving(problem["id"])
        resolve_problem(problem["id"], cause="c", solution="s", helped=False)
        result = archive_problem(problem["id"])
        self.assertEqual(result["status"], "archived")


# ── convert_to_knowledge ──────────────────────────────────────────

class TestConvertToKnowledge(unittest.TestCase):

    @patch("src.solve._problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.solve._storage.DATA_FILE", NOTES_TEST)
    def setUp(self):
        _clean()

    @patch("src.solve._problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.solve._storage.DATA_FILE", NOTES_TEST)
    def tearDown(self):
        _clean()

    @patch("src.solve._problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.solve._storage.DATA_FILE", NOTES_TEST)
    def test_creates_knowledge_record(self):
        problem = _make_problem()
        start_investigation(problem["id"])
        start_solving(problem["id"])
        resolve_problem(problem["id"], cause="venv not active", solution="activate it", helped=True)

        record = convert_to_knowledge(problem["id"])
        self.assertIn("id", record)
        self.assertEqual(record["type"], "solution")
        self.assertIn("решена", record["title"])
        self.assertIn("Ошибка Python", record["title"])

    @patch("src.solve._problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.solve._storage.DATA_FILE", NOTES_TEST)
    def test_sets_related_record_id(self):
        problem = _make_problem()
        start_investigation(problem["id"])
        start_solving(problem["id"])
        resolve_problem(problem["id"], cause="c", solution="s", helped=True)

        record = convert_to_knowledge(problem["id"])
        updated = get_problem_summary(problem["id"])
        self.assertEqual(updated["related_record_id"], record["id"])

    @patch("src.solve._problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.solve._storage.DATA_FILE", NOTES_TEST)
    def test_duplicate_conversion_rejected(self):
        problem = _make_problem()
        start_investigation(problem["id"])
        start_solving(problem["id"])
        resolve_problem(problem["id"], cause="c", solution="s", helped=True)

        convert_to_knowledge(problem["id"])
        with self.assertRaises(SolveError):
            convert_to_knowledge(problem["id"])

    @patch("src.solve._problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.solve._storage.DATA_FILE", NOTES_TEST)
    def test_convert_unresolved_rejected(self):
        problem = _make_problem()
        start_investigation(problem["id"])
        with self.assertRaises(SolveError):
            convert_to_knowledge(problem["id"])

    @patch("src.solve._problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.solve._storage.DATA_FILE", NOTES_TEST)
    def test_convert_new_rejected(self):
        problem = _make_problem()
        with self.assertRaises(SolveError):
            convert_to_knowledge(problem["id"])

    @patch("src.solve._problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.solve._storage.DATA_FILE", NOTES_TEST)
    def test_convert_failed_includes_not_resolved_label(self):
        problem = _make_problem()
        start_investigation(problem["id"])
        start_solving(problem["id"])
        resolve_problem(problem["id"], cause="c", solution="s", helped=False)

        record = convert_to_knowledge(problem["id"])
        self.assertIn("не решена", record["title"])

    @patch("src.solve._problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.solve._storage.DATA_FILE", NOTES_TEST)
    def test_knowledge_text_includes_fields(self):
        problem = _make_problem(
            description="Описание",
            context="Контекст",
            error_message="Ошибка",
            tags=["t1"],
        )
        start_investigation(problem["id"])
        start_solving(problem["id"])
        resolve_problem(problem["id"], cause="Причина", solution="Решение", helped=True)

        record = convert_to_knowledge(problem["id"])
        self.assertIn("Статус: решена", record["text"])
        self.assertIn("Описание", record["text"])
        self.assertIn("Контекст: Контекст", record["text"])
        self.assertIn("Ошибка: Ошибка", record["text"])
        self.assertIn("Причина: Причина", record["text"])
        self.assertIn("Решение: Решение", record["text"])
        self.assertIn("Результат: помогло", record["text"])

    @patch("src.solve._problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.solve._storage.DATA_FILE", NOTES_TEST)
    def test_knowledge_record_saved_to_notes(self):
        from src.storage import get_all_records

        problem = _make_problem()
        start_investigation(problem["id"])
        start_solving(problem["id"])
        resolve_problem(problem["id"], cause="c", solution="s", helped=True)

        convert_to_knowledge(problem["id"])
        records = get_all_records()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["type"], "solution")

    @patch("src.solve._problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.solve._storage.DATA_FILE", NOTES_TEST)
    def test_convert_missing_problem(self):
        with self.assertRaises(SolveError):
            convert_to_knowledge("nonexistent")


# ── get_problem_summary ───────────────────────────────────────────

class TestGetProblemSummary(unittest.TestCase):

    @patch("src.solve._problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.solve._storage.DATA_FILE", NOTES_TEST)
    def setUp(self):
        _clean()

    @patch("src.solve._problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.solve._storage.DATA_FILE", NOTES_TEST)
    def tearDown(self):
        _clean()

    @patch("src.solve._problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.solve._storage.DATA_FILE", NOTES_TEST)
    def test_returns_expected_keys(self):
        problem = _make_problem()
        summary = get_problem_summary(problem["id"])
        expected = {
            "id", "created_at", "title", "description", "context",
            "error_message", "tags", "status", "cause", "solution",
            "helped", "related_record_id",
        }
        self.assertEqual(set(summary.keys()), expected)

    @patch("src.solve._problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.solve._storage.DATA_FILE", NOTES_TEST)
    def test_missing_problem_raises(self):
        with self.assertRaises(SolveError):
            get_problem_summary("nonexistent")

    @patch("src.solve._problems.DATA_FILE", PROBLEMS_TEST)
    @patch("src.solve._storage.DATA_FILE", NOTES_TEST)
    def test_reflects_current_status(self):
        problem = _make_problem()
        start_investigation(problem["id"])
        summary = get_problem_summary(problem["id"])
        self.assertEqual(summary["status"], "investigating")


# ── Таблица переходов ─────────────────────────────────────────────

class TestTransitionTable(unittest.TestCase):

    def test_new_can_only_investigate(self):
        self.assertEqual(_TRANSITIONS["new"], ("investigating",))

    def test_investigating_can_solve_or_fail(self):
        self.assertEqual(_TRANSITIONS["investigating"], ("solving", "failed"))

    def test_solving_can_solved_or_fail(self):
        self.assertEqual(_TRANSITIONS["solving"], ("solved", "failed"))

    def test_solved_can_only_archive(self):
        self.assertEqual(_TRANSITIONS["solved"], ("archived",))

    def test_failed_can_archive_or_retry(self):
        self.assertEqual(_TRANSITIONS["failed"], ("archived", "solving"))

    def test_archived_has_no_transitions(self):
        self.assertEqual(_TRANSITIONS["archived"], ())


if __name__ == "__main__":
    unittest.main()
