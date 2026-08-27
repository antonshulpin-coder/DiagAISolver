MAX_SEARCH_RESULTS = 5
MAX_KNOWLEDGE_TEXT = 500
MAX_PLAN_SOLUTIONS = 3


def build_analyze_problem_context(
    problem: dict,
    knowledge_results: list[tuple[dict, float]],
    problem_results: list[tuple[dict, float]],
) -> dict:
    return {
        "problem": _compact_problem(problem),
        "similar_knowledge": [_compact_knowledge(r) for r, _ in knowledge_results[:MAX_SEARCH_RESULTS]],
        "similar_problems": [_compact_problem(r) for r, _ in problem_results[:MAX_SEARCH_RESULTS]],
    }


def build_analyze_experience_context(
    problem: dict,
    knowledge_results: list[tuple[dict, float]],
    problem_results: list[tuple[dict, float]],
) -> dict:
    return {
        "problem": _compact_problem(problem),
        "knowledge_options": [_compact_knowledge(r) for r, _ in knowledge_results[:MAX_SEARCH_RESULTS]],
        "problem_options": [_compact_problem(r) for r, _ in problem_results[:MAX_SEARCH_RESULTS]],
    }


def build_create_plan_context(problem: dict, cause: str, similar_solutions: list[str]) -> dict:
    return {
        "problem": _compact_problem(problem),
        "cause": cause,
        "similar_solutions": similar_solutions[:MAX_PLAN_SOLUTIONS],
    }


def build_analyze_result_context(problem: dict, solution: str, helped: bool | None) -> dict:
    return {
        "problem": _compact_problem(problem),
        "solution": solution,
        "helped": helped,
    }


def build_format_knowledge_context(problem: dict) -> dict:
    return {
        "problem": _compact_problem(problem),
        "cause": problem.get("cause", ""),
        "solution": problem.get("solution", ""),
        "helped": problem.get("helped"),
    }


def _compact_problem(problem: dict) -> dict:
    return {
        "title": problem.get("title", ""),
        "description": problem.get("description", ""),
        "context": problem.get("context", ""),
        "error_message": problem.get("error_message", ""),
        "tags": problem.get("tags", []),
        "status": problem.get("status", ""),
        "cause": problem.get("cause", ""),
        "solution": problem.get("solution", ""),
    }


def _compact_knowledge(record: dict) -> dict:
    return {
        "title": record.get("title", ""),
        "type": record.get("type", ""),
        "text": record.get("text", "")[:MAX_KNOWLEDGE_TEXT],
        "tags": record.get("tags", []),
    }


def build_suggest_hypotheses_context(problem: dict, diagnostic_context: dict) -> dict:
    """Контекст для suggest_hypotheses: компактная проблема + диагностика."""
    return {
        "problem": _compact_problem(problem),
        "diagnostic": _compact_diagnostic_context(diagnostic_context),
    }


def build_suggest_next_check_context(problem: dict, diagnostic_context: dict) -> dict:
    """Контекст для suggest_next_check: компактная проблема + диагностика."""
    return {
        "problem": _compact_problem(problem),
        "diagnostic": _compact_diagnostic_context(diagnostic_context),
    }


def _compact_diagnostic_context(diagnostic_context) -> dict:
    """Компактный срез диагностики для AI.

    Не передаём ID/времена; ограничиваем число гипотез/шагов.
    Сама get_diagnostic_context() (src/diagnostic.py) уже обрезает,
    здесь повторно ограничиваем защитно.
    """
    if not isinstance(diagnostic_context, dict):
        diagnostic_context = {}
    open_h = diagnostic_context.get("open_hypotheses") or []
    rejected_h = diagnostic_context.get("rejected_hypotheses") or []
    steps = diagnostic_context.get("recent_steps") or []
    return {
        "open_hypotheses": open_h[:MAX_SEARCH_RESULTS],
        "rejected_hypotheses": rejected_h[:MAX_SEARCH_RESULTS],
        "recent_steps": steps[:MAX_SEARCH_RESULTS],
        "conclusion": diagnostic_context.get("conclusion", ""),
    }
