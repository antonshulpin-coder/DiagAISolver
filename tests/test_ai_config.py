import json
import unittest
from pathlib import Path
from unittest.mock import patch

from src.ai.config import AIConfig, load_config, get_ai_provider
from src.ai.provider import NullProvider
from src.ai.types import AIResponse
from tests.fake_provider import FakeProvider


SETTINGS_TEST = Path(__file__).resolve().parent.parent / "data" / "settings_ai_test.json"


def _clean():
    SETTINGS_TEST.unlink(missing_ok=True)


def _write_settings(data):
    SETTINGS_TEST.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


# ── AIConfig defaults ─────────────────────────────────────────────

class TestAIConfigDefaults(unittest.TestCase):

    def test_default_values(self):
        cfg = AIConfig()
        self.assertFalse(cfg.enabled)
        self.assertEqual(cfg.provider, "openai")
        self.assertEqual(cfg.model, "gpt-4o-mini")
        self.assertEqual(cfg.timeout, 30)
        self.assertEqual(cfg.base_url, "https://api.openai.com/v1")
        self.assertEqual(cfg.app_url, "https://github.com/antonshulpin-coder/DiagAISolver")
        self.assertEqual(cfg.app_title, "DiagAISolver")


# ── load_config ───────────────────────────────────────────────────

class TestLoadConfig(unittest.TestCase):

    def test_valid_settings(self):
        _write_settings({
            "academy_root": "/tmp",
            "ai": {
                "enabled": True,
                "provider": "openai",
                "model": "gpt-4o",
                "timeout": 60,
                "base_url": "https://openrouter.ai/api/v1",
            },
        })
        cfg = load_config(SETTINGS_TEST)
        self.assertTrue(cfg.enabled)
        self.assertEqual(cfg.provider, "openai")
        self.assertEqual(cfg.model, "gpt-4o")
        self.assertEqual(cfg.timeout, 60)
        self.assertEqual(cfg.base_url, "https://openrouter.ai/api/v1")
        _clean()

    def test_missing_file_returns_defaults(self):
        cfg = load_config(Path("/nonexistent/path.json"))
        self.assertFalse(cfg.enabled)
        self.assertEqual(cfg.provider, "openai")

    def test_invalid_json_returns_defaults(self):
        SETTINGS_TEST.write_text("not json {{{", encoding="utf-8")
        cfg = load_config(SETTINGS_TEST)
        self.assertFalse(cfg.enabled)
        _clean()

    def test_empty_file_returns_defaults(self):
        SETTINGS_TEST.write_text("", encoding="utf-8")
        cfg = load_config(SETTINGS_TEST)
        self.assertFalse(cfg.enabled)
        _clean()

    def test_missing_ai_section_returns_defaults(self):
        _write_settings({"academy_root": "/tmp"})
        cfg = load_config(SETTINGS_TEST)
        self.assertFalse(cfg.enabled)
        self.assertEqual(cfg.provider, "openai")
        _clean()

    def test_ai_section_not_dict_returns_defaults(self):
        _write_settings({"ai": "invalid"})
        cfg = load_config(SETTINGS_TEST)
        self.assertFalse(cfg.enabled)
        _clean()

    def test_partial_ai_config_fills_defaults(self):
        _write_settings({"ai": {"enabled": True}})
        cfg = load_config(SETTINGS_TEST)
        self.assertTrue(cfg.enabled)
        self.assertEqual(cfg.provider, "openai")
        self.assertEqual(cfg.model, "gpt-4o-mini")
        self.assertEqual(cfg.timeout, 30)
        self.assertEqual(cfg.base_url, "https://api.openai.com/v1")
        _clean()

    def test_none_path_uses_default(self):
        cfg = load_config(None)
        self.assertIsInstance(cfg, AIConfig)


# ── get_ai_provider ───────────────────────────────────────────────

class TestGetAIProvider(unittest.TestCase):

    def test_disabled_returns_null(self):
        cfg = AIConfig(enabled=False)
        p = get_ai_provider(config=cfg)
        self.assertIsInstance(p, NullProvider)

    def test_enabled_openai_returns_openai_provider(self):
        cfg = AIConfig(enabled=True, provider="openai", model="gpt-4o", timeout=15, base_url="https://openrouter.ai/api/v1", app_url="https://example.org/app", app_title="MyApp")
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=False):
            p = get_ai_provider(config=cfg)
        self.assertEqual(type(p).__name__, "OpenAIProvider")
        self.assertEqual(p.model, "gpt-4o")
        self.assertEqual(p.timeout, 15)
        self.assertEqual(p.base_url, "https://openrouter.ai/api/v1")
        self.assertEqual(p.api_url, "https://openrouter.ai/api/v1/chat/completions")
        self.assertEqual(p.app_url, "https://example.org/app")
        self.assertEqual(p.app_title, "MyApp")

    def test_enabled_openai_no_key_returns_openai_provider(self):
        cfg = AIConfig(enabled=True, provider="openai")
        with patch.dict("os.environ", {}, clear=True):
            p = get_ai_provider(config=cfg)
        self.assertEqual(type(p).__name__, "OpenAIProvider")
        self.assertEqual(p.api_key, "")

    def test_unknown_provider_returns_null(self):
        cfg = AIConfig(enabled=True, provider="unknown_ai")
        p = get_ai_provider(config=cfg)
        self.assertIsInstance(p, NullProvider)

    def test_none_config_loads_default(self):
        with patch("src.ai.config.DEFAULT_SETTINGS", SETTINGS_TEST):
            _write_settings({"ai": {"enabled": False}})
            p = get_ai_provider(config=None)
            self.assertIsInstance(p, NullProvider)
            _clean()

    def test_api_key_from_constructor(self):
        cfg = AIConfig(enabled=True, provider="openai")
        p = get_ai_provider(config=cfg, api_key="sk-direct")
        self.assertEqual(type(p).__name__, "OpenAIProvider")
        self.assertEqual(p.api_key, "sk-direct")

    def test_initialization_exception_returns_null(self):
        cfg = AIConfig(enabled=True, provider="openai")
        with patch("src.ai.config.get_ai_provider.__wrapped__" if hasattr(get_ai_provider, '__wrapped__') else "src.ai.openai.OpenAIProvider.__init__", side_effect=RuntimeError("init failed")):
            p = get_ai_provider(config=cfg)
        self.assertIsInstance(p, NullProvider)


# ── Secret isolation ──────────────────────────────────────────────

class TestSecretIsolation(unittest.TestCase):

    def test_api_key_not_in_settings(self):
        _write_settings({
            "ai": {
                "enabled": True,
                "provider": "openai",
                "model": "gpt-4o-mini",
                "timeout": 30,
            },
        })
        cfg = load_config(SETTINGS_TEST)
        raw = SETTINGS_TEST.read_text(encoding="utf-8")
        self.assertNotIn("sk-", raw)
        self.assertNotIn("api_key", raw)
        _clean()

    def test_api_key_not_in_config_repr(self):
        cfg = AIConfig(enabled=True, provider="openai")
        r = repr(cfg)
        self.assertNotIn("sk-", r)
        self.assertNotIn("api_key", r)

    def test_api_key_not_in_null_provider_error(self):
        cfg = AIConfig(enabled=False)
        p = get_ai_provider(config=cfg)
        r = p.analyze_problem({"title": "T"}, {})
        self.assertNotIn("sk-", r.error or "")


# ── SOLVE integration ─────────────────────────────────────────────

class TestSolveConfigIntegration(unittest.TestCase):

    @patch("src.commands.input", side_effect=["0"])
    @patch("src.commands.print")
    def test_solve_flow_auto_detects_disabled(self, mock_print, mock_input):
        from src.commands import solve_flow
        cfg = AIConfig(enabled=False)
        with patch("src.ai.config.load_config", return_value=cfg):
            solve_flow()
        calls = [str(c) for c in mock_print.call_args_list]
        self.assertTrue(any("недоступен" in c for c in calls))

    @patch("src.commands.input", side_effect=["0"])
    @patch("src.commands.print")
    def test_solve_flow_explicit_provider_overrides_config(self, mock_print, mock_input):
        from src.commands import solve_flow
        fake = FakeProvider()
        solve_flow(provider=fake)
        calls = [str(c) for c in mock_print.call_args_list]
        self.assertTrue(any("подключён" in c for c in calls))

    @patch("src.commands.input", side_effect=["0"])
    @patch("src.commands.print")
    def test_solve_flow_broken_config_still_works(self, mock_print, mock_input):
        from src.commands import solve_flow
        with patch("src.ai.config.load_config", side_effect=RuntimeError("config broken")):
            solve_flow()
        calls = [str(c) for c in mock_print.call_args_list]
        self.assertTrue(any("недоступен" in c for c in calls))
