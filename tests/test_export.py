import json
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from src import commands
from src.commands import (
    _export_backup,
    _export_markdown,
    _format_investigation_history,
    _problems_to_markdown,
)


def _full_problem():
    return {
        "id": "P1",
        "title": "Приложение падает",
        "status": "solved",
        "description": "Крашится при старте",
        "solution": "Установил модуль x",
        "diagnostic": {
            "hypotheses": [
                {"id": "H1", "text": "Пропал модуль", "status": "confirmed", "source": "ai"},
                {"id": "H2", "text": "Права", "status": "rejected", "source": "manual"},
            ],
            "steps": [
                {"id": "S1", "hypothesis_id": "H2", "description": "Проверить права",
                 "status": "done", "outcome": "ОК", "result": "rejected"},
                {"id": "S2", "hypothesis_id": "H1", "description": "Проверить импорт",
                 "status": "done", "outcome": "Нет", "result": "confirmed"},
            ],
            "conclusion": "Пропал модуль x",
        },
    }


def _no_solution_problem():
    return {
        "id": "P2",
        "title": "Сервер не стартует",
        "status": "new",
        "description": "Нет лога",
        "solution": "",
    }


def _no_diagnostic_problem():
    return {
        "id": "P3",
        "title": "Медленный ответ",
        "status": "investigating",
        "description": "Долго грузится",
        "solution": "Увеличил таймаут",
    }


def _fixed_dt(y, mo, d, h=0, mi=0):
    class _FD:
        @staticmethod
        def now():
            return datetime(y, mo, d, h, mi, 0)
    return _FD


class ExportBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.src_file = self.tmp / "source.json"

    def tearDown(self):
        self._tmp.cleanup()


class TestProblemsToMarkdown(ExportBase):

    def test_full_problem_all_sections(self):
        md = _problems_to_markdown([_full_problem()])
        self.assertIn("## Приложение падает  [solved]", md)
        self.assertIn("ID: P1", md)
        self.assertIn("Крашится при старте", md)
        self.assertIn("**Решение:**", md)
        self.assertIn("Установил модуль x", md)
        self.assertIn("--- Как расследовали ---", md)
        self.assertIn("Вывод: Пропал модуль x", md)
        self.assertIn("Причина (подтверждена):", md)
        self.assertIn("[H1] Пропал модуль", md)
        self.assertIn("Выполненные шаги:", md)
        self.assertIn("[S1] Проверить права → ОК → Права (отклонена)", md)
        self.assertIn("Отклонённые гипотезы:", md)
        self.assertIn("[H2] Права", md)

    def test_problem_without_solution(self):
        md = _problems_to_markdown([_no_solution_problem()])
        self.assertIn("## Сервер не стартует  [new]", md)
        self.assertIn("Нет лога", md)
        self.assertNotIn("**Решение:**", md)
        self.assertNotIn("--- Как расследовали ---", md)

    def test_problem_without_diagnostic(self):
        md = _problems_to_markdown([_no_diagnostic_problem()])
        self.assertIn("**Решение:**", md)
        self.assertIn("Увеличил таймаут", md)
        self.assertNotIn("--- Как расследовали ---", md)

    def test_multiple_problems(self):
        md = _problems_to_markdown([_full_problem(), _no_solution_problem()])
        self.assertIn("## Приложение падает  [solved]", md)
        self.assertIn("## Сервер не стартует  [new]", md)
        self.assertLess(md.index("## Приложение падает"),
                        md.index("## Сервер не стартует"))

    def test_reuses_investigation_history(self):
        problem = _full_problem()
        md = _problems_to_markdown([problem])
        md_lines = {line.rstrip() for line in md.splitlines()}
        history = _format_investigation_history(problem)
        body = [history[0].lstrip("\n")] + history[1:]
        for line in body:
            if line.strip():
                self.assertIn(line.rstrip(), md_lines)

    def test_empty_problems(self):
        self.assertEqual(_problems_to_markdown([]), "")


class TestExportMarkdown(ExportBase):

    def test_creates_file_with_date(self):
        with patch.object(commands, "datetime", _fixed_dt(2026, 8, 27, 12, 0)):
            path, count = _export_markdown([_full_problem()], out_dir=self.tmp)
        self.assertEqual(path.name, "problems_2026-08-27.md")
        self.assertEqual(count, 1)
        self.assertTrue(path.exists())
        self.assertEqual(
            path.read_text(encoding="utf-8"),
            _problems_to_markdown([_full_problem()]),
        )

    def test_does_not_modify_storage(self):
        self.src_file.write_bytes(
            json.dumps([_full_problem()], ensure_ascii=False).encode("utf-8")
        )
        before = self.src_file.read_bytes()
        with patch.object(commands, "datetime", _fixed_dt(2026, 8, 27, 12, 0)):
            _export_markdown([_full_problem()], out_dir=self.tmp)
        self.assertEqual(self.src_file.read_bytes(), before)


class TestExportBackup(ExportBase):

    def test_byte_for_byte_timestamp(self):
        raw = json.dumps([_full_problem()], ensure_ascii=False).encode("utf-8")
        self.src_file.write_bytes(raw)
        with patch.object(commands, "datetime", _fixed_dt(2026, 8, 27, 10, 0)):
            with patch.object(commands._problems, "DATA_FILE", self.src_file):
                path = _export_backup(out_dir=self.tmp)
        self.assertEqual(path.name, "problems_2026-08-27_10-00-00.json")
        self.assertEqual(path.read_bytes(), raw)

    def test_timestamp_does_not_overwrite(self):
        self.src_file.write_bytes(b'[{"id":"P1"}]')
        with patch.object(commands, "datetime", _fixed_dt(2026, 8, 27, 10, 0)):
            with patch.object(commands._problems, "DATA_FILE", self.src_file):
                p1 = _export_backup(out_dir=self.tmp)
        with patch.object(commands, "datetime", _fixed_dt(2026, 8, 27, 10, 1)):
            with patch.object(commands._problems, "DATA_FILE", self.src_file):
                p2 = _export_backup(out_dir=self.tmp)
        self.assertNotEqual(p1, p2)
        self.assertEqual(p1.name, "problems_2026-08-27_10-00-00.json")
        self.assertEqual(p2.name, "problems_2026-08-27_10-01-00.json")
        self.assertTrue(p1.exists())
        self.assertTrue(p2.exists())

    def test_missing_source_writes_empty_list(self):
        with patch.object(commands, "datetime", _fixed_dt(2026, 8, 27, 10, 0)):
            with patch.object(commands._problems, "DATA_FILE", self.tmp / "nope.json"):
                path = _export_backup(out_dir=self.tmp)
        self.assertEqual(path.read_text(encoding="utf-8"), "[]")


class TestExportCommand(ExportBase):

    def _run_export(self, choice, problems, export_dir, backup_dir):
        self.src_file.write_bytes(
            json.dumps(problems, ensure_ascii=False).encode("utf-8")
        )
        buf = StringIO()
        with patch("src.commands.input", side_effect=[choice]), \
             patch.object(commands._problems, "DATA_FILE", self.src_file), \
             patch.object(commands, "EXPORT_DIR", export_dir), \
             patch.object(commands, "BACKUP_DIR", backup_dir), \
             patch.object(commands, "datetime", _fixed_dt(2026, 8, 27, 12, 0)):
            with redirect_stdout(buf):
                commands.export()
        return buf.getvalue()

    def test_export_all_creates_both_and_reports(self):
        export_dir = self.tmp / "export"
        backup_dir = self.tmp / "backup"
        problems = [_full_problem(), _no_solution_problem()]
        out = self._run_export("3", problems, export_dir, backup_dir)
        self.assertTrue((export_dir / "problems_2026-08-27.md").exists())
        self.assertTrue((backup_dir / "problems_2026-08-27_12-00-00.json").exists())
        self.assertIn("Экспорт:", out)
        self.assertIn("Бэкап:", out)
        self.assertIn("2 записей", out)

    def test_export_markdown_menu_option(self):
        export_dir = self.tmp / "export"
        backup_dir = self.tmp / "backup"
        out = self._run_export("1", [_full_problem()], export_dir, backup_dir)
        self.assertTrue((export_dir / "problems_2026-08-27.md").exists())
        self.assertIn("1 записей", out)
        self.assertNotIn("Бэкап:", out)

    def test_export_backup_menu_option(self):
        export_dir = self.tmp / "export"
        backup_dir = self.tmp / "backup"
        out = self._run_export("2", [_full_problem()], export_dir, backup_dir)
        self.assertTrue((backup_dir / "problems_2026-08-27_12-00-00.json").exists())
        self.assertIn("Бэкап:", out)
        self.assertNotIn("/problems_2026-08-27.md", out)

    def test_empty_storage_no_crash(self):
        export_dir = self.tmp / "export"
        backup_dir = self.tmp / "backup"
        out = self._run_export("1", [], export_dir, backup_dir)
        self.assertTrue((export_dir / "problems_2026-08-27.md").exists())
        self.assertIn("0 записей", out)

    def test_invalid_choice_no_crash(self):
        export_dir = self.tmp / "export"
        backup_dir = self.tmp / "backup"
        out = self._run_export("9", [_full_problem()], export_dir, backup_dir)
        self.assertIn("Неверный выбор.", out)
        self.assertFalse(list(export_dir.glob("*.md")))
        self.assertFalse(list(backup_dir.glob("*.json")))


class TestMenuAndRouter(unittest.TestCase):

    def test_menu_shows_export_option(self):
        from src.menu import show_menu
        buf = StringIO()
        with redirect_stdout(buf):
            show_menu()
        self.assertIn("5. Экспорт и бэкап", buf.getvalue())

    @patch("src.router.export")
    def test_route_5_calls_export(self, mock_export):
        from src.router import route
        self.assertTrue(route("5"))
        mock_export.assert_called_once()


if __name__ == "__main__":
    unittest.main()
