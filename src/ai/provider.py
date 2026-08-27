from src.ai.types import AIResponse


SYSTEM_PROMPT = (
    "Ты — AI-помощник для разработчика. "
    "Твоя задача — помогать анализировать технические проблемы и предлагать решения.\n\n"
    "Правила:\n"
    "- Отвечай кратко и по существу\n"
    "- Если не уверен — скажи об этом (confidence низкий)\n"
    "- Не выдумывай факты\n"
    "- Основывайся на переданных данных\n"
    "- Язык ответа — русский (как у пользователя)"
)


class AIProvider:
    """Базовый контракт AI-провайдера.

    Все методы возвращают AIResponse.
    Если AI недоступен — возвращают AIResponse(success=False).
    Никогда не бросают исключения наружу.
    """

    def analyze_problem(self, problem: dict, search_results: dict) -> AIResponse:
        """Анализ новой проблемы."""
        raise NotImplementedError

    def analyze_experience(self, problem: dict, search_results: dict) -> AIResponse:
        """Анализ найденного опыта."""
        raise NotImplementedError

    def create_plan(self, problem: dict, cause: str, similar_solutions: list[str]) -> AIResponse:
        """Составление плана решения."""
        raise NotImplementedError

    def analyze_result(self, problem: dict, solution: str, helped: bool | None) -> AIResponse:
        """Анализ результата решения."""
        raise NotImplementedError

    def format_knowledge(self, problem: dict) -> AIResponse:
        """Помощь в формировании Knowledge Record."""
        raise NotImplementedError

    def suggest_hypotheses(self, problem: dict, diagnostic_context: dict) -> AIResponse:
        """Предлагает гипотезы о причине проблемы (диагностика).

        diagnostic_context — компактный контекст расследования (см. get_diagnostic_context).
        Возвращает AIResponse, где suggestions = список строк-гипотез, content = пояснение.
        """
        raise NotImplementedError

    def suggest_next_check(self, problem: dict, diagnostic_context: dict) -> AIResponse:
        """Предлагает следующий шаг проверки гипотез (диагностика).

        Возвращает AIResponse, где content = описание одного шага, suggestions = альтернативы.
        """
        raise NotImplementedError


class NullProvider(AIProvider):
    """Заглушка — возвращает success=False для всех методов.

    Используется когда:
    - AI не настроен
    - API-ключ отсутствует
    - AI отключён в настройках
    """

    def analyze_problem(self, problem: dict, search_results: dict) -> AIResponse:
        return AIResponse(success=False, content="", suggestions=[], confidence=0.0)

    def analyze_experience(self, problem: dict, search_results: dict) -> AIResponse:
        return AIResponse(success=False, content="", suggestions=[], confidence=0.0)

    def create_plan(self, problem: dict, cause: str, similar_solutions: list[str]) -> AIResponse:
        return AIResponse(success=False, content="", suggestions=[], confidence=0.0)

    def analyze_result(self, problem: dict, solution: str, helped: bool | None) -> AIResponse:
        return AIResponse(success=False, content="", suggestions=[], confidence=0.0)

    def format_knowledge(self, problem: dict) -> AIResponse:
        return AIResponse(success=False, content="", suggestions=[], confidence=0.0)

    def suggest_hypotheses(self, problem: dict, diagnostic_context: dict) -> AIResponse:
        return AIResponse(success=False, content="", suggestions=[], confidence=0.0)

    def suggest_next_check(self, problem: dict, diagnostic_context: dict) -> AIResponse:
        return AIResponse(success=False, content="", suggestions=[], confidence=0.0)
