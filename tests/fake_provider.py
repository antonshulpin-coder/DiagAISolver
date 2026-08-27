from src.ai.types import AIResponse
from src.ai.provider import AIProvider


class FakeProvider(AIProvider):
    """Тестовый провайдер с предопределёнными ответами.

    Логирует все вызовы в self.calls для проверки.
    """

    def __init__(self, responses=None):
        self.responses = responses or {}
        self.calls: list[tuple[str, tuple, dict]] = []

    def analyze_problem(self, problem: dict, search_results: dict) -> AIResponse:
        self.calls.append(("analyze_problem", (problem, search_results), {}))
        return self.responses.get(
            "analyze_problem",
            AIResponse(
                success=True,
                content="Тестовый анализ проблемы",
                suggestions=["Проверь venv", "Посмотри логи"],
                confidence=0.9,
            ),
        )

    def analyze_experience(self, problem: dict, search_results: dict) -> AIResponse:
        self.calls.append(("analyze_experience", (problem, search_results), {}))
        return self.responses.get(
            "analyze_experience",
            AIResponse(
                success=True,
                content="Тестовый анализ опыта",
                suggestions=["Попробуй pip install", "Перезапусти терминал"],
                confidence=0.8,
            ),
        )

    def create_plan(self, problem: dict, cause: str, similar_solutions: list[str]) -> AIResponse:
        self.calls.append(("create_plan", (problem, cause, similar_solutions), {}))
        return self.responses.get(
            "create_plan",
            AIResponse(
                success=True,
                content="Тестовый план решения",
                suggestions=["Шаг 1: установи зависимости", "Шаг 2: перезапусти"],
                confidence=0.7,
            ),
        )

    def analyze_result(self, problem: dict, solution: str, helped: bool | None) -> AIResponse:
        self.calls.append(("analyze_result", (problem, solution, helped), {}))
        return self.responses.get(
            "analyze_result",
            AIResponse(
                success=True,
                content="Тестовый анализ результата",
                suggestions=["Решение рабочее", "Стоит добавить в базу знаний"],
                confidence=0.85,
            ),
        )

    def format_knowledge(self, problem: dict) -> AIResponse:
        self.calls.append(("format_knowledge", (problem,), {}))
        return self.responses.get(
            "format_knowledge",
            AIResponse(
                success=True,
                content="Тестовый текст записи",
                suggestions=["Добавь тег python", "Уточни описание"],
                confidence=0.75,
            ),
        )

    def suggest_hypotheses(self, problem: dict, diagnostic_context: dict) -> AIResponse:
        self.calls.append(("suggest_hypotheses", (problem, diagnostic_context), {}))
        return self.responses.get(
            "suggest_hypotheses",
            AIResponse(
                success=True,
                content="Возможные причины: сломан venv или нет пакета",
                suggestions=["Проверь venv", "Посмотри установленные пакеты"],
                confidence=0.8,
            ),
        )

    def suggest_next_check(self, problem: dict, diagnostic_context: dict) -> AIResponse:
        self.calls.append(("suggest_next_check", (problem, diagnostic_context), {}))
        return self.responses.get(
            "suggest_next_check",
            AIResponse(
                success=True,
                content="Проверить активацию виртуального окружения",
                suggestions=["Проверить pip list", "Проверить версию Python"],
                confidence=0.75,
            ),
        )

    def get_calls(self, method_name: str | None = None) -> list[tuple[str, tuple, dict]]:
        if method_name is None:
            return list(self.calls)
        return [c for c in self.calls if c[0] == method_name]

    def call_count(self, method_name: str | None = None) -> int:
        return len(self.get_calls(method_name))
