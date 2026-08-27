import unittest
from pathlib import Path
from unittest.mock import patch

from src.ai.types import AIResponse
from src.ai.provider import NullProvider
from src.solve import (
    ai_analyze_problem,
    ai_analyze_experience,
    ai_create_plan,
    ai_analyze_result,
    ai_format_knowledge,
    _safe_ai_call,
    _get_provider,
    find_similar,
    resolve_problem,
    convert_to_knowledge,
    start_investigation,
    start_solving,
    SolveError,
)
from tests.fake_provider import FakeProvider


PROBLEMS_TEST = Path(__file__).resolve().parent.parent / "data" / "problems_solve_ai_test.json"
NOTES_TEST = Path(__file__).resolve().parent.parent / "data" / "notes_solve_ai_test.json"


def _clean():
    PROBLEMS_TEST.unlink(missing_ok=True)
    NOTES_TEST.unlink(missing_ok=True)


def _patchboth(fn):
    return patch("src.solve._problems.DATA_FILE", PROBLEMS_TEST)(
        patch("src.solve._storage.DATA_FILE", NOTES_TEST)(fn)
    )


def _make_problem(**overrides):
    from src.problems import create_problem
    defaults = dict(
        title="Ошибка Python",
        description="При запуске падает",
        context="Windows 11",
        error_message="ModuleNotFoundError: No module named 'flask'",
        tags=["python", "flask"],
    )
    defaults.update(overrides)
    return create_problem(**defaults)


# ── _safe_ai_call ────────────────────────────────────────────────

class TestSafeAiCall(unittest.TestCase):

    def test_successful_call(self):
        result = _safe_ai_call(lambda: AIResponse(success=True, content="ok"))
        self.assertTrue(result.success)
        self.assertEqual(result.content, "ok")

    def test_exception_returns_fallback(self):
        def boom():
            raise RuntimeError("AI broken")
        result = _safe_ai_call(boom)
        self.assertFalse(result.success)
        self.assertEqual(result.content, "")

    def test_custom_fallback(self):
        fallback = AIResponse(success=False, content="custom fallback")
        def boom():
            raise ValueError("x")
        result = _safe_ai_call(boom, fallback)
        self.assertEqual(result.content, "custom fallback")


# ── _get_provider ────────────────────────────────────────────────

class TestGetProvider(unittest.TestCase):

    def test_none_returns_null(self):
        p = _get_provider(None)
        self.assertIsInstance(p, NullProvider)

    def test_returns_given_provider(self):
        fake = FakeProvider()
        p = _get_provider(fake)
        self.assertIs(p, fake)


# ── ai_analyze_problem ───────────────────────────────────────────

class TestAiAnalyzeProblem(unittest.TestCase):

    def test_with_null_provider(self):
        r = ai_analyze_problem({"title": "T"}, [], [], provider=None)
        self.assertFalse(r.success)

    def test_with_fake_provider(self):
        fake = FakeProvider()
        r = ai_analyze_problem({"title": "T"}, [], [], provider=fake)
        self.assertTrue(r.success)
        self.assertIn("анализ", r.content.lower())
        self.assertEqual(fake.call_count("analyze_problem"), 1)

    def test_exception_in_provider(self):
        class BrokenProvider(NullProvider):
            def analyze_problem(self, problem, search_results):
                raise RuntimeError("API down")
        r = ai_analyze_problem({"title": "T"}, [], [], provider=BrokenProvider())
        self.assertFalse(r.success)

    def test_context_passed_to_provider(self):
        fake = FakeProvider()
        kr = [({"title": "K1", "type": "note", "text": "t", "tags": []}, 5.0)]
        pr = [({"title": "P1"}, 3.0)]
        ai_analyze_problem({"title": "T"}, kr, pr, provider=fake)
        call = fake.get_calls("analyze_problem")[0]
        ctx = call[1][0]
        self.assertEqual(ctx["problem"]["title"], "T")
        self.assertEqual(len(ctx["similar_knowledge"]), 1)


# ── ai_analyze_experience ────────────────────────────────────────

class TestAiAnalyzeExperience(unittest.TestCase):

    def test_with_null_provider(self):
        r = ai_analyze_experience({"title": "T"}, [], [], provider=None)
        self.assertFalse(r.success)

    def test_with_fake_provider(self):
        fake = FakeProvider()
        r = ai_analyze_experience({"title": "T"}, [], [], provider=fake)
        self.assertTrue(r.success)
        self.assertIn("опыт", r.content)
        self.assertEqual(fake.call_count("analyze_experience"), 1)

    def test_exception_in_provider(self):
        class BrokenProvider(NullProvider):
            def analyze_experience(self, problem, search_results):
                raise RuntimeError("fail")
        r = ai_analyze_experience({"title": "T"}, [], [], provider=BrokenProvider())
        self.assertFalse(r.success)


# ── ai_create_plan ───────────────────────────────────────────────

class TestAiCreatePlan(unittest.TestCase):

    def test_with_null_provider(self):
        r = ai_create_plan({"title": "T"}, "cause", ["sol1"], provider=None)
        self.assertFalse(r.success)

    def test_with_fake_provider(self):
        fake = FakeProvider()
        r = ai_create_plan({"title": "T"}, "cause", ["sol1"], provider=fake)
        self.assertTrue(r.success)
        self.assertIn("план", r.content)
        self.assertEqual(fake.call_count("create_plan"), 1)

    def test_exception_in_provider(self):
        class BrokenProvider(NullProvider):
            def create_plan(self, problem, cause, similar_solutions):
                raise RuntimeError("fail")
        r = ai_create_plan({"title": "T"}, "cause", [], provider=BrokenProvider())
        self.assertFalse(r.success)


# ── ai_analyze_result ────────────────────────────────────────────

class TestAiAnalyzeResult(unittest.TestCase):

    def test_with_null_provider(self):
        r = ai_analyze_result({"title": "T"}, "fix", True, provider=None)
        self.assertFalse(r.success)

    def test_with_fake_provider(self):
        fake = FakeProvider()
        r = ai_analyze_result({"title": "T"}, "fix", True, provider=fake)
        self.assertTrue(r.success)
        self.assertIn("результата", r.content)
        self.assertEqual(fake.call_count("analyze_result"), 1)

    def test_exception_in_provider(self):
        class BrokenProvider(NullProvider):
            def analyze_result(self, problem, solution, helped):
                raise RuntimeError("fail")
        r = ai_analyze_result({"title": "T"}, "fix", None, provider=BrokenProvider())
        self.assertFalse(r.success)


# ── ai_format_knowledge ──────────────────────────────────────────

class TestAiFormatKnowledge(unittest.TestCase):

    def test_with_null_provider(self):
        r = ai_format_knowledge({"title": "T"}, provider=None)
        self.assertFalse(r.success)

    def test_with_fake_provider(self):
        fake = FakeProvider()
        r = ai_format_knowledge({"title": "T"}, provider=fake)
        self.assertTrue(r.success)
        self.assertEqual(fake.call_count("format_knowledge"), 1)

    def test_exception_in_provider(self):
        class BrokenProvider(NullProvider):
            def format_knowledge(self, problem):
                raise RuntimeError("fail")
        r = ai_format_knowledge({"title": "T"}, provider=BrokenProvider())
        self.assertFalse(r.success)


# ── AI не изменяет данные ────────────────────────────────────────

class TestAIDoesNotModifyData(unittest.TestCase):
    """AI-функции НЕ должны изменять данные."""

    @_patchboth
    def test_analyze_problem_readonly(self):
        from src.problems import create_problem
        p = create_problem(title="T")
        original = dict(p)
        fake = FakeProvider()
        ai_analyze_problem(p, [], [], provider=fake)
        from src.problems import get_problem
        current = get_problem(p["id"])
        self.assertEqual(current["status"], original["status"])

    @_patchboth
    def test_analyze_experience_readonly(self):
        from src.problems import create_problem
        p = create_problem(title="T")
        fake = FakeProvider()
        ai_analyze_experience(p, [], [], provider=fake)
        from src.problems import get_problem
        current = get_problem(p["id"])
        self.assertEqual(current["status"], "new")

    @_patchboth
    def test_create_plan_readonly(self):
        from src.problems import create_problem
        p = create_problem(title="T")
        fake = FakeProvider()
        ai_create_plan(p, "cause", [], provider=fake)
        from src.problems import get_problem
        current = get_problem(p["id"])
        self.assertEqual(current["status"], "new")

    @_patchboth
    def test_analyze_result_readonly(self):
        from src.problems import create_problem
        p = create_problem(title="T")
        fake = FakeProvider()
        ai_analyze_result(p, "solution", True, provider=fake)
        from src.problems import get_problem
        current = get_problem(p["id"])
        self.assertEqual(current["status"], "new")

    @_patchboth
    def test_format_knowledge_readonly(self):
        from src.problems import create_problem
        p = create_problem(title="T")
        fake = FakeProvider()
        ai_format_knowledge(p, provider=fake)
        from src.problems import get_problem
        current = get_problem(p["id"])
        self.assertEqual(current["status"], "new")


# ── SOLVE lifecycle + AI ─────────────────────────────────────────

class TestSolveLifecycleWithAI(unittest.TestCase):

    @_patchboth
    def setUp(self):
        _clean()

    @_patchboth
    def tearDown(self):
        _clean()

    @_patchboth
    def test_full_lifecycle_with_fake_provider(self):
        from src.problems import create_problem
        fake = FakeProvider()

        p = create_problem(title="T", description="D", tags=["python"])
        start_investigation(p["id"])

        kr, pr = find_similar(p)
        ai_resp = ai_analyze_problem(p, kr, pr, provider=fake)
        self.assertTrue(ai_resp.success)

        start_solving(p["id"])

        plan = ai_create_plan(p, "cause", [], provider=fake)
        self.assertTrue(plan.success)

        result = resolve_problem(p["id"], cause="cause", solution="sol", helped=True)
        self.assertEqual(result["status"], "solved")

        ar = ai_analyze_result(result, "sol", True, provider=fake)
        self.assertTrue(ar.success)

        record = convert_to_knowledge(p["id"])
        self.assertIsNotNone(record["id"])

        fmt = ai_format_knowledge(result, provider=fake)
        self.assertTrue(fmt.success)

    @_patchboth
    def test_full_lifecycle_without_ai(self):
        from src.problems import create_problem

        p = create_problem(title="T", description="D", tags=["python"])
        start_investigation(p["id"])

        kr, pr = find_similar(p)
        ai_resp = ai_analyze_problem(p, kr, pr, provider=None)
        self.assertFalse(ai_resp.success)

        start_solving(p["id"])

        plan = ai_create_plan(p, "cause", [], provider=None)
        self.assertFalse(plan.success)

        result = resolve_problem(p["id"], cause="cause", solution="sol", helped=True)
        self.assertEqual(result["status"], "solved")

        ar = ai_analyze_result(result, "sol", True, provider=None)
        self.assertFalse(ar.success)

        record = convert_to_knowledge(p["id"])
        self.assertIsNotNone(record["id"])

    @_patchboth
    def test_broken_provider_does_not_break_lifecycle(self):
        from src.problems import create_problem

        class BrokenProvider(NullProvider):
            def analyze_problem(self, p, sr):
                raise RuntimeError("AI exploded")
            def create_plan(self, p, c, s):
                raise RuntimeError("AI exploded")
            def analyze_result(self, p, s, h):
                raise RuntimeError("AI exploded")

        broken = BrokenProvider()
        p = create_problem(title="T")
        start_investigation(p["id"])

        kr, pr = find_similar(p)
        ai_resp = ai_analyze_problem(p, kr, pr, provider=broken)
        self.assertFalse(ai_resp.success)

        start_solving(p["id"])
        plan = ai_create_plan(p, "cause", [], provider=broken)
        self.assertFalse(plan.success)

        result = resolve_problem(p["id"], cause="c", solution="s", helped=True)
        self.assertEqual(result["status"], "solved")

        ar = ai_analyze_result(result, "s", True, provider=broken)
        self.assertFalse(ar.success)


# ── CLI: solve_flow с AI ─────────────────────────────────────────

class TestSolveFlowWithAI(unittest.TestCase):

    @_patchboth
    def setUp(self):
        _clean()

    @_patchboth
    def tearDown(self):
        _clean()

    @_patchboth
    @patch("src.commands.input", side_effect=["0"])
    @patch("src.commands.print")
    def test_solve_flow_with_null_provider(self, mock_print, mock_input):
        from src.commands import solve_flow
        solve_flow(provider=None)

    @_patchboth
    @patch("src.commands.input", side_effect=["0"])
    @patch("src.commands.print")
    def test_solve_flow_with_fake_provider(self, mock_print, mock_input):
        from src.commands import solve_flow
        fake = FakeProvider()
        solve_flow(provider=fake)

    @_patchboth
    @patch("src.commands.input", side_effect=["0"])
    @patch("src.commands.print")
    def test_solve_flow_with_broken_provider(self, mock_print, mock_input):
        from src.commands import solve_flow

        class BrokenProvider(NullProvider):
            def analyze_problem(self, p, sr):
                raise RuntimeError("broken")

        solve_flow(provider=BrokenProvider())


# ── _show_ai_analysis ────────────────────────────────────────────

class TestShowAiAnalysis(unittest.TestCase):

    @patch("src.commands.print")
    def test_shows_successful_response(self, mock_print):
        from src.commands import _show_ai_analysis
        resp = AIResponse(
            success=True,
            content="Test content",
            suggestions=["s1", "s2"],
            confidence=0.8,
        )
        _show_ai_analysis(resp)
        calls = [str(c) for c in mock_print.call_args_list]
        self.assertTrue(any("Test content" in c for c in calls))
        self.assertTrue(any("s1" in c for c in calls))

    @patch("src.commands.print")
    def test_shows_low_confidence_warning(self, mock_print):
        from src.commands import _show_ai_analysis
        resp = AIResponse(
            success=True,
            content="Maybe",
            confidence=0.3,
        )
        _show_ai_analysis(resp)
        calls = [str(c) for c in mock_print.call_args_list]
        self.assertTrue(any("низкая уверенность" in c for c in calls))

    @patch("src.commands.print")
    def test_does_not_show_failed_response(self, mock_print):
        from src.commands import _show_ai_analysis
        resp = AIResponse(success=False, content="error")
        _show_ai_analysis(resp)
        mock_print.assert_not_called()

    @patch("src.commands.print")
    def test_custom_label(self, mock_print):
        from src.commands import _show_ai_analysis
        resp = AIResponse(success=True, content="x", confidence=0.9)
        _show_ai_analysis(resp, label="CUSTOM")
        calls = [str(c) for c in mock_print.call_args_list]
        self.assertTrue(any("CUSTOM" in c for c in calls))


# ── _is_ai_available ─────────────────────────────────────────────

class TestIsAiAvailable(unittest.TestCase):

    def test_none_returns_false(self):
        from src.commands import _is_ai_available
        self.assertFalse(_is_ai_available(None))

    def test_null_provider_returns_false(self):
        from src.commands import _is_ai_available
        self.assertFalse(_is_ai_available(NullProvider()))

    def test_fake_provider_returns_true(self):
        from src.commands import _is_ai_available
        self.assertTrue(_is_ai_available(FakeProvider()))
