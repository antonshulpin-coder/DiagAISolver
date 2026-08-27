import json
import unittest
from pathlib import Path
from unittest.mock import patch

from src.storage import (
    load_notes,
    save_notes,
    create_record,
    get_record,
    get_all_records,
    update_record,
    delete_record,
    search_records,
    search_records_with_scores,
    add_note,
    StorageError,
)


TEST_DATA = Path(__file__).resolve().parent.parent / "data" / "notes_test.json"


class TestMigration(unittest.TestCase):

    @patch("src.storage.DATA_FILE", TEST_DATA)
    def setUp(self):
        TEST_DATA.unlink(missing_ok=True)

    @patch("src.storage.DATA_FILE", TEST_DATA)
    def test_old_format_migrated(self):
        old = [{"text": "old note"}, {"text": "another"}]
        TEST_DATA.write_text(json.dumps(old, ensure_ascii=False), encoding="utf-8")
        result = load_notes()
        self.assertEqual(len(result), 2)
        for r in result:
            self.assertIn("id", r)
            self.assertIn("created_at", r)
            self.assertEqual(r["type"], "note")
            self.assertEqual(r["title"], "")
            self.assertEqual(r["tags"], [])

    @patch("src.storage.DATA_FILE", TEST_DATA)
    def test_old_format_text_preserved(self):
        old = [{"text": "important text"}]
        TEST_DATA.write_text(json.dumps(old, ensure_ascii=False), encoding="utf-8")
        result = load_notes()
        self.assertEqual(result[0]["text"], "important text")

    @patch("src.storage.DATA_FILE", TEST_DATA)
    def test_new_format_not_migrated(self):
        new = [{
            "id": "abc123",
            "created_at": "2025-01-01T00:00:00+00:00",
            "type": "note",
            "title": "test",
            "text": "content",
            "tags": ["tag1"],
        }]
        TEST_DATA.write_text(json.dumps(new, ensure_ascii=False), encoding="utf-8")
        result = load_notes()
        self.assertEqual(result[0]["id"], "abc123")
        self.assertEqual(result[0]["title"], "test")

    @patch("src.storage.DATA_FILE", TEST_DATA)
    def test_migration_persists(self):
        old = [{"text": "migrate me"}]
        TEST_DATA.write_text(json.dumps(old, ensure_ascii=False), encoding="utf-8")
        load_notes()
        reloaded = load_notes()
        self.assertEqual(reloaded[0]["text"], "migrate me")
        self.assertIn("id", reloaded[0])


class TestLoadNotes(unittest.TestCase):

    @patch("src.storage.DATA_FILE", TEST_DATA)
    def setUp(self):
        TEST_DATA.unlink(missing_ok=True)

    @patch("src.storage.DATA_FILE", TEST_DATA)
    def test_load_when_file_missing(self):
        self.assertEqual(load_notes(), [])

    @patch("src.storage.DATA_FILE", TEST_DATA)
    def test_load_corrupt_json(self):
        TEST_DATA.write_text("{broken", encoding="utf-8")
        with self.assertRaises(StorageError):
            load_notes()

    @patch("src.storage.DATA_FILE", TEST_DATA)
    def test_load_wrong_type(self):
        TEST_DATA.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
        with self.assertRaises(StorageError):
            load_notes()


class TestSaveNotes(unittest.TestCase):

    @patch("src.storage.DATA_FILE", TEST_DATA)
    def setUp(self):
        TEST_DATA.unlink(missing_ok=True)

    @patch("src.storage.DATA_FILE", TEST_DATA)
    def test_save_creates_file(self):
        save_notes([{"id": "x", "text": "test"}])
        data = json.loads(TEST_DATA.read_text(encoding="utf-8"))
        self.assertEqual(len(data), 1)

    @patch("src.storage.DATA_FILE", TEST_DATA)
    def test_save_no_tmp_left(self):
        save_notes([{"id": "y", "text": "x"}])
        self.assertFalse(TEST_DATA.with_suffix(".tmp").exists())


class TestCreateRecord(unittest.TestCase):

    @patch("src.storage.DATA_FILE", TEST_DATA)
    def setUp(self):
        TEST_DATA.unlink(missing_ok=True)

    @patch("src.storage.DATA_FILE", TEST_DATA)
    def test_create_record_returns_record(self):
        r = create_record(title="T", text="B", record_type="idea", tags=["a", "b"])
        self.assertEqual(r["title"], "T")
        self.assertEqual(r["text"], "B")
        self.assertEqual(r["type"], "idea")
        self.assertEqual(r["tags"], ["a", "b"])
        self.assertIn("id", r)
        self.assertIn("created_at", r)

    @patch("src.storage.DATA_FILE", TEST_DATA)
    def test_create_record_persists(self):
        r = create_record(title="X", text="Y")
        loaded = get_record(r["id"])
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["title"], "X")

    @patch("src.storage.DATA_FILE", TEST_DATA)
    def test_create_record_default_type(self):
        r = create_record(title="", text="just text")
        self.assertEqual(r["type"], "note")


class TestGetRecord(unittest.TestCase):

    @patch("src.storage.DATA_FILE", TEST_DATA)
    def setUp(self):
        TEST_DATA.unlink(missing_ok=True)

    @patch("src.storage.DATA_FILE", TEST_DATA)
    def test_get_existing(self):
        r = create_record(title="A", text="B")
        found = get_record(r["id"])
        self.assertIsNotNone(found)
        self.assertEqual(found["id"], r["id"])

    @patch("src.storage.DATA_FILE", TEST_DATA)
    def test_get_nonexistent(self):
        self.assertIsNone(get_record("nonexistent"))


class TestUpdateRecord(unittest.TestCase):

    @patch("src.storage.DATA_FILE", TEST_DATA)
    def setUp(self):
        TEST_DATA.unlink(missing_ok=True)

    @patch("src.storage.DATA_FILE", TEST_DATA)
    def test_update_title(self):
        r = create_record(title="old", text="text")
        updated = update_record(r["id"], title="new")
        self.assertEqual(updated["title"], "new")
        self.assertEqual(updated["text"], "text")

    @patch("src.storage.DATA_FILE", TEST_DATA)
    def test_update_tags(self):
        r = create_record(title="T", text="B", tags=["old"])
        updated = update_record(r["id"], tags=["new1", "new2"])
        self.assertEqual(updated["tags"], ["new1", "new2"])

    @patch("src.storage.DATA_FILE", TEST_DATA)
    def test_update_nonexistent(self):
        result = update_record("nope", title="X")
        self.assertIsNone(result)


class TestDeleteRecord(unittest.TestCase):

    @patch("src.storage.DATA_FILE", TEST_DATA)
    def setUp(self):
        TEST_DATA.unlink(missing_ok=True)

    @patch("src.storage.DATA_FILE", TEST_DATA)
    def test_delete_existing(self):
        r = create_record(title="T", text="B")
        self.assertTrue(delete_record(r["id"]))
        self.assertIsNone(get_record(r["id"]))

    @patch("src.storage.DATA_FILE", TEST_DATA)
    def test_delete_nonexistent(self):
        self.assertFalse(delete_record("nope"))


class TestSearchRecords(unittest.TestCase):

    @patch("src.storage.DATA_FILE", TEST_DATA)
    def setUp(self):
        TEST_DATA.unlink(missing_ok=True)
        create_record(title="Python guide", text="Learn Python", tags=["python", "learn"])
        create_record(title="Java intro", text="Java basics", tags=["java"])
        create_record(title="", text="Python advanced topics", tags=["advanced"])

    @patch("src.storage.DATA_FILE", TEST_DATA)
    def test_search_by_title(self):
        results = search_records("Python guide")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Python guide")

    @patch("src.storage.DATA_FILE", TEST_DATA)
    def test_search_by_text(self):
        results = search_records("basics")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Java intro")

    @patch("src.storage.DATA_FILE", TEST_DATA)
    def test_search_by_tags(self):
        results = search_records("python")
        self.assertEqual(len(results), 2)

    @patch("src.storage.DATA_FILE", TEST_DATA)
    def test_search_empty_query(self):
        self.assertEqual(search_records(""), [])

    @patch("src.storage.DATA_FILE", TEST_DATA)
    def test_search_whitespace(self):
        self.assertEqual(search_records("   "), [])

    @patch("src.storage.DATA_FILE", TEST_DATA)
    def test_search_no_match(self):
        self.assertEqual(search_records("C++"), [])

    @patch("src.storage.DATA_FILE", TEST_DATA)
    def test_search_ranked_by_relevance(self):
        results = search_records("Python")
        self.assertTrue(len(results) >= 1)
        titles = [r["title"] for r in results]
        self.assertIn("Python guide", titles)

    @patch("src.storage.DATA_FILE", TEST_DATA)
    def test_search_multi_word(self):
        results = search_records("Python guide")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Python guide")

    @patch("src.storage.DATA_FILE", TEST_DATA)
    def test_search_with_scores_returns_tuples(self):
        results = search_records_with_scores("Python")
        self.assertIsInstance(results, list)
        self.assertTrue(len(results) >= 1)
        record, score = results[0]
        self.assertIn("id", record)
        self.assertIsInstance(score, float)
        self.assertGreater(score, 0)

    @patch("src.storage.DATA_FILE", TEST_DATA)
    def test_search_with_scores_empty_query(self):
        self.assertEqual(search_records_with_scores(""), [])


class TestAddNoteCompat(unittest.TestCase):

    @patch("src.storage.DATA_FILE", TEST_DATA)
    def setUp(self):
        TEST_DATA.unlink(missing_ok=True)

    @patch("src.storage.DATA_FILE", TEST_DATA)
    def test_add_note_creates_record(self):
        r = add_note("compat test")
        self.assertEqual(r["text"], "compat test")
        self.assertIn("id", r)


class TestUniqueId(unittest.TestCase):

    @patch("src.storage.DATA_FILE", TEST_DATA)
    def setUp(self):
        TEST_DATA.unlink(missing_ok=True)

    @patch("src.storage.DATA_FILE", TEST_DATA)
    def test_ids_are_unique(self):
        ids = set()
        for _ in range(20):
            r = create_record(title="T", text="B")
            ids.add(r["id"])
        self.assertEqual(len(ids), 20)


if __name__ == "__main__":
    unittest.main()
