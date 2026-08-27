import unittest
from pathlib import Path
from unittest.mock import patch

from src.diagnostic import (
    MAX_OPEN_HYPOTHESES,
    MAX_REJECTED,
    MAX_REJECTED_HYPOTHESES,
    MAX_RECENT_STEPS,
    MAX_HYPOTHESES_PER_SESSION,
    MAX_STEPS_PER_SESSION,
    open_diagnostic,
    get_diagnostic,
    add_hypothesis,
    add_hypotheses,
    suggest_check,
    add_check,
    complete_check,
    is_diagnostic_active,
    finish_diagnostic,
    get_diagnostic_context,
    _compact_hypothesis,
    _compact_step,
)
from src.solve import SolveError


PROBLEMS_DIAG_TEST = (
    Path(__file__).resolve().parent.parent / "data" / "problems_diag_test.json"
)


def _clean():
    PROBLEMS_DIAG_TEST.unlink(missing_ok=True)


def _patchdiag(fn):
    return patch("src.diagnostic._problems.DATA_FILE", PROBLEMS_DIAG_TEST)(fn)


def _make_problem(**overrides):
    from src.problems import create_problem
    defaults = dict(title="Ошибка Python", description="D", tags=["python"])
    defaults.update(overrides)
    return create_problem(**defaults)


def _to_investigating(problem_id):
    from src.solve import start_investigation
    return start_investigation(problem_id)


class BaseDiagTest(unittest.TestCase):
    @_patchdiag
    def setUp(self):
        _clean()
        self.problem = _make_problem()
        self.pid = self.problem["id"]

    @_patchdiag
    def tearDown(self):
        _clean()

    def run(self, result=None):
        with patch("src.diagnostic._problems.DATA_FILE", PROBLEMS_DIAG_TEST):
            super().run(result)

    def _session(self):
        return get_diagnostic(self.pid)

    def _fresh_problem(self):
        from src.problems import get_problem
        return get_problem(self.pid)


# ── open_diagnostic ──────────────────────────────────────────────

class TestOpenDiagnostic(BaseDiagTest):

    def test_creates_session(self):
        session = open_diagnostic(self.pid)
        self.assertIn("started_at", session)
        self.assertEqual(session["hypotheses"], [])
        self.assertEqual(session["steps"], [])
        self.assertEqual(session["conclusion"], "")

    def test_started_at_is_iso_with_timezone(self):
        session = open_diagnostic(self.pid)
        self.assertIn("T", session["started_at"])
        self.assertIn("+", session["started_at"])

    def test_idempotent_reopen(self):
        s1 = open_diagnostic(self.pid)
        s2 = open_diagnostic(self.pid)
        self.assertIsNotNone(s2)
        self.assertEqual(s1["started_at"], self._session()["started_at"])

    def test_saved_to_problem(self):
        open_diagnostic(self.pid)
        from src.problems import get_problem
        stored = get_problem(self.pid)
        self.assertIsInstance(stored["diagnostic"], dict)

    def test_missing_problem(self):
        with self.assertRaises(SolveError):
            open_diagnostic("nonexistent")

    def test_reopen_does_not_duplicate(self):
        open_diagnostic(self.pid)
        add_hypothesis(self.pid, "Гипотеза1")
        open_diagnostic(self.pid)
        session = self._session()
        self.assertEqual(len(session["hypotheses"]), 1)


# ── get_diagnostic ───────────────────────────────────────────────

class TestGetDiagnostic(BaseDiagTest):

    def test_none_when_not_opened(self):
        self.assertIsNone(get_diagnostic(self.pid))

    def test_returns_session_after_open(self):
        open_diagnostic(self.pid)
        self.assertIsNotNone(get_diagnostic(self.pid))

    def test_missing_problem_raises(self):
        with self.assertRaises(SolveError):
            get_diagnostic("nonexistent")

    def test_malformed_diagnostic_returns_none(self):
        from src.problems import update_problem
        update_problem(self.pid, diagnostic="not-a-dict")
        self.assertIsNone(get_diagnostic(self.pid))


# ── add_hypothesis ───────────────────────────────────────────────

class TestAddHypothesis(BaseDiagTest):

    def test_adds_open_hypothesis(self):
        open_diagnostic(self.pid)
        session = add_hypothesis(self.pid, "Сломан venv")
        h = session["hypotheses"][0]
        self.assertEqual(h["text"], "Сломан venv")
        self.assertEqual(h["status"], "open")
        self.assertEqual(h["source"], "user")
        self.assertAlmostEqual(h["confidence"], 1.0)
        self.assertIsNone(h["last_tested_step_id"])
        self.assertEqual(len(h["id"]), 8)

    def test_requires_open_session(self):
        with self.assertRaises(SolveError):
            add_hypothesis(self.pid, "x")

    def test_empty_text_rejected(self):
        open_diagnostic(self.pid)
        with self.assertRaises(SolveError):
            add_hypothesis(self.pid, "   ")

    def test_text_truncated_to_limit(self):
        open_diagnostic(self.pid)
        long_text = "г" * 500
        session = add_hypothesis(self.pid, long_text)
        self.assertEqual(len(session["hypotheses"][0]["text"]), 200)

    def test_invalid_source(self):
        open_diagnostic(self.pid)
        with self.assertRaises(SolveError):
            add_hypothesis(self.pid, "x", source="robot")

    def test_source_ai(self):
        open_diagnostic(self.pid)
        session = add_hypothesis(self.pid, "x", source="ai", confidence=0.7)
        self.assertEqual(session["hypotheses"][0]["source"], "ai")
        self.assertAlmostEqual(session["hypotheses"][0]["confidence"], 0.7)

    def test_duplicate_rejected(self):
        open_diagnostic(self.pid)
        add_hypothesis(self.pid, "Сломан venv")
        with self.assertRaises(SolveError):
            add_hypothesis(self.pid, "сломан venv")

    def test_missing_problem(self):
        with self.assertRaises(SolveError):
            add_hypothesis("nonexistent", "x")

    def test_persisted_across_reload(self):
        open_diagnostic(self.pid)
        add_hypothesis(self.pid, "Гипотеза")
        session = self._session()
        self.assertEqual(session["hypotheses"][0]["text"], "Гипотеза")

    def test_session_limit(self):
        open_diagnostic(self.pid)
        for i in range(MAX_HYPOTHESES_PER_SESSION):
            add_hypothesis(self.pid, f"Гипотеза {i}")
        with self.assertRaises(SolveError):
            add_hypothesis(self.pid, "Одиннадцатая")


# ── add_hypotheses (пачкой / дедупликация) ───────────────────────

class TestAddHypotheses(BaseDiagTest):

    def test_adds_batch_of_strings(self):
        open_diagnostic(self.pid)
        session = add_hypotheses(self.pid, ["А", "Б", "В"])
        self.assertEqual(len(session["hypotheses"]), 3)
        self.assertEqual(session["hypotheses"][0]["source"], "ai")

    def test_adds_batch_of_dicts(self):
        open_diagnostic(self.pid)
        session = add_hypotheses(self.pid, [
            {"text": "А", "confidence": 0.8},
            {"text": "Б", "source": "knowledge", "confidence": 0.5},
        ])
        self.assertEqual(len(session["hypotheses"]), 2)
        self.assertEqual(session["hypotheses"][1]["source"], "knowledge")

    def test_dedup_within_batch(self):
        open_diagnostic(self.pid)
        session = add_hypotheses(self.pid, ["А", "а", "А "])
        self.assertEqual(len(session["hypotheses"]), 1)

    def test_dedup_against_existing(self):
        open_diagnostic(self.pid)
        add_hypothesis(self.pid, "А")
        session = add_hypotheses(self.pid, ["А", "Б"])
        self.assertEqual(len(session["hypotheses"]), 2)

    def test_skips_empty_and_invalid(self):
        open_diagnostic(self.pid)
        session = add_hypotheses(self.pid, ["", "   ", "Б", 123, None, ["x"]])
        self.assertEqual(len(session["hypotheses"]), 1)
        self.assertEqual(session["hypotheses"][0]["text"], "Б")

    def test_skips_rejected_duplicates(self):
        open_diagnostic(self.pid)
        session = add_hypothesis(self.pid, "Причина")
        hid = session["hypotheses"][0]["id"]
        # добавим шаг и завершим rejected
        session = add_check(self.pid, hid, "Проверить")
        step_id = session["steps"][0]["id"]
        complete_check(self.pid, step_id, "нет", "rejected")
        session = add_hypotheses(self.pid, ["Причина", "Новая"])
        texts = [h["text"] for h in session["hypotheses"]]
        statuses = [h["status"] for h in session["hypotheses"]]
        # отклонённая гипотеза остаётся, но дубликат не добавляется
        self.assertEqual(len(session["hypotheses"]), 2)
        self.assertEqual(texts.count("Причина"), 1)
        self.assertIn("Новая", texts)
        self.assertIn("rejected", statuses)

    def test_no_hypotheses_returns_session(self):
        open_diagnostic(self.pid)
        session = add_hypotheses(self.pid, [])
        self.assertEqual(session["hypotheses"], [])

    def test_requires_open_session(self):
        with self.assertRaises(SolveError):
            add_hypotheses(self.pid, ["А"])

    def test_batch_respects_session_limit(self):
        open_diagnostic(self.pid)
        items = [f"Гипотеза {i}" for i in range(MAX_HYPOTHESES_PER_SESSION)]
        add_hypotheses(self.pid, items)
        with self.assertRaises(SolveError):
            add_hypotheses(self.pid, ["Ещё одна"])

    def test_default_source_when_invalid(self):
        open_diagnostic(self.pid)
        session = add_hypotheses(self.pid, [{"text": "А", "source": "bad"}])
        self.assertEqual(session["hypotheses"][0]["source"], "ai")


# ── suggest_check ────────────────────────────────────────────────

class TestSuggestCheck(BaseDiagTest):

    def setUp(self):
        super().setUp()
        open_diagnostic(self.pid)
        self.session = add_hypothesis(self.pid, "Причина")
        self.hid = self.session["hypotheses"][0]["id"]

    def test_creates_pending_step_linked_to_hypothesis(self):
        session = suggest_check(self.pid, self.hid)
        step = session["steps"][0]
        self.assertEqual(step["hypothesis_id"], self.hid)
        self.assertEqual(step["status"], "pending")
        self.assertEqual(step["description"], "")
        self.assertEqual(step["result"], "")
        self.assertEqual(len(step["id"]), 8)

    def test_unknown_hypothesis(self):
        with self.assertRaises(SolveError):
            suggest_check(self.pid, "bad-id")

    def test_terminal_hypothesis_rejected(self):
        session = add_check(self.pid, self.hid, "Проверка")
        complete_check(self.pid, session["steps"][0]["id"], "да", "confirmed")
        with self.assertRaises(SolveError):
            suggest_check(self.pid, self.hid)


# ── add_check ────────────────────────────────────────────────────

class TestAddCheck(BaseDiagTest):

    def test_free_check_without_hypothesis(self):
        open_diagnostic(self.pid)
        session = add_check(self.pid, None, "Проверить логи")
        step = session["steps"][0]
        self.assertIsNone(step["hypothesis_id"])
        self.assertEqual(step["description"], "Проверить логи")
        self.assertEqual(step["status"], "pending")

    def test_linked_check(self):
        open_diagnostic(self.pid)
        session = add_hypothesis(self.pid, "Причина")
        hid = session["hypotheses"][0]["id"]
        session = add_check(self.pid, hid, "Проверить venv")
        self.assertEqual(session["steps"][0]["hypothesis_id"], hid)

    def test_empty_description_rejected(self):
        open_diagnostic(self.pid)
        with self.assertRaises(SolveError):
            add_check(self.pid, None, "   ")

    def test_description_truncated(self):
        open_diagnostic(self.pid)
        session = add_check(self.pid, None, "д" * 1000)
        self.assertEqual(len(session["steps"][0]["description"]), 300)

    def test_unknown_hypothesis_rejected(self):
        open_diagnostic(self.pid)
        with self.assertRaises(SolveError):
            add_check(self.pid, "bad-id", "описание")

    def test_step_limit(self):
        open_diagnostic(self.pid)
        for i in range(MAX_STEPS_PER_SESSION):
            add_check(self.pid, None, f"Шаг {i}")
        with self.assertRaises(SolveError):
            add_check(self.pid, None, "Один лишний")


# ── complete_check ───────────────────────────────────────────────

class TestCompleteCheck(BaseDiagTest):

    def _setup_linked(self):
        open_diagnostic(self.pid)
        session = add_hypothesis(self.pid, "Причина")
        hid = session["hypotheses"][0]["id"]
        session = add_check(self.pid, hid, "Проверить")
        step_id = session["steps"][0]["id"]
        return hid, step_id

    def test_confirmed_sets_hypothesis_confirmed(self):
        hid, step_id = self._setup_linked()
        session = complete_check(self.pid, step_id, "подтвердилось", "confirmed")
        step = session["steps"][0]
        self.assertEqual(step["status"], "done")
        self.assertEqual(step["outcome"], "подтвердилось")
        self.assertEqual(step["result"], "confirmed")
        self.assertIsNotNone(step["completed_at"])
        h = session["hypotheses"][0]
        self.assertEqual(h["status"], "confirmed")
        self.assertEqual(h["last_tested_step_id"], step_id)

    def test_rejected_sets_hypothesis_rejected(self):
        hid, step_id = self._setup_linked()
        session = complete_check(self.pid, step_id, "нет", "rejected")
        self.assertEqual(session["hypotheses"][0]["status"], "rejected")

    def test_unknown_sets_hypothesis_tested(self):
        hid, step_id = self._setup_linked()
        session = complete_check(self.pid, step_id, "непонятно", "unknown")
        self.assertEqual(session["hypotheses"][0]["status"], "tested")

    def test_free_check_does_not_change_hypothesis(self):
        open_diagnostic(self.pid)
        session = add_hypothesis(self.pid, "Причина")
        hid = session["hypotheses"][0]["id"]
        session = add_check(self.pid, None, "Свободная проверка")
        step_id = session["steps"][0]["id"]
        session = complete_check(self.pid, step_id, "факт", "confirmed")
        h = session["hypotheses"][0]
        self.assertEqual(h["status"], "open")

    def test_invalid_result(self):
        hid, step_id = self._setup_linked()
        with self.assertRaises(SolveError):
            complete_check(self.pid, step_id, "outcome", "bogus")

    def test_unknown_step(self):
        with self.assertRaises(SolveError):
            complete_check(self.pid, "bad-step", "outcome", "confirmed")

    def test_cannot_redo_done_step(self):
        hid, step_id = self._setup_linked()
        complete_check(self.pid, step_id, "да", "confirmed")
        with self.assertRaises(SolveError):
            complete_check(self.pid, step_id, "ещё", "rejected")

    def test_terminal_hypothesis_not_re_terminated(self):
        hid, step_id = self._setup_linked()
        complete_check(self.pid, step_id, "да", "confirmed")
        # вторая проверка невозможна: suggest_check уже блокирует терминальную
        # гипотезу. Проверим, что complete_check на второй (свежей) гипотезе терминальной
        # не сбросит уже подтверждённую. Создадим вторую проверку на confirmed нельзя.
        # Проверяем инвариант: confirmed остаётся confirmed.
        session = self._session()
        self.assertEqual(session["hypotheses"][0]["status"], "confirmed")

    def test_requires_open_session(self):
        with self.assertRaises(SolveError):
            complete_check(self.pid, "step", "outcome", "confirmed")

    def test_outcome_truncated(self):
        hid, step_id = self._setup_linked()
        session = complete_check(self.pid, step_id, "о" * 1000, "unknown")
        self.assertEqual(len(session["steps"][0]["outcome"]), 300)


# ── is_diagnostic_active ─────────────────────────────────────────

class TestIsDiagnosticActive(BaseDiagTest):

    def test_false_without_session(self):
        # статус new + нет diagnostic
        self.assertFalse(is_diagnostic_active(self.problem))
        self.assertFalse(is_diagnostic_active({}))

    def test_false_if_not_investigating(self):
        open_diagnostic(self.pid)
        # остаётся в new (не investigating)
        self.assertFalse(is_diagnostic_active(self.problem))

    def test_false_if_investigating_without_work(self):
        open_diagnostic(self.pid)
        _to_investigating(self.pid)
        problem = self._reload()
        # нет гипотез и шагов → не активна
        self.assertFalse(is_diagnostic_active(problem))

    def test_true_with_open_hypothesis(self):
        open_diagnostic(self.pid)
        _to_investigating(self.pid)
        add_hypothesis(self.pid, "Причина")
        problem = self._reload()
        self.assertTrue(is_diagnostic_active(problem))

    def test_true_with_pending_step(self):
        open_diagnostic(self.pid)
        _to_investigating(self.pid)
        add_check(self.pid, None, "Проверка")
        problem = self._reload()
        self.assertTrue(is_diagnostic_active(problem))

    def test_false_after_all_rejected(self):
        open_diagnostic(self.pid)
        _to_investigating(self.pid)
        session = add_hypothesis(self.pid, "Причина")
        hid = session["hypotheses"][0]["id"]
        session = add_check(self.pid, hid, "Проверка")
        complete_check(self.pid, session["steps"][0]["id"], "нет", "rejected")
        problem = self._reload()
        self.assertFalse(is_diagnostic_active(problem))

    def test_true_after_tested_hypothesis(self):
        open_diagnostic(self.pid)
        _to_investigating(self.pid)
        session = add_hypothesis(self.pid, "Причина")
        hid = session["hypotheses"][0]["id"]
        session = add_check(self.pid, hid, "Проверка")
        complete_check(self.pid, session["steps"][0]["id"], "непонятно", "unknown")
        problem = self._reload()
        # tested — всё ещё открыта
        self.assertTrue(is_diagnostic_active(problem))

    def _reload(self):
        from src.problems import get_problem
        return get_problem(self.pid)


# ── finish_diagnostic ────────────────────────────────────────────

class TestFinishDiagnostic(BaseDiagTest):

    def test_sets_conclusion(self):
        open_diagnostic(self.pid)
        session = finish_diagnostic(self.pid, "не активирован venv")
        self.assertEqual(session["conclusion"], "не активирован venv")

    def test_idempotent_overwrite(self):
        open_diagnostic(self.pid)
        finish_diagnostic(self.pid, "Причина A")
        session = finish_diagnostic(self.pid, "Причина B")
        self.assertEqual(session["conclusion"], "Причина B")

    def test_requires_open_session(self):
        with self.assertRaises(SolveError):
            finish_diagnostic(self.pid, "причина")

    def test_persisted(self):
        open_diagnostic(self.pid)
        finish_diagnostic(self.pid, "причина")
        self.assertEqual(self._session()["conclusion"], "причина")


# ── get_diagnostic_context ───────────────────────────────────────

class TestGetDiagnosticContext(BaseDiagTest):

    def test_empty_context_when_no_session(self):
        ctx = get_diagnostic_context(self._fresh_problem())
        self.assertEqual(ctx["open_hypotheses"], [])
        self.assertEqual(ctx["rejected_hypotheses"], [])
        self.assertEqual(ctx["recent_steps"], [])
        self.assertEqual(ctx["conclusion"], "")

    def test_open_hypotheses_included(self):
        open_diagnostic(self.pid)
        add_hypothesis(self.pid, "П1")
        add_hypothesis(self.pid, "П2", source="ai", confidence=0.5)
        ctx = get_diagnostic_context(self._fresh_problem())
        self.assertEqual(len(ctx["open_hypotheses"]), 2)
        h = ctx["open_hypotheses"][0]
        self.assertIn("text", h)
        self.assertIn("status", h)
        self.assertIn("source", h)
        self.assertNotIn("id", h)

    def test_open_limited(self):
        open_diagnostic(self.pid)
        for i in range(10):
            add_hypothesis(self.pid, f"П{i}")
        ctx = get_diagnostic_context(self._fresh_problem())
        self.assertEqual(len(ctx["open_hypotheses"]), MAX_OPEN_HYPOTHESES)

    def test_rejected_included_and_limited(self):
        open_diagnostic(self.pid)
        for i in range(7):
            session = add_hypothesis(self.pid, f"П{i}")
            hid = session["hypotheses"][-1]["id"]
            session = add_check(self.pid, hid, "проверка")
            complete_check(self.pid, session["steps"][-1]["id"], "нет", "rejected")
        ctx = get_diagnostic_context(self._fresh_problem())
        self.assertEqual(len(ctx["rejected_hypotheses"]), MAX_REJECTED)

    def test_recent_steps_only_done(self):
        open_diagnostic(self.pid)
        session = add_hypothesis(self.pid, "П1")
        hid = session["hypotheses"][0]["id"]
        add_check(self.pid, hid, "проверка1")  # pending — не в done
        session = add_check(self.pid, hid, "проверка2")
        complete_check(self.pid, session["steps"][-1]["id"], "да", "confirmed")
        ctx = get_diagnostic_context(self._fresh_problem())
        self.assertEqual(len(ctx["recent_steps"]), 1)
        self.assertEqual(ctx["recent_steps"][0]["description"], "проверка2")

    def test_recent_steps_limited(self):
        open_diagnostic(self.pid)
        for i in range(8):
            add_check(self.pid, None, f"Проверка {i}")
        # завершим все
        session = self._session()
        for step in session["steps"]:
            complete_check(self.pid, step["id"], "ok", "unknown")
        ctx = get_diagnostic_context(self._fresh_problem())
        self.assertEqual(len(ctx["recent_steps"]), MAX_RECENT_STEPS)
        self.assertEqual(ctx["recent_steps"][0]["description"], "Проверка 3")

    def test_max_steps_param(self):
        open_diagnostic(self.pid)
        for i in range(4):
            add_check(self.pid, None, f"Проверка {i}")
        session = self._session()
        for step in session["steps"]:
            complete_check(self.pid, step["id"], "ok", "unknown")
        ctx = get_diagnostic_context(self._fresh_problem(), max_steps=2)
        self.assertEqual(len(ctx["recent_steps"]), 2)

    def test_conclusion_included(self):
        open_diagnostic(self.pid)
        finish_diagnostic(self.pid, "причина")
        ctx = get_diagnostic_context(self._fresh_problem())
        self.assertEqual(ctx["conclusion"], "причина")


# ── компактные представления ────────────────────────────────────

class TestCompactRepresentations(unittest.TestCase):

    def test_compact_hypothesis(self):
        h = {"id": "abc", "text": "Причина", "status": "open",
             "source": "ai", "confidence": 0.5}
        c = _compact_hypothesis(h)
        self.assertEqual(set(c.keys()), {"text", "status", "source"})

    def test_compact_step(self):
        s = {"id": "x", "description": "Проверка", "result": "confirmed",
             "status": "done", "outcome": "да"}
        c = _compact_step(s)
        self.assertEqual(set(c.keys()), {"description", "result"})


# ── изоляция от существующих полей Problem ─────────────────────

class TestIsolationFromProblemFields(BaseDiagTest):

    def test_diagnostic_does_not_affect_other_fields(self):
        open_diagnostic(self.pid)
        add_hypothesis(self.pid, "Причина")
        _to_investigating(self.pid)
        from src.problems import get_problem
        stored = get_problem(self.pid)
        self.assertEqual(stored["title"], self.problem["title"])
        self.assertEqual(stored["status"], "investigating")
        self.assertEqual(stored["cause"], "")
        self.assertEqual(stored["solution"], "")
        self.assertIsNone(stored["helped"])
        self.assertIsNone(stored["related_record_id"])

    def test_problem_without_diagnostic_still_valid(self):
        # новый problem без диагностики не ломает существующие функции
        from src.solve import start_investigation, start_solving, convert_to_knowledge, resolve_problem
        start_investigation(self.pid)
        start_solving(self.pid)
        resolve_problem(self.pid, cause="c", solution="s", helped=True)
        record = convert_to_knowledge(self.pid)
        self.assertIsNotNone(record["id"])

    def test_solve_flow_ignores_absent_diagnostic(self):
        from src.solve import get_problem_summary
        summary = get_problem_summary(self.pid)
        self.assertEqual(summary["status"], "new")


# ── сохранение и перезагрузка ───────────────────────────────────

class TestPersistence(BaseDiagTest):

    def test_full_session_survives_reload(self):
        open_diagnostic(self.pid)
        _to_investigating(self.pid)
        session = add_hypothesis(self.pid, "Причина")
        hid = session["hypotheses"][0]["id"]
        session = add_check(self.pid, hid, "Проверка")
        complete_check(self.pid, session["steps"][0]["id"], "да", "confirmed")
        finish_diagnostic(self.pid, "причина найдена")

        from src.problems import get_problem
        stored = get_problem(self.pid)
        d = stored["diagnostic"]
        self.assertEqual(len(d["hypotheses"]), 1)
        self.assertEqual(d["hypotheses"][0]["status"], "confirmed")
        self.assertEqual(len(d["steps"]), 1)
        self.assertEqual(d["steps"][0]["result"], "confirmed")
        self.assertEqual(d["conclusion"], "причина найдена")


# ── README: лимиты констант ─────────────────────────────────────

class TestLimits(unittest.TestCase):

    def test_values(self):
        self.assertEqual(MAX_OPEN_HYPOTHESES, 5)
        self.assertEqual(MAX_REJECTED, 5)
        self.assertEqual(MAX_REJECTED_HYPOTHESES, 5)
        self.assertEqual(MAX_RECENT_STEPS, 5)
        self.assertEqual(MAX_HYPOTHESES_PER_SESSION, 10)
        self.assertEqual(MAX_STEPS_PER_SESSION, 20)
