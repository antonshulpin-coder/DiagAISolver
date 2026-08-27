import json
import unittest
from pathlib import Path
from unittest.mock import patch

from src.problems import (
    load_problems,
    save_problems,
    create_problem,
    get_problem,
    get_all_problems,
    update_problem,
    delete_problem,
    search_problems,
    search_problems_with_scores,
    ProblemError,
    VALID_STATUSES,
)


TEST_DATA = Path(__file__).resolve().parent.parent / "data" / "problems_test.json"


class TestCreateProblem(unittest.TestCase):

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def setUp(self):
        TEST_DATA.unlink(missing_ok=True)

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def test_create_returns_problem(self):
        p = create_problem(title="Test", description="Desc")
        self.assertEqual(p["title"], "Test")
        self.assertEqual(p["description"], "Desc")
        self.assertIn("id", p)
        self.assertIn("created_at", p)

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def test_create_default_status(self):
        p = create_problem(title="X")
        self.assertEqual(p["status"], "new")

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def test_create_default_solution_empty(self):
        p = create_problem(title="X")
        self.assertEqual(p["solution"], "")

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def test_create_default_cause_empty(self):
        p = create_problem(title="X")
        self.assertEqual(p["cause"], "")

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def test_create_default_helped_none(self):
        p = create_problem(title="X")
        self.assertIsNone(p["helped"])

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def test_create_default_related_record_id_none(self):
        p = create_problem(title="X")
        self.assertIsNone(p["related_record_id"])

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def test_create_with_tags(self):
        p = create_problem(title="X", tags=["a", "b"])
        self.assertEqual(p["tags"], ["a", "b"])

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def test_create_default_tags_empty(self):
        p = create_problem(title="X")
        self.assertEqual(p["tags"], [])

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def test_create_persists(self):
        p = create_problem(title="Persist")
        loaded = get_problem(p["id"])
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["title"], "Persist")

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def test_create_context(self):
        p = create_problem(title="X", context="Windows 11")
        self.assertEqual(p["context"], "Windows 11")

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def test_create_error_message(self):
        p = create_problem(title="X", error_message="ModuleNotFoundError")
        self.assertEqual(p["error_message"], "ModuleNotFoundError")


class TestUniqueId(unittest.TestCase):

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def setUp(self):
        TEST_DATA.unlink(missing_ok=True)

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def test_ids_are_unique(self):
        ids = set()
        for _ in range(20):
            p = create_problem(title="X")
            ids.add(p["id"])
        self.assertEqual(len(ids), 20)


class TestCreatedAt(unittest.TestCase):

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def setUp(self):
        TEST_DATA.unlink(missing_ok=True)

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def test_created_at_is_iso(self):
        p = create_problem(title="X")
        self.assertIn("T", p["created_at"])
        self.assertIn("+", p["created_at"])

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def test_created_at_is_recent(self):
        from datetime import datetime, timezone
        before = datetime.now(timezone.utc)
        p = create_problem(title="X")
        after = datetime.now(timezone.utc)
        self.assertGreaterEqual(p["created_at"], before.isoformat())
        self.assertLessEqual(p["created_at"], after.isoformat())


class TestGetProblem(unittest.TestCase):

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def setUp(self):
        TEST_DATA.unlink(missing_ok=True)

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def test_get_existing(self):
        p = create_problem(title="Find me")
        found = get_problem(p["id"])
        self.assertIsNotNone(found)
        self.assertEqual(found["id"], p["id"])

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def test_get_nonexistent(self):
        self.assertIsNone(get_problem("nope"))


class TestGetAllProblems(unittest.TestCase):

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def setUp(self):
        TEST_DATA.unlink(missing_ok=True)

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def test_empty(self):
        self.assertEqual(get_all_problems(), [])

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def test_multiple(self):
        create_problem(title="A")
        create_problem(title="B")
        all_p = get_all_problems()
        self.assertEqual(len(all_p), 2)


class TestUpdateProblem(unittest.TestCase):

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def setUp(self):
        TEST_DATA.unlink(missing_ok=True)

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def test_update_title(self):
        p = create_problem(title="old")
        updated = update_problem(p["id"], title="new")
        self.assertEqual(updated["title"], "new")

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def test_update_status(self):
        p = create_problem(title="X")
        updated = update_problem(p["id"], status="investigating")
        self.assertEqual(updated["status"], "investigating")

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def test_update_solution(self):
        p = create_problem(title="X")
        updated = update_problem(p["id"], solution="Fixed it")
        self.assertEqual(updated["solution"], "Fixed it")

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def test_update_cause(self):
        p = create_problem(title="X")
        updated = update_problem(p["id"], cause="Bad config")
        self.assertEqual(updated["cause"], "Bad config")

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def test_update_helped_true(self):
        p = create_problem(title="X")
        updated = update_problem(p["id"], helped=True)
        self.assertTrue(updated["helped"])

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def test_update_helped_false(self):
        p = create_problem(title="X")
        updated = update_problem(p["id"], helped=False)
        self.assertFalse(updated["helped"])

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def test_update_helped_none(self):
        p = create_problem(title="X")
        update_problem(p["id"], helped=True)
        updated = update_problem(p["id"], helped=None)
        self.assertIsNone(updated["helped"])

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def test_update_tags(self):
        p = create_problem(title="X")
        updated = update_problem(p["id"], tags=["new"])
        self.assertEqual(updated["tags"], ["new"])

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def test_update_nonexistent(self):
        result = update_problem("nope", title="X")
        self.assertIsNone(result)

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def test_update_persists(self):
        p = create_problem(title="X")
        update_problem(p["id"], title="changed")
        loaded = get_problem(p["id"])
        self.assertEqual(loaded["title"], "changed")


class TestDeleteProblem(unittest.TestCase):

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def setUp(self):
        TEST_DATA.unlink(missing_ok=True)

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def test_delete_existing(self):
        p = create_problem(title="X")
        self.assertTrue(delete_problem(p["id"]))
        self.assertIsNone(get_problem(p["id"]))

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def test_delete_nonexistent(self):
        self.assertFalse(delete_problem("nope"))

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def test_delete_only_target(self):
        p1 = create_problem(title="A")
        p2 = create_problem(title="B")
        delete_problem(p1["id"])
        self.assertIsNone(get_problem(p1["id"]))
        self.assertIsNotNone(get_problem(p2["id"]))


class TestSearchProblems(unittest.TestCase):

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def setUp(self):
        TEST_DATA.unlink(missing_ok=True)
        create_problem(
            title="Flask crash",
            description="Server crashes on startup",
            error_message="ModuleNotFoundError: No module named 'flask'",
            tags=["flask", "crash"],
        )
        create_problem(
            title="Python import error",
            description="Cannot import module",
            tags=["python", "import"],
        )

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def test_search_by_title(self):
        results = search_problems("Flask crash")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Flask crash")

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def test_search_by_tags(self):
        results = search_problems("python")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Python import error")

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def test_search_by_error_message(self):
        results = search_problems("ModuleNotFoundError")
        self.assertEqual(len(results), 1)

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def test_search_empty_query(self):
        self.assertEqual(search_problems(""), [])

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def test_search_no_match(self):
        self.assertEqual(search_problems("golang"), [])

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def test_search_with_scores(self):
        results = search_problems_with_scores("flask")
        self.assertTrue(len(results) >= 1)
        record, score = results[0]
        self.assertIn("id", record)
        self.assertGreater(score, 0)


class TestLoadProblems(unittest.TestCase):

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def setUp(self):
        TEST_DATA.unlink(missing_ok=True)

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def test_load_missing_file(self):
        self.assertEqual(load_problems(), [])

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def test_load_corrupt_json(self):
        TEST_DATA.write_text("{broken", encoding="utf-8")
        with self.assertRaises(ProblemError):
            load_problems()

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def test_load_wrong_type(self):
        TEST_DATA.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
        with self.assertRaises(ProblemError):
            load_problems()


class TestSaveProblems(unittest.TestCase):

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def setUp(self):
        TEST_DATA.unlink(missing_ok=True)

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def test_save_creates_file(self):
        save_problems([{"id": "x", "title": "test"}])
        data = json.loads(TEST_DATA.read_text(encoding="utf-8"))
        self.assertEqual(len(data), 1)

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def test_save_no_tmp_left(self):
        save_problems([{"id": "y", "title": "x"}])
        self.assertFalse(TEST_DATA.with_suffix(".tmp").exists())


class TestAllStatuses(unittest.TestCase):

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def setUp(self):
        TEST_DATA.unlink(missing_ok=True)

    @patch("src.problems.DATA_FILE", TEST_DATA)
    def test_all_statuses_acceptable(self):
        for status in VALID_STATUSES:
            p = create_problem(title=f"Status {status}")
            updated = update_problem(p["id"], status=status)
            self.assertEqual(updated["status"], status)


if __name__ == "__main__":
    unittest.main()
