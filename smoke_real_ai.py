"""Real AI smoke-test: live run of OpenAIProvider against the real API.

Run from repo root with the key in the environment (key is never printed):
    set OPENAI_API_KEY=sk-...
    python smoke_real_ai.py
Optional endpoint override (e.g. OpenRouter):
    set OPENAI_BASE_URL=https://openrouter.ai/api/v1

DANGER: never place the key in this file, commit, or any command above.
The key is read ONLY from the OPENAI_API_KEY environment variable.
Output is masked and truncated; raw model responses are never printed in full.
This script is idempotent and writes nothing to data/.
"""

import hashlib
import os
import sys
from pathlib import Path

from src.ai.openai import OpenAIProvider

# ---------------------------------------------------------------------------
# Limits / sanity bounds (see src/ai/context.py + src/diagnostic.py).
# ---------------------------------------------------------------------------
SANITY_MAX_SUGGESTIONS = 12   # defensive bound for any suggestions list
RESPONSE_PREVIEW = 100        # characters of the model answer to print


def mask_key(key: str) -> str:
    """Return masked form of a key: sk-***LAST4."""
    if not key:
        return "<нет>"
    tail = key[-4:] if len(key) >= 4 else key
    return f"sk-***{tail}"


def classify_error(resp) -> str:
    """Map an unsuccessful AIResponse.error to a stable short tag."""
    err = (resp.error or "").lower()
    if "api key не задан" in err or "не задан" in err:
        return "no-key"
    if "401" in err:
        return "HTTP 401"
    if "403" in err:
        return "HTTP 403"
    if "429" in err:
        return "HTTP 429"
    if "ошибка сервера" in err:
        return "HTTP 5xx"
    if "таймаут" in err:
        return "timeout"
    if "сетевая ошибка" in err:
        return "network"
    if "отказалась" in err:
        return "refusal"
    if "пустой ответ" in err:
        return "empty"
    if "невалидный json" in err or "неожиданный формат" in err:
        return "malformed"
    return err or "unknown"


def preview(text: str) -> str:
    text = (text or "").replace("\n", " ").strip()
    if len(text) > RESPONSE_PREVIEW:
        return text[:RESPONSE_PREVIEW] + "…"
    return text


def check_step(name: str, desc: str, resp) -> tuple[str, bool]:
    """Run one logical check, print result, return (tag, ok)."""
    if resp.success:
        print(f"[OK]   {name}")
        print(f"       {desc}")
        suggestions = getattr(resp, "suggestions", None) or []
        if suggestions:
            print(f"       suggestions: {len(suggestions)}")
            for s in suggestions[:3]:
                print(f"         - {preview(s)}")
        else:
            print(f"       content: {preview(resp.content)}")

        empty_sugs = [s for s in suggestions if not (s or "").strip()]
        over = len(suggestions) > SANITY_MAX_SUGGESTIONS
        if empty_sugs:
            print(f"       [WARN] {len(empty_sugs)} пустых suggestion")
            return "warn-empty-sugs", False
        if over:
            print(f"       [WARN] suggestions {len(suggestions)} > {SANITY_MAX_SUGGESTIONS}")
            return "warn-over-limit", False
        if not suggestions and not (resp.content or "").strip():
            print(f"       [WARN] ответ пуст")
            return "warn-empty", False
        return "success", True

    tag = classify_error(resp)
    print(f"[FAIL] {name} ({tag}): {preview(resp.error)}")
    return tag, False


def file_sha256(path: Path) -> str:
    if not path.exists():
        return "<отсутствует>"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    key = os.environ.get("OPENAI_API_KEY", "")
    print("=== Real AI smoke-test ===")
    print(f"key: {mask_key(key)}")
    if not key:
        print("no-key: переменная OPENAI_API_KEY не задана. Запуск из своего терминала:")
        print('  set OPENAI_API_KEY=sk-...')
        print('  python smoke_real_ai.py')
        return 1

    base_url = os.environ.get("OPENAI_BASE_URL") or OpenAIProvider.DEFAULT_BASE_URL
    print(f"base_url: {base_url}")
    provider = OpenAIProvider(api_key=key, base_url=base_url)

    problems_path = Path("data") / "problems.json"
    before = file_sha256(problems_path)
    print(f"data/problems.json (до):  {before[:12]}…")

    demo_problem = {
        "title": "Приложение не запускается после обновления",
        "description": "После обновления до 1.4.0 CLI падает с ошибкой при старте.",
        "context": "Обновление через pip, среда Windows, Python 3.12.",
        "error_message": "ModuleNotFoundError: No module named 'x'",
        "tags": ["cli", "upgrade", "windows"],
        "status": "open",
        "cause": "",
        "solution": "",
    }

    fabricated_diagnostic = {
        "open_hypotheses": [
            {"text": "Несовместимая версия зависимости", "status": "open", "source": "AI"},
        ],
        "rejected_hypotheses": [
            {"text": "Проблема с правами доступа к каталогу", "status": "rejected", "source": "AI"},
        ],
        "recent_steps": [
            {"description": "Проверить версию установленных пакетов", "status": "done", "result": "pending"},
        ],
        "conclusion": "",
    }

    search_results = {
        "knowledge": [],
        "problems": [],
    }

    print("\n--- Шаг 1: базовый метод format_knowledge (простой smoke) ---")
    step, ok = check_step(
        "format_knowledge",
        "помощь в формулировке Knowledge Record по демо-проблеме",
        provider.format_knowledge(demo_problem),
    )
    if not ok and step in ("HTTP 401", "no-key"):
        print("Остановка: неверный/отсутствующий ключ.")
        return 2

    print("\n--- Шаг 2: suggest_hypotheses (диагностика, демо + фабричный контекст) ---")
    r1 = provider.suggest_hypotheses(demo_problem, fabricated_diagnostic)
    step, ok = check_step(
        "suggest_hypotheses",
        "гипотезы причины по открытой проблеме",
        r1,
    )
    if not ok and step in ("HTTP 401", "no-key"):
        print("Остановка: неверный/отсутствующий ключ.")
        return 2

    print("\n--- Шаг 3: suggest_next_check (тот же контекст) ---")
    r2 = provider.suggest_next_check(demo_problem, fabricated_diagnostic)
    step, ok = check_step(
        "suggest_next_check",
        "следующий шаг проверки гипотез",
        r2,
    )

    after = file_sha256(problems_path)
    print("\n--- Изоляция хранилища ---")
    print(f"data/problems.json (после): {after[:12]}…")
    if before == after:
        print("[OK]   data/problems.json не изменён (скрипт работал на in-memory объекте).")
    else:
        print("[FAIL] data/problems.json ИЗМЕНИЛСЯ — нарушена изоляция!")
        return 3

    print("\n=== Итог: smoke-test завершён (см. строки выше). ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
