import unittest

from src.search import rank_records, _tokenize, _normalize


RECORDS = [
    {
        "id": "r1",
        "created_at": "2026-01-01T00:00:00+00:00",
        "type": "note",
        "title": "Python guide",
        "text": "Learn Python from scratch",
        "tags": ["python", "learn"],
    },
    {
        "id": "r2",
        "created_at": "2026-01-02T00:00:00+00:00",
        "type": "note",
        "title": "Java basics",
        "text": "Introduction to Java programming",
        "tags": ["java"],
    },
    {
        "id": "r3",
        "created_at": "2026-01-03T00:00:00+00:00",
        "type": "note",
        "title": "VSCode setup",
        "text": "How to configure Python in VSCode",
        "tags": ["vscode", "python"],
    },
    {
        "id": "r4",
        "created_at": "2026-01-04T00:00:00+00:00",
        "type": "problem",
        "title": "Ошибка Python vscode",
        "text": "При запуске кода в vscode возникает ошибка Python",
        "tags": ["python", "vscode", "ошибка"],
    },
    {
        "id": "r5",
        "created_at": "2026-01-05T00:00:00+00:00",
        "type": "note",
        "title": "Flask web framework",
        "text": "Building web apps with Flask and Python",
        "tags": ["flask", "web"],
    },
]


class TestNormalize(unittest.TestCase):

    def test_lowercase(self):
        self.assertEqual(_normalize("Hello World"), "hello world")

    def test_extra_spaces(self):
        self.assertEqual(_normalize("  hello   world  "), "hello world")

    def test_mixed(self):
        self.assertEqual(_normalize("  HELLO  World  "), "hello world")


class TestTokenize(unittest.TestCase):

    def test_single_word(self):
        self.assertEqual(_tokenize("python"), ["python"])

    def test_multiple_words(self):
        self.assertEqual(_tokenize("python vscode"), ["python", "vscode"])

    def test_duplicates_removed(self):
        self.assertEqual(_tokenize("python python"), ["python"])

    def test_empty(self):
        self.assertEqual(_tokenize(""), [])

    def test_whitespace_only(self):
        self.assertEqual(_tokenize("   "), [])

    def test_case_insensitive(self):
        self.assertEqual(_tokenize("Python PYTHON"), ["python"])

    def test_extra_spaces(self):
        self.assertEqual(_tokenize("  python  vscode  "), ["python", "vscode"])


class TestRankRecords(unittest.TestCase):

    def test_empty_query(self):
        self.assertEqual(rank_records("", RECORDS), [])

    def test_whitespace_query(self):
        self.assertEqual(rank_records("   ", RECORDS), [])

    def test_no_match(self):
        self.assertEqual(rank_records("golang", RECORDS), [])

    def test_single_word_finds_match(self):
        results = rank_records("flask", RECORDS)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0]["id"], "r5")

    def test_search_by_title(self):
        results = rank_records("Java basics", RECORDS)
        self.assertTrue(len(results) >= 1)
        self.assertEqual(results[0][0]["id"], "r2")

    def test_search_by_tags(self):
        results = rank_records("vscode", RECORDS)
        ids = [r[0]["id"] for r in results]
        self.assertIn("r3", ids)
        self.assertIn("r4", ids)

    def test_search_by_text(self):
        results = rank_records("scratch", RECORDS)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0]["id"], "r1")

    def test_multi_word_query(self):
        results = rank_records("python vscode", RECORDS)
        ids = [r[0]["id"] for r in results]
        self.assertIn("r3", ids)
        self.assertIn("r4", ids)

    def test_exact_title_beats_contains(self):
        r_exact = {
            "id": "e1",
            "created_at": "2026-01-01T00:00:00+00:00",
            "type": "note",
            "title": "python",
            "text": "",
            "tags": [],
        }
        r_contains = {
            "id": "c1",
            "created_at": "2026-01-01T00:00:00+00:00",
            "type": "note",
            "title": "learning python today",
            "text": "",
            "tags": [],
        }
        results = rank_records("python", [r_exact, r_contains])
        self.assertEqual(results[0][0]["id"], "e1")

    def test_title_match_beats_tag_match(self):
        r_title = {
            "id": "t1",
            "created_at": "2026-01-01T00:00:00+00:00",
            "type": "note",
            "title": "python",
            "text": "",
            "tags": [],
        }
        r_tag = {
            "id": "g1",
            "created_at": "2026-01-01T00:00:00+00:00",
            "type": "note",
            "title": "something else",
            "text": "",
            "tags": ["python"],
        }
        results = rank_records("python", [r_title, r_tag])
        self.assertEqual(results[0][0]["id"], "t1")

    def test_tag_match_beats_text_match(self):
        r_tag = {
            "id": "g2",
            "created_at": "2026-01-01T00:00:00+00:00",
            "type": "note",
            "title": "",
            "text": "something",
            "tags": ["flask"],
        }
        r_text = {
            "id": "x1",
            "created_at": "2026-01-01T00:00:00+00:00",
            "type": "note",
            "title": "",
            "text": "flask is great",
            "tags": [],
        }
        results = rank_records("flask", [r_tag, r_text])
        self.assertEqual(results[0][0]["id"], "g2")

    def test_coverage_bonus(self):
        r_multi = {
            "id": "m1",
            "created_at": "2026-01-01T00:00:00+00:00",
            "type": "note",
            "title": "python vscode error",
            "text": "description",
            "tags": [],
        }
        r_single = {
            "id": "s1",
            "created_at": "2026-01-01T00:00:00+00:00",
            "type": "note",
            "title": "python",
            "text": "just python",
            "tags": [],
        }
        results = rank_records("python vscode error", [r_multi, r_single])
        self.assertEqual(results[0][0]["id"], "m1")

    def test_russian_text(self):
        results = rank_records("ошибка", RECORDS)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0]["id"], "r4")

    def test_russian_multi_word(self):
        results = rank_records("ошибка python vscode", RECORDS)
        self.assertTrue(len(results) >= 1)
        self.assertEqual(results[0][0]["id"], "r4")

    def test_english_text(self):
        results = rank_records("Introduction", RECORDS)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0]["id"], "r2")

    def test_case_insensitive_search(self):
        r1 = rank_records("PYTHON", RECORDS)
        r2 = rank_records("python", RECORDS)
        r3 = rank_records("Python", RECORDS)
        self.assertEqual([r[0]["id"] for r in r1], [r[0]["id"] for r in r2])
        self.assertEqual([r[0]["id"] for r in r2], [r[0]["id"] for r in r3])

    def test_extra_spaces_in_query(self):
        r1 = rank_records("python  vscode", RECORDS)
        r2 = rank_records("python vscode", RECORDS)
        self.assertEqual([r[0]["id"] for r in r1], [r[0]["id"] for r in r2])

    def test_duplicate_words_in_query(self):
        r1 = rank_records("python python", RECORDS)
        r2 = rank_records("python", RECORDS)
        self.assertEqual([r[0]["id"] for r in r1], [r[0]["id"] for r in r2])

    def test_results_sorted_by_score(self):
        results = rank_records("python", RECORDS)
        scores = [r[1] for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_score_is_positive(self):
        results = rank_records("python", RECORDS)
        for _record, score in results:
            self.assertGreater(score, 0)

    def test_score_available_in_results(self):
        results = rank_records("python", RECORDS)
        for record, score in results:
            self.assertIn("id", record)
            self.assertIsInstance(score, float)


if __name__ == "__main__":
    unittest.main()
