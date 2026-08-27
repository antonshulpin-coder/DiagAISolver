import json
import os
import urllib.error
import urllib.request

from src.ai.context import (
    build_analyze_experience_context,
    build_analyze_problem_context,
    build_analyze_result_context,
    build_create_plan_context,
    build_format_knowledge_context,
    build_suggest_hypotheses_context,
    build_suggest_next_check_context,
)
from src.ai.provider import SYSTEM_PROMPT
from src.ai.types import AIResponse


class OpenAIProvider:
    """Провайдер для OpenAI-совместимого API через stdlib (без SDK).

    Поддерживает переопределение base_url (например, OpenRouter).
    По умолчанию — официальный API OpenAI.
    """

    DEFAULT_BASE_URL = "https://api.openai.com/v1"
    DEFAULT_APP_URL = "https://github.com/antonshulpin-coder/DiagAISolver"
    DEFAULT_APP_TITLE = "DiagAISolver"
    API_URL = "https://api.openai.com/v1/chat/completions"  # для обратной совместимости

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-4o-mini",
        timeout: int = 30,
        base_url: str | None = None,
        app_url: str | None = None,
        app_title: str | None = None,
    ):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.model = model
        self.timeout = timeout
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self.api_url = f"{self.base_url}/chat/completions"
        self.app_url = app_url or os.environ.get("AI_APP_URL") or self.DEFAULT_APP_URL
        self.app_title = app_title or os.environ.get("AI_APP_TITLE") or self.DEFAULT_APP_TITLE

    def _chat(self, user_content: str) -> AIResponse:
        """Общий механизм: отправка одного сообщения и получение ответа."""
        if not self.api_key:
            return AIResponse(success=False, content="", error="API key не задан")

        payload = json.dumps({
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "max_completion_tokens": 1000,
        }).encode("utf-8")

        req = urllib.request.Request(
            self.api_url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": self.app_url,
                "X-Title": self.app_title,
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return _parse_response(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return _handle_http_error(e)
        except urllib.error.URLError as e:
            return AIResponse(success=False, content="", error=f"Сетевая ошибка: {e.reason}")
        except TimeoutError:
            return AIResponse(success=False, content="", error=f"Таймаут {self.timeout}с")
        except Exception as e:
            return AIResponse(success=False, content="", error=str(e))

    def analyze_problem(self, problem: dict, search_results: dict) -> AIResponse:
        ctx = build_analyze_problem_context(
            problem,
            search_results.get("knowledge", []),
            search_results.get("problems", []),
        )
        return self._chat(f"Проанализируй проблему:\n{json.dumps(ctx, ensure_ascii=False)}")

    def analyze_experience(self, problem: dict, search_results: dict) -> AIResponse:
        ctx = build_analyze_experience_context(
            problem,
            search_results.get("knowledge", []),
            search_results.get("problems", []),
        )
        return self._chat(f"Оцени найденный опыт:\n{json.dumps(ctx, ensure_ascii=False)}")

    def create_plan(self, problem: dict, cause: str, similar_solutions: list[str]) -> AIResponse:
        ctx = build_create_plan_context(problem, cause, similar_solutions)
        return self._chat(f"Составь план решения:\n{json.dumps(ctx, ensure_ascii=False)}")

    def analyze_result(self, problem: dict, solution: str, helped: bool | None) -> AIResponse:
        ctx = build_analyze_result_context(problem, solution, helped)
        return self._chat(f"Проанализируй результат:\n{json.dumps(ctx, ensure_ascii=False)}")

    def format_knowledge(self, problem: dict) -> AIResponse:
        ctx = build_format_knowledge_context(problem)
        return self._chat(f"Помоги сформулировать запись знаний:\n{json.dumps(ctx, ensure_ascii=False)}")

    def suggest_hypotheses(self, problem: dict, diagnostic_context: dict) -> AIResponse:
        ctx = build_suggest_hypotheses_context(problem, diagnostic_context)
        prompt = (
            "Предложи гипотезы о причине проблемы в рамках диагностики. "
            "Верни JSON вида {\"suggestions\": [\"гипотеза 1\", ...], \"explanation\": \"пояснение\"}. "
            "Не повторяй уже отклонённые гипотезы.\n"
            f"{json.dumps(ctx, ensure_ascii=False)}"
        )
        resp = self._chat(prompt)
        if not resp.success:
            return resp
        suggestions, explanation = _parse_hypotheses_response(resp.content)
        return AIResponse(
            success=True,
            content=explanation if explanation else resp.content,
            suggestions=suggestions,
            confidence=resp.confidence,
        )

    def suggest_next_check(self, problem: dict, diagnostic_context: dict) -> AIResponse:
        ctx = build_suggest_next_check_context(problem, diagnostic_context)
        prompt = (
            "Предложи следующий шаг проверки гипотез в рамках диагностики. "
            "Верни JSON вида {\"check\": \"что проверить\", \"alternatives\": [\"альтернатива 1\", ...]}. "
            "Не повторяй уже выполненные шаги.\n"
            f"{json.dumps(ctx, ensure_ascii=False)}"
        )
        resp = self._chat(prompt)
        if not resp.success:
            return resp
        check, alternatives = _parse_next_check_response(resp.content)
        return AIResponse(
            success=True,
            content=check,
            suggestions=alternatives,
            confidence=resp.confidence,
        )


def _clean_suggestions(items) -> list[str]:
    """Очистка и дедупликация списка строк-предложений.

    Отбрасывает пустые и нестроковые; дубли убирает (по нормализованному тексту).
    """
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if not isinstance(item, str):
            continue
        text = item.strip()
        if not text:
            continue
        key = " ".join(text.lower().split())
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def _parse_hypotheses_response(content: str) -> tuple[list[str], str]:
    """Разбирает ответ suggest_hypotheses: (suggestions, explanation).

    Пытается распарсить JSON; при неудаче берёт непустые строки как гипотезы.
    """
    raw = content.strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        lines = [
            line.lstrip("- *•\t ").strip()
            for line in raw.splitlines()
            if line.strip()
        ]
        return _clean_suggestions(lines), raw

    if isinstance(data, list):
        return _clean_suggestions(data), ""

    if isinstance(data, dict):
        suggestions: list[str] = []
        for key in ("suggestions", "hypotheses"):
            value = data.get(key)
            if isinstance(value, list):
                suggestions = _clean_suggestions(value)
                break
        explanation = data.get("explanation")
        if not isinstance(explanation, str):
            explanation = data.get("content", "")
        if not isinstance(explanation, str):
            explanation = ""
        return suggestions, explanation.strip()

    return [], raw


def _parse_next_check_response(content: str) -> tuple[str, list[str]]:
    """Разбирает ответ suggest_next_check: (check, alternatives)."""
    raw = content.strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw, []

    if isinstance(data, list):
        items = _clean_suggestions(data)
        if items:
            return items[0], items[1:]
        return "", []

    if isinstance(data, dict):
        check = data.get("check") or data.get("description") or data.get("content") or ""
        if not isinstance(check, str):
            check = ""
        alternatives = data.get("alternatives")
        if not isinstance(alternatives, list):
            alternatives = []
        return check.strip(), _clean_suggestions(alternatives)

    return raw, []


def _parse_response(raw: str) -> AIResponse:
    """Парсинг HTTP-ответа OpenAI в AIResponse."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return AIResponse(success=False, content="", error=f"Невалидный JSON: {e}")

    try:
        message = data["choices"][0]["message"]
    except (KeyError, IndexError, TypeError):
        return AIResponse(success=False, content="", error="Неожиданный формат ответа API")

    refusal = message.get("refusal")
    if refusal:
        return AIResponse(success=False, content="", error=f"Модель отказалась: {refusal}")

    content = message.get("content")
    if not content:
        return AIResponse(success=False, content="", error="Пустой ответ API")

    return AIResponse(success=True, content=content, confidence=0.7)


def _handle_http_error(e: urllib.error.HTTPError) -> AIResponse:
    """Обработка HTTP-ошибок OpenAI API."""
    code = e.code
    if code == 401:
        return AIResponse(success=False, content="", error="Неверный API key (401)")
    elif code == 403:
        return AIResponse(success=False, content="", error="Доступ запрещён (403)")
    elif code == 429:
        return AIResponse(success=False, content="", error="Превышен лимит запросов (429)")
    elif code >= 500:
        return AIResponse(success=False, content="", error=f"Ошибка сервера OpenAI ({code})")
    else:
        return AIResponse(success=False, content="", error=f"HTTP ошибка ({code})")
