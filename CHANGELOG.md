# CHANGELOG

## v1.3.5/v1.3.6 — Real AI smoke-test + настраиваемый endpoint

### v1.3.5 — инструмент реального smoke-теста
- Новый `smoke_real_ai.py` (в корне, не в `src/`): последовательный прогон `format_knowledge`, `suggest_hypotheses`, `suggest_next_check` на демо-проблеме.
- Ключ читается ТОЛЬКО из `OPENAI_API_KEY`; вывод маскируется (`sk-***last4`), ответы обрезаются до 100 символов; изоляция `data/problems.json` (хэш до/после); идемпотентен, в `data/` ничего не пишет.
- **Реальный прогон: все 3 шага → HTTP 403.** Диагноз: ключ `sk-or-v1-...` (OpenRouter) отклонён и на `api.openai.com`, и на OpenRouter; на OpenRouter тело ошибки `"Access denied by security policy."` — блокировка по политике безопасности аккаунта/ключа, НЕ по коду. Основание: не 401 (ключ), не 402 (кредиты). **Пункт Real AI smoke-test остаётся открытым** до решения на стороне провайдера.

### v1.3.6 — настраиваемый API endpoint (base_url)
- `src/ai/openai.py`: `OpenAIProvider(base_url=...)` (по умолчанию `https://api.openai.com/v1`); URL = `base_url + "/chat/completions"`. Поддержана правка `_chat` на `self.api_url`.
- `src/ai/config.py`: `AIConfig.base_url`, `AI_DEFAULTS["base_url"]`, `load_config` и `get_ai_provider` передают `base_url` в провайдер.
- `smoke_real_ai.py`: чтение `OPENAI_BASE_URL` (например `https://openrouter.ai/api/v1`) для перепроверки.
- Тесты: `tests/test_ai_openai.py` +4 (default/custom/trailing-slash/URL), `tests/test_ai_config.py` base_url (defaults/fill/provider).
- Полный набор: **545 passed** (541 + 4 новых).
- Код совместим назад: повтор по умолчанию = прежнее поведение (api.openai.com).

### Версия
- `pyproject.toml` → **1.3.6** (первое изменение кода с 1.3.0; v1.3.1–1.3.5 код не трогали).

---

## v1.3.2/v1.3.3 — Инфраструктура репозитория и доки

### v1.3.2 — remote-бэкап
- Добавлен remote `origin` → `https://github.com/antonshulpin-coder/DiagAISolver.git` (приватный).
- Auth: HTTPS + Git Credential Manager (токен в Windows Credential Store, не в файлах репо).
- Запушены вся история `main` и тег `v1.3.0`. Греп-скан по токенам (`ghp_`, `github_pat_`, `glpat-`) — чисто.
- Локальный бэкап личных данных: `backup/problems_2026-08-27.json`; `backup/` добавлен в `.gitignore`.

### v1.3.3 — обновление документации
- `AI_HANDOFF.md`: раздел «Инфраструктура репозитория», статус/версия (метаданные-релиз), «Следующий этап → Ожидает решения пользователя».
- `CHANGELOG.md`: новая запись (эта).
- **Код не менялся** (v1.3.1/v1.3.2/v1.3.3 — только инфраструктура/доки).

### Версия
- `pyproject.toml` остаётся **1.3.0** (код не менялся; конвенция — bump только при изменении кода, как в v1.3.1/v1.3.2).

---

## v1.3.0 — Полировка UX диагностики

### Что сделано
- `src/commands.py`:
  - **UX1** `_confirm_cause(problem)` — подтверждение причины одним нажатием: при ровно одной confirmed-гипотезе предлагает её текст и принимает по Enter/y; при нескольких — нумерованный выбор; при отсутствии — прежний ручной ввод без изменений.
  - **UX2** `_show_diagnostic_state` — секции «История проверок» (выполненные шаги: описание → результат → затронутая гипотеза (статус)) и «Проверено/Отклонено» (терминальные гипотезы). Пустая история не выводится; лимит показа `_DIAG_HISTORY_LIMIT = 6` + сообщение «… и ещё N».
  - **UX3** `_diagnostic_ai_hint(problem, provider)` + пункт меню «5. Подсказка «что дальше»» — следующий шаг при застрявшей сессии (есть открытые гипотезы и нет pending-шагов); иначе «Подсказка недоступна сейчас» без вызова AI. Reuse `suggest_next_check` + `get_diagnostic_context`; y → `add_check` с обработкой «Выполнили уже?». Ошибки AI → информативное сообщение, graceful.
- Номера существующих пунктов меню (1–4, 0) не менялись; старое поведение сохранено.

### Изоляция / ограничения
- Изменён только `src/commands.py` + новый тест-файл.
- `src/diagnostic.py`, `src/solve.py`, `src/problems.py`, AI-слой — без изменений.
- Для UX1 confirmed-гипотезы берутся из полной сессии `problem["diagnostic"]` (компактный контекст их не отдаёт — см. v1.2.4).

### Тесты
- `tests/test_diagnostic_ux.py` — **20 тестов** (UX1: 9, UX2: 5, UX3: 6).
- Полный набор: **541 passed** (521 + 20 новых).

### Версия
- Поднята до `1.3.0`

---

## v1.2.4 — AI Diagnostic SOLVE (Phase 4: данные расследования в AI-контексте)

### Что сделано
- `src/solve.py` — `_build_knowledge_text(problem, diagnostic_context=None)` расширен опциональной секцией «Расследование»:
  - открытые гипотезы `[id] text (AI|вручную) — статус`
  - выполненные шаги: `описание → результат → затронутая гипотеза (статус)`
  - вывод (conclusion), если диагностика завершена
  - если диагностики/данных нет — секция не добавляется, текст байт-в-байт идентичен старому
- Новый помощник `_build_investigation_text(problem, diagnostic_context=None)` — строит секцию; `""` при отсутствии данных
- Терминальные гипотезы (confirmed/rejected) отображаются со статусом (подтверждена/отклонена)

### Подача контекста / лимиты
- При `None` данные берутся из `problem["diagnostic"]` → все существующие вызовы (`convert_to_knowledge`) работают **без правок** (сигнатурная совместимость)
- Переиспользован лимит обрезки `MAX_SEARCH_RESULTS` (тот же, что у `_compact_diagnostic_context`): гипотезы ≤ `MAX_SEARCH_RESULTS*2`, выполненные шаги ≤ `MAX_SEARCH_RESULTS`
- Приоритет при обрезке: вывод (всегда сохраняется) > статусы гипотез > результаты шагов

### Изоляция данных (соблюдено)
- Полный AI-ответ и сырые данные расследования НЕ пишутся в problems.json
- `src/diagnostic.py`, `src/commands.py`, `src/problems.py` — без изменений
- read-only: строим секцию только на чтении `problem`/`diagnostic`
- `convert_to_knowledge` (public) не менялся

### Тесты
- `tests/test_diagnostic_ai_context.py` — 15 тестов
- Полный набор: **521 passed** (506 + 15 новых)

### Примечание (отклонение от черновика)
- Источником секции служит полная сессия `problem["diagnostic"]`, а не `get_diagnostic_context(problem)`: компактный контекст по дизайну ядра НЕ отдаёт `id` гипотез, привязку шаг→гипотеза и **confirmed**-гипотезы, без которых нельзя отобразить терминальные статусы. `get_diagnostic_context`/`diagnostic.py` не менялись. Лимит обрезки взят из `_compact_diagnostic_context` (`MAX_SEARCH_RESULTS`).

### Версия
- Поднята до `1.2.4`

---

## v1.2.3 — AI Diagnostic SOLVE (Phase 3: интеграция диагностики в CLI)

### Что сделано
- `src/commands.py` — цикл диагностики подключён к SOLVE flow:
  - `_show_diagnostic_state(problem)` — печать состояния (открытые гипотезы, pending-шаги, вывод)
  - `_diagnostic_add_hypotheses(problem, provider)` — AI (принять все / выбрать номера / отказ → ручной ввод), graceful fallback, ошибки ядра не роняют CLI
  - `_diagnostic_add_check(problem, provider)` — AI-шаг или ручной ввод; после добавления можно сразу отметить выполненным
  - `_diagnostic_complete_step(problem, step_id=None)` — общий хелпер: показ pending-шагов, ввод результата (confirmed/rejected/unknown) + краткого результата, отображение затронутых гипотез
  - `_diagnostic_loop(problem, provider)` — меню диагностики (1 гипотезы, 2 шаг, 3 отметить, 4 завершить, 0 выйти); пункт 4 → `finish_diagnostic` → возвращает conclusion
  - `_continue_with_conclusion(...)` — `start_solving` + `_do_solve` с предзаполненной причиной
- Опция `d` («Диагностика») в `_investigate_problem` (существующие пункты 1/2/3 не перенумеровывались)
- `_do_solve(problem, provider, cause_default="")` — опциональная причина по умолчанию (Enter = принять); дефолт пустой ⇒ поведение идентично старому

### Гарантии / ограничения
- `src/diagnostic.py` — НЕ изменён; публичный API диагностики не тронут
- `src/solve.py`, `src/problems.py` — без изменений
- Линейный путь SOLVE без диагностики сохранён (все старые пункты меню работают)
- Полный AI-ответ НЕ записывается в problems.json
- Любые ошибки AI/provider → graceful fallback на ручной ввод
- NullProvider (success=False) → ручной путь работает без падения

### Тесты
- `tests/test_diagnostic_cli.py` — 18 тестов (по аналогии с test_solve_cli.py, in-memory stdin/stdout)
- Полный набор: **506 passed** (488 + 18 новых)

### Версия
- Поднята до `1.2.3`

---

## v1.2.2 — AI Diagnostic SOLVE (Phase 2: AI-слой диагностики)

### Что сделано
- Добавлены 2 новых метода в AIProvider/NullProvider/OpenAIProvider и FakeProvider:
  - `suggest_hypotheses(problem, diagnostic_context) -> AIResponse`
  - `suggest_next_check(problem, diagnostic_context) -> AIResponse`
- `src/ai/context.py`: +2 builder'а (`build_suggest_hypotheses_context`, `build_suggest_next_check_context`) + `_compact_diagnostic_context`
- `src/ai/__init__.py`: экспорт новых builder'ов
- `tests/test_diagnostic_ai.py`: 62 новых теста
- `tests/fake_provider.py`: +2 метода

### Архитектура
- **AI — советник**: методы возвращают AIResponse, НЕ изменяют `Problem`/`diagnostic` (stateless).
- `suggest_hypotheses` → `AIResponse.suggestions` = список строк-гипотез, `content` = пояснение.
- `suggest_next_check` → `AIResponse.content` = описание одного шага, `suggestions` = альтернативы.
- Сигнатуры — `(problem, diagnostic_context)`: вся информация о расследовании приходит компактно из `get_diagnostic_context` (открытые/отклонённые гипотезы, последние шаги, вывод).
- Полный AI-ответ НЕ сохраняется в problems.json.

### Защита
- `_clean_suggestions`: отбрасывает пустые/нестроковые и дубли (устойчиво к повторным предложениям).
- `_parse_hypotheses_response`/`_parse_next_check_response`: устойчивы к плохому JSON (fallback на строки), не крашатся на мусоре.
- Соблюдены лимиты контекста (`MAX_SEARCH_RESULTS` защитно ограничивает срез).
- Ошибки провайдера (HTTP/timeout/network/refusal/empty/malformed/no key) → `success=False` → локальный режим.

### Обратная совместимость
- Все старые AI-методы (`analyze_problem`, `analyze_experience`, `create_plan`, `analyze_result`, `format_knowledge`) работают как раньше.
- `NullProvider` по-прежнему возвращает `success=False`.
- `src/diagnostic.py`, `src/solve.py`, `src/commands.py` — без изменений.

### Тесты
- `tests/test_diagnostic_ai.py` — 62 теста (контракт, NullProvider, FakeProvider, context builder, лимиты, парсинг, успех/malformed/empty/refusal/HTTP/timeout/network/no-key, readonly, обратная совместимость, полный цикл)
- Полный набор: **488 passed** (426 + 62 новых)

### Версия
- Поднята до `1.2.2`

---

## v1.2.1 — AI Diagnostic SOLVE (Phase 1: ядро диагностики)

### Что сделано
- Реализован `src/diagnostic.py` — чистое ядро диагностики (10 публичных функций), без CLI и без AI
- Добавлен `"diagnostic"` в `UPDATEABLE_FIELDS` (`src/problems.py`)
- Полный цикл расследования: гипотезы → проверки → результаты → вывод
- Дедупликация гипотез, лимиты сессии, статусные переходы, tz-абсолютные временные метки, атомарное сохранение через `update_problem`

### Модель
- `DiagnosticSession` хранится в `problem["diagnostic"]`: `{started_at, hypotheses, steps, conclusion}`
- `Hypothesis` (id, text, status open/confirmed/rejected/tested, confidence, source ai/user/knowledge, created_at, last_tested_step_id)
- `InvestigationStep` (id, hypothesis_id, description, status pending/done, outcome, result confirmed/rejected/unknown, created_at, completed_at)
- `active` вычисляется через `is_diagnostic_active()`, не хранится

### Лимиты
- `MAX_OPEN_HYPOTHESES=5`, `MAX_REJECTED=5`, `MAX_RECENT_STEPS=5`
- `MAX_HYPOTHESES_PER_SESSION=10`, `MAX_STEPS_PER_SESSION=20`
- `MAX_HYPOTHESIS_TEXT=200`, `MAX_STEP_DESCRIPTION=300`, `MAX_OUTCOME_TEXT=300`

### Функции
- `open_diagnostic`, `get_diagnostic`, `add_hypothesis`, `add_hypotheses`, `suggest_check`, `add_check`, `complete_check`, `is_diagnostic_active`, `finish_diagnostic`, `get_diagnostic_context`

### Тесты
- `tests/test_diagnostic.py` — 75 тестов (полный охват: жизненный цикл, лимиты, дедупликация, изоляция, персистентность, контекст для AI)
- Полный набор: **426 passed** (351 существующих + 75 новых)
- Гибкое тестирование через патч `DATA_FILE` в `BaseDiagTest.run()`

### Обратная совместимость
- Существующий SOLVE и все 351 тест не сломаны
- `NullProvider` по-прежнему работает
- Фаза 2 (AI-методы, provider, context, CLI) НЕ реализована

### Версия
- Поднята до `1.2.1`

---

## v1.2 — AI Diagnostic SOLVE (архитектура, код не начат)

### Проектирование
- Создан `docs/DIAGNOSTIC_DESIGN.md` — полный архитектурный план v1.2
- SOLVE превращается из линейного сценария в итеративное расследование
- Модели: `DiagnosticSession`, `Hypothesis`, `InvestigationStep`
- 2 новых AI-метода: `suggest_hypotheses`, `suggest_next_check`
- Обратная совместимость: существующий SOLVE и 351 тест не ломаются

### Что решено (кратко)
- Диагностика хранится в поле `problem["diagnostic"]` (не отдельный файл)
- `active` вычисляется, не хранится
- Лимиты: 10 гипотез / 20 шагов на сессию (защита от бесконечного цикла)
- AI недоступен → локальный режим (пользователь сам вводит гипотезы/проверки)
- Knowledge Record расширяется секцией «Расследование» (опционально)

### Файлы
- `docs/DIAGNOSTIC_DESIGN.md` — новый дизайн-документ
- Код ещё НЕ реализован (согласно инструкции)

---

## v1.1.1 — Smoke-test OpenAI провайдера

### Что сделано
- Проверен реальный OpenAI API минимальным запросом — **NOT RUN** (нет `OPENAI_API_KEY` в environment)
- Проведён полный offline smoke-test всех сценариев поставщика

### Результат offline smoke-test (8/8 PASS)
| Сценарий | Результат |
|----------|-----------|
| Успешный ответ | ✅ PASS |
| HTTP 401 | ✅ PASS |
| HTTP 429 | ✅ PASS |
| Timeout | ✅ PASS |
| Сетевая ошибка | ✅ PASS |
| Malformed JSON | ✅ PASS |
| Refusal | ✅ PASS |
| Null content | ✅ PASS |

### Изменения
- Версия поднята до `1.1.1`

---

## v1.1.0 — OpenAI API compatibility

### Изменено
- `max_tokens` → `max_completion_tokens` в запросах к OpenAI API (deprecated param)
- Обработка `null` content в ответах API
- Обработка `refusal` поля в ответах API
- 5 новых тестов (351 total)

---

## v1.0 Phase 4 (2026-08-27)

### Добавлено
- Модуль `src/ai/config.py` — конфигурация AI
- `AIConfig` — dataclass (enabled, provider, model, timeout)
- `load_config(path)` — загрузка из settings.json с safe defaults
- `get_ai_provider(config, api_key)` — фабрика: конфигурация → AIProvider
- Секция `ai` в `config/settings.json` (enabled, provider, model, timeout)
- Автоопределение провайдера в `solve_flow()` из конфигурации

### Архитектурные решения
- Конфигурация хранится в `config/settings.json` (общий файл с academy_root)
- API key **никогда** не хранится в settings.json
- Фабрика `get_ai_provider()` не бросает исключения — возвращает NullProvider при ошибке
- `solve_flow(provider=None)` загружает провайдер из конфигурации
- Обратная совместимость: `solve_flow(provider=FakeProvider())` по-прежнему работает
- Если settings.json отсутствует или повреждён — используются безопасные defaults (AI отключён)

### Тесты
- 22 теста для test_ai_config.py: defaults (1), load_config (8), get_ai_provider (7), secret isolation (3), SOLVE integration (3)
- Итого: 346 тестов (было 324)

## v1.0 Phase 3 (2026-08-27)

### Добавлено
- Модуль `src/ai/openai.py` — OpenAIProvider через stdlib (urllib.request)
- `OpenAIProvider` — провайдер для OpenAI API
- API key из переменной окружения `OPENAI_API_KEY`
- Модель настраивается через параметр `model` (по умолчанию `gpt-4o-mini`)
- Таймаут настраивается через параметр `timeout` (по умолчанию 30с)
- `_parse_response(raw)` — парсинг HTTP-ответа в AIResponse
- `_handle_http_error(e)` — обработка HTTP-ошибок (401/403/429/500+)
- Обработка timeout и connection errors
- Обработка invalid JSON и malformed ответов

### Архитектурные решения
- Используется stdlib (`urllib.request`), не SDK
- HTTP-специфика скрыта внутри OpenAIProvider
- Core знает только AIProvider (контракт)
- Все 5 методов используют общий `_chat()` механизм
- Используются существующие context builders из `src/ai/context.py`
- Используется SYSTEM_PROMPT из `src/ai/provider.py`
- API key не попадает в ошибки и логи
- Нет реальных API-запросов в тестах — все через mock

### Тесты
- 47 тестов для test_ai_openai.py: constructor (8), parse_response (6), http_error (6), no_key (4), success (5), errors (8), request_params (4), all_methods (1), security (2), readonly (2), type (1)
- Итого: 324 теста (было 277)

## v1.0 Phase 2 (2026-08-27)

### Добавлено
- `src/solve.py` — AI-интеграция: ai_analyze_problem, ai_analyze_experience, ai_create_plan, ai_analyze_result, ai_format_knowledge, _safe_ai_call, _get_provider
- `src/commands.py` — AI в SOLVE: _is_ai_available, _show_ai_analysis, provider параметр во всех SOLVE-функциях
- `tests/test_solve_ai.py` — 39 тестов AI-интеграции

### Архитектурные решения
- AI-вызовы через `_safe_ai_call` — исключения перехватываются, SOLVE не падает
- Provider передаётся явно через цепочку вызовов (solver → commands)
- NullProvider по умолчанию — SOLVE работает без AI
- AI-анализ показывается до/после ключевых шагов SOLVE
- AI никогда не изменяет данные — только анализирует и предлагает

### Тесты
- 39 AI-тестов: safe_call (3), get_provider (2), ai_* (16), data isolation (5), lifecycle (3), CLI (3), display (4), availability (3)
- Итого: 277 тестов (было 238)

## v1.0 Phase 1 (2026-08-27)

### Добавлено
- `src/ai/types.py` — AIResponse dataclass (success, content, suggestions, confidence, error)
- `src/ai/provider.py` — AIProvider (контракт), NullProvider (заглушка), SYSTEM_PROMPT
- `src/ai/context.py` — build_*_context функции (5 штук), _compact_problem, _compact_knowledge
- `src/ai/__init__.py` — экспорт модуля AI
- `tests/fake_provider.py` — FakeProvider для тестов (предопределённые ответы, лог вызовов)
- `tests/test_ai.py` — 57 тестов AI-слоя

### Архитектурные решения
- AI — советник,Harness — хозяин данных
- AIProvider — 5 методов: analyze_problem, analyze_experience, create_plan, analyze_result, format_knowledge
- NullProvider — заглушка по умолчанию (AI недоступен)
- Контекст: проблема + топ-5 результатов (без ID, служебных полей)
- Максимум 500 символов в тексте knowledge record
- Максимум 3 решения для плана

### Тесты
- 57 AI-тестов: AIResponse (8), AIProviderBase (5), NullProvider (6), FakeProvider (13), Context (17), SYSTEM_PROMPT (3), Constants (3), DataIsolation (2)
- Итого: 238 тестов (было 181)

## v0.9.4 (2026-08-27)

### Добавлено
- Меню SOLVE: "1. Новая проблема" / "2. Продолжить существующую" / "0. Назад"
- Продолжение существующих проблем (investigating/solving/failed)
- Повтор попытки для failed проблем (failed → solving)
- Архивирование failed проблем из меню продолжения
- Конвертация failed проблем в базу знаний из меню продолжения
- Предложение повтора после helped=None (продолжить решение / вернуться в меню)
- Быстрая отметка solving проблем как solved/failed (без повторного ввода)

### Улучшено
- `_build_knowledge_text`: добавлены статус ("Статус: решена/не решена") и результат ("Результат: помогло/не помогло")
- Порядок полей в knowledge record: статус → описание → контекст → ошибка → причина → решение → результат

### Исправлено
- Эмодзи "❌" в router.py заменён на текст "!" для совместимости с PowerShell cp1251

### Тесты
- 21 CLI-тест (было 10): делегирование, меню SOLVE (выход, неверный выбор), пустой заголовок, выход из investigation, happy path, helped=no, helped=None, helped=None с повтором, неверный выбор, KeyboardInterrupt, SolveError, использование найденного решения, продолжение investigating/solving/failed, повтор/архив/конвертация failed, нет активных проблем, отмена выбора
- 1 обновлённый тест: knowledge_text_includes_fields (проверка статуса и результата)
- Итого: 181 тест (было 170)

## v0.9.3 (2026-08-27)

### Добавлено
- CLI-интерфейс SOLVE в `src/commands.py`
- `solve_flow()` — основной сценарий с обработкой ошибок
- Пошаговый ввод: название, описание, контекст, ошибка, теги
- Автоматический переход new → investigating
- Поиск похожего опыта (knowledge + problems) с отображением результатов
- Три варианта действий: использовать найденное, продолжить, выйти
- Ввод решения: причина, решение, помогло ли (да/нет/не знаю)
- Итоговый отчёт SOLVE ЗАВЕРШЁН
- Опция конвертации Problem → Knowledge Record
- Обработка ошибок: SolveError, ProblemError, StorageError, KeyboardInterrupt

### Изменено
- `src/router.py`: импорт `solve_flow` вместо `solve`
- `tests/test_router.py`: mock обновлён для `solve_flow`

### Тесты
- 10 CLI-тестов: делегирование, пустой заголовок, выход, happy path, helped=no, helped=None, неверный выбор, KeyboardInterrupt, SolveError, использование найденного решения
- 7 router-тестов (обновлён)
- Итого: 170 тестов (было 160)

## v0.9.2 (2026-08-27)

### Добавлено
- Модуль `src/solve.py` — бизнес-логика SOLVE
- `SolveError` — исключение для ошибок бизнес-логики
- `build_search_query(problem)` — формирует поисковый запрос из title, error_message, tags
- `find_similar(problem)` — поиск похожего в knowledge records и problems с динамическим min_coverage
- `start_investigation(problem_id)` — new → investigating
- `start_solving(problem_id)` — investigating → solving
- `resolve_problem(problem_id, cause, solution, helped)` — fixing решение (solving → solved/failed)
- `archive_problem(problem_id)` — solved/failed → archived
- `convert_to_knowledge(problem_id)` — конвертация Problem → Knowledge Record
- `get_problem_summary(problem_id)` — структура для CLI
- Таблица переходов статусов с валидацией
- `failed → solving` разрешён для повторной попытки

### Архитектурные решения
- `resolve_problem` разрешён ТОЛЬКО из solving (не из investigating)
- `find_similar` использует динамический min_coverage: `min(0.3, 1.0 / len(terms))`
- `convert_to_knowledge` создаёт новую запись типа `solution`, запрещает повторную конвертацию

### Тесты
- 48 тестов для solve.py: build_search_query, find_similar, переходы статусов, resolve, archive, convert_to_knowledge, summary
- Итого: 160 тестов (было 112)

## v0.9.1 (2026-08-27)

### Добавлено
- Модуль `src/problems.py` — хранилище проблем с CRUD и поиском
- Модель Problem: id, created_at, title, description, context, error_message, tags, status, solution, cause, helped, related_record_id
- Статусы: new, investigating, solving, solved, failed, archived
- Хранение в `data/problems.json` (отдельный от notes.json)
- Атомарная запись через .tmp, обработка ошибок JSON, ProblemError
- Маппинг полей проблемы в формат поиска (description/error_message → text)
- `search_problems()` и `search_problems_with_scores()` с интеграцией в `rank_records`
- Значение `helped`: поддержка true, false, None

### Тесты
- 43 теста для problems.py: создание, уникальность ID, даты, значения по умолчанию, получение, обновление (helped: true/false/None), удаление, поиск, пустая база, повреждённый JSON, безопасное сохранение, все статусы
- Итого: 112 тестов (было 69)

## v0.8.0 (2026-08-27)

### Добавлено
- Модуль `src/search.py` — локальный детерминированный поиск с ранжированием
- Мульти-словный поиск: запрос "ошибка python vscode" ищет записи со всеми тремя термами
- Ранжирование по релевантности: title (10/6) > tags (8/5) > text (3)
- Точное совпадение имеет больший вес, чем частичное
- Бонус за покрытие: записи, содержащие больше термов из запроса, получают приоритет
- Фильтр `min_coverage` — запись возвращается только если все термы найдены
- `search_records_with_scores(query)` — возвращает (record, score) для будущего использования
- Обработка: регистр, множественные пробелы, повторяющиеся слова, русский/английский текст

### Тесты
- 69 тестов (было 34): 25 для search.py, 31 для storage.py, 7 для router.py

### Архитектура
- `search.py` отделён от CLI — алгоритм можно использовать напрямую в SOLVE
- `search_records(query)` сохраняет обратную совместимость (возвращает list[record])
- Константы весов вынесены в верхний уровень модуля

## v0.7.0 (2026-08-27)

### Добавлено
- Модель записи знаний: `id`, `created_at`, `type`, `title`, `text`, `tags`
- Уникальный ID для каждой записи (uuid4, 12 hex символов)
- Дата создания в формате ISO 8601
- Типы записей: note, bookmark, idea, problem (пользовательский ввод)
- Заголовок и теги для каждой записи
- Просмотр всех записей с кратким превью
- Просмотр полной записи
- Редактирование записей (с оставлением полей без изменения через Enter)
- Удаление записей с подтверждением (да/нет, y/yes)
- Поиск по заголовку, тексту и тегам
- Автоматическая миграция старого формата (`{"text": "..."}`) в новый
- Обратная совместимость со старыми данными

### Тесты
- 34 теста (было 18): миграция, CRUD, поиск, уникальность ID

### Исправлено
- Пустой поисковый запрос возвращает пустой список (v0.6.1)
- Двойное нажатие Enter при выходе из базы знаний (v0.6.1)
- Опечатка "Pyton" → "Python" в данных (v0.6.1)
- Версия читается из pyproject.toml, не захардкожена (v0.6.1)
- Виртуальное окружение пересоздано под Python 3.12 (v0.6.1)
