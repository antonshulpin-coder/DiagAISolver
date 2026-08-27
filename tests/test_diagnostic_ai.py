import json
import unittest
from io import BytesIO
from unittest.mock import MagicMock, patch
import urllib.error

from src.ai.provider import AIProvider, NullProvider
from src.ai.types import AIResponse
from src.ai.context import (
    build_suggest_hypotheses_context,
    build_suggest_next_check_context,
    _compact_diagnostic_context,
)
from src.ai.openai import (
    OpenAIProvider,
    _clean_suggestions,
    _parse_hypotheses_response,
    _parse_next_check_response,
)
from tests.fake_provider import FakeProvider

from src.diagnostic import (
    get_diagnostic_context,
    open_diagnostic,
    add_hypothesis,
    add_hypotheses,
    add_check,
    complete_check,
)

from pathlib import Path


# ── Helpers ───────────────────────────────────────────────────────

def _diagnostic_context_for(problem):
    """Возвращает компактный контекст диагностики для проблемы."""
    return get_diagnostic_context(problem)


# ── AIProvider base contract ──────────────────────────────────────

class TestAIProviderDiagnosticContract(unittest.TestCase):

    def setUp(self):
        self.provider = AIProvider()

    def test_suggest_hypotheses_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            self.provider.suggest_hypotheses({}, {})

    def test_suggest_next_check_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            self.provider.suggest_next_check({}, {})


# ── NullProvider ─────────────────────────────────────────────────

class TestNullProviderDiagnostic(unittest.TestCase):

    def setUp(self):
        self.provider = NullProvider()

    def test_suggest_hypotheses_returns_success_false(self):
        r = self.provider.suggest_hypotheses(
            {"title": "T"}, {"open_hypotheses": [], "rejected_hypotheses": []}
        )
        self.assertFalse(r.success)
        self.assertEqual(r.content, "")
        self.assertEqual(r.suggestions, [])
        self.assertAlmostEqual(r.confidence, 0.0)
        self.assertIsNone(r.error)

    def test_suggest_next_check_returns_success_false(self):
        r = self.provider.suggest_next_check(
            {"title": "T"}, {"open_hypotheses": [], "recent_steps": []}
        )
        self.assertFalse(r.success)
        self.assertEqual(r.content, "")
        self.assertEqual(r.suggestions, [])
        self.assertAlmostEqual(r.confidence, 0.0)

    def test_is_ai_provider_subclass(self):
        self.assertIsInstance(self.provider, AIProvider)


# ── FakeProvider diagnostic methods ──────────────────────────────

class TestFakeProviderDiagnostic(unittest.TestCase):

    def setUp(self):
        self.provider = FakeProvider()

    def test_suggest_hypotheses_default_success(self):
        r = self.provider.suggest_hypotheses({"title": "T"}, {})
        self.assertTrue(r.success)
        self.assertIn("venv", r.content.lower())
        self.assertTrue(len(r.suggestions) >= 1)

    def test_suggest_next_check_default_success(self):
        r = self.provider.suggest_next_check({"title": "T"}, {})
        self.assertTrue(r.success)
        self.assertIn("виртуальн", r.content.lower())
        self.assertTrue(len(r.suggestions) >= 1)

    def test_suggest_hypotheses_custom_response(self):
        provider = FakeProvider(responses={
            "suggest_hypotheses": AIResponse(
                success=True, content="Кастом", suggestions=["Гип1"], confidence=0.4,
            ),
        })
        r = provider.suggest_hypotheses({"title": "T"}, {})
        self.assertEqual(r.content, "Кастом")
        self.assertEqual(r.suggestions, ["Гип1"])

    def test_suggest_next_check_custom_response(self):
        provider = FakeProvider(responses={
            "suggest_next_check": AIResponse(
                success=True, content="Шаг1", suggestions=["Шаг2"], confidence=0.5,
            ),
        })
        r = provider.suggest_next_check({"title": "T"}, {})
        self.assertEqual(r.content, "Шаг1")
        self.assertEqual(r.suggestions, ["Шаг2"])

    def test_calls_logged(self):
        self.provider.suggest_hypotheses({"title": "T"}, {"open_hypotheses": []})
        self.provider.suggest_next_check({"title": "T"}, {})
        self.assertEqual(self.provider.call_count("suggest_hypotheses"), 1)
        self.assertEqual(self.provider.call_count("suggest_next_check"), 1)

    def test_args_captured(self):
        problem = {"title": "T"}
        dc = {"open_hypotheses": []}
        self.provider.suggest_hypotheses(problem, dc)
        calls = self.provider.get_calls("suggest_hypotheses")
        self.assertEqual(calls[0][1][0], problem)
        self.assertEqual(calls[0][1][1], dc)


# ── Context builders для diagnostic_context ──────────────────────

class TestBuildSuggestHypothesesContext(unittest.TestCase):

    def test_basic_structure(self):
        dc = {
            "open_hypotheses": [{"text": "Г1", "status": "open", "source": "ai"}],
            "rejected_hypotheses": [{"text": "Г2", "status": "rejected", "source": "user"}],
            "recent_steps": [{"description": "шаг", "result": "unknown"}],
            "conclusion": "вывод",
        }
        ctx = build_suggest_hypotheses_context({"title": "T"}, dc)
        self.assertEqual(ctx["problem"]["title"], "T")
        self.assertEqual(ctx["diagnostic"]["open_hypotheses"][0]["text"], "Г1")
        self.assertEqual(ctx["diagnostic"]["rejected_hypotheses"][0]["text"], "Г2")
        self.assertEqual(ctx["diagnostic"]["conclusion"], "вывод")

    def test_no_diagnostic_context(self):
        ctx = build_suggest_hypotheses_context({"title": "T"}, None)
        self.assertEqual(ctx["diagnostic"]["open_hypotheses"], [])
        self.assertEqual(ctx["diagnostic"]["recent_steps"], [])


class TestBuildSuggestNextCheckContext(unittest.TestCase):

    def test_basic_structure(self):
        dc = {
            "open_hypotheses": [{"text": "Г1", "status": "open", "source": "ai"}],
            "recent_steps": [{"description": "шаг", "result": "unknown"}],
            "conclusion": "вывод",
        }
        ctx = build_suggest_next_check_context({"title": "T"}, dc)
        self.assertEqual(ctx["problem"]["title"], "T")
        self.assertEqual(ctx["diagnostic"]["open_hypotheses"][0]["text"], "Г1")
        self.assertEqual(ctx["diagnostic"]["recent_steps"][0]["description"], "шаг")


class TestCompactDiagnosticContext(unittest.TestCase):

    def test_non_dict_returns_empty(self):
        c = _compact_diagnostic_context(None)
        self.assertEqual(c, {"open_hypotheses": [], "rejected_hypotheses": [],
                             "recent_steps": [], "conclusion": ""})
        c2 = _compact_diagnostic_context("str")
        self.assertEqual(c2["open_hypotheses"], [])
        self.assertEqual(c2["recent_steps"], [])

    def test_missing_keys(self):
        c = _compact_diagnostic_context({})
        self.assertEqual(c["open_hypotheses"], [])
        self.assertEqual(c["rejected_hypotheses"], [])
        self.assertEqual(c["recent_steps"], [])
        self.assertEqual(c["conclusion"], "")

    def test_missing_conclusion(self):
        c = _compact_diagnostic_context({"open_hypotheses": []})
        self.assertEqual(c["conclusion"], "")

    def test_limits(self):
        many = [{"text": f"Г{i}"} for i in range(50)]
        c = _compact_diagnostic_context({
            "open_hypotheses": many,
            "rejected_hypotheses": many,
            "recent_steps": many,
        })
        self.assertTrue(len(c["open_hypotheses"]) <= 5)


# ── Лимиты контекста диагностики ────────────────────────────────

class TestDiagnosticContextLimits(unittest.TestCase):

    def test_get_diagnostic_context_is_compact_and_limited(self):
        # контекст диагностики уже ограничен на уровне ядра (Phase 1)
        ctx = get_diagnostic_context({})
        self.assertEqual(ctx["open_hypotheses"], [])
        self.assertEqual(ctx["rejected_hypotheses"], [])
        self.assertEqual(ctx["recent_steps"], [])
        self.assertEqual(ctx["conclusion"], "")

    def test_none_diagnostic_returns_empty_context(self):
        problem = {"status": "investigating", "diagnostic": None}
        ctx = get_diagnostic_context(problem)
        self.assertEqual(ctx["open_hypotheses"], [])
        self.assertEqual(ctx["recent_steps"], [])


# ── Парсинг ответов ──────────────────────────────────────────────

class TestCleanSuggestions(unittest.TestCase):

    def test_dedup_and_empty(self):
        items = ["А", "  А  ", "", "Б", None, "  ", "а"]
        result = _clean_suggestions(items)
        self.assertEqual(result, ["А", "Б"])

    def test_case_insensitive_dedup(self):
        result = _clean_suggestions(["Причина", "причина", "ПРИЧИНА"])
        self.assertEqual(len(result), 1)

    def test_non_strings_skipped(self):
        result = _clean_suggestions(["x", 123, ["nested"], "   "])
        self.assertEqual(result, ["x"])


class TestParseHypothesesResponse(unittest.TestCase):

    def test_json_with_suggestions(self):
        content = json.dumps({
            "suggestions": ["Гипотеза 1", "Гипотеза 2", "Гипотеза 1"],
            "explanation": "Разбор",
        })
        suggestions, explanation = _parse_hypotheses_response(content)
        self.assertEqual(suggestions, ["Гипотеза 1", "Гипотеза 2"])
        self.assertEqual(explanation, "Разбор")

    def test_json_list(self):
        suggestions, explanation = _parse_hypotheses_response(
            json.dumps(["Гипотеза 1", "Гипотеза 2", ""])
        )
        self.assertEqual(suggestions, ["Гипотеза 1", "Гипотеза 2"])
        self.assertEqual(explanation, "")

    def test_line_fallback(self):
        suggestions, explanation = _parse_hypotheses_response(
            "- Гипотеза 1\n* Гипотеза 2\n\nпустая\n- Гипотеза 1"
        )
        self.assertEqual(suggestions, ["Гипотеза 1", "Гипотеза 2", "пустая"])
        self.assertEqual(explanation, "- Гипотеза 1\n* Гипотеза 2\n\nпустая\n- Гипотеза 1")

    def test_malformed_json_does_not_crash(self):
        suggestions, _ = _parse_hypotheses_response("not json { broken")
        self.assertIsInstance(suggestions, list)


class TestParseNextCheckResponse(unittest.TestCase):

    def test_json(self):
        check, alternatives = _parse_next_check_response(json.dumps({
            "check": "Проверить логи",
            "alternatives": ["Альт 1", "Альт 2"],
        }))
        self.assertEqual(check, "Проверить логи")
        self.assertEqual(alternatives, ["Альт 1", "Альт 2"])

    def test_plain_text(self):
        check, alternatives = _parse_next_check_response("   Проверить логи   ")
        self.assertEqual(check, "Проверить логи")
        self.assertEqual(alternatives, [])

    def test_empty(self):
        check, alternatives = _parse_next_check_response("")
        self.assertEqual(check, "")
        self.assertEqual(alternatives, [])


# ── OpenAIProvider: успех ─────────────────────────────────────────

def _mock_response_bytes(content="Test response"):
    return json.dumps({
        "choices": [{"message": {"content": content}}],
    }).encode("utf-8")


def _openai_body(inner_content):
    """Полный конверт OpenAI-ответа, где content = заданная строка."""
    return json.dumps({
        "choices": [{"message": {"content": inner_content}}],
    }).encode("utf-8")


def _mock_context_manager(response_bytes):
    mock_resp = MagicMock()
    mock_resp.read.return_value = response_bytes
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    return MagicMock(return_value=mock_resp)


def _make_http_error(code):
    return urllib.error.HTTPError(
        url="https://api.openai.com/v1/chat/completions",
        code=code, msg="error", hdrs=None, fp=BytesIO(b""),
    )


class TestOpenAISuggestHypothesesSuccess(unittest.TestCase):

    @patch("src.ai.openai.urllib.request.urlopen")
    def test_success_with_json_suggestions(self, mock_urlopen):
        inner = json.dumps({
            "suggestions": ["Сломан venv", "Нет пакета"],
            "explanation": "Разбор проблемы",
        })
        mock_urlopen.return_value = _mock_context_manager(_openai_body(inner))()
        p = OpenAIProvider(api_key="sk-test")
        r = p.suggest_hypotheses({"title": "T"}, {})
        self.assertTrue(r.success)
        self.assertEqual(r.suggestions, ["Сломан venv", "Нет пакета"])
        self.assertEqual(r.content, "Разбор проблемы")

    @patch("src.ai.openai.urllib.request.urlopen")
    def test_success_with_plain_text_lines(self, mock_urlopen):
        inner = "- Гипотеза A\n- Гипотеза B"
        mock_urlopen.return_value = _mock_context_manager(_openai_body(inner))()
        p = OpenAIProvider(api_key="sk-test")
        r = p.suggest_hypotheses({"title": "T"}, {})
        self.assertTrue(r.success)
        self.assertEqual(r.suggestions, ["Гипотеза A", "Гипотеза B"])

    @patch("src.ai.openai.urllib.request.urlopen")
    def test_prompt_contains_diagnostic_context(self, mock_urlopen):
        mock_urlopen.return_value = _mock_context_manager(b"{}")()
        p = OpenAIProvider(api_key="sk-test")
        p.suggest_hypotheses({"title": "T", "description": "D"},
                             {"rejected_hypotheses": [{"text": "X"}]})
        req = mock_urlopen.call_args[0][0]
        user_content = json.loads(req.data.decode("utf-8"))["messages"][1]["content"]
        self.assertIn("diagnostic", user_content)
        self.assertIn("rejected", user_content)


class TestOpenAISuggestNextCheckSuccess(unittest.TestCase):

    @patch("src.ai.openai.urllib.request.urlopen")
    def test_success_with_json(self, mock_urlopen):
        inner = json.dumps({
            "check": "Проверить активацию venv",
            "alternatives": ["Проверить pip list", "Проверить версию Python"],
        })
        mock_urlopen.return_value = _mock_context_manager(_openai_body(inner))()
        p = OpenAIProvider(api_key="sk-test")
        r = p.suggest_next_check({"title": "T"}, {})
        self.assertTrue(r.success)
        self.assertEqual(r.content, "Проверить активацию venv")
        self.assertEqual(r.suggestions, ["Проверить pip list", "Проверить версию Python"])

    @patch("src.ai.openai.urllib.request.urlopen")
    def test_success_with_plain_text(self, mock_urlopen):
        inner = "Проверить логи"
        mock_urlopen.return_value = _mock_context_manager(_openai_body(inner))()
        p = OpenAIProvider(api_key="sk-test")
        r = p.suggest_next_check({"title": "T"}, {})
        self.assertTrue(r.success)
        self.assertEqual(r.content, "Проверить логи")

    @patch("src.ai.openai.urllib.request.urlopen")
    def test_prompt_contains_open_hypotheses(self, mock_urlopen):
        mock_urlopen.return_value = _mock_context_manager(b"{}")()
        p = OpenAIProvider(api_key="sk-test")
        p.suggest_next_check({"title": "T"},
                             {"open_hypotheses": [{"text": "Гип1"}]})
        req = mock_urlopen.call_args[0][0]
        user_content = json.loads(req.data.decode("utf-8"))["messages"][1]["content"]
        self.assertIn("open_hypotheses", user_content)


# ── OpenAIProvider: malformed / empty / refusal ──────────────────

class TestOpenAISuggestMalformed(unittest.TestCase):

    @patch("src.ai.openai.urllib.request.urlopen")
    def test_malformed_json_body_suggest_hypotheses(self, mock_urlopen):
        mock_urlopen.return_value = _mock_context_manager(b"not json")()
        p = OpenAIProvider(api_key="sk-test")
        r = p.suggest_hypotheses({"title": "T"}, {})
        self.assertFalse(r.success)
        self.assertIn("JSON", r.error)

    @patch("src.ai.openai.urllib.request.urlopen")
    def test_malformed_body_suggest_next_check(self, mock_urlopen):
        mock_urlopen.return_value = _mock_context_manager(b"not json")()
        p = OpenAIProvider(api_key="sk-test")
        r = p.suggest_next_check({"title": "T"}, {})
        self.assertFalse(r.success)

    @patch("src.ai.openai.urllib.request.urlopen")
    def test_malformed_dict_no_choices(self, mock_urlopen):
        body = json.dumps({"error": "bad"}).encode("utf-8")
        mock_urlopen.return_value = _mock_context_manager(body)()
        p = OpenAIProvider(api_key="sk-test")
        r = p.suggest_hypotheses({"title": "T"}, {})
        self.assertFalse(r.success)

    @patch("src.ai.openai.urllib.request.urlopen")
    def test_empty_content_suggest_hypotheses(self, mock_urlopen):
        body = json.dumps({"choices": [{"message": {"content": ""}}]}).encode("utf-8")
        mock_urlopen.return_value = _mock_context_manager(body)()
        p = OpenAIProvider(api_key="sk-test")
        r = p.suggest_hypotheses({"title": "T"}, {})
        self.assertFalse(r.success)

    @patch("src.ai.openai.urllib.request.urlopen")
    def test_empty_content_suggest_next_check(self, mock_urlopen):
        body = json.dumps({"choices": [{"message": {"content": ""}}]}).encode("utf-8")
        mock_urlopen.return_value = _mock_context_manager(body)()
        p = OpenAIProvider(api_key="sk-test")
        r = p.suggest_next_check({"title": "T"}, {})
        self.assertFalse(r.success)

    @patch("src.ai.openai.urllib.request.urlopen")
    def test_refusal_suggest_hypotheses(self, mock_urlopen):
        body = json.dumps({
            "choices": [{"message": {"content": None, "refusal": "no"}}]
        }).encode("utf-8")
        mock_urlopen.return_value = _mock_context_manager(body)()
        p = OpenAIProvider(api_key="sk-test")
        r = p.suggest_hypotheses({"title": "T"}, {})
        self.assertFalse(r.success)
        self.assertIn("отказалась", r.error)

    @patch("src.ai.openai.urllib.request.urlopen")
    def test_refusal_suggest_next_check(self, mock_urlopen):
        body = json.dumps({
            "choices": [{"message": {"content": None, "refusal": "no"}}]
        }).encode("utf-8")
        mock_urlopen.return_value = _mock_context_manager(body)()
        p = OpenAIProvider(api_key="sk-test")
        r = p.suggest_next_check({"title": "T"}, {})
        self.assertFalse(r.success)


# ── OpenAIProvider: HTTP / timeout / network ─────────────────────

class TestOpenAISuggestErrors(unittest.TestCase):

    @patch("src.ai.openai.urllib.request.urlopen")
    def test_http_401_suggest_hypotheses(self, mock_urlopen):
        mock_urlopen.side_effect = _make_http_error(401)
        p = OpenAIProvider(api_key="sk-bad")
        r = p.suggest_hypotheses({"title": "T"}, {})
        self.assertFalse(r.success)
        self.assertIn("401", r.error)

    @patch("src.ai.openai.urllib.request.urlopen")
    def test_http_429_suggest_next_check(self, mock_urlopen):
        mock_urlopen.side_effect = _make_http_error(429)
        p = OpenAIProvider(api_key="sk-test")
        r = p.suggest_next_check({"title": "T"}, {})
        self.assertFalse(r.success)
        self.assertIn("429", r.error)

    @patch("src.ai.openai.urllib.request.urlopen")
    def test_http_500_suggest_hypotheses(self, mock_urlopen):
        mock_urlopen.side_effect = _make_http_error(500)
        p = OpenAIProvider(api_key="sk-test")
        r = p.suggest_hypotheses({"title": "T"}, {})
        self.assertFalse(r.success)
        self.assertIn("500", r.error)

    @patch("src.ai.openai.urllib.request.urlopen")
    def test_timeout_suggest_next_check(self, mock_urlopen):
        mock_urlopen.side_effect = TimeoutError("timed out")
        p = OpenAIProvider(api_key="sk-test", timeout=12)
        r = p.suggest_next_check({"title": "T"}, {})
        self.assertFalse(r.success)
        self.assertIn("12", r.error)

    @patch("src.ai.openai.urllib.request.urlopen")
    def test_network_error_suggest_hypotheses(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
        p = OpenAIProvider(api_key="sk-test")
        r = p.suggest_hypotheses({"title": "T"}, {})
        self.assertFalse(r.success)
        self.assertIn("Connection refused", r.error)


# ── Отсутствие API key ───────────────────────────────────────────

class TestOpenAISuggestNoKey(unittest.TestCase):

    @patch.dict("os.environ", {}, clear=True)
    def test_suggest_hypotheses_no_key(self):
        p = OpenAIProvider()
        r = p.suggest_hypotheses({"title": "T"}, {})
        self.assertFalse(r.success)
        self.assertIn("API key", r.error)

    @patch.dict("os.environ", {}, clear=True)
    def test_suggest_next_check_no_key(self):
        p = OpenAIProvider()
        r = p.suggest_next_check({"title": "T"}, {})
        self.assertFalse(r.success)
        self.assertIn("API key", r.error)


# ── readonly / data isolation ────────────────────────────────────

class TestDiagnosticAIReadonly(unittest.TestCase):

    def test_null_provider_readonly(self):
        provider = NullProvider()
        problem = {"title": "T", "status": "investigating", "diagnostic": {}}
        dc = {"open_hypotheses": [], "rejected_hypotheses": [], "recent_steps": []}
        problem_orig = dict(problem)
        dc_orig = dict(dc)
        provider.suggest_hypotheses(problem, dc)
        provider.suggest_next_check(problem, dc)
        self.assertEqual(problem, problem_orig)
        self.assertEqual(dc, dc_orig)

    def test_fake_provider_readonly(self):
        provider = FakeProvider()
        problem = {"title": "T", "diagnostic": {}}
        dc = {"open_hypotheses": [], "rejected_hypotheses": []}
        problem_orig = dict(problem)
        dc_orig = dict(dc)
        provider.suggest_hypotheses(problem, dc)
        provider.suggest_next_check(problem, dc)
        self.assertEqual(problem, problem_orig)
        self.assertEqual(dc, dc_orig)

    @patch("src.ai.openai.urllib.request.urlopen")
    def test_openai_readonly(self, mock_urlopen):
        inner = json.dumps({
            "suggestions": ["S1"],
            "check": "Проверить",
            "explanation": "x",
        })
        mock_urlopen.return_value = _mock_context_manager(_openai_body(inner))()
        p = OpenAIProvider(api_key="sk-test")
        problem = {"title": "T", "diagnostic": {"hypotheses": []}}
        dc = {"open_hypotheses": [], "rejected_hypotheses": [], "recent_steps": []}
        problem_orig = dict(problem)
        dc_orig = dict(dc)
        p.suggest_hypotheses(problem, dc)
        p.suggest_next_check(problem, dc)
        self.assertEqual(problem, problem_orig)
        self.assertEqual(dc, dc_orig)


# ── Обратная совместимость старых AI-методов ────────────────────

class TestBackwardCompatibility(unittest.TestCase):

    def test_null_provider_all_old_methods_still_fail(self):
        p = NullProvider()
        self.assertFalse(p.analyze_problem({}, {"knowledge": [], "problems": []}).success)
        self.assertFalse(p.analyze_experience({}, {"knowledge": [], "problems": []}).success)
        self.assertFalse(p.create_plan({}, "c", []).success)
        self.assertFalse(p.analyze_result({}, "s", True).success)
        self.assertFalse(p.format_knowledge({}).success)

    def test_fake_provider_old_methods_still_work(self):
        p = FakeProvider()
        self.assertTrue(p.analyze_problem({}, {"knowledge": [], "problems": []}).success)
        self.assertTrue(p.create_plan({}, "c", []).success)
        self.assertTrue(p.format_knowledge({}).success)

    @patch("src.ai.openai.urllib.request.urlopen")
    def test_openai_old_methods_still_work(self, mock_urlopen):
        mock_urlopen.return_value = _mock_context_manager(b'{"choices":[{"message":{"content":"ok"}}]}')()
        p = OpenAIProvider(api_key="sk-test")
        self.assertTrue(p.analyze_problem({}, {"knowledge": [], "problems": []}).success)
        self.assertTrue(p.create_plan({}, "c", []).success)
        self.assertTrue(p.format_knowledge({}).success)
        self.assertEqual(mock_urlopen.call_count, 3)


# ── Защита от пустых/дублирующихся suggestions на уровне ядра ───
# (проверка, что AI-предложения корректно проходят через add_hypotheses)

class TestAISuggestionsFeedIntoCore(unittest.TestCase):

    def test_ai_suggestions_passed_to_add_hypotheses(self):
        # имитируем сценарий Phase 3: AI-предложения → add_hypotheses
        problem = {
            "id": "x123", "status": "investigating",
            "diagnostic": {
                "started_at": "2026-01-01T00:00:00+00:00",
                "hypotheses": [],
                "steps": [],
                "conclusion": "",
            },
        }
        ctx = get_diagnostic_context(problem)
        provider = FakeProvider()
        resp = provider.suggest_hypotheses(problem, ctx)
        self.assertTrue(resp.success)
        self.assertTrue(len(resp.suggestions) >= 1)
        # все suggestions — непустые строки
        self.assertTrue(all(isinstance(s, str) and s.strip() for s in resp.suggestions))

    def test_next_check_content_is_nonempty_string(self):
        problem = {
            "id": "x124", "status": "investigating",
            "diagnostic": {
                "started_at": "2026-01-01T00:00:00+00:00",
                "hypotheses": [{
                    "id": "h1", "text": "Гипотеза", "status": "open",
                    "confidence": 0.8, "source": "ai",
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "last_tested_step_id": None,
                }],
                "steps": [],
                "conclusion": "",
            },
        }
        ctx = get_diagnostic_context(problem)
        provider = FakeProvider()
        resp = provider.suggest_next_check(problem, ctx)
        self.assertTrue(resp.success)
        self.assertIsInstance(resp.content, str)
        self.assertTrue(resp.content.strip())

    def test_ai_does_not_modify_problem_or_diagnostic(self):
        problem = {
            "id": "x125", "status": "investigating",
            "diagnostic": {
                "started_at": "2026-01-01T00:00:00+00:00",
                "hypotheses": [{
                    "id": "h1", "text": "Гипотеза", "status": "open",
                    "confidence": 0.8, "source": "ai",
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "last_tested_step_id": None,
                }],
                "steps": [],
                "conclusion": "",
            },
        }
        import copy
        original = copy.deepcopy(problem)
        ctx = get_diagnostic_context(problem)
        provider = FakeProvider()
        provider.suggest_hypotheses(problem, ctx)
        provider.suggest_next_check(problem, ctx)
        self.assertEqual(problem, original)


# ── Полный цикл диагностики с AI (без проблемного хранилища) ────
# Включён для встраивания новых AI-методов в полный цикл.

class TestBackupFullLoop(unittest.TestCase):
    """Полный цикл диагностики на in-memory проблеме (без файла)."""

    def _problem(self):
        return {
            "id": "loop1", "status": "investigating",
            "diagnostic": {
                "started_at": "2026-01-01T00:00:00+00:00",
                "hypotheses": [], "steps": [], "conclusion": "",
            },
        }

    def test_suggest_and_add_hypotheses(self):
        problem = self._problem()
        provider = FakeProvider()
        resp = provider.suggest_hypotheses(problem, get_diagnostic_context(problem))
        self.assertTrue(resp.success)
        # Напрямую добавим предложения в сессию (как сделал бы CLI в Phase 3)
        session = problem["diagnostic"]
        for text in resp.suggestions:
            session["hypotheses"].append({
                "id": f"h{len(session['hypotheses'])}", "text": text,
                "status": "open", "confidence": resp.confidence,
                "source": "ai", "created_at": "2026-01-01T00:00:00+00:00",
                "last_tested_step_id": None,
            })
        self.assertEqual(len(session["hypotheses"]), len(resp.suggestions))

    def test_suggest_next_check_creates_step_description(self):
        problem = self._problem()
        problem["diagnostic"]["hypotheses"].append({
            "id": "h0", "text": "Сломан venv", "status": "open",
            "confidence": 0.8, "source": "ai",
            "created_at": "2026-01-01T00:00:00+00:00", "last_tested_step_id": None,
        })
        provider = FakeProvider()
        resp = provider.suggest_next_check(problem, get_diagnostic_context(problem))
        self.assertTrue(resp.success)
        self.assertTrue(resp.content.strip())


# ── API key не в ответах/ошибках новых методов ───────────────────

class TestDiagnosticKeySecurity(unittest.TestCase):

    @patch("src.ai.openai.urllib.request.urlopen")
    def test_key_not_in_error(self, mock_urlopen):
        mock_urlopen.side_effect = _make_http_error(401)
        p = OpenAIProvider(api_key="sk-secret-diag-key-999")
        r = p.suggest_hypotheses({"title": "T"}, {})
        self.assertNotIn("sk-secret-diag-key", r.error or "")
        r2 = p.suggest_next_check({"title": "T"}, {})
        self.assertNotIn("sk-secret-diag-key", r2.error or "")


if __name__ == "__main__":
    unittest.main()
