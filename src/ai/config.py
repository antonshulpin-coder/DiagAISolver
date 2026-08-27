"""Конфигурация AI — загрузка настроек и фабрика провайдеров."""

import json
from dataclasses import dataclass, field
from pathlib import Path

from src.ai.provider import NullProvider

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_SETTINGS = PROJECT_ROOT / "config" / "settings.json"

AI_DEFAULTS = {
    "enabled": False,
    "provider": "openai",
    "model": "gpt-4o-mini",
    "timeout": 30,
    "base_url": "https://api.openai.com/v1",
}


@dataclass
class AIConfig:
    """Настройки AI из settings.json."""
    enabled: bool = False
    provider: str = "openai"
    model: str = "gpt-4o-mini"
    timeout: int = 30
    base_url: str = "https://api.openai.com/v1"


def load_config(settings_path: Path | str | None = None) -> AIConfig:
    """Загружает AI-конфигурацию из settings.json.

    Если файл отсутствует или повреждён — возвращает безопасные defaults.
    Никогда не бросает исключения.
    """
    path = Path(settings_path) if settings_path else DEFAULT_SETTINGS

    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return AIConfig()

    ai_raw = data.get("ai", {})
    if not isinstance(ai_raw, dict):
        return AIConfig()

    return AIConfig(
        enabled=bool(ai_raw.get("enabled", AI_DEFAULTS["enabled"])),
        provider=str(ai_raw.get("provider", AI_DEFAULTS["provider"])),
        model=str(ai_raw.get("model", AI_DEFAULTS["model"])),
        timeout=int(ai_raw.get("timeout", AI_DEFAULTS["timeout"])),
        base_url=str(ai_raw.get("base_url", AI_DEFAULTS["base_url"])),
    )


def get_ai_provider(config: AIConfig | None = None, api_key: str | None = None):
    """Фабрика: конфигурация → AIProvider.

    Возвращает AIProvider или NullProvider.
    Никогда не бросает исключения наружу.
    """
    try:
        if config is None:
            config = load_config()

        if not config.enabled:
            return NullProvider()

        if config.provider == "openai":
            from src.ai.openai import OpenAIProvider
            return OpenAIProvider(
                api_key=api_key,
                model=config.model,
                timeout=config.timeout,
                base_url=config.base_url,
            )

        return NullProvider()
    except Exception:
        return NullProvider()
