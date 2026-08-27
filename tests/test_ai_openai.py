import json
import unittest
from io import BytesIO
from unittest.mock import MagicMock, patch
import urllib.error

from src.ai.openai import OpenAIProvider, _parse_response, _handle_http_error
from src.ai.provider import SYSTEM_PROMPT


def _make_response_bytes(content="Test response"):
    return json.dumps({
        "choices": [{"message": {"content": content}}],
    }).encode("utf-8")


def _make_http_error(code, reason="error"):
    return urllib.error.HTTPError(
        url="https://api.openai.com/v1/chat/completions",
        code=code,
        msg=reason,
        hdrs=None,
        fp=BytesIO(b""),
    )


def _mock_context_manager(response_bytes):
    mock_resp = MagicMock()
    mock_resp.read.return_value = response_bytes
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    return MagicMock(return_value=mock_resp)


# ── Constructor ───────────────────────────────────────────────────

class TestOpenAIProviderInit(unittest.TestCase):

    @patch.dict("os.environ", {}, clear=True)
    def test_no_key_from_env(self):
        p = OpenAIProvider()
        self.assertEqual(p.api_key, "")

    @patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=True)
    def test_key_from_env(self):
        p = OpenAIProvider()
        self.assertEqual(p.api_key, "sk-test")

    def test_key_from_constructor(self):
        p = OpenAIProvider(api_key="sk-direct")
        self.assertEqual(p.api_key, "sk-direct")

    def test_constructor_overrides_env(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-env"}, clear=False):
            p = OpenAIProvider(api_key="sk-direct")
            self.assertEqual(p.api_key, "sk-direct")

    def test_default_model(self):
        p = OpenAIProvider(api_key="k")
        self.assertEqual(p.model, "gpt-4o-mini")

    def test_custom_model(self):
        p = OpenAIProvider(api_key="k", model="gpt-4o")
        self.assertEqual(p.model, "gpt-4o")

    def test_default_timeout(self):
        p = OpenAIProvider(api_key="k")
        self.assertEqual(p.timeout, 30)

    def test_custom_timeout(self):
        p = OpenAIProvider(api_key="k", timeout=60)
        self.assertEqual(p.timeout, 60)


# ── _parse_response ───────────────────────────────────────────────

class TestParseResponse(unittest.TestCase):

    def test_valid_response(self):
        raw = json.dumps({"choices": [{"message": {"content": "hello"}}]})
        r = _parse_response(raw)
        self.assertTrue(r.success)
        self.assertEqual(r.content, "hello")
        self.assertAlmostEqual(r.confidence, 0.7)

    def test_invalid_json(self):
        r = _parse_response("not json at all")
        self.assertFalse(r.success)
        self.assertIn("JSON", r.error)

    def test_malformed_no_choices(self):
        r = _parse_response(json.dumps({"error": "bad"}))
        self.assertFalse(r.success)

    def test_malformed_empty_choices(self):
        r = _parse_response(json.dumps({"choices": []}))
        self.assertFalse(r.success)

    def test_malformed_no_message(self):
        r = _parse_response(json.dumps({"choices": [{"text": "x"}]}))
        self.assertFalse(r.success)

    def test_empty_content(self):
        r = _parse_response(json.dumps({"choices": [{"message": {"content": ""}}]}))
        self.assertFalse(r.success)

    def test_null_content(self):
        r = _parse_response(json.dumps({"choices": [{"message": {"content": None}}]}))
        self.assertFalse(r.success)
        self.assertIn("Пустой", r.error)

    def test_content_key_missing(self):
        r = _parse_response(json.dumps({"choices": [{"message": {"role": "assistant"}}]}))
        self.assertFalse(r.success)
        self.assertIn("Пустой", r.error)

    def test_refusal(self):
        raw = json.dumps({"choices": [{"message": {"content": None, "refusal": "I cannot help with that"}}]})
        r = _parse_response(raw)
        self.assertFalse(r.success)
        self.assertIn("отказалась", r.error)
        self.assertIn("I cannot help", r.error)

    def test_refusal_over_content(self):
        raw = json.dumps({"choices": [{"message": {"content": "some text", "refusal": "No"}}]})
        r = _parse_response(raw)
        self.assertFalse(r.success)
        self.assertIn("отказалась", r.error)


# ── _handle_http_error ────────────────────────────────────────────

class TestHandleHttpError(unittest.TestCase):

    def test_401(self):
        r = _handle_http_error(_make_http_error(401))
        self.assertFalse(r.success)
        self.assertIn("401", r.error)

    def test_403(self):
        r = _handle_http_error(_make_http_error(403))
        self.assertFalse(r.success)
        self.assertIn("403", r.error)

    def test_429(self):
        r = _handle_http_error(_make_http_error(429))
        self.assertFalse(r.success)
        self.assertIn("429", r.error)

    def test_500(self):
        r = _handle_http_error(_make_http_error(500))
        self.assertFalse(r.success)
        self.assertIn("500", r.error)

    def test_503(self):
        r = _handle_http_error(_make_http_error(503))
        self.assertFalse(r.success)
        self.assertIn("503", r.error)

    def test_other_http(self):
        r = _handle_http_error(_make_http_error(418))
        self.assertFalse(r.success)
        self.assertIn("418", r.error)


# ── No API key ────────────────────────────────────────────────────

class TestOpenAIProviderNoKey(unittest.TestCase):

    @patch.dict("os.environ", {}, clear=True)
    def test_analyze_problem_no_key(self):
        p = OpenAIProvider()
        r = p.analyze_problem({"title": "T"}, {"knowledge": [], "problems": []})
        self.assertFalse(r.success)
        self.assertIn("API key", r.error)

    @patch.dict("os.environ", {}, clear=True)
    def test_create_plan_no_key(self):
        p = OpenAIProvider()
        r = p.create_plan({"title": "T"}, "cause", [])
        self.assertFalse(r.success)

    @patch.dict("os.environ", {}, clear=True)
    def test_analyze_result_no_key(self):
        p = OpenAIProvider()
        r = p.analyze_result({"title": "T"}, "fix", True)
        self.assertFalse(r.success)

    @patch.dict("os.environ", {}, clear=True)
    def test_format_knowledge_no_key(self):
        p = OpenAIProvider()
        r = p.format_knowledge({"title": "T"})
        self.assertFalse(r.success)


# ── Successful API calls ──────────────────────────────────────────

class TestOpenAIProviderSuccess(unittest.TestCase):

    @patch("src.ai.openai.urllib.request.urlopen")
    def test_analyze_problem_success(self, mock_urlopen):
        mock_urlopen.return_value = _mock_context_manager(
            _make_response_bytes("Analysis result")
        )()
        p = OpenAIProvider(api_key="sk-test")
        r = p.analyze_problem(
            {"title": "T", "description": "D"},
            {"knowledge": [({"title": "K1", "type": "note", "text": "t"}, 0.8)],
             "problems": [({"title": "P1", "description": "d"}, 0.6)]},
        )
        self.assertTrue(r.success)
        self.assertEqual(r.content, "Analysis result")
        self.assertAlmostEqual(r.confidence, 0.7)

    @patch("src.ai.openai.urllib.request.urlopen")
    def test_analyze_experience_success(self, mock_urlopen):
        mock_urlopen.return_value = _mock_context_manager(
            _make_response_bytes("Experience relevant")
        )()
        p = OpenAIProvider(api_key="sk-test")
        r = p.analyze_experience(
            {"title": "T"},
            {"knowledge": [({"title": "K1", "type": "note", "text": "t"}, 0.8)],
             "problems": []},
        )
        self.assertTrue(r.success)

    @patch("src.ai.openai.urllib.request.urlopen")
    def test_create_plan_success(self, mock_urlopen):
        mock_urlopen.return_value = _mock_context_manager(
            _make_response_bytes("Plan: step 1, step 2")
        )()
        p = OpenAIProvider(api_key="sk-test")
        r = p.create_plan({"title": "T"}, "cause", ["sol1"])
        self.assertTrue(r.success)

    @patch("src.ai.openai.urllib.request.urlopen")
    def test_analyze_result_success(self, mock_urlopen):
        mock_urlopen.return_value = _mock_context_manager(
            _make_response_bytes("Solution helped")
        )()
        p = OpenAIProvider(api_key="sk-test")
        r = p.analyze_result({"title": "T"}, "fix", True)
        self.assertTrue(r.success)

    @patch("src.ai.openai.urllib.request.urlopen")
    def test_format_knowledge_success(self, mock_urlopen):
        mock_urlopen.return_value = _mock_context_manager(
            _make_response_bytes("Knowledge record text")
        )()
        p = OpenAIProvider(api_key="sk-test")
        r = p.format_knowledge({"title": "T"})
        self.assertTrue(r.success)


# ── Errors ────────────────────────────────────────────────────────

class TestOpenAIProviderErrors(unittest.TestCase):

    @patch("src.ai.openai.urllib.request.urlopen")
    def test_401_error(self, mock_urlopen):
        mock_urlopen.side_effect = _make_http_error(401)
        p = OpenAIProvider(api_key="sk-bad")
        r = p.analyze_problem({"title": "T"}, {"knowledge": [], "problems": []})
        self.assertFalse(r.success)
        self.assertIn("401", r.error)

    @patch("src.ai.openai.urllib.request.urlopen")
    def test_429_error(self, mock_urlopen):
        mock_urlopen.side_effect = _make_http_error(429)
        p = OpenAIProvider(api_key="sk-test")
        r = p.create_plan({"title": "T"}, "c", [])
        self.assertFalse(r.success)
        self.assertIn("429", r.error)

    @patch("src.ai.openai.urllib.request.urlopen")
    def test_500_error(self, mock_urlopen):
        mock_urlopen.side_effect = _make_http_error(500)
        p = OpenAIProvider(api_key="sk-test")
        r = p.analyze_result({"title": "T"}, "s", True)
        self.assertFalse(r.success)
        self.assertIn("500", r.error)

    @patch("src.ai.openai.urllib.request.urlopen")
    def test_timeout(self, mock_urlopen):
        mock_urlopen.side_effect = TimeoutError("timed out")
        p = OpenAIProvider(api_key="sk-test", timeout=10)
        r = p.format_knowledge({"title": "T"})
        self.assertFalse(r.success)
        self.assertIn("10", r.error)

    @patch("src.ai.openai.urllib.request.urlopen")
    def test_connection_error(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
        p = OpenAIProvider(api_key="sk-test")
        r = p.analyze_problem({"title": "T"}, {"knowledge": [], "problems": []})
        self.assertFalse(r.success)
        self.assertIn("Connection refused", r.error)

    @patch("src.ai.openai.urllib.request.urlopen")
    def test_invalid_json_response(self, mock_urlopen):
        mock_urlopen.return_value = _mock_context_manager(b"not json")()
        p = OpenAIProvider(api_key="sk-test")
        r = p.analyze_problem({"title": "T"}, {"knowledge": [], "problems": []})
        self.assertFalse(r.success)
        self.assertIn("JSON", r.error)

    @patch("src.ai.openai.urllib.request.urlopen")
    def test_malformed_api_response(self, mock_urlopen):
        body = json.dumps({"error": "bad request"}).encode("utf-8")
        mock_urlopen.return_value = _mock_context_manager(body)()
        p = OpenAIProvider(api_key="sk-test")
        r = p.create_plan({"title": "T"}, "c", [])
        self.assertFalse(r.success)

    @patch("src.ai.openai.urllib.request.urlopen")
    def test_empty_content_response(self, mock_urlopen):
        body = json.dumps({"choices": [{"message": {"content": ""}}]}).encode("utf-8")
        mock_urlopen.return_value = _mock_context_manager(body)()
        p = OpenAIProvider(api_key="sk-test")
        r = p.analyze_problem({"title": "T"}, {"knowledge": [], "problems": []})
        self.assertFalse(r.success)


# ── Request parameters ────────────────────────────────────────────

class TestOpenAIProviderRequestParams(unittest.TestCase):

    @patch("src.ai.openai.urllib.request.urlopen")
    def test_model_in_payload(self, mock_urlopen):
        mock_urlopen.return_value = _mock_context_manager(
            _make_response_bytes("ok")
        )()
        p = OpenAIProvider(api_key="sk-test", model="gpt-4o")
        p.analyze_problem({"title": "T"}, {"knowledge": [], "problems": []})
        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data.decode("utf-8"))
        self.assertEqual(body["model"], "gpt-4o")

    @patch("src.ai.openai.urllib.request.urlopen")
    def test_timeout_in_urlopen(self, mock_urlopen):
        mock_urlopen.return_value = _mock_context_manager(
            _make_response_bytes("ok")
        )()
        p = OpenAIProvider(api_key="sk-test", timeout=45)
        p.analyze_problem({"title": "T"}, {"knowledge": [], "problems": []})
        self.assertEqual(mock_urlopen.call_args[1]["timeout"], 45)

    @patch("src.ai.openai.urllib.request.urlopen")
    def test_system_prompt_in_messages(self, mock_urlopen):
        mock_urlopen.return_value = _mock_context_manager(
            _make_response_bytes("ok")
        )()
        p = OpenAIProvider(api_key="sk-test")
        p.analyze_problem({"title": "T"}, {"knowledge": [], "problems": []})
        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data.decode("utf-8"))
        messages = body["messages"]
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[0]["content"], SYSTEM_PROMPT)

    @patch("src.ai.openai.urllib.request.urlopen")
    def test_api_key_in_header(self, mock_urlopen):
        mock_urlopen.return_value = _mock_context_manager(
            _make_response_bytes("ok")
        )()
        p = OpenAIProvider(api_key="sk-secret-key")
        p.analyze_problem({"title": "T"}, {"knowledge": [], "problems": []})
        req = mock_urlopen.call_args[0][0]
        self.assertEqual(req.get_header("Authorization"), "Bearer sk-secret-key")

    @patch("src.ai.openai.urllib.request.urlopen")
    def test_max_completion_tokens_in_payload(self, mock_urlopen):
        mock_urlopen.return_value = _mock_context_manager(
            _make_response_bytes("ok")
        )()
        p = OpenAIProvider(api_key="sk-test")
        p.analyze_problem({"title": "T"}, {"knowledge": [], "problems": []})
        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data.decode("utf-8"))
        self.assertIn("max_completion_tokens", body)
        self.assertNotIn("max_tokens", body)
        self.assertEqual(body["max_completion_tokens"], 1000)


# ── All 5 methods use common mechanism ────────────────────────────

class TestOpenAIProviderMethodsUseChat(unittest.TestCase):

    @patch("src.ai.openai.urllib.request.urlopen")
    def test_all_five_methods(self, mock_urlopen):
        mock_urlopen.return_value = _mock_context_manager(
            _make_response_bytes("response")
        )()
        p = OpenAIProvider(api_key="sk-test")

        r1 = p.analyze_problem({"title": "T"}, {"knowledge": [], "problems": []})
        r2 = p.analyze_experience({"title": "T"}, {"knowledge": [], "problems": []})
        r3 = p.create_plan({"title": "T"}, "c", [])
        r4 = p.analyze_result({"title": "T"}, "s", True)
        r5 = p.format_knowledge({"title": "T"})

        self.assertTrue(all(r.success for r in [r1, r2, r3, r4, r5]))
        self.assertEqual(mock_urlopen.call_count, 5)


# ── API key security ──────────────────────────────────────────────

class TestOpenAIProviderKeySecurity(unittest.TestCase):

    @patch("src.ai.openai.urllib.request.urlopen")
    def test_key_not_in_http_error(self, mock_urlopen):
        mock_urlopen.side_effect = _make_http_error(401)
        p = OpenAIProvider(api_key="sk-super-secret-key-12345")
        r = p.analyze_problem({"title": "T"}, {"knowledge": [], "problems": []})
        self.assertNotIn("sk-super-secret-key", r.error)

    @patch.dict("os.environ", {}, clear=True)
    def test_key_not_in_no_key_error(self):
        p = OpenAIProvider()
        r = p.analyze_problem({"title": "T"}, {"knowledge": [], "problems": []})
        self.assertNotIn("sk-", r.error)


# ── Readonly ──────────────────────────────────────────────────────

class TestOpenAIProviderReadonly(unittest.TestCase):

    @patch("src.ai.openai.urllib.request.urlopen")
    def test_does_not_modify_problem(self, mock_urlopen):
        mock_urlopen.return_value = _mock_context_manager(
            _make_response_bytes("analysis")
        )()
        p = OpenAIProvider(api_key="sk-test")
        problem = {"title": "T", "status": "new"}
        original = dict(problem)
        p.analyze_problem(problem, {"knowledge": [], "problems": []})
        self.assertEqual(problem, original)

    @patch("src.ai.openai.urllib.request.urlopen")
    def test_does_not_modify_knowledge(self, mock_urlopen):
        mock_urlopen.return_value = _mock_context_manager(
            _make_response_bytes("analysis")
        )()
        p = OpenAIProvider(api_key="sk-test")
        kr = [({"title": "K1", "type": "note", "text": "t", "tags": []}, 0.8)]
        original = [dict(r) for r, _ in kr]
        p.analyze_experience({"title": "T"}, {"knowledge": kr, "problems": []})
        self.assertEqual([dict(r) for r, _ in kr], original)


# ── Type check ────────────────────────────────────────────────────

class TestOpenAIProviderType(unittest.TestCase):

    def test_provider_has_correct_methods(self):
        p = OpenAIProvider(api_key="k")
        for method in ("analyze_problem", "analyze_experience", "create_plan",
                       "analyze_result", "format_knowledge"):
            self.assertTrue(callable(getattr(p, method)))
