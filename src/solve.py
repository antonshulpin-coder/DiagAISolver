"""Бизнес-логика SOLVE — проведение проблемы через жизненный цикл."""


from src import problems as _problems
from src import storage as _storage
from src.search import rank_records
from src.ai.types import AIResponse
from src.ai.provider import NullProvider
from src.ai.context import (
    build_analyze_problem_context,
    build_analyze_experience_context,
    build_create_plan_context,
    build_analyze_result_context,
    build_format_knowledge_context,
    MAX_SEARCH_RESULTS,
)


# ── Переходы статусов ──────────────────────────────────────────────

# Ключ — текущий статус, значение — допустимые следующие статусы.
# failed → solving разрешён для повторной попытки.
_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "new":           ("investigating",),
    "investigating": ("solving", "failed"),
    "solving":       ("solved", "failed"),
    "solved":        ("archived",),
    "failed":        ("archived", "solving"),
    "archived":      (),
}


class SolveError(Exception):
    """Ошибка бизнес-логики SOLVE."""
    pass


# ── Построение поискового запроса ──────────────────────────────────

def build_search_query(problem: dict) -> str:
    """Формирует поисковый запрос из релевантных полей проблемы.

    Используются title, error_message и tags.
    Description намеренно исключён — он слишком длинный и снизит точность.
    """
    parts: list[str] = []
    if problem.get("title"):
        parts.append(problem["title"])
    if problem.get("error_message"):
        parts.append(problem["error_message"])
    if problem.get("tags"):
        parts.extend(problem["tags"])
    return " ".join(parts)


# ── Поиск похожего опыта ──────────────────────────────────────────

def find_similar(problem: dict) -> tuple[list[tuple[dict, float]], list[tuple[dict, float]]]:
    """Ищет похожие записи в базе знаний и базе проблем.

    Возвращает (knowledge_results, problems_results),
    где каждый элемент — список (record, score).
    """
    query = build_search_query(problem)
    if not query.strip():
        return [], []

    from src.search import _tokenize
    terms = _tokenize(query)
    min_cov = min(0.3, 1.0 / len(terms)) if terms else 1.0

    knowledge_notes = _storage.load_notes()
    knowledge_ranked = rank_records(query, knowledge_notes, min_coverage=min_cov)

    problems_list = _problems.load_problems()
    problem_search_records = [_problems._problem_to_search_record(p) for p in problems_list]
    problems_ranked = rank_records(query, problem_search_records, min_coverage=min_cov)
    id_to_problem = {p["id"]: p for p in problems_list}
    problems_results = [(id_to_problem[r["id"]], score) for r, score in problems_ranked]

    return knowledge_ranked, problems_results


# ── Переходы статусов ─────────────────────────────────────────────

def _validate_transition(current: str, target: str) -> None:
    allowed = _TRANSITIONS.get(current, ())
    if target not in allowed:
        if not allowed:
            raise SolveError(
                f"Недопустимый переход: {current} → {target} "
                f"(статус {current} не имеет допустимых переходов)"
            )
        raise SolveError(
            f"Недопустимый переход: {current} → {target} "
            f"(допустимы: {', '.join(allowed)})"
        )


def _transition(problem_id: str, target: str) -> dict:
    """Переводит проблему в целевой статус. Возвращает обновлённую проблему."""
    problem = _problems.get_problem(problem_id)
    if problem is None:
        raise SolveError(f"Проблема не найдена: {problem_id}")
    _validate_transition(problem["status"], target)
    return _problems.update_problem(problem_id, status=target)


def start_investigation(problem_id: str) -> dict:
    """new → investigating."""
    return _transition(problem_id, "investigating")


def start_solving(problem_id: str) -> dict:
    """investigating → solving."""
    return _transition(problem_id, "solving")


def archive_problem(problem_id: str) -> dict:
    """solved / failed → archived."""
    return _transition(problem_id, "archived")


# ── Решение проблемы ──────────────────────────────────────────────

def resolve_problem(
    problem_id: str,
    cause: str,
    solution: str,
    helped: bool | None,
) -> dict:
    """Фиксирует решение проблемы.

    helped=True  → solved
    helped=False → failed
    helped=None  → статус не меняется (только записываются cause/solution)

    Переход разрешён только из solving.
    """
    problem = _problems.get_problem(problem_id)
    if problem is None:
        raise SolveError(f"Проблема не найдена: {problem_id}")

    current = problem["status"]
    if current != "solving":
        raise SolveError(
            f"Нельзя решить проблему в статусе {current} "
            f"(требуется solving)"
        )

    fields: dict = {"cause": cause, "solution": solution, "helped": helped}

    if helped is True:
        fields["status"] = "solved"
    elif helped is False:
        fields["status"] = "failed"

    return _problems.update_problem(problem_id, **fields)


# ── Конвертация Problem → Knowledge Record ────────────────────────

def convert_to_knowledge(problem_id: str) -> dict:
    """Создаёт Knowledge Record на основе решённой проблемы.

    Требования:
    - статус должен быть solved или failed;
    - related_record_id должен быть None (повторная конвертация запрещена).

    Возвращает созданную Knowledge Record.
    """
    problem = _problems.get_problem(problem_id)
    if problem is None:
        raise SolveError(f"Проблема не найдена: {problem_id}")

    if problem["status"] not in ("solved", "failed"):
        raise SolveError(
            f"Нельзя конвертировать проблему в статусе {problem['status']} "
            f"(требуется solved или failed)"
        )

    if problem.get("related_record_id") is not None:
        raise SolveError(
            f"Проблема уже конвертирована в запись "
            f"(related_record_id: {problem['related_record_id']})"
        )

    text = _build_knowledge_text(problem)
    status_label = "решена" if problem["status"] == "solved" else "не решена"
    title = f"[{status_label}] {problem['title']}"

    record = _storage.create_record(
        title=title,
        text=text,
        record_type="solution",
        tags=problem.get("tags"),
    )

    _problems.update_problem(problem_id, related_record_id=record["id"])
    return record


def _build_knowledge_text(problem: dict, diagnostic_context: dict | None = None) -> str:
    """Собирает текст knowledge record из полей проблемы.

    diagnostic_context — данные диагностики для секции «Расследование».
    Если None — берётся из problem["diagnostic"]. Если данных диагностики нет —
    секция не добавляется, текст байт-в-байт идентичен старому.
    """
    parts: list[str] = []

    status_label = "решена" if problem.get("status") == "solved" else "не решена"
    parts.append(f"Статус: {status_label}")

    if problem.get("description"):
        parts.append(problem["description"])
    if problem.get("context"):
        parts.append(f"Контекст: {problem['context']}")
    if problem.get("error_message"):
        parts.append(f"Ошибка: {problem['error_message']}")
    if problem.get("cause"):
        parts.append(f"Причина: {problem['cause']}")
    if problem.get("solution"):
        parts.append(f"Решение: {problem['solution']}")
    if problem.get("helped") is not None:
        helped_label = "помогло" if problem["helped"] else "не помогло"
        parts.append(f"Результат: {helped_label}")

    investigation = _build_investigation_text(problem, diagnostic_context)
    if investigation:
        parts.append(investigation)

    return "\n\n".join(parts)


def _build_investigation_text(problem: dict, diagnostic_context: dict | None = None) -> str:
    """Строит секцию «Расследование» из данных диагностики.

    Возвращает "" если диагностики нет или она пуста.
    При обрезке соблюдается приоритет: вывод > статусы гипотез > результаты шагов.
    Лимит MAX_SEARCH_RESULTS — тот же, что у _compact_diagnostic_context.
    """
    if diagnostic_context is None:
        diagnostic_context = problem.get("diagnostic")
    if not isinstance(diagnostic_context, dict):
        return ""

    hypotheses = diagnostic_context.get("hypotheses") or []
    steps = diagnostic_context.get("steps") or []
    conclusion = diagnostic_context.get("conclusion", "") or ""
    if not hypotheses and not steps and not conclusion:
        return ""

    hyp_by_id = {h.get("id"): h for h in hypotheses}
    status_label = {
        "open": "открыта",
        "tested": "проверена",
        "confirmed": "подтверждена",
        "rejected": "отклонена",
    }

    lines = ["Расследование:"]

    ordered = (
        [h for h in hypotheses if h.get("status") in ("open", "tested")]
        + [h for h in hypotheses if h.get("status") == "confirmed"]
        + [h for h in hypotheses if h.get("status") == "rejected"]
    )[:MAX_SEARCH_RESULTS * 2]

    if ordered:
        lines.append("Гипотезы:")
        for h in ordered:
            source = "AI" if h.get("source") == "ai" else "вручную"
            status = status_label.get(h.get("status"), h.get("status", ""))
            lines.append(
                f"- [{h.get('id')}] {h.get('text', '')} ({source}) — {status}"
            )

    done_steps = [s for s in steps if s.get("status") == "done"][-MAX_SEARCH_RESULTS:]
    if done_steps:
        lines.append("Проверки:")
        for s in done_steps:
            result = s.get("result", "")
            outcome = s.get("outcome", "")
            detail = f"{result}: {outcome}" if outcome else result
            affected = ""
            hyp = hyp_by_id.get(s.get("hypothesis_id"))
            if hyp:
                status = status_label.get(hyp.get("status"), hyp.get("status", ""))
                affected = f" → {hyp.get('text', '')} ({status})"
            lines.append(f"- {s.get('description', '')} → {detail or '—'}{affected}")

    if conclusion:
        lines.append(f"Вывод: {conclusion}")

    return "\n".join(lines)

    return "\n\n".join(parts)


# ── Сводка по проблеме ────────────────────────────────────────────

def get_problem_summary(problem_id: str) -> dict:
    """Возвращает подготовленную структуру с данными проблемы для CLI."""
    problem = _problems.get_problem(problem_id)
    if problem is None:
        raise SolveError(f"Проблема не найдена: {problem_id}")

    return {
        "id": problem["id"],
        "created_at": problem["created_at"],
        "title": problem["title"],
        "description": problem.get("description", ""),
        "context": problem.get("context", ""),
        "error_message": problem.get("error_message", ""),
        "tags": problem.get("tags", []),
        "status": problem["status"],
        "cause": problem.get("cause", ""),
        "solution": problem.get("solution", ""),
        "helped": problem.get("helped"),
        "related_record_id": problem.get("related_record_id"),
    }


# ── AI-интеграция ────────────────────────────────────────────────

def _safe_ai_call(fn, fallback=None):
    """Обёртка: вызывает fn, перехватывает исключения.

    Возвращает результат fn или fallback (AIResponse с success=False).
    Никогда не бросает исключения наружу.
    """
    if fallback is None:
        fallback = AIResponse(success=False, content="", suggestions=[], confidence=0.0)
    try:
        return fn()
    except Exception:
        return fallback


def _get_provider(provider=None):
    """Возвращает provider или NullProvider если None."""
    if provider is None:
        return NullProvider()
    return provider


def ai_analyze_problem(
    problem: dict,
    knowledge_results: list[tuple[dict, float]],
    problem_results: list[tuple[dict, float]],
    provider=None,
) -> AIResponse:
    """AI-анализ новой проблемы.

    Если provider=None или произошла ошибка — возвращает AIResponse(success=False).
    Никогда не бросает исключения.
    """
    p = _get_provider(provider)
    ctx = build_analyze_problem_context(problem, knowledge_results, problem_results)
    return _safe_ai_call(
        lambda: p.analyze_problem(ctx, {"knowledge": knowledge_results, "problems": problem_results})
    )


def ai_analyze_experience(
    problem: dict,
    knowledge_results: list[tuple[dict, float]],
    problem_results: list[tuple[dict, float]],
    provider=None,
) -> AIResponse:
    """AI-анализ найденного опыта.

    Если provider=None или произошла ошибка — возвращает AIResponse(success=False).
    Никогда не бросает исключения.
    """
    p = _get_provider(provider)
    ctx = build_analyze_experience_context(problem, knowledge_results, problem_results)
    return _safe_ai_call(
        lambda: p.analyze_experience(ctx, {"knowledge": knowledge_results, "problems": problem_results})
    )


def ai_create_plan(
    problem: dict,
    cause: str,
    similar_solutions: list[str],
    provider=None,
) -> AIResponse:
    """AI-план решения.

    Если provider=None или произошла ошибка — возвращает AIResponse(success=False).
    Никогда не бросает исключения.
    """
    p = _get_provider(provider)
    ctx = build_create_plan_context(problem, cause, similar_solutions)
    return _safe_ai_call(
        lambda: p.create_plan(ctx, cause, similar_solutions)
    )


def ai_analyze_result(
    problem: dict,
    solution: str,
    helped: bool | None,
    provider=None,
) -> AIResponse:
    """AI-анализ результата решения.

    Если provider=None или произошла ошибка — возвращает AIResponse(success=False).
    Никогда не бросает исключения.
    """
    p = _get_provider(provider)
    ctx = build_analyze_result_context(problem, solution, helped)
    return _safe_ai_call(
        lambda: p.analyze_result(ctx, solution, helped)
    )


def ai_format_knowledge(
    problem: dict,
    provider=None,
) -> AIResponse:
    """AI-помощь при формировании Knowledge Record.

    Если provider=None или произошла ошибка — возвращает AIResponse(success=False).
    Никогда не бросает исключения.
    """
    p = _get_provider(provider)
    ctx = build_format_knowledge_context(problem)
    return _safe_ai_call(
        lambda: p.format_knowledge(ctx)
    )
