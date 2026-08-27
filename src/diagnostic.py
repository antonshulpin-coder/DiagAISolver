"""Бизнес-логика диагностики — итеративное расследование проблемы.

Диагностика — расширение статуса investigating. Хранится в поле
problem["diagnostic"] и позволяет идти по циклу:

    проблема → гипотезы → проверки → результаты → новые гипотезы → решение

Модуль чистый (без CLI и без AI). Все мутации атомарно сохраняются через
problems.update_problem(). При ошибках бросает SolveError.
"""


import uuid
from datetime import datetime, timezone

from src import problems as _problems
from src.solve import SolveError


# ── Лимиты ────────────────────────────────────────────────────────

MAX_OPEN_HYPOTHESES = 5          # гипотез в контексте для AI
MAX_REJECTED = 5                 # отклонённых в контексте для AI
MAX_REJECTED_HYPOTHESES = MAX_REJECTED   # синоним (по дизайну)
MAX_RECENT_STEPS = 5             # последних шагов в контексте для AI

MAX_HYPOTHESES_PER_SESSION = 10  # жёсткий лимит гипотез на сессию
MAX_STEPS_PER_SESSION = 20       # жёсткий лимит шагов на сессию

MAX_HYPOTHESIS_TEXT = 200        # макс. длина текста гипотезы
MAX_STEP_DESCRIPTION = 300       # макс. длина описания шага
MAX_OUTCOME_TEXT = 300           # макс. длина результата проверки

VALID_HYPOTHESIS_SOURCES = ("ai", "user", "knowledge")
VALID_STEP_RESULTS = ("confirmed", "rejected", "unknown")
VALID_STEP_STATUSES = ("pending", "done")
VALID_HYPOTHESIS_STATUSES = ("open", "confirmed", "rejected", "tested")

# Терминальные состояния гипотезы — их нельзя менять повторными проверками.
_TERMINAL_HYPOTHESIS = ("confirmed", "rejected")


# ── Вспомогательные ───────────────────────────────────────────────

def _new_id(length=8):
    return uuid.uuid4().hex[:length]


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _require_problem(problem_id: str) -> dict:
    """Возвращает проблему или бросает SolveError."""
    problem = _problems.get_problem(problem_id)
    if problem is None:
        raise SolveError(f"Проблема не найдена: {problem_id}")
    return problem


def _require_session(problem_id: str) -> dict:
    """Возвращает существующую сессию диагностики или бросает SolveError."""
    problem = _require_problem(problem_id)
    session = problem.get("diagnostic")
    if not isinstance(session, dict):
        raise SolveError("Диагностика не открыта для этой проблемы")
    return session


def _save_session(problem_id: str, session: dict) -> dict:
    """Сохраняет сессию и возвращает её (актуальную из файла)."""
    updated = _problems.update_problem(problem_id, diagnostic=session)
    if updated is None:
        raise SolveError(f"Проблема не найдена: {problem_id}")
    return updated["diagnostic"]


def _normalize_text(text: str, limit: int) -> str:
    """Обрезает и чистит текст; возвращает строку."""
    return text.strip()[:limit]


def _normalized_key(text: str) -> str:
    """Нормализованный ключ для дедупликации гипотез."""
    return " ".join(text.strip().lower().split())


def _find_hypothesis(session: dict, hypothesis_id: str) -> dict | None:
    for h in session.get("hypotheses", []):
        if h.get("id") == hypothesis_id:
            return h
    return None


def _find_step(session: dict, step_id: str) -> dict | None:
    for s in session.get("steps", []):
        if s.get("id") == step_id:
            return s
    return None


# ── Жизненный цикл диагностики ───────────────────────────────────

def open_diagnostic(problem_id: str) -> dict:
    """Открывает диагностическую сессию для проблемы.

    Если сессия уже существует — возвращает её без изменений.
    Инициализирует problem["diagnostic"] = {started_at, hypotheses, steps, conclusion}.
    """
    problem = _require_problem(problem_id)
    existing = problem.get("diagnostic")
    if isinstance(existing, dict):
        return existing

    session = {
        "started_at": _now_iso(),
        "hypotheses": [],
        "steps": [],
        "conclusion": "",
    }
    return _save_session(problem_id, session)


def get_diagnostic(problem_id: str) -> dict | None:
    """Возвращает сессию диагностики или None (если не открыта)."""
    problem = _require_problem(problem_id)
    session = problem.get("diagnostic")
    if not isinstance(session, dict):
        return None
    return session


def is_diagnostic_active(problem: dict) -> bool:
    """Вычисляет, активна ли диагностика.

    Активна, если проблема в статусе investigating И есть
    незакрытая гипотеза (open/tested) ИЛИ непроверенный шаг (pending).
    """
    if problem.get("status") != "investigating":
        return False
    session = problem.get("diagnostic")
    if not isinstance(session, dict):
        return False
    has_open = any(
        h.get("status") in ("open", "tested")
        for h in session.get("hypotheses", [])
    )
    has_pending = any(
        s.get("status") == "pending"
        for s in session.get("steps", [])
    )
    return has_open or has_pending


# ── Гипотезы ─────────────────────────────────────────────────────

def add_hypothesis(
    problem_id: str,
    text: str,
    source: str = "user",
    confidence: float = 1.0,
) -> dict:
    """Добавляет гипотезу (status="open") в сессию.

    source: "ai" | "user" | "knowledge"
    confidence: уверенность (0-1); для пользовательских по умолчанию 1.0.
    """
    if source not in VALID_HYPOTHESIS_SOURCES:
        raise SolveError(f"Недопустимый источник гипотезы: {source}")

    text = _normalize_text(text, MAX_HYPOTHESIS_TEXT)
    if not text:
        raise SolveError("Гипотеза не может быть пустой")

    session = _require_session(problem_id)
    hypotheses = session.get("hypotheses", [])

    if len(hypotheses) >= MAX_HYPOTHESES_PER_SESSION:
        raise SolveError("Лимит диагностики превышен: максимум 10 гипотез")

    key = _normalized_key(text)
    if any(_normalized_key(h.get("text", "")) == key for h in hypotheses):
        raise SolveError("Гипотеза уже существует")

    hypothesis = {
        "id": _new_id(),
        "text": text,
        "status": "open",
        "confidence": float(confidence),
        "source": source,
        "created_at": _now_iso(),
        "last_tested_step_id": None,
    }
    hypotheses.append(hypothesis)
    return _save_session(problem_id, session)


def add_hypotheses(problem_id: str, hypotheses: list[dict]) -> dict:
    """Добавляет гипотезы пачкой (для AI-ответа).

    Дедупликация по нормализованному text. Гипотезы, совпадающие с
    уже отклонёнными (rejected), отбрасываются. Пустые — отбрасываются.
    Соблюдается лимит MAX_HYPOTHESES_PER_SESSION.
    """
    if not hypotheses:
        return _require_session(problem_id)

    session = _require_session(problem_id)
    current = session.get("hypotheses", [])
    existing_keys = {_normalized_key(h.get("text", "")) for h in current}
    rejected_keys = {
        _normalized_key(h.get("text", ""))
        for h in current if h.get("status") == "rejected"
    }

    added = False
    for item in hypotheses:
        if isinstance(item, str):
            text = _normalize_text(item, MAX_HYPOTHESIS_TEXT)
            source = "ai"
            confidence = 0.0
        elif isinstance(item, dict):
            raw_text = item.get("text") or item.get("suggestion") or ""
            text = _normalize_text(raw_text, MAX_HYPOTHESIS_TEXT)
            source = item.get("source", "ai")
            if source not in VALID_HYPOTHESIS_SOURCES:
                source = "ai"
            try:
                confidence = float(item.get("confidence", 0.0))
            except (TypeError, ValueError):
                confidence = 0.0
        else:
            continue

        if not text:
            continue
        key = _normalized_key(text)
        if key in existing_keys or key in rejected_keys:
            continue
        if len(current) >= MAX_HYPOTHESES_PER_SESSION:
            raise SolveError("Лимит диагностики превышен: максимум 10 гипотез")

        current.append({
            "id": _new_id(),
            "text": text,
            "status": "open",
            "confidence": confidence,
            "source": source,
            "created_at": _now_iso(),
            "last_tested_step_id": None,
        })
        existing_keys.add(key)
        added = True

    if added:
        return _save_session(problem_id, session)
    return session


# ── Проверки (шаги) ──────────────────────────────────────────────

def assert_check_below_limit(session: dict) -> None:
    """Бросает SolveError, если исчерпан лимит шагов за сессию."""
    if len(session.get("steps", [])) >= MAX_STEPS_PER_SESSION:
        raise SolveError("Лимит диагностики превышен: максимум 20 проверок")


def _ensure_open_hypothesis(session: dict, hypothesis_id: str | None) -> None:
    """Проверяет, что гипотеза существует (если задана) и ещё не терминальна."""
    if hypothesis_id is None:
        return
    hypothesis = _find_hypothesis(session, hypothesis_id)
    if hypothesis is None:
        raise SolveError(f"Гипотеза не найдена: {hypothesis_id}")
    if hypothesis.get("status") in _TERMINAL_HYPOTHESIS:
        raise SolveError(
            f"Гипотеза уже {hypothesis['status']} — нельзя добавить новую проверку"
        )


def suggest_check(problem_id: str, hypothesis_id: str) -> dict:
    """Добавляет шаг проверки (status="pending") для конкретной гипотезы.

    description пока пуст — его заполняет AI (Phase 2) или пользователь.
    """
    session = _require_session(problem_id)
    _ensure_open_hypothesis(session, hypothesis_id)
    assert_check_below_limit(session)

    step = {
        "id": _new_id(),
        "hypothesis_id": hypothesis_id,
        "description": "",
        "status": "pending",
        "outcome": "",
        "result": "",
        "created_at": _now_iso(),
        "completed_at": None,
    }
    session.setdefault("steps", []).append(step)
    return _save_session(problem_id, session)


def add_check(
    problem_id: str,
    hypothesis_id: str | None,
    description: str,
) -> dict:
    """Добавляет произвольный шаг проверки (пользовательский).

    hypothesis_id может быть None (свободная проверка).
    """
    description = _normalize_text(description, MAX_STEP_DESCRIPTION)
    if not description:
        raise SolveError("Описание проверки не может быть пустым")

    session = _require_session(problem_id)
    _ensure_open_hypothesis(session, hypothesis_id)
    assert_check_below_limit(session)

    step = {
        "id": _new_id(),
        "hypothesis_id": hypothesis_id,
        "description": description,
        "status": "pending",
        "outcome": "",
        "result": "",
        "created_at": _now_iso(),
        "completed_at": None,
    }
    session.setdefault("steps", []).append(step)
    return _save_session(problem_id, session)


def complete_check(
    problem_id: str,
    step_id: str,
    outcome: str,
    result: str,
) -> dict:
    """Завершает шаг проверки и двигает связанную гипотезу.

    result: "confirmed" | "rejected" | "unknown"
      - confirmed → гипотеза confirmed
      - rejected  → гипотеза rejected
      - unknown   → гипотеза tested
    Свободный шаг (без hypothesis_id) не меняет гипотезу.
    """
    if result not in VALID_STEP_RESULTS:
        raise SolveError(
            f"Недопустимый результат проверки: {result} "
            f"(допустимо: {', '.join(VALID_STEP_RESULTS)})"
        )

    session = _require_session(problem_id)
    step = _find_step(session, step_id)
    if step is None:
        raise SolveError(f"Шаг не найден: {step_id}")
    if step.get("status") != "pending":
        raise SolveError("Шаг уже завершён")

    step["status"] = "done"
    step["outcome"] = _normalize_text(outcome, MAX_OUTCOME_TEXT)
    step["result"] = result
    step["completed_at"] = _now_iso()

    hypothesis_id = step.get("hypothesis_id")
    if hypothesis_id is not None:
        hypothesis = _find_hypothesis(session, hypothesis_id)
        if hypothesis is not None and hypothesis.get("status") not in _TERMINAL_HYPOTHESIS:
            if result == "confirmed":
                hypothesis["status"] = "confirmed"
            elif result == "rejected":
                hypothesis["status"] = "rejected"
            else:  # unknown
                hypothesis["status"] = "tested"
            hypothesis["last_tested_step_id"] = step_id

    return _save_session(problem_id, session)


def finish_diagnostic(problem_id: str, conclusion: str) -> dict:
    """Завершает диагностику: фиксирует conclusion (причину).

    Устанавливает conclusion на сессии. Позволяет перейти к решению.
    """
    session = _require_session(problem_id)
    session["conclusion"] = _normalize_text(conclusion, MAX_HYPOTHESIS_TEXT)
    return _save_session(problem_id, session)


# ── Контекст диагностики для AI ──────────────────────────────────

def get_diagnostic_context(problem: dict, max_steps: int = MAX_RECENT_STEPS) -> dict:
    """Собирает компактный контекст диагностики для AI.

    Включает открытые/отклонённые гипотезы, последние выполненные шаги
    и вывод. Ограничивается лимитами; не передаёт внутренние ID/времена.
    """
    session = problem.get("diagnostic") or {}
    hypotheses = session.get("hypotheses", []) if isinstance(session, dict) else []
    steps = session.get("steps", []) if isinstance(session, dict) else []

    return {
        "open_hypotheses": [
            _compact_hypothesis(h)
            for h in hypotheses
            if h.get("status") in ("open", "tested")
        ][:MAX_OPEN_HYPOTHESES],
        "rejected_hypotheses": [
            _compact_hypothesis(h)
            for h in hypotheses
            if h.get("status") == "rejected"
        ][:MAX_REJECTED_HYPOTHESES],
        "recent_steps": [
            _compact_step(s)
            for s in steps
            if s.get("status") == "done"
        ][-max_steps:],
        "conclusion": session.get("conclusion", "") if isinstance(session, dict) else "",
    }


def _compact_hypothesis(h: dict) -> dict:
    return {
        "text": h.get("text", ""),
        "status": h.get("status", ""),
        "source": h.get("source", ""),
    }


def _compact_step(s: dict) -> dict:
    return {
        "description": s.get("description", ""),
        "result": s.get("result", ""),
    }
