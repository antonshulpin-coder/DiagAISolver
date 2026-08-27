from pathlib import Path
from datetime import datetime

from src.academy import browse_academy
from src.storage import (
    create_record,
    get_all_records,
    get_record,
    update_record,
    delete_record,
    search_records,
)
from src.solve import (
    start_investigation,
    start_solving,
    archive_problem,
    resolve_problem,
    convert_to_knowledge,
    find_similar,
    get_problem_summary,
    SolveError,
    ai_analyze_problem,
    ai_analyze_experience,
    ai_create_plan,
    ai_analyze_result,
    ai_format_knowledge,
)
from src import problems as _problems
from src import storage as _storage
from src import diagnostic as _diagnostic
from src import projects as _projects
from src.ai.provider import NullProvider
from src.ai.types import AIResponse
from src.ai.config import get_ai_provider


def _is_ai_available(provider):
    """Проверяет, доступен ли AI (не NullProvider)."""
    if provider is None:
        return False
    return not isinstance(provider, NullProvider)


def _show_ai_analysis(response, label="AI-АНАЛИЗ"):
    """Показывает AI-анализ в CLI."""
    if not response.success:
        return

    print(f"\n{'=' * 50}")
    print(f"                 {label}")
    print(f"{'=' * 50}")
    print(f"\n{response.content}")

    if response.suggestions:
        print("\nПредложения:")
        for i, s in enumerate(response.suggestions, 1):
            print(f"  {i}. {s}")

    if response.confidence < 0.5:
        print("\n(низкая уверенность — проверьте самостоятельно)")

    print()


def learn():
    browse_academy()


def build():
    print("\nРежим создания проектов пока в разработке.")


# ── SOLVE CLI ─────────────────────────────────────────────────────


def solve():
    solve_flow()


def solve_flow(provider=None):
    if provider is None:
        provider = get_ai_provider()
    try:
        _solve_run(provider)
    except SolveError as exc:
        print(f"\nОшибка: {exc}")
    except _problems.ProblemError as exc:
        print(f"\nОшибка данных: {exc}")
    except _storage.StorageError as exc:
        print(f"\nОшибка хранилища: {exc}")
    except (KeyboardInterrupt, EOFError):
        print("\n\nВозврат в главное меню.")


def _solve_run(provider=None):
    print("\n" + "=" * 50)
    print("                 SOLVE")
    print("=" * 50)

    if _is_ai_available(provider):
        print("[AI подключён]")
    else:
        print("[AI недоступен — продолжаем без AI]")

    print("\n1. Новая проблема")
    print("2. Продолжить существующую")
    print("0. Назад")

    choice = input("\nВыберите: ").strip()

    if choice == "0":
        return
    elif choice == "1":
        _create_new_problem(provider)
    elif choice == "2":
        _continue_existing_problem(provider)
    else:
        print("\nНеверный выбор.")


def _create_new_problem(provider=None):
    print("\n--- Новая проблема ---\n")

    title = input("Название: ").strip()
    if not title:
        print("\nНазвание обязательно.")
        return

    description = input("\nЧто произошло?: ").strip()
    context = input("Контекст: ").strip()
    error_message = input("Сообщение об ошибке (если есть): ").strip()
    tags_raw = input("Теги (через запятую): ").strip()
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []

    problem = _problems.create_problem(
        title=title,
        description=description,
        context=context,
        error_message=error_message,
        tags=tags,
    )

    print(f"\nПроблема создана: {problem['id']}")
    print(f"Статус: {problem['status']}")

    start_investigation(problem["id"])
    print("\nПереведено в investigating. Поиск похожего опыта...\n")

    _investigate_problem(problem, provider)


def _continue_existing_problem(provider=None):
    problems = _problems.get_all_problems()
    active = [p for p in problems if p["status"] in ("investigating", "solving", "failed")]

    if not active:
        print("\nНет проблем для продолжения.")
        return

    print("\n--- Активные проблемы ---")
    for i, p in enumerate(active, start=1):
        status_label = {
            "investigating": "расследование",
            "solving": "в работе",
            "failed": "не решена",
        }.get(p["status"], p["status"])
        print(f"{i}. [{status_label}] {p['title']}")
        if p.get("tags"):
            print(f"   Теги: {', '.join(p['tags'])}")

    choice = input("\nНомер проблемы (Enter — отмена): ").strip()
    if not choice.isdigit() or not 1 <= int(choice) <= len(active):
        print("\nОтмена.")
        return

    problem = active[int(choice) - 1]
    _handle_existing_problem(problem, provider)


def _handle_existing_problem(problem, provider=None):
    status = problem["status"]

    if status == "investigating":
        print(f"\nПроблема: {problem['title']}")
        print("Статус: расследование")
        _investigate_problem(problem, provider)
    elif status == "solving":
        print(f"\nПроблема: {problem['title']}")
        print("Статус: в работе")
        print("1. Продолжить решение")
        print("2. Пометить как решённую")
        print("3. Пометить как нерешённую")
        print("п. Привязать к проекту / отвязать")
        print("0. Назад")

        choice = input("\nВыберите: ").strip()
        if choice == "1":
            _do_solve(problem, provider)
        elif choice == "2":
            result = resolve_problem(problem["id"], cause="", solution="", helped=True)
            print(f"\nСтатус: решена")
            _ask_convert(result, provider)
        elif choice == "3":
            result = resolve_problem(problem["id"], cause="", solution="", helped=False)
            print(f"\nСтатус: не решена")
            _ask_convert(result, provider)
        elif choice in ("п", "П", "p", "P"):
            _bind_problem_flow(problem["id"])
        else:
            print("\nОтмена.")
    elif status == "failed":
        print(f"\nПроблема: {problem['title']}")
        print("Статус: не решена")
        print("1. Повторить попытку")
        print("2. Архивировать")
        print("3. Конвертировать в базу знаний")
        print("п. Привязать к проекту / отвязать")
        print("0. Назад")

        choice = input("\nВыберите: ").strip()
        if choice == "1":
            start_solving(problem["id"])
            print("\nСтатус: solving")
            _do_solve(problem, provider)
        elif choice == "2":
            archive_problem(problem["id"])
            print("\nПроблема архивирована.")
        elif choice == "3":
            record = convert_to_knowledge(problem["id"])
            print(f"\nЗапись сохранена в Базу знаний: {record['id']}")
        elif choice in ("п", "П", "p", "P"):
            _bind_problem_flow(problem["id"])
        else:
            print("\nОтмена.")


def _investigate_problem(problem, provider=None):
    kr, pr = find_similar(problem)

    ai_response = ai_analyze_problem(problem, kr, pr, provider)
    if ai_response.success:
        _show_ai_analysis(ai_response)

    if kr or pr:
        _show_knowledge_results(kr)
        _show_problem_results(pr)
    else:
        print("Ничего не найдено.\n")

    print("---\n")
    print("1. Использовать найденное решение как ориентир")
    print("2. Продолжить самостоятельно")
    print("3. Сохранить проблему и выйти")
    print("d. Диагностика")

    choice = input("\nВыберите: ").strip()

    if choice == "1":
        _use_existing_solution(kr, problem, provider)
    elif choice == "2":
        _continue_solving(problem, provider)
    elif choice in ("d", "D", "д", "Д"):
        conclusion = _diagnostic_loop(problem, provider)
        if conclusion:
            _continue_with_conclusion(problem, provider, conclusion)
        else:
            return
    elif choice == "3":
        print("\nПроблема сохранена. Статус: investigating.")
        return
    else:
        print("\nНеверный выбор. Проблема сохранена со статусом investigating.")
        return


def _use_existing_solution(kr, problem, provider=None):
    if not kr:
        print("\nНет подходящих записей.")
        _continue_solving(problem, provider)
        return

    print("\n--- Найденные записи ---")
    for i, (record, score) in enumerate(kr, start=1):
        print(f"\n{i}. [{score:.1f}] {record.get('title', '(без заголовка)')}")
        print(f"   Тип: {record.get('type', '?')}")
        if record.get("tags"):
            print(f"   Теги: {', '.join(record['tags'])}")
        if record.get("text"):
            preview = record["text"][:150].replace("\n", " ")
            if len(record["text"]) > 150:
                preview += "..."
            print(f"   {preview}")

    pick = input("\nНомер записи (Enter — продолжить самостоятельно): ").strip()
    if pick.isdigit() and 1 <= int(pick) <= len(kr):
        record, _ = kr[int(pick) - 1]
        print(f"\n--- Полная запись: {record.get('title', '(без заголовка)')} ---")
        print(f"Тип: {record.get('type', '?')}")
        if record.get("tags"):
            print(f"Теги: {', '.join(record['tags'])}")
        print(f"\n{record.get('text', '(пусто)')}")

        try_again = input("\nПопробовать это решение? (да/нет): ").strip().lower()
        if try_again in ("да", "y", "yes"):
            start_solving(problem["id"])
            _do_solve(problem, provider)
            return

    _continue_solving(problem, provider)


def _continue_solving(problem, provider=None):
    start_solving(problem["id"])
    print("\nСтатус: solving")
    _do_solve(problem, provider)


def _do_solve(problem, provider=None, cause_default=""):
    ai_plan = ai_create_plan(problem, "", [], provider)
    if ai_plan.success:
        _show_ai_analysis(ai_plan, label="AI-ПЛАН")

    print("\n--- Решение ---\n")
    if cause_default:
        cause = input(f"Причина проблемы [{cause_default}]: ").strip() or cause_default
    else:
        cause = input("Причина проблемы: ").strip()
    solution = input("Что было сделано: ").strip()

    print("\nПомогло ли решение?")
    print("1. Да")
    print("2. Нет")
    print("3. Не знаю")
    helped_choice = input("\nВыберите: ").strip()

    if helped_choice == "1":
        helped = True
    elif helped_choice == "2":
        helped = False
    else:
        helped = None

    result = resolve_problem(
        problem["id"],
        cause=cause,
        solution=solution,
        helped=helped,
    )

    ai_result = ai_analyze_result(result, solution, helped, provider)
    if ai_result.success:
        _show_ai_analysis(ai_result, label="AI-АНАЛИЗ РЕЗУЛЬТАТА")

    _show_summary(result)

    _show_investigation_history(problem)

    if result["status"] in ("solved", "failed"):
        _ask_convert(result, provider)
    elif result["status"] == "solving":
        _ask_retry_or_continue(result, provider)


def _show_summary(problem):
    status_label = {
        "solved": "РЕШЕНА",
        "failed": "НЕ РЕШЕНА",
        "solving": "В РАБОТЕ",
    }.get(problem["status"], problem["status"].upper())

    print("\n" + "=" * 50)
    print("SOLVE ЗАВЕРШЁН")
    print("=" * 50)
    print(f"\nПроблема: {problem['title']}")
    print(f"Статус: {status_label}")
    if problem.get("cause"):
        print(f"Причина: {problem['cause']}")
    if problem.get("solution"):
        print(f"Решение: {problem['solution']}")
    print(f"\nID: {problem['id']}")


def _ask_convert(problem, provider=None):
    print("\nСохранить этот опыт в Базу знаний?")
    print("1. Да")
    print("2. Нет")
    choice = input("\nВыберите: ").strip()

    if choice == "1":
        record = convert_to_knowledge(problem["id"])
        print(f"\nЗапись сохранена в Базу знаний.")
        print(f"ID: {record['id']}")

        ai_knowledge = ai_format_knowledge(problem, provider)
        if ai_knowledge.success and ai_knowledge.suggestions:
            print("\nAI-рекомендации по записи:")
            for i, s in enumerate(ai_knowledge.suggestions, 1):
                print(f"  {i}. {s}")
    else:
        print("\nОпыт не сохранён.")


def _ask_retry_or_continue(problem, provider=None):
    print("\nПроблема осталась в работе.")
    print("1. Продолжить решение")
    print("2. Вернуться в меню")

    choice = input("\nВыберите: ").strip()
    if choice == "1":
        _do_solve(problem, provider)
    else:
        print("\nПроблема сохранена. Статус: solving.")


def _show_knowledge_results(kr):
    if not kr:
        return
    print(f"НАЙДЕНЫ ПОХОЖИЕ РЕШЕНИЯ ({len(kr)}):\n")
    for i, (record, score) in enumerate(kr, start=1):
        print(f"{i}. [{score:.1f}] {record.get('title', '(без заголовка)')}")
        print(f"   Тип: {record.get('type', '?')}")
        if record.get("tags"):
            print(f"   Теги: {', '.join(record['tags'])}")
        if record.get("text"):
            preview = record["text"][:120].replace("\n", " ")
            if len(record["text"]) > 120:
                preview += "..."
            print(f"   {preview}")
        print()


def _show_problem_results(pr):
    if not pr:
        return
    print(f"ПОХОЖИЕ ПРОБЛЕМЫ ({len(pr)}):\n")
    for i, (problem, score) in enumerate(pr, start=1):
        status = problem.get("status", "?")
        print(f"{i}. [{score:.1f}] [{status}] {problem.get('title', '(без заголовка)')}")
        if problem.get("tags"):
            print(f"   Теги: {', '.join(problem['tags'])}")
        if problem.get("solution"):
            print(f"   Решение: {problem['solution'][:100]}")
        print()


# ── ДИАГНОСТИКА (CLI) ─────────────────────────────────────────────

# Максимум выполненных шагов и терминальных гипотез в истории состояния.
_DIAG_HISTORY_LIMIT = 6
_HYP_STATUS_RU = {
    "open": "открыта",
    "tested": "проверена",
    "confirmed": "подтверждена",
    "rejected": "отклонена",
}


def _show_diagnostic_state(problem):
    """Показывает текущее состояние диагностики."""
    session = problem.get("diagnostic")
    if not isinstance(session, dict):
        print("\nДиагностика не открыта.")
        return

    print("\n--- Диагностика ---")
    open_h = [h for h in session.get("hypotheses", []) if h.get("status") == "open"]
    if open_h:
        print("Гипотезы:")
        for h in open_h:
            source = "AI" if h.get("source") == "ai" else "вручную"
            print(f"  [{h['id']}] {h['text']} ({source})")
    else:
        print("Гипотез нет.")

    pending = [s for s in session.get("steps", []) if s.get("status") == "pending"]
    if pending:
        print("Ожидают проверки:")
        for s in pending:
            print(f"  [{s['id']}] {s['description']}")

    done = [s for s in session.get("steps", []) if s.get("status") == "done"]
    if done:
        shown = done[:_DIAG_HISTORY_LIMIT]
        print("История проверок:")
        for s in shown:
            hyp = next(
                (h for h in session.get("hypotheses", [])
                 if h.get("id") == s.get("hypothesis_id")),
                None,
            )
            status_ru = _HYP_STATUS_RU.get(hyp.get("status"), "—") if hyp else "—"
            hyp_part = f" → {hyp['text']} ({status_ru})" if hyp else ""
            detail = s.get("outcome") or s.get("result", "")
            step_part = f" → {detail}" if detail else ""
            print(f"  [{s['id']}] {s.get('description', '')}{step_part}{hyp_part}")
        if len(done) > _DIAG_HISTORY_LIMIT:
            print(f"  … и ещё {len(done) - _DIAG_HISTORY_LIMIT} шаг(ов)")

    terminal = [h for h in session.get("hypotheses", [])
                if h.get("status") in ("confirmed", "rejected")]
    if terminal:
        shown = terminal[:_DIAG_HISTORY_LIMIT]
        print("Проверено/Отклонено:")
        for h in shown:
            status_ru = _HYP_STATUS_RU.get(h.get("status"), h.get("status"))
            print(f"  [{h['id']}] {h['text']} — {status_ru}")
        if len(terminal) > _DIAG_HISTORY_LIMIT:
            print(f"  … и ещё {len(terminal) - _DIAG_HISTORY_LIMIT} гипотез(ы)")

    conclusion = session.get("conclusion", "")
    if conclusion:
        print(f"Вывод: {conclusion}")
    print()


def _format_investigation_history(problem) -> list[str]:
    """Форматирует секцию «Как расследовали» для отчёта solve.

    Компактный консольный отчёт по полной сессии problem["diagnostic"]:
    вывод, подтверждённая причина, выполненные шаги, отклонённые гипотезы.
    Без диагностики/с пустой сессией возвращает пустой список (секция не нужна).
    """
    session = problem.get("diagnostic")
    if not isinstance(session, dict):
        return []
    hypotheses = session.get("hypotheses") or []
    steps = session.get("steps") or []
    conclusion = session.get("conclusion") or ""
    if not hypotheses and not steps and not conclusion:
        return []

    lines = ["\n--- Как расследовали ---"]

    if conclusion:
        lines.append(f"Вывод: {conclusion}")

    confirmed = [h for h in hypotheses if h.get("status") == "confirmed"]
    if confirmed:
        lines.append("Причина (подтверждена):")
        for h in confirmed:
            lines.append(f"  [{h['id']}] {h['text']}")

    done = [s for s in steps if s.get("status") == "done"]
    if done:
        shown = done[:_DIAG_HISTORY_LIMIT]
        lines.append("Выполненные шаги:")
        for s in shown:
            hyp = next(
                (h for h in hypotheses if h.get("id") == s.get("hypothesis_id")),
                None,
            )
            status_ru = _HYP_STATUS_RU.get(hyp.get("status"), "—") if hyp else "—"
            hyp_part = f" → {hyp['text']} ({status_ru})" if hyp else ""
            detail = s.get("outcome") or s.get("result", "")
            step_part = f" → {detail}" if detail else ""
            lines.append(f"  [{s['id']}] {s.get('description', '')}{step_part}{hyp_part}")
        if len(done) > _DIAG_HISTORY_LIMIT:
            lines.append(f"  … и ещё {len(done) - _DIAG_HISTORY_LIMIT} шаг(ов)")

    rejected = [h for h in hypotheses if h.get("status") == "rejected"]
    if rejected:
        lines.append("Отклонённые гипотезы:")
        for h in rejected[:_DIAG_HISTORY_LIMIT]:
            lines.append(f"  [{h['id']}] {h['text']}")
        if len(rejected) > _DIAG_HISTORY_LIMIT:
            lines.append(f"  … и ещё {len(rejected) - _DIAG_HISTORY_LIMIT} гипотез(ы)")

    return lines


def _show_investigation_history(problem):
    """Печатает секцию «Как расследовали» в отчёт solve (если есть диагностика)."""
    for line in _format_investigation_history(problem):
        print(line)


def _diagnostic_manual_hypotheses():
    """Ручной ввод гипотез (по одной на строку, пустая строка — конец)."""
    print("\nВведите гипотезы (по одной на строку, пустая строка — конец):")
    texts = []
    while True:
        line = input().strip()
        if not line:
            break
        texts.append(line)
    return [{"text": t, "source": "user"} for t in texts]


def _diagnostic_add_hypotheses(problem, provider):
    """Добавляет гипотезы: через AI (если доступен) или вручную."""
    selected = None
    if _is_ai_available(provider):
        ctx = _diagnostic.get_diagnostic_context(problem)
        response = provider.suggest_hypotheses(problem, ctx)
        if response.success and response.suggestions:
            print(f"\n{response.content}")
            print("\nПредложенные гипотезы:")
            for i, s in enumerate(response.suggestions, 1):
                print(f"  {i}. {s}")
            print("\nПринять все [y], выбрать номера (через запятую), отказ [n]:")
            choice = input("Выберите: ").strip().lower()
            if choice == "y":
                selected = [{"text": s, "source": "ai"} for s in response.suggestions]
            elif choice and choice not in ("n", "no", "нет"):
                nums = []
                for part in choice.replace(";", ",").split(","):
                    part = part.strip()
                    if part.isdigit() and 1 <= int(part) <= len(response.suggestions):
                        nums.append(int(part))
                if nums:
                    selected = [
                        {"text": response.suggestions[i - 1], "source": "ai"}
                        for i in nums
                    ]

    if selected is None:
        selected = _diagnostic_manual_hypotheses()

    if not selected:
        print("\nГипотезы не добавлены.")
        return

    try:
        _diagnostic.add_hypotheses(problem["id"], selected)
    except SolveError as exc:
        print(f"\nОшибка: {exc}")


def _diagnostic_add_check(problem, provider):
    """Добавляет шаг проверки: через AI (если доступен) или вручную."""
    description = None
    if _is_ai_available(provider):
        ctx = _diagnostic.get_diagnostic_context(problem)
        response = provider.suggest_next_check(problem, ctx)
        if response.success and response.content:
            print(f"\nРекомендуемый шаг: {response.content}")
            take = input("Взять этот шаг? (y/n): ").strip().lower()
            if take == "y":
                description = response.content

    if description is None:
        description = input("\nОписание шага: ").strip()
        if not description:
            print("\nШаг не добавлен (пустое описание).")
            return

    try:
        session = _diagnostic.add_check(problem["id"], None, description)
    except SolveError as exc:
        print(f"\nОшибка: {exc}")
        return

    done = input("\nВыполнили уже этот шаг? (y/n): ").strip().lower()
    if done == "y":
        new_step_id = session["steps"][-1]["id"]
        fresh = _problems.get_problem(problem["id"])
        _diagnostic_complete_step(fresh, step_id=new_step_id)


def _diagnostic_complete_step(problem, step_id=None):
    """Завершает шаг проверки и показывает затронутые гипотезы.

    step_id=None — интерактивный выбор из pending-шагов.
    """
    session = problem.get("diagnostic") or {}
    pending = [s for s in session.get("steps", []) if s.get("status") == "pending"]
    if not pending:
        print("\nНет шагов, ожидающих проверки.")
        return

    if step_id is None:
        print("\n--- Шаги, ожидающие проверки ---")
        for s in pending:
            print(f"  [{s['id']}] {s['description']}")
        step_id = input("\nID шага: ").strip()
    step = next((s for s in pending if s["id"] == step_id), None)
    if step is None:
        print("\nШаг не найден.")
        return

    print("\nРезультат (confirmed / rejected / unknown):")
    result = input("Результат: ").strip().lower()
    if result not in _diagnostic.VALID_STEP_RESULTS:
        print(f"\nНедопустимый результат: {result} "
              f"(допустимо: confirmed, rejected, unknown).")
        return
    outcome = input("Краткий результат: ").strip()

    try:
        session = _diagnostic.complete_check(problem["id"], step_id, outcome, result)
    except SolveError as exc:
        print(f"\nОшибка: {exc}")
        return

    print("\nЗатронутые гипотезы:")
    hyp_id = step.get("hypothesis_id")
    if hyp_id:
        hypothesis = next(
            (h for h in session.get("hypotheses", []) if h.get("id") == hyp_id),
            None,
        )
        if hypothesis:
            print(f"  [{hypothesis['id']}] {hypothesis['text']} → {hypothesis['status']}")
        else:
            print("  (гипотеза не найдена)")
    else:
        print("  (свободный шаг — гипотезы не затронуты)")


def _confirm_cause(problem):
    """Подтверждает причину: одной гипотезой-одним нажатием, выбором или вручную."""
    session = _diagnostic.get_diagnostic(problem["id"]) or {}
    confirmed = [
        h for h in session.get("hypotheses", [])
        if h.get("status") == "confirmed"
    ]
    if len(confirmed) == 1:
        text = confirmed[0]["text"]
        print(f"\nПодтверждённая гипотеза: {text}")
        accept = input("Принять этой причиной? (Enter/y — да): ").strip().lower()
        if accept in ("", "y", "yes", "д", "да"):
            return text
    elif len(confirmed) > 1:
        print("\nПодтверждённые гипотезы — выбрать причину:")
        for i, h in enumerate(confirmed, 1):
            print(f"  {i}. {h['text']}")
        choice = input("Номер: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(confirmed):
            return confirmed[int(choice) - 1]["text"]

    default = session.get("conclusion", "") or ""
    if default:
        print(f"\nТекущая причина: {default}")
    conclusion = input("Причина (Enter — использовать текущую): ").strip() or default
    return conclusion or None


def _diagnostic_ai_hint(problem, provider):
    """Подсказка «что дальше»: следующий шаг при застрявшей сессии."""
    session = problem.get("diagnostic") or {}
    open_count = sum(
        h.get("status") in ("open", "tested")
        for h in session.get("hypotheses", [])
    )
    pending = any(s.get("status") == "pending" for s in session.get("steps", []))
    if open_count == 0 or pending:
        print("\nПодсказка недоступна сейчас.")
        return
    if not _is_ai_available(provider):
        print("\nПодсказка недоступна сейчас (AI не настроен).")
        return

    try:
        ctx = _diagnostic.get_diagnostic_context(problem)
        response = provider.suggest_next_check(problem, ctx)
    except Exception:
        print("\nНе удалось получить подсказку.")
        return
    if not response.success or not response.content:
        print("\nНе удалось получить подсказку.")
        return

    print(f"\nПодсказка «что дальше»: {response.content}")
    take = input("Взять этот шаг? (y/n): ").strip().lower()
    if take != "y":
        return

    try:
        session = _diagnostic.add_check(problem["id"], None, response.content)
    except SolveError as exc:
        print(f"\nОшибка: {exc}")
        return

    done = input("\nВыполнили уже этот шаг? (y/n): ").strip().lower()
    if done == "y":
        new_step_id = session["steps"][-1]["id"]
        fresh = _problems.get_problem(problem["id"])
        _diagnostic_complete_step(fresh, step_id=new_step_id)


def _diagnostic_loop(problem, provider=None):
    """Цикл диагностики. Возвращает conclusion при завершении, иначе None."""
    _diagnostic.open_diagnostic(problem["id"])

    while True:
        problem = _problems.get_problem(problem["id"])
        if problem is None:
            print("\nОшибка: проблема не найдена.")
            return None
        _show_diagnostic_state(problem)

        print("1. Предложить/добавить гипотезы")
        print("2. Добавить шаг проверки")
        print("3. Отметить шаг выполненным")
        print("4. Подтвердить причину (завершить)")
        print("5. Подсказка «что дальше»")
        print("0. Выйти (прогресс сохраняется)")
        choice = input("\nВыберите: ").strip()

        if choice == "0":
            print("\nПрогресс сохранён. Статус: investigating.")
            return None
        elif choice == "1":
            _diagnostic_add_hypotheses(problem, provider)
        elif choice == "2":
            _diagnostic_add_check(problem, provider)
        elif choice == "3":
            _diagnostic_complete_step(problem)
        elif choice == "4":
            conclusion = _confirm_cause(problem)
            if not conclusion:
                print("\nПричина не указана.")
                continue
            try:
                _diagnostic.finish_diagnostic(problem["id"], conclusion)
            except SolveError as exc:
                print(f"\nОшибка: {exc}")
                continue
            return conclusion
        elif choice == "5":
            _diagnostic_ai_hint(problem, provider)
        else:
            print("\nНеверный выбор.")


def _continue_with_conclusion(problem, provider, conclusion):
    """Переход к решению с предзаполненной причиной из диагностики."""
    start_solving(problem["id"])
    print("\nСтатус: solving")
    _do_solve(problem, provider, cause_default=conclusion)


# ── БАЗА ЗНАНИЙ ───────────────────────────────────────────────────

def _input_record_details():
    print("\n--- Новая запись ---")

    record_type = input("Тип (note/bookmark/idea/problem): ").strip()
    if not record_type:
        record_type = "note"

    title = input("Заголовок: ").strip()

    print("Текст (пустая строка — конец ввода):")
    lines = []
    while True:
        line = input()
        if line == "":
            break
        lines.append(line)
    text = "\n".join(lines)

    tags_raw = input("Теги (через запятую, или пусто): ").strip()
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []

    return record_type, title, text, tags


def _show_record(record, index=None):
    prefix = f"{index}. " if index is not None else ""
    print(f"\n{prefix}[{record['type']}] {record['title'] or '(без заголовка)'}")
    print(f"    ID: {record['id']}  |  Создано: {record['created_at'][:10]}")
    if record["tags"]:
        print(f"    Теги: {', '.join(record['tags'])}")
    if record["text"]:
        preview = record["text"][:120].replace("\n", " ")
        if len(record["text"]) > 120:
            preview += "..."
        print(f"    {preview}")


def _show_record_full(record):
    print(f"\n{'=' * 50}")
    print(f"Тип: {record['type']}")
    print(f"Заголовок: {record['title'] or '(без заголовка)'}")
    print(f"ID: {record['id']}")
    print(f"Создано: {record['created_at']}")
    if record["tags"]:
        print(f"Теги: {', '.join(record['tags'])}")
    print(f"{'=' * 50}")
    print(record["text"] if record["text"] else "(пусто)")
    print(f"{'=' * 50}")


def _pick_record():
    records = get_all_records()
    if not records:
        print("\nЗаписей пока нет.")
        return None

    print("\n--- Выберите запись ---")
    for i, r in enumerate(records, start=1):
        _show_record(r, index=i)

    choice = input("\nНомер: ").strip()
    if not choice.isdigit() or not 1 <= int(choice) <= len(records):
        print("\nНеверный номер.")
        return None

    return records[int(choice) - 1]


def _add():
    record_type, title, text, tags = _input_record_details()
    if not title and not text:
        print("\nЗапись не может быть пустой.")
        return
    record = create_record(title=title, text=text, record_type=record_type, tags=tags)
    print(f"\nЗапись создана: {record['id']}")


def _view():
    records = get_all_records()
    if not records:
        print("\nЗаписей пока нет.")
        return
    print("\n--- Все записи ---")
    for i, r in enumerate(records, start=1):
        _show_record(r, index=i)


def _search():
    query = input("\nПоисковый запрос: ").strip()
    if not query:
        print("\nЗапрос не может быть пустым.")
        return
    results = search_records(query)
    if not results:
        print("\nНичего не найдено.")
        return
    print(f"\n--- Результаты ({len(results)}) ---")
    for i, r in enumerate(results, start=1):
        _show_record(r, index=i)


def _delete():
    record = _pick_record()
    if record is None:
        return
    _show_record_full(record)
    confirm = input("\nУдалить? (да/нет): ").strip().lower()
    if confirm in ("да", "y", "yes"):
        delete_record(record["id"])
        print("\nЗапись удалена.")
    else:
        print("\nУдаление отменено.")


def _edit():
    record = _pick_record()
    if record is None:
        return
    _show_record_full(record)

    print("\n--- Редактирование (Enter — оставить как есть) ---")

    new_type = input(f"Тип [{record['type']}]: ").strip()
    new_title = input(f"Заголовок [{record['title']}]: ").strip()
    new_tags_raw = input(f"Теги [{', '.join(record['tags'])}]: ").strip()

    print("Текст (пустая строка — конец ввода, Enter без текста — оставить как есть):")
    lines = []
    first = True
    while True:
        line = input()
        if line == "" and first:
            break
        first = False
        if line == "":
            break
        lines.append(line)
    new_text = "\n".join(lines) if lines else None

    fields = {}
    if new_type:
        fields["type"] = new_type
    if new_title:
        fields["title"] = new_title
    if new_tags_raw is not None:
        fields["tags"] = [t.strip() for t in new_tags_raw.split(",") if t.strip()]
    if new_text is not None:
        fields["text"] = new_text

    if fields:
        update_record(record["id"], **fields)
        print("\nЗапись обновлена.")
    else:
        print("\nИзменений нет.")


def knowledge():
    actions = {
        "1": _add,
        "2": _view,
        "3": _search,
        "4": _delete,
        "5": _edit,
    }

    while True:
        print("\n====== БАЗА ЗНАНИЙ ======")
        print("1. Добавить запись")
        print("2. Просмотреть записи")
        print("3. Поиск")
        print("4. Удалить запись")
        print("5. Редактировать запись")
        print("0. Назад")

        choice = input("\nВыберите пункт: ").strip()

        if choice == "0":
            break

        action = actions.get(choice)
        if action:
            action()
            input("\nНажмите Enter...")
        else:
            print("\nНеверный выбор.")
            input("\nНажмите Enter...")


# ── ЭКСПОРТ И БЭКАП (только чтение хранилища) ─────────────────────

EXPORT_DIR = Path(__file__).resolve().parents[1] / "export"
BACKUP_DIR = Path(__file__).resolve().parents[1] / "backup"


def _problems_to_markdown(problems) -> str:
    """Формирует markdown-представление всех проблем (только чтение).

    Для каждой проблемы: статус, описание, решение (если есть), история
    расследования (единый формат с отчётом solve через
    _format_investigation_history). Отсутствующие секции пропускаются.
    """
    chunks = []
    for p in problems:
        title = p.get("title") or "(без названия)"
        status = p.get("status") or "?"
        lines = [f"## {title}  [{status}]", f"ID: {p.get('id', '?')}"]
        description = (p.get("description") or "").strip()
        if description:
            lines.append("")
            lines.append(description)
        solution = (p.get("solution") or "").strip()
        if solution:
            lines.append("")
            lines.append("**Решение:**")
            lines.append(solution)
        history = _format_investigation_history(p)
        if history:
            lines.append("")
            body = [history[0].lstrip("\n")] + history[1:]
            for line in body:
                if line.strip():
                    lines.append(line)
        chunks.append("\n".join(lines))
    return "\n\n".join(chunks)


def _export_markdown(problems, out_dir=None):
    """Пишет markdown-экспорт в <out_dir>/problems_<дата>.md.

    Возвращает (путь, количество записей).
    """
    out_dir = Path(out_dir) if out_dir else EXPORT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    path = out_dir / f"problems_{date_str}.md"
    path.write_text(_problems_to_markdown(problems), encoding="utf-8")
    return path, len(problems)


def _export_backup(out_dir=None):
    """Копирует data/problems.json в <out_dir>/problems_<дата-время>.json.

    Возвращает путь. Имя с timestamp, чтобы не перезаписывать прошлые бэкапы.
    """
    out_dir = Path(out_dir) if out_dir else BACKUP_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    dest = out_dir / f"problems_{ts}.json"
    source = _problems.DATA_FILE
    if source.exists():
        dest.write_bytes(source.read_bytes())
    else:
        dest.write_text("[]", encoding="utf-8")
    return dest


def _export_menu():
    print("\n====== ЭКСПОРТ И БЭКАП ======")
    print("1. Экспорт в Markdown (export/)")
    print("2. Бэкап JSON (backup/)")
    print("3. Всё (markdown + backup)")
    print("0. Назад")

    choice = input("\nВыберите пункт: ").strip()

    problems = _problems.load_problems()
    count = len(problems)

    if choice == "1":
        path = _export_markdown(problems)[0]
        print(f"\nЭкспорт: {path} ({count} записей)")
    elif choice == "2":
        path = _export_backup()
        print(f"\nБэкап: {path} ({count} записей)")
    elif choice == "3":
        path = _export_markdown(problems)[0]
        bk_path = _export_backup()
        print(f"\nЭкспорт: {path} ({count} записей)")
        print(f"Бэкап: {bk_path}")
    elif choice == "0":
        return
    else:
        print("\nНеверный выбор.")


def export():
    """Команда экспорта: markdown-экспорт и/или бэкап (только чтение)."""
    try:
        _export_menu()
    except _problems.ProblemError as exc:
        print(f"\nОшибка данных: {exc}")
    except OSError as exc:
        print(f"\nОшибка файла: {exc}")
    except (KeyboardInterrupt, EOFError):
        print("\n\nВозврат в главное меню.")


# ── ПРОЕКТЫ (ядерное хранилище, ступень v1.5.0) ─────────────────


def _pick_project(prompt="\nНомер проекта (Enter — отмена): "):
    """Выводит проекты, возвращает (выбранный, список) или (None, [])."""
    projects = _projects.get_all_projects()
    for i, pr in enumerate(projects, start=1):
        status = "закрыт" if pr["status"] == "done" else "активен"
        print(f"{i}. {pr['name']} [{status}]")
    if not projects:
        print("Проектов нет.")
        return None, projects
    choice = input(prompt).strip()
    if not choice.isdigit() or not 1 <= int(choice) <= len(projects):
        print("\nОтмена.")
        return None, projects
    return projects[int(choice) - 1], projects


def _bind_problem_flow(problem_id):
    """Выбор проекта (или «без проекта») для привязки/отвязки проблемы."""
    projects = _projects.get_all_projects()
    print("\n--- Куда привязать проблему ---")
    if projects:
        for i, pr in enumerate(projects, start=1):
            status = "закрыт" if pr["status"] == "done" else "активен"
            print(f"{i}. {pr['name']} [{status}]")
    else:
        print("Проектов пока нет.")
    print("0. Без проекта (отвязать)")
    print("Enter. Назад")

    choice = input("\nВыберите: ").strip()
    if choice == "":
        return
    if choice == "0":
        result = _projects.bind_problem(problem_id, None)
        if result is not None:
            print("\nПроблема отвязана от проекта.")
        else:
            print("\nПроблема не найдена.")
        return
    if choice.isdigit() and 1 <= int(choice) <= len(projects):
        pr = projects[int(choice) - 1]
        result = _projects.bind_problem(problem_id, pr["id"])
        if result is not None:
            print(f"\nПроблема привязана к проекту «{pr['name']}».")
        else:
            print("\nПроблема не найдена.")
        return
    print("\nНеверный выбор.")


def _create_project():
    print("\n--- Новый проект ---")
    name = input("Название: ").strip()
    if not name:
        print("\nНазвание обязательно.")
        return
    goal = input("Цель: ").strip()
    project = _projects.create_project(name, goal)
    print(f"\nПроект создан: {project['id']}")
    print(f"Статус: {project['status']}")


def _list_projects():
    print("\n--- Проекты ---")
    projects = _projects.get_all_projects()
    if not projects:
        print("Пока нет проектов.")
        return
    project_map = {p["id"]: p for p in projects}
    problems = _problems.get_all_problems()
    counts = {}
    for p in problems:
        pid = p.get("project_id")
        if pid in project_map:
            counts[pid] = counts.get(pid, 0) + 1
    for pr in projects:
        status = "закрыт" if pr["status"] == "done" else "активен"
        count = counts.get(pr["id"], 0)
        print(f"{pr['name']} [{status}] — подзадач: {count}")
        if pr["goal"]:
            print(f"   Цель: {pr['goal']}")


def _open_project():
    project, _ = _pick_project("\n\nНомер проекта (Enter — отмена): ")
    if project is None:
        return
    problems = _projects.problems_of_project(project["id"])
    solved = sum(1 for p in problems if p["status"] == "solved")
    status = "закрыт" if project["status"] == "done" else "активен"
    print(f"\nПроект: {project['name']} [{status}]")
    print(f"Цель: {project['goal'] or '(не указана)'}")
    print(f"Подзадач: {len(problems)} (решено: {solved})")
    print("\n(Экран проекта — в v1.5.1.)")


def _rename_project():
    project, _ = _pick_project()
    if project is None:
        return
    print(f"\nТекущее название: {project['name']}")
    print(f"Текущая цель: {project['goal']}")
    new_name = input("Новое название (Enter — не менять): ").strip()
    new_goal = input("Новая цель (Enter — не менять): ").strip()
    updated = _projects.rename_project(
        project["id"],
        name=new_name if new_name else None,
        goal=new_goal if new_goal else None,
    )
    if updated is not None:
        print("\nПроект обновлён.")
    else:
        print("\nПроект не найден.")


def _toggle_project():
    project, _ = _pick_project()
    if project is None:
        return
    if project["status"] == "done":
        _projects.reopen_project(project["id"])
        print("\nПроект переоткрыт (active).")
    else:
        _projects.close_project(project["id"])
        print("\nПроект закрыт (done).")


def _delete_project():
    project, _ = _pick_project()
    if project is None:
        return
    count = _projects.count_project_problems(project["id"])
    if count:
        confirm = input(
            f"\nК проекту привязано {count} проблем. Они будут ОТВЯЗАНЫ (не удалены). Продолжить? (y/n): "
        ).strip()
        confirm = confirm.lower()
        if confirm not in ("y", "д", "yes"):
            print("\nОтменено.")
            return
        _projects.unbind_all_problems(project["id"])
    _projects.delete_project(project["id"])
    print("\nПроект удалён.")


def _bind_unbind_flow():
    problems = _problems.get_all_problems()
    if not problems:
        print("\nНет проблем для привязки.")
        return
    print("\n--- Проблемы ---")
    for i, p in enumerate(problems, start=1):
        print(f"{i}. [{p['status']}] {p['title']}")
    choice = input("\nНомер проблемы (Enter — отмена): ").strip()
    if not choice.isdigit() or not 1 <= int(choice) <= len(problems):
        print("\nОтмена.")
        return
    _bind_problem_flow(problems[int(choice) - 1]["id"])


def _filter_problems():
    print("\n--- Проблемы по проекту ---")
    print("1. По проекту")
    print("2. Без проекта")
    print("3. Все")
    print("0. Назад")
    choice = input("\nВыберите: ").strip()
    if choice == "0":
        return

    problems = _problems.get_all_problems()
    project_map = {p["id"]: p["name"] for p in _projects.get_all_projects()}

    if choice == "1":
        project, _ = _pick_project()
        if project is None:
            return
        matched = [p for p in problems if p.get("project_id") == project["id"]]
        label = project["name"]
    elif choice == "2":
        matched = [p for p in problems if not p.get("project_id")]
        label = "без проекта"
    else:
        matched = problems
        label = "все"

    print(f"\n--- Проблемы ({label}): {len(matched)} ---")
    for i, p in enumerate(matched, start=1):
        proj = project_map.get(p.get("project_id"))
        proj_txt = f" [проект: {proj}]" if proj else ""
        print(f"{i}. [{p['status']}] {p['title']}{proj_txt}")


def _projects_loop():
    while True:
        print("\n====== ПРОЕКТЫ ======")
        print("1. Создать проект")
        print("2. Список проектов")
        print("3. Открыть проект")
        print("4. Переименовать")
        print("5. Закрыть / переоткрыть")
        print("6. Удалить проект")
        print("7. Привязать / отвязать проблему")
        print("8. Проблемы проекта (фильтр)")
        print("0. Назад")

        choice = input("\nВыберите: ").strip()
        if choice == "0":
            return
        elif choice == "1":
            _create_project()
        elif choice == "2":
            _list_projects()
        elif choice == "3":
            _open_project()
        elif choice == "4":
            _rename_project()
        elif choice == "5":
            _toggle_project()
        elif choice == "6":
            _delete_project()
        elif choice == "7":
            _bind_unbind_flow()
        elif choice == "8":
            _filter_problems()
        else:
            print("\nНеверный выбор.")


def projects():
    """Команда «Проекты»: CRUD проектов, привязка проблем, фильтр списка."""
    try:
        _projects_loop()
    except _projects.ProjectError as exc:
        print(f"\nОшибка данных: {exc}")
    except _problems.ProblemError as exc:
        print(f"\nОшибка данных: {exc}")
    except (KeyboardInterrupt, EOFError):
        print("\n\nВозврат в главное меню.")
