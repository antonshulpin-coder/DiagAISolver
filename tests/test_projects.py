import json
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from src import commands
from src import problems as _problems
from src import projects as _projects


PROBLEMS_TEST = Path(__file__).resolve().parent.parent / "data" / "problems_projects_test.json"
PROJECTS_TEST = Path(__file__).resolve().parent.parent / "data" / "projects_test.json"


def _clean():
    PROBLEMS_TEST.unlink(missing_ok=True)
    PROJECTS_TEST.unlink(missing_ok=True)


def _patch_data_files(func):
    @patch.object(_problems, "DATA_FILE", PROBLEMS_TEST)
    @patch.object(_projects, "DATA_FILE", PROJECTS_TEST)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper


class ProjectBase(unittest.TestCase):
    """Запускает патчи хранилищ на время каждого теста (изолирует data/)."""

    def setUp(self):
        _clean()
        self._problems_patch = patch.object(_problems, "DATA_FILE", PROBLEMS_TEST)
        self._projects_patch = patch.object(_projects, "DATA_FILE", PROJECTS_TEST)
        self._problems_patch.start()
        self._projects_patch.start()
        self.addCleanup(self._projects_patch.stop)
        self.addCleanup(self._problems_patch.stop)

    def tearDown(self):
        _clean()

    def _create_problem(self, title="Проблема А"):
        return _problems.create_problem(title=title, description="описание")

    def _create_project(self, name="Мой проект", goal="Цель"):
        return _projects.create_project(name, goal)


class TestProjectCrud(ProjectBase):

    def test_create_writes_file_and_fields(self):
        pr = _projects.create_project("Шифрование", "Секретность")
        self.assertTrue(PROJECTS_TEST.exists())
        self.assertTrue(pr["id"].startswith("p_"))
        self.assertEqual(pr["name"], "Шифрование")
        self.assertEqual(pr["goal"], "Секретность")
        self.assertEqual(pr["status"], "active")
        self.assertNotEqual(pr["created"], "")

    def test_create_requires_name(self):
        with self.assertRaises(_projects.ProjectError):
            _projects.create_project("   ")

    def test_create_trims_goal(self):
        pr = _projects.create_project("X", "  цель  ")
        self.assertEqual(pr["goal"], "цель")

    def test_created_field_is_iso(self):
        pr = _projects.create_project("X")
        self.assertIn("T", pr["created"])
        self.assertIn("+", pr["created"])

    def test_list_and_get(self):
        a = _projects.create_project("A")
        b = _projects.create_project("B")
        all_projects = _projects.get_all_projects()
        self.assertEqual(len(all_projects), 2)
        self.assertEqual(_projects.get_project(a["id"])["name"], "A")
        self.assertEqual(_projects.get_project(b["id"])["name"], "B")
        self.assertIsNone(_projects.get_project("p_nope"))

    def test_rename_name_and_goal(self):
        pr = _projects.create_project("Старое", "Старая цель")
        updated = _projects.rename_project(pr["id"], name="Новое", goal="Новая цель")
        self.assertEqual(updated["name"], "Новое")
        self.assertEqual(updated["goal"], "Новая цель")
        self.assertEqual(_projects.get_project(pr["id"])["name"], "Новое")

    def test_rename_only_goal(self):
        pr = _projects.create_project("Имя", "Старая цель")
        _projects.rename_project(pr["id"], goal="Другая цель")
        got = _projects.get_project(pr["id"])
        self.assertEqual(got["name"], "Имя")
        self.assertEqual(got["goal"], "Другая цель")

    def test_rename_requires_nonempty_name(self):
        pr = _projects.create_project("Имя")
        with self.assertRaises(_projects.ProjectError):
            _projects.rename_project(pr["id"], name="   ")

    def test_rename_missing_id_returns_none(self):
        self.assertIsNone(_projects.rename_project("p_missing", name="X"))

    def test_close_and_reopen(self):
        pr = _projects.create_project("Имя")
        self.assertEqual(_projects.close_project(pr["id"])["status"], "done")
        self.assertEqual(_projects.get_project(pr["id"])["status"], "done")
        self.assertEqual(_projects.reopen_project(pr["id"])["status"], "active")
        self.assertEqual(_projects.get_project(pr["id"])["status"], "active")

    def test_invalid_status_rejected(self):
        pr = _projects.create_project("Имя")
        with self.assertRaises(_projects.ProjectError):
            _projects.set_project_status(pr["id"], "bogus")

    def test_delete_and_missing_delete(self):
        pr = _projects.create_project("Имя")
        self.assertTrue(_projects.delete_project(pr["id"]))
        self.assertIsNone(_projects.get_project(pr["id"]))
        self.assertFalse(_projects.delete_project(pr["id"]))


class TestProjectStorage(ProjectBase):

    def test_missing_file_returns_empty(self):
        self.assertEqual(_projects.load_projects(), [])

    def test_broken_json_raises_without_crash(self):
        PROJECTS_TEST.parent.mkdir(exist_ok=True)
        PROJECTS_TEST.write_text("{broken", encoding="utf-8")
        with self.assertRaises(_projects.ProjectError):
            _projects.load_projects()

    def test_non_list_raises(self):
        PROJECTS_TEST.parent.mkdir(exist_ok=True)
        PROJECTS_TEST.write_text("{}", encoding="utf-8")
        with self.assertRaises(_projects.ProjectError):
            _projects.load_projects()

    def test_atomic_write_persistence(self):
        a = _projects.create_project("A")
        b = _projects.create_project("B")
        reloaded = _projects.load_projects()
        self.assertEqual([p["id"] for p in reloaded], [a["id"], b["id"]])


class TestProjectIdMigration(ProjectBase):

    def test_adding_project_id_preserves_existing_fields_byte_for_byte(self):
        problem = {
            "id": "abc123",
            "created_at": "2026-01-01T00:00:00+00:00",
            "title": "Старая проблема",
            "description": "текст",
            "context": "",
            "error_message": "ошибка",
            "tags": ["x", "y"],
            "status": "new",
            "solution": "",
            "cause": "",
            "helped": None,
            "related_record_id": None,
        }
        PROBLEMS_TEST.parent.mkdir(exist_ok=True)
        PROBLEMS_TEST.write_text(
            json.dumps([problem], ensure_ascii=False, indent=4), encoding="utf-8"
        )
        _problems.update_problem("abc123", project_id="p_1")
        reloaded = _problems.load_problems()[0]
        self.assertEqual(reloaded["project_id"], "p_1")
        for key, value in problem.items():
            self.assertEqual(reloaded[key], value)
        before = json.dumps(problem, ensure_ascii=False, sort_keys=True)
        stripped = {k: v for k, v in reloaded.items() if k != "project_id"}
        after = json.dumps(stripped, ensure_ascii=False, sort_keys=True)
        self.assertEqual(after, before)

    def test_load_does_not_auto_add_project_id(self):
        problem = {"id": "abc123", "title": "Без проекта", "status": "new"}
        PROBLEMS_TEST.parent.mkdir(exist_ok=True)
        PROBLEMS_TEST.write_text(
            json.dumps([problem], ensure_ascii=False), encoding="utf-8"
        )
        self.assertNotIn("project_id", _problems.load_problems()[0])


class TestBindUnbind(ProjectBase):

    def test_bind_problem_sets_project_id(self):
        pr = self._create_project()
        p = self._create_problem()
        updated = _projects.bind_problem(p["id"], pr["id"])
        self.assertEqual(updated["project_id"], pr["id"])
        self.assertEqual(_projects.problems_of_project(pr["id"])[0]["id"], p["id"])
        self.assertEqual(_projects.count_project_problems(pr["id"]), 1)

    def test_bind_unknown_project_raises(self):
        p = self._create_problem()
        with self.assertRaises(_projects.ProjectError):
            _projects.bind_problem(p["id"], "p_nope")

    def test_bind_unknown_problem_returns_none(self):
        pr = self._create_project()
        self.assertIsNone(_projects.bind_problem("nope", pr["id"]))

    def test_unbind_sets_none(self):
        pr = self._create_project()
        p = self._create_problem()
        _projects.bind_problem(p["id"], pr["id"])
        updated = _projects.bind_problem(p["id"], None)
        self.assertIsNone(updated["project_id"])
        self.assertEqual(_projects.count_project_problems(pr["id"]), 0)

    def test_problem_belongs_to_at_most_one_project(self):
        a = self._create_project("A")
        b = self._create_project("B")
        p = self._create_problem()
        _projects.bind_problem(p["id"], a["id"])
        _projects.bind_problem(p["id"], b["id"])
        self.assertEqual(_problems.get_problem(p["id"])["project_id"], b["id"])
        self.assertEqual(_projects.count_project_problems(a["id"]), 0)
        self.assertEqual(_projects.count_project_problems(b["id"]), 1)


class TestDeleteUnbindHardRule(ProjectBase):

    def test_unbind_all_keeps_problems(self):
        pr = self._create_project()
        p1 = self._create_problem("П1")
        p2 = self._create_problem("П2")
        _projects.bind_problem(p1["id"], pr["id"])
        _projects.bind_problem(p2["id"], pr["id"])
        self.assertTrue(_projects.unbind_all_problems(pr["id"]))
        self.assertEqual(len(_problems.get_all_problems()), 2)
        self.assertIsNone(_problems.get_problem(p1["id"])["project_id"])
        self.assertIsNone(_problems.get_problem(p2["id"])["project_id"])

    def test_delete_project_cli_unbinds_but_keeps_problems(self):
        pr = self._create_project()
        p = self._create_problem()
        _projects.bind_problem(p["id"], pr["id"])
        buf = StringIO()
        with patch("src.commands.input", side_effect=["6", "1", "y", "0"]):
            with redirect_stdout(buf):
                commands.projects()
        self.assertIsNone(_projects.get_project(pr["id"]))
        remaining = _problems.get_all_problems()
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0]["id"], p["id"])
        self.assertIsNone(remaining[0].get("project_id"))

    def test_delete_project_cancel_keeps_everything(self):
        pr = self._create_project()
        p = self._create_problem()
        _projects.bind_problem(p["id"], pr["id"])
        buf = StringIO()
        with patch("src.commands.input", side_effect=["6", "1", "n", "0"]):
            with redirect_stdout(buf):
                commands.projects()
        self.assertIsNotNone(_projects.get_project(pr["id"]))
        self.assertEqual(_problems.get_problem(p["id"])["project_id"], pr["id"])


class TestProjectsCli(ProjectBase):

    def test_create_via_cli(self):
        buf = StringIO()
        with patch("src.commands.input", side_effect=["1", "Новый проект", "Цель", "0"]):
            with redirect_stdout(buf):
                commands.projects()
        projects = _projects.get_all_projects()
        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0]["name"], "Новый проект")
        self.assertEqual(projects[0]["goal"], "Цель")

    def test_list_shows_counters(self):
        pr = self._create_project("Проект")
        p = self._create_problem("Привязанная")
        _projects.bind_problem(p["id"], pr["id"])
        self._create_problem("Вне")
        buf = StringIO()
        with patch("src.commands.input", side_effect=["2", "0"]):
            with redirect_stdout(buf):
                commands.projects()
        self.assertIn("Проект", buf.getvalue())
        self.assertIn("подзадач: 1", buf.getvalue())

    def test_open_project_stub(self):
        pr = self._create_project("Проект")
        buf = StringIO()
        with patch("src.commands.input", side_effect=["3", "1", "0"]):
            with redirect_stdout(buf):
                commands.projects()
        self.assertIn("v1.5.1", buf.getvalue())

    def test_filter_by_project(self):
        pr = self._create_project()
        p = self._create_problem("Внутри")
        other = self._create_problem("Другая")
        _projects.bind_problem(p["id"], pr["id"])
        buf = StringIO()
        with patch("src.commands.input", side_effect=["8", "1", "1", "0"]):
            with redirect_stdout(buf):
                commands.projects()
        out = buf.getvalue()
        self.assertIn(p["title"], out)
        self.assertNotIn(other["title"], out)

    def test_filter_without_project(self):
        self._create_problem("Свободная")
        p2 = self._create_problem("Еще свободная")
        buf = StringIO()
        with patch("src.commands.input", side_effect=["8", "2", "0"]):
            with redirect_stdout(buf):
                commands.projects()
        out = buf.getvalue()
        self.assertIn(p2["title"], out)
        self.assertIn("(без проекта)", out)

    def test_bind_problem_flow_binds_and_unbinds(self):
        pr = self._create_project()
        p = self._create_problem()
        buf = StringIO()
        with patch("src.commands.input", side_effect=["1"]):
            with redirect_stdout(buf):
                commands._bind_problem_flow(p["id"])
        self.assertEqual(_problems.get_problem(p["id"])["project_id"], pr["id"])
        self.assertIn("привязана", buf.getvalue())
        buf2 = StringIO()
        with patch("src.commands.input", side_effect=["0"]):
            with redirect_stdout(buf2):
                commands._bind_problem_flow(p["id"])
        self.assertIsNone(_problems.get_problem(p["id"])["project_id"])
        self.assertIn("отвязана", buf2.getvalue())


class TestProjectsCommandErrorHandling(ProjectBase):

    def test_projects_catches_project_error_without_crash(self):
        PROJECTS_TEST.parent.mkdir(exist_ok=True)
        PROJECTS_TEST.write_text("{broken", encoding="utf-8")
        buf = StringIO()
        with patch("src.commands.input", side_effect=["2", "0"]):
            with redirect_stdout(buf):
                commands.projects()
        out = buf.getvalue()
        self.assertIn("Ошибка данных", out)
        self.assertIn("повреждён", out)

    def test_bind_to_missing_project_reports_error_without_crash(self):
        p = self._create_problem()
        # меню 7 -> выбор проблемы -> вариантов проектов нет -> "Проектов пока нет"
        buf = StringIO()
        with patch("src.commands.input", side_effect=["7", "1", "1", "0"]):
            with redirect_stdout(buf):
                commands.projects()
        out = buf.getvalue()
        self.assertIn("Проектов пока нет", out)
        # проблема по-прежнему без проекта
        self.assertNotIn("project_id", _problems.get_problem(p["id"]))


class TestProjectsMenuRouter(unittest.TestCase):

    def _start_patches(self):
        self._pp = patch.object(_problems, "DATA_FILE", PROBLEMS_TEST)
        self._prp = patch.object(_projects, "DATA_FILE", PROJECTS_TEST)
        self._pp.start()
        self._prp.start()
        self.addCleanup(self._prp.stop)
        self.addCleanup(self._pp.stop)
        _clean()

    def setUp(self):
        self._start_patches()

    def tearDown(self):
        _clean()

    def test_menu_shows_projects_option(self):
        from src.menu import show_menu
        buf = StringIO()
        with redirect_stdout(buf):
            show_menu()
        self.assertIn("6. Проекты", buf.getvalue())

    @patch("src.router.projects")
    def test_route_6_calls_projects(self, mock_projects):
        from src.router import route
        self.assertTrue(route("6"))
        mock_projects.assert_called_once()


if __name__ == "__main__":
    unittest.main()
