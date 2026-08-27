import unittest

from src.ai.types import AIResponse
from src.ai.provider import AIProvider, NullProvider, SYSTEM_PROMPT
from src.ai.context import (
    build_analyze_problem_context,
    build_analyze_experience_context,
    build_create_plan_context,
    build_analyze_result_context,
    build_format_knowledge_context,
    _compact_problem,
    _compact_knowledge,
    MAX_SEARCH_RESULTS,
    MAX_KNOWLEDGE_TEXT,
    MAX_PLAN_SOLUTIONS,
)
from tests.fake_provider import FakeProvider


# ── AIResponse ─────────────────────────────────────────────────────

class TestAIResponse(unittest.TestCase):

    def test_create_with_all_fields(self):
        r = AIResponse(
            success=True,
            content="Анализ",
            suggestions=["Шаг 1", "Шаг 2"],
            confidence=0.9,
            error=None,
        )
        self.assertTrue(r.success)
        self.assertEqual(r.content, "Анализ")
        self.assertEqual(r.suggestions, ["Шаг 1", "Шаг 2"])
        self.assertAlmostEqual(r.confidence, 0.9)
        self.assertIsNone(r.error)

    def test_create_minimal(self):
        r = AIResponse(success=False, content="")
        self.assertFalse(r.success)
        self.assertEqual(r.content, "")
        self.assertEqual(r.suggestions, [])
        self.assertAlmostEqual(r.confidence, 0.0)
        self.assertIsNone(r.error)

    def test_default_suggestions_is_empty_list(self):
        r = AIResponse(success=True, content="x")
        self.assertEqual(r.suggestions, [])
        r.suggestions.append("test")
        self.assertEqual(r.suggestions, ["test"])

    def test_default_confidence_zero(self):
        r = AIResponse(success=True, content="x")
        self.assertAlmostEqual(r.confidence, 0.0)

    def test_default_error_none(self):
        r = AIResponse(success=True, content="x")
        self.assertIsNone(r.error)

    def test_error_field(self):
        r = AIResponse(success=False, content="", error="API timeout")
        self.assertEqual(r.error, "API timeout")

    def test_empty_content(self):
        r = AIResponse(success=True, content="")
        self.assertEqual(r.content, "")

    def test_empty_suggestions(self):
        r = AIResponse(success=True, content="x", suggestions=[])
        self.assertEqual(r.suggestions, [])


# ── AIProvider base ────────────────────────────────────────────────

class TestAIProviderBase(unittest.TestCase):

    def setUp(self):
        self.provider = AIProvider()

    def test_analyze_problem_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            self.provider.analyze_problem({}, {"knowledge": [], "problems": []})

    def test_analyze_experience_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            self.provider.analyze_experience({}, {"knowledge": [], "problems": []})

    def test_create_plan_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            self.provider.create_plan({}, "cause", [])

    def test_analyze_result_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            self.provider.analyze_result({}, "solution", True)

    def test_format_knowledge_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            self.provider.format_knowledge({})


# ── NullProvider ───────────────────────────────────────────────────

class TestNullProvider(unittest.TestCase):

    def setUp(self):
        self.provider = NullProvider()

    def test_analyze_problem_returns_success_false(self):
        r = self.provider.analyze_problem({}, {"knowledge": [], "problems": []})
        self.assertFalse(r.success)
        self.assertEqual(r.content, "")
        self.assertEqual(r.suggestions, [])
        self.assertAlmostEqual(r.confidence, 0.0)
        self.assertIsNone(r.error)

    def test_analyze_experience_returns_success_false(self):
        r = self.provider.analyze_experience({}, {"knowledge": [], "problems": []})
        self.assertFalse(r.success)

    def test_create_plan_returns_success_false(self):
        r = self.provider.create_plan({}, "cause", [])
        self.assertFalse(r.success)

    def test_analyze_result_returns_success_false(self):
        r = self.provider.analyze_result({}, "solution", True)
        self.assertFalse(r.success)

    def test_format_knowledge_returns_success_false(self):
        r = self.provider.format_knowledge({})
        self.assertFalse(r.success)

    def test_is_ai_provider_subclass(self):
        self.assertIsInstance(self.provider, AIProvider)


# ── FakeProvider ───────────────────────────────────────────────────

class TestFakeProvider(unittest.TestCase):

    def setUp(self):
        self.provider = FakeProvider()

    def test_analyze_problem_default_success(self):
        r = self.provider.analyze_problem(
            {"title": "test"}, {"knowledge": [], "problems": []}
        )
        self.assertTrue(r.success)
        self.assertIn("анализ", r.content.lower())

    def test_analyze_experience_default_success(self):
        r = self.provider.analyze_experience(
            {"title": "test"}, {"knowledge": [], "problems": []}
        )
        self.assertTrue(r.success)
        self.assertIn("опыт", r.content)

    def test_create_plan_default_success(self):
        r = self.provider.create_plan({"title": "test"}, "cause", ["sol1"])
        self.assertTrue(r.success)
        self.assertIn("план", r.content)

    def test_analyze_result_default_success(self):
        r = self.provider.analyze_result({"title": "test"}, "fix", True)
        self.assertTrue(r.success)
        self.assertIn("результата", r.content)

    def test_format_knowledge_default_success(self):
        r = self.provider.format_knowledge({"title": "test"})
        self.assertTrue(r.success)
        self.assertIn("записи", r.content)

    def test_custom_response(self):
        provider = FakeProvider(responses={
            "analyze_problem": AIResponse(
                success=True, content="Кастомный анализ",
                suggestions=["custom"], confidence=0.5,
            ),
        })
        r = provider.analyze_problem({"title": "x"}, {"knowledge": [], "problems": []})
        self.assertEqual(r.content, "Кастомный анализ")
        self.assertEqual(r.suggestions, ["custom"])

    def test_custom_error_response(self):
        provider = FakeProvider(responses={
            "analyze_problem": AIResponse(
                success=False, content="", error="Network error",
            ),
        })
        r = provider.analyze_problem({"title": "x"}, {"knowledge": [], "problems": []})
        self.assertFalse(r.success)
        self.assertEqual(r.error, "Network error")

    def test_calls_logged(self):
        self.provider.analyze_problem(
            {"title": "t"}, {"knowledge": [], "problems": []}
        )
        self.provider.create_plan({"title": "t"}, "c", [])
        calls = self.provider.get_calls()
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][0], "analyze_problem")
        self.assertEqual(calls[1][0], "create_plan")

    def test_call_count_all(self):
        self.provider.analyze_problem({}, {"knowledge": [], "problems": []})
        self.provider.create_plan({}, "", [])
        self.assertEqual(self.provider.call_count(), 2)

    def test_call_count_by_method(self):
        self.provider.analyze_problem({}, {"knowledge": [], "problems": []})
        self.provider.analyze_problem({}, {"knowledge": [], "problems": []})
        self.provider.create_plan({}, "", [])
        self.assertEqual(self.provider.call_count("analyze_problem"), 2)
        self.assertEqual(self.provider.call_count("create_plan"), 1)

    def test_get_calls_filtered(self):
        self.provider.analyze_problem({}, {"knowledge": [], "problems": []})
        self.provider.create_plan({}, "", [])
        self.provider.create_plan({}, "", [])
        filtered = self.provider.get_calls("create_plan")
        self.assertEqual(len(filtered), 2)
        self.assertTrue(all(c[0] == "create_plan" for c in filtered))

    def test_calls_args_captured(self):
        problem = {"title": "t"}
        sr = {"knowledge": [], "problems": []}
        self.provider.analyze_problem(problem, sr)
        calls = self.provider.get_calls("analyze_problem")
        self.assertEqual(calls[0][1][0], problem)
        self.assertEqual(calls[0][1][1], sr)

    def test_is_ai_provider_subclass(self):
        self.assertIsInstance(self.provider, AIProvider)


# ── Context builders ───────────────────────────────────────────────

class TestCompactProblem(unittest.TestCase):

    def test_all_fields(self):
        p = {
            "id": "abc", "created_at": "2026-01-01",
            "title": "T", "description": "D", "context": "C",
            "error_message": "E", "tags": ["python"],
            "status": "new", "cause": "X", "solution": "Y",
            "helped": True, "related_record_id": "r1",
        }
        c = _compact_problem(p)
        self.assertEqual(c["title"], "T")
        self.assertEqual(c["description"], "D")
        self.assertEqual(c["context"], "C")
        self.assertEqual(c["error_message"], "E")
        self.assertEqual(c["tags"], ["python"])
        self.assertEqual(c["status"], "new")
        self.assertEqual(c["cause"], "X")
        self.assertEqual(c["solution"], "Y")
        self.assertNotIn("id", c)
        self.assertNotIn("created_at", c)
        self.assertNotIn("helped", c)
        self.assertNotIn("related_record_id", c)

    def test_empty_problem(self):
        c = _compact_problem({})
        self.assertEqual(c["title"], "")
        self.assertEqual(c["description"], "")
        self.assertEqual(c["context"], "")
        self.assertEqual(c["error_message"], "")
        self.assertEqual(c["tags"], [])
        self.assertEqual(c["status"], "")
        self.assertEqual(c["cause"], "")
        self.assertEqual(c["solution"], "")


class TestCompactKnowledge(unittest.TestCase):

    def test_all_fields(self):
        r = {
            "id": "abc", "created_at": "2026-01-01",
            "title": "T", "type": "solution",
            "text": "Hello world", "tags": ["flask"],
        }
        c = _compact_knowledge(r)
        self.assertEqual(c["title"], "T")
        self.assertEqual(c["type"], "solution")
        self.assertEqual(c["text"], "Hello world")
        self.assertEqual(c["tags"], ["flask"])
        self.assertNotIn("id", c)
        self.assertNotIn("created_at", c)

    def test_text_truncated(self):
        long_text = "x" * (MAX_KNOWLEDGE_TEXT + 100)
        r = {"title": "T", "type": "note", "text": long_text, "tags": []}
        c = _compact_knowledge(r)
        self.assertEqual(len(c["text"]), MAX_KNOWLEDGE_TEXT)

    def test_text_not_truncated_when_short(self):
        r = {"title": "T", "type": "note", "text": "short", "tags": []}
        c = _compact_knowledge(r)
        self.assertEqual(c["text"], "short")

    def test_empty_record(self):
        c = _compact_knowledge({})
        self.assertEqual(c["title"], "")
        self.assertEqual(c["type"], "")
        self.assertEqual(c["text"], "")
        self.assertEqual(c["tags"], [])


class TestBuildAnalyzeProblemContext(unittest.TestCase):

    def test_basic_structure(self):
        p = {"title": "T", "description": "D"}
        kr = [({"title": "K1", "type": "solution", "text": "t", "tags": []}, 5.0)]
        pr = [({"title": "P1"}, 3.0)]
        ctx = build_analyze_problem_context(p, kr, pr)
        self.assertEqual(ctx["problem"]["title"], "T")
        self.assertEqual(len(ctx["similar_knowledge"]), 1)
        self.assertEqual(ctx["similar_knowledge"][0]["title"], "K1")
        self.assertEqual(len(ctx["similar_problems"]), 1)

    def test_limits_to_max_search_results(self):
        p = {"title": "T"}
        kr = [({"title": f"K{i}", "type": "note", "text": "", "tags": []}, float(i))
              for i in range(10)]
        pr = [({"title": f"P{i}"}, float(i)) for i in range(10)]
        ctx = build_analyze_problem_context(p, kr, pr)
        self.assertEqual(len(ctx["similar_knowledge"]), MAX_SEARCH_RESULTS)
        self.assertEqual(len(ctx["similar_problems"]), MAX_SEARCH_RESULTS)

    def test_empty_results(self):
        ctx = build_analyze_problem_context({"title": "T"}, [], [])
        self.assertEqual(ctx["similar_knowledge"], [])
        self.assertEqual(ctx["similar_problems"], [])


class TestBuildAnalyzeExperienceContext(unittest.TestCase):

    def test_basic_structure(self):
        p = {"title": "T"}
        kr = [({"title": "K1", "type": "solution", "text": "t", "tags": []}, 5.0)]
        pr = [({"title": "P1"}, 3.0)]
        ctx = build_analyze_experience_context(p, kr, pr)
        self.assertEqual(ctx["problem"]["title"], "T")
        self.assertEqual(len(ctx["knowledge_options"]), 1)
        self.assertEqual(len(ctx["problem_options"]), 1)

    def test_limits(self):
        p = {"title": "T"}
        kr = [({"title": f"K{i}", "type": "note", "text": "", "tags": []}, float(i))
              for i in range(10)]
        pr = [({"title": f"P{i}"}, float(i)) for i in range(10)]
        ctx = build_analyze_experience_context(p, kr, pr)
        self.assertEqual(len(ctx["knowledge_options"]), MAX_SEARCH_RESULTS)
        self.assertEqual(len(ctx["problem_options"]), MAX_SEARCH_RESULTS)


class TestBuildCreatePlanContext(unittest.TestCase):

    def test_basic(self):
        ctx = build_create_plan_context(
            {"title": "T"}, "cause", ["sol1", "sol2", "sol3", "sol4"]
        )
        self.assertEqual(ctx["problem"]["title"], "T")
        self.assertEqual(ctx["cause"], "cause")
        self.assertEqual(len(ctx["similar_solutions"]), MAX_PLAN_SOLUTIONS)

    def test_empty(self):
        ctx = build_create_plan_context({"title": "T"}, "", [])
        self.assertEqual(ctx["cause"], "")
        self.assertEqual(ctx["similar_solutions"], [])


class TestBuildAnalyzeResultContext(unittest.TestCase):

    def test_basic(self):
        ctx = build_analyze_result_context({"title": "T"}, "fix", True)
        self.assertEqual(ctx["problem"]["title"], "T")
        self.assertEqual(ctx["solution"], "fix")
        self.assertTrue(ctx["helped"])

    def test_helped_none(self):
        ctx = build_analyze_result_context({"title": "T"}, "fix", None)
        self.assertIsNone(ctx["helped"])


class TestBuildFormatKnowledgeContext(unittest.TestCase):

    def test_basic(self):
        p = {"title": "T", "cause": "C", "solution": "S", "helped": True}
        ctx = build_format_knowledge_context(p)
        self.assertEqual(ctx["problem"]["title"], "T")
        self.assertEqual(ctx["cause"], "C")
        self.assertEqual(ctx["solution"], "S")
        self.assertTrue(ctx["helped"])

    def test_empty_problem(self):
        ctx = build_format_knowledge_context({})
        self.assertEqual(ctx["cause"], "")
        self.assertEqual(ctx["solution"], "")
        self.assertIsNone(ctx["helped"])


# ── SYSTEM_PROMPT ──────────────────────────────────────────────────

class TestSystemPrompt(unittest.TestCase):

    def test_is_string(self):
        self.assertIsInstance(SYSTEM_PROMPT, str)

    def test_not_empty(self):
        self.assertTrue(len(SYSTEM_PROMPT) > 0)

    def test_mentions_rules(self):
        self.assertIn("Правила", SYSTEM_PROMPT)


# ── AI не влияет на данные ─────────────────────────────────────────

class TestAIDoesNotAffectData(unittest.TestCase):
    """AI-слой НЕ должен изменять данные Core."""

    def test_null_provider_readonly(self):
        provider = NullProvider()
        problem = {"title": "T", "status": "new"}
        original = dict(problem)
        provider.analyze_problem(problem, {"knowledge": [], "problems": []})
        provider.analyze_experience(problem, {"knowledge": [], "problems": []})
        provider.create_plan(problem, "cause", [])
        provider.analyze_result(problem, "solution", True)
        provider.format_knowledge(problem)
        self.assertEqual(problem, original)

    def test_fake_provider_readonly(self):
        provider = FakeProvider()
        problem = {"title": "T", "status": "new"}
        original = dict(problem)
        provider.analyze_problem(problem, {"knowledge": [], "problems": []})
        provider.analyze_experience(problem, {"knowledge": [], "problems": []})
        provider.create_plan(problem, "cause", [])
        provider.analyze_result(problem, "solution", True)
        provider.format_knowledge(problem)
        self.assertEqual(problem, original)


# ── Константы ──────────────────────────────────────────────────────

class TestConstants(unittest.TestCase):

    def test_max_search_results(self):
        self.assertEqual(MAX_SEARCH_RESULTS, 5)

    def test_max_knowledge_text(self):
        self.assertEqual(MAX_KNOWLEDGE_TEXT, 500)

    def test_max_plan_solutions(self):
        self.assertEqual(MAX_PLAN_SOLUTIONS, 3)
