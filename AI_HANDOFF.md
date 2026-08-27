# AI_HANDOFF.md

## Текущая версия
**1.3.7 (app-identification headers для OpenRouter)** — 549 тестов. Кодовая база: AI Diagnostic SOLVE (v1.2) + Полировка UX диагностики (v1.3) + настраиваемый API endpoint (v1.3.6) + заголовки HTTP-Referer/X-Title (v1.3.7).

## Состояние проекта
Полностью рабочий CLI-инструмент с базой знаний, хранилищем проблем и режимом SOLVE. 549 тестов проходит. AI конфигурируется через `config/settings.json`. OpenAI API использует актуальные параметры (`max_completion_tokens`, обработка `refusal` и `null` content); endpoint переопределяем через `ai.base_url` (напр. OpenRouter); заголовки идентификации приложения `ai.app_url`/`ai.app_title` (HTTP-Referer/X-Title).

**Текущий этап:** v1.3 Полировка UX диагностики (UX1 — причина одним нажатием, UX2 — история расследования, UX3 — AI-подсказка «что дальше») реализована в `src/commands.py` (код v1.3.0). Архитектурный план диагностики — `docs/DIAGNOSTIC_DESIGN.md`. **v1.3 закрыта**; v1.3.1–1.3.3 — инфраструктура/доки; v1.3.5/1.3.6 — smoke-инструмент + endpoint; v1.3.7 — заголовки идентификации. **Real AI smoke-test: прогон ранее дал 403 (OpenRouter security policy); после заголовков — на перепроверку пользователем (v1.3.7).**

## Инфраструктура репозитория (v1.3.2–v1.3.3; дополнено v1.3.6)

- Remote: `https://github.com/antonshulpin-coder/DiagAISolver.git` (приватный репозиторий).
- Auth: HTTPS + Git Credential Manager (токен в Windows Credential Store, НЕ в файлах репо). Проверено греп-сканом — токенов в дереве нет.
- Тег релиза: `v1.3.0` (аннотированный → `87ec152`).
- Данные `data/problems.json` — в .gitignore (личные данные). Локальная копия: `backup/` (игнорируется). Бэкап разовый, не автоматизирован.
- Пушить только в origin; force-push запрещён. Push — по явной команде пользователя.
- Git-identity (локально в репо): `antonshulpin-coder <anton.shulpin@gmail.com>`.
- Коммиты по фазам v0.1→v1.3.0: `8968eb8`, `459a39c`, `a25a0a7`, `f1b64bb`, `3b4dfd3`, `87ec152`; chore: `cee4ba3` (backup/.gitignore); docs v1.3.3: `a0201b5`; docs v1.3.4: `6b1f927`.
- `smoke_real_ai.py` (корень): реальный прогон OpenAI-слоя. Ключ ТОЛЬКО из `OPENAI_API_KEY`; endpoint через `OPENAI_BASE_URL`; вывод маскируется; `data/` не трогает.

## v1.3 — Полировка UX диагностики (v1.3.0)

### UX1: подтверждение причины одним нажатием
- `src/commands.py` → новый `_confirm_cause(problem)`, вызывается из пункта 4 цикла.
- ровно одна confirmed-гипотеза → показ текста, принять по Enter/`y`;
- несколько confirmed → нумерованный выбор;
- нет confirmed → прежний ручной ввод без изменений; отказ → ручной ввод.
- confirmed-гипотезы берутся из полной сессии `problem["diagnostic"]` (компактный контекст их не отдаёт).

### UX2: история расследования в состоянии
- `_show_diagnostic_state`: секция «История проверок» (done-шаги: `[id] описание → результат → затронутая гипотеза (статус)`) и «Проверено/Отклонено» (терминальные гипотезы).
- пустая история → блоки не выводятся; лимит показа `_DIAG_HISTORY_LIMIT = 6` + «… и ещё N».

### UX3: AI-подсказка «что дальше»
- новый пункт меню «5. Подсказка «что дальше»» (номера 1–4, 0 не менялись);
- условие: есть открытые гипотезы И нет pending-шагов; иначе «Подсказка недоступна сейчас» без вызова AI;
- reuse `suggest_next_check` + `get_diagnostic_context`; y → `add_check` с обработкой «Выполнили уже?»; ошибки AI → информативное сообщение, graceful.

### Изоляция / ограничения
- Изменён только `src/commands.py` + новый тест-файл. Ядро (`diagnostic.py`, `solve.py`, `problems.py`) и AI-слой не тронуты.
- Номера существующих пунктов меню и старое поведение сохранены (регресс-тесты зелёные без правок).

### Тесты
- `tests/test_diagnostic_ux.py` — **20 тестов** (UX1: 9, UX2: 5, UX3: 6).
- Полный набор: **541 passed** (521 + 20 новых).

## v1.2 Phase 4 — Данные расследования в AI-контексте (v1.2.4)

### Расширение Knowledge Record
- `src/solve.py` — `_build_knowledge_text(problem, diagnostic_context=None)` расширен опциональной секцией «Расследование»:
  - открытые гипотезы `[id] text (AI|вручную) — статус` (открыта/проверена/подтверждена/отклонена)
  - выполненные шаги: `описание → result: outcome → затронутая гипотеза (статус)`
  - вывод (conclusion), если диагностика завершена
  - если диагностики/данных нет — секция не добавляется, текст байт-в-байт идентичен старому
- Новый помощник `_build_investigation_text(problem, diagnostic_context=None)` — `""` при отсутствии данных
- Терминальные гипотезы (confirmed/rejected) отображаются со статусом

### Подача контекста / лимиты
- При `None` данные берутся из `problem["diagnostic"]` → все существующие вызовы (`convert_to_knowledge`) работают **без правок** (сигнатурная совместимость).
- Переиспользован лимит `MAX_SEARCH_RESULTS` (тот же, что у `_compact_diagnostic_context`): гипотезы ≤ `MAX_SEARCH_RESULTS*2`, выполненные шаги ≤ `MAX_SEARCH_RESULTS`.
- Приоритет при обрезке: вывод (всегда сохраняется) > статусы гипотез > результаты шагов.

### Изоляция данных (соблюдено)
- Полный AI-ответ и сырые данные расследования НЕ пишутся в problems.json.
- `src/diagnostic.py`, `src/commands.py`, `src/problems.py` — без изменений.
- read-only: секция строится только на чтении `problem`/`diagnostic`.
- `convert_to_knowledge` (public) не менялся.

### Примечание (отклонение от черновика)
Источником секции служит полная сессия `problem["diagnostic"]`, а не `get_diagnostic_context(problem)`: компактный контекст по дизайну ядра НЕ отдаёт `id` гипотез, привязку шаг→гипотеза и **confirmed**-гипотезы, без которых нельзя отобразить терминальные статусы. `get_diagnostic_context`/`diagnostic.py` не менялись. Лимит обрезки взят из `_compact_diagnostic_context` (`MAX_SEARCH_RESULTS`).

### Тесты
- `tests/test_diagnostic_ai_context.py` — **15 тестов**: регресс байт-в-байт без диагностики; активная диагностика → секция; conclusion при завершении; шаги с результатами → статусы; терминальные confirmed/rejected; лимиты/приоритет вывода; `get_diagnostic_context` readonly; ничего не пишется в problems.json; сигнатурная совместимость (без нового параметра / явный параметр / не-dict); пустая диагностика → без секции; end-to-end `convert_to_knowledge` включает расследование.
- Полный набор: **521 passed** (506 + 15 новых).

## v1.2 Phase 3 — Интеграция диагностики в CLI (v1.2.3)

### Новые функции в `src/commands.py`
- `_show_diagnostic_state(problem)` — печать состояния: открытые гипотезы (`[id] text (AI|вручную)`), pending-шаги проверки, вывод (conclusion), если задан.
- `_diagnostic_add_hypotheses(problem, provider)` — AI: показать `content` + нумерованный список; принять все [y], выбрать номера через запятую, или отказ → ручной ввод (по одной на строку). `success=False`/пустой список → сразу ручной ввод. Ошибки ядра (лимит и т.п.) → показать, не падать. Пустой итог → «Гипотезы не добавлены».
- `_diagnostic_add_check(problem, provider)` — AI-шаг (`suggest_next_check`): показать `content`, y → взять, n → ручной ввод; ошибки ловить. После добавления спросить «Выполнили уже этот шаг?» — при y сразу `complete_check`.
- `_diagnostic_complete_step(problem, step_id=None)` — общий хелпер: показать pending-шаги, выбор по id; ввод результата (`confirmed/rejected/unknown` из `VALID_STEP_RESULTS`) + краткого результата; `complete_check` → показать затронутые гипотезы с новыми статусами. `step_id` можно передать (немедленное выполнение).
- `_diagnostic_loop(problem, provider) -> str | None` — меню: 1 гипотезы, 2 шаг, 3 отметить выполненным, 4 подтвердить причину (завершить), 0 выйти (прогресс сохраняется). Перед меню — состояние. Пункт 4 → `finish_diagnostic` → возвращает conclusion. Ошибки ядра → печать + возврат в цикл.
- `_continue_with_conclusion(problem, provider, conclusion)` — `start_solving` + `_do_solve` с предзаполненной причиной.

### Интеграция в `_investigate_problem`
- Добавлена опция `d` («Диагностика»). Существующие пункты меню (1/2/3) **не перенумеровывались** — 21 тест solve-flow остался зелёным без правок.
- Если `_diagnostic_loop` вернула conclusion → предзаполнить причину в solve.

### Обратимо-совместимая правка solve-ввода причины
- `_do_solve(problem, provider=None, cause_default="")` — опциональный дефолт причины; Enter = принять. Дефолт пустой ⇒ поведение идентично старому.

### Гарантии / ограничения (соблюдены)
- `src/diagnostic.py` — НЕ изменён; публичный API диагностики не тронут.
- `src/solve.py`, `src/problems.py` — без изменений.
- Линейный путь SOLVE без диагностики сохранён.
- Полный AI-ответ НЕ записывается в problems.json.
- Любые ошибки AI/provider → graceful fallback на ручной ввод.
- NullProvider (`success=False`) → ручной путь работает без падения.

### Тесты
- `tests/test_diagnostic_cli.py` — **18 тестов** (по аналогии с test_solve_cli.py, in-memory stdin/stdout через `@patch("src.commands.input")` и temp DATA_FILE):
  - вход в диагностику, пустое состояние; AI-гипотезы (принять все / выбрать по номерам / отказ → вручную); NullProvider → ручной путь; AI-шаг (принятие / отказ → вручную); немедленное выполнение шага → complete_check; завершение существующего pending-шага; неверный id шага → ошибка, цикл продолжается; conclusion → дефолт причины в solve; выход → прогресс сохранён + повторный вход показывает состояние; лимит гипотез → ошибка без падения; регресс старых пунктов меню investigate.
- Полный набор: **506 passed** (488 + 18 новых).

### Обратная совместимость
- SOLVE flow, старые пункты меню investigate, все старые AI-методы — работают как раньше.
- `src/diagnostic.py`, `src/solve.py`, `src/problems.py` — без изменений.

### Важно
- **Phase 4 НЕ начата**: `_build_knowledge_text` не расширен секцией «Расследование».
- API key нигде не сохраняется (код, settings.json, тесты, логи, AI_HANDOFF).

## v1.2 Phase 2 — AI-слой диагностики (v1.2.2)

### Новые методы AIProvider (сигнатуры фиксированы)
```
suggest_hypotheses(problem, diagnostic_context) -> AIResponse
suggest_next_check(problem, diagnostic_context) -> AIResponse
```
- `suggest_hypotheses`: `AIResponse.suggestions` = список строк-гипотез; `content` = пояснение.
- `suggest_next_check`: `AIResponse.content` = описание одного шага проверки; `suggestions` = альтернативные шаги.
- Оба метода **stateless**: НЕ изменяют `Problem` и `diagnostic_context` (readonly).
- `diagnostic_context` — компактный срез расследования из `get_diagnostic_context()` (открытые/отклонённые гипотезы, последние шаги, вывод). Отдельные аргументы `search_results`/`hypotheses`/`steps` не нужны — вся информация уже внутри контекста.

### Архитектура (принцип Core/AI)
- **AI — советник**: возвращает структурированный `AIResponse`, ничего не сохраняет.
- Полный AI-ответ НЕ пишется в problems.json; CLI (Phase 3) будет подставлять предложения в `add_hypotheses`/`add_check`.
- `NullProvider`/`FakeProvider`/`OpenAIProvider` реализуют оба метода; база `AIProvider` бросает `NotImplementedError`.

### Изменения AIProvider (`src/ai/provider.py`)
- Базовый `AIProvider`: +2 абстрактных метода (поднимают `NotImplementedError`).
- `NullProvider`: +2 метода, оба возвращают `AIResponse(success=False, ...)` (локальный режим).
- Существующие 5 методов — без изменений сигнатур.

### Изменения context (`src/ai/context.py`)
- `build_suggest_hypotheses_context(problem, diagnostic_context) -> dict`
- `build_suggest_next_check_context(problem, diagnostic_context) -> dict`
- `_compact_diagnostic_context(diagnostic_context) -> dict` — защитно ограничивает срез (гипотезы/шаги ≤ `MAX_SEARCH_RESULTS`), всегда возвращает полный словарь (`open_hypotheses`, `rejected_hypotheses`, `recent_steps`, `conclusion`).
- Экспорт новых builder'ов в `src/ai/__init__.py`.

### Изменения OpenAIProvider (`src/ai/openai.py`)
- 2 новых метода используют **существующий механизм** `_chat(...)` (один HTTP-клиент, без второго API-слоя).
- `suggest_hypotheses`: промпт просит JSON `{"suggestions": [...], "explanation": "..."}`; парсинг через `_parse_hypotheses_response`.
- `suggest_next_check`: промпт просит JSON `{"check": "...", "alternatives": [...]}`; парсинг через `_parse_next_check_response`.
- Новые приватные помощники: `_clean_suggestions`, `_parse_hypotheses_response`, `_parse_next_check_response`.
- Все ошибки (HTTP/timeout/network/refusal/empty/malformed/no-key) → `success=False` через `_chat` → локальный режим.
- Возвращают `AIResponse` (существующий тип), без новых типов.

### Защита от пустых/дублирующихся suggestions
- `_clean_suggestions`: убирает пустые/нестроковые и дубли (по нормализованному тексту).
- Парсеры устойчивы к плохому JSON: fallback на построчный разбор, никогда не крашат.
- `suggest_hypotheses` с пустым/мусорным ответом → `success=False` (fail-safe).

### fake_provider.py
- +2 метода: `suggest_hypotheses`, `suggest_next_check` (с дефолтными ответами, логом вызовов, поддержкой кастомных ответов).

### Тесты
- `tests/test_diagnostic_ai.py` — **62 теста**: базовый контракт, NullProvider, FakeProvider, context builder, лимиты, парсинг, успешный OpenAI, malformed/empty/refusal, HTTP-ошибки, timeout, network, отсутствие API key, readonly/data isolation, обратная совместимость старых AI-методов, полный цикл диагностики.
- Полный набор: **488 passed** (426 + 62 новых).

### Обратная совместимость
- Старые AI-методы (`analyze_problem`, `analyze_experience`, `create_plan`, `analyze_result`, `format_knowledge`) работают как раньше.
- `NullProvider`, SOLVE flow, `src/diagnostic.py`, `src/solve.py`, `src/commands.py` — без изменений.

### Важно
- **Phase 3 НЕ начата**: `commands.py` не менялся, цикл диагностики в CLI ещё не добавлен.
- API key нигде не сохраняется (код, settings.json, тесты, логи, AI_HANDOFF).

## v1.2 Phase 1 — Ядро диагностики (v1.2.1, справка для Phase 3)

- `src/diagnostic.py` — 10 функций: `open_diagnostic`, `get_diagnostic`, `add_hypothesis`, `add_hypotheses`, `suggest_check`, `add_check`, `complete_check`, `is_diagnostic_active`, `finish_diagnostic`, `get_diagnostic_context`
- Хранится в `problem["diagnostic"]`; `"diagnostic"` в `UPDATEABLE_FIELDS`
- Модель: `Hypothesis` (id, text, status open/confirmed/rejected/tested, confidence, source ai/user/knowledge, created_at, last_tested_step_id); `InvestigationStep` (id, hypothesis_id, description, status pending/done, outcome, result confirmed/rejected/unknown, created_at, completed_at)
- Переходы результата шага → гипотеза: confirmed→confirmed, rejected→rejected, unknown→tested; свободный шаг не меняет гипотезу
- Лимиты: `MAX_OPEN_HYPOTHESES=5`, `MAX_REJECTED=5`, `MAX_RECENT_STEPS=5`, `MAX_HYPOTHESES_PER_SESSION=10`, `MAX_STEPS_PER_SESSION=20`, тексты 200/300/300
- `tests/test_diagnostic.py` — 75 тестов



## Smoke-test OpenAI провайдера (v1.1.1)

**Реальный API-запрос: NOT RUN** — переменная `OPENAI_API_KEY` отсутствует в environment (не считается ошибкой проекта).

**Offline smoke-test: 8/8 PASS**

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

> API key никогда не выводится и не сохраняется. При наличии `OPENAI_API_KEY` реальный smoke-test можно выполнить запросом к `/v1/chat/completions`.

## Завершённые версии

| Версия | Этап | Статус |
|--------|------|--------|
| v0.7 | Структурированные записи знаний | ✅ |
| v0.8 | Поиск с ранжированием | ✅ |
| v0.9.1 | Модель Problem | ✅ |
| v0.9.2 | Бизнес-логика SOLVE | ✅ |
| v0.9.3 | CLI-диалог SOLVE | ✅ |
| v0.9.4 | Интеграция и стабилизация | ✅ |
| v1.0 Phase 1 | AI-ядро (types, provider, context) | ✅ |
| v1.0 Phase 2 | Интеграция AI с SOLVE | ✅ |
| v1.0 Phase 3 | OpenAI провайдер (stdlib) | ✅ |
| v1.0 Phase 4 | Конфигурация AI | ✅ |
| v1.1.0 | OpenAI API compatibility | ✅ |
| v1.1.1 | Smoke-test OpenAI провайдера | ✅ |
| v1.2 | AI Diagnostic SOLVE (дизайн) | 📐 спроектирован |
| v1.2.1 | AI Diagnostic SOLVE Phase 1 (ядро diagnostic.py) | ✅ |
| v1.2.2 | AI Diagnostic SOLVE Phase 2 (AI-слой) | ✅ |
| v1.2.3 | AI Diagnostic SOLVE Phase 3 (интеграция CLI) | ✅ |
| v1.2.4 | AI Diagnostic SOLVE Phase 4 (данные расследования в AI-контексте) | ✅ |
| v1.3.0 | Полировка UX диагностики (UX1 причина, UX2 история, UX3 подсказка) | ✅ |
| v1.3.1–v1.3.3 | Инфраструктура/доки (коммиты по фазам, remote-бэкап, .gitignore, handoff) — код не менялся | ✅ |
| v1.3.5 | Real AI smoke-test: скрипт + прогон (все шаги 403 — OpenRouter security policy) | ⚠️ открыт |
| v1.3.6 | Endpoint/base_url в OpenAIProvider + AIConfig | ✅ |
| v1.3.7 | App-identification headers (HTTP-Referer/X-Title) для OpenRouter | ✅ |

## Результаты тестов (v1.3.7)
```
549 passed in 2.76s
```
- test_problems.py: 43
- test_solve.py: 48
- test_solve_cli.py: 21
- test_search.py: 31
- test_storage.py: 31
- test_router.py: 7
- test_ai.py: 57
- test_solve_ai.py: 39
- test_ai_openai.py: 52
- test_ai_config.py: 22
- test_diagnostic.py: 75
- test_diagnostic_ai.py: 62
- test_diagnostic_cli.py: 18
- test_diagnostic_ai_context.py: 15
- test_diagnostic_ux.py: 20

## Что реализовано в v1.0 Phase 4

### Конфигурация AI

**config/settings.json:**
```json
{
  "academy_root": "G:\\Academy\\Academy-Marketing",
  "ai": {
    "enabled": false,
    "provider": "openai",
    "model": "gpt-4o-mini",
    "timeout": 30
  }
}
```

**src/ai/config.py:**
- `AIConfig` — dataclass (enabled, provider, model, timeout)
- `load_config(path=None)` — загружает из settings.json, safe defaults при ошибке
- `get_ai_provider(config=None, api_key=None)` — фабрика: конфигурация → AIProvider

### Provider factory

```
config → get_ai_provider() → AIProvider
                            ↓
enabled=false → NullProvider
provider=openai → OpenAIProvider(model, timeout)
unknown → NullProvider
error → NullProvider
```

### Автоопределение провайдера

`src/commands.py`:
- `solve_flow(provider=None)` — если provider не передан, загружает из конфигурации
- `solve()` — вызывает `solve_flow()` → автоопределение

**Обратная совместимость:** `solve_flow(provider=FakeProvider(...))` по-прежнему работает для тестов.

### API key

| Источник | Приоритет |
|----------|-----------|
| `api_key=...` в конструкторе | Высокий |
| Переменная окружения `OPENAI_API_KEY` | По умолчанию |
| Нет ключа | OpenAIProvider возвращается, но `success=False` при вызове |

API key **никогда** не хранится в settings.json.

### Defaults

| Параметр | Значение |
|----------|----------|
| enabled | false |
| provider | openai |
| model | gpt-4o-mini |
| timeout | 30 |

Если settings.json отсутствует или повреждён — используются безопасные defaults (AI отключён).

### Fail-safe

| Сценарий | Поведение |
|----------|-----------|
| AI disabled | NullProvider → success=False → SOLVE работает |
| Нет API key | OpenAIProvider → success=False → SOLVE работает |
| Unknown provider | NullProvider → success=False → SOLVE работает |
| Ошибка инициализации | NullProvider → success=False → SOLVE работает |
| settings.json повреждён | Defaults → AI отключён → SOLVE работает |
| settings.json отсутствует | Defaults → AI отключён → SOLVE работает |

### Тесты (22 новых)

| Группа | Кол-во | Что проверяем |
|--------|--------|---------------|
| AIConfig defaults | 1 | Значения по умолчанию |
| load_config | 8 | valid, missing file, invalid JSON, empty, missing ai, ai not dict, partial, None path |
| get_ai_provider | 7 | disabled, enabled+key, no key, unknown, none config, api_key param, init exception |
| Secret isolation | 3 | api_key не в settings, не в repr, не в ошибке |
| SOLVE integration | 3 | disabled config, explicit provider, broken config |

### Архитектура

```
config/settings.json          — настройки AI
src/ai/config.py              — AIConfig, load_config(), get_ai_provider()
src/ai/provider.py            — AIProvider (контракт), NullProvider
src/ai/openai.py              — OpenAIProvider (реальный API)
src/ai/types.py               — AIResponse
src/ai/context.py             — Context builders
src/solve.py                  — ai_*() функции (provider параметр)
src/commands.py               — CLI, auto-detect provider
```

### Безопасность

- API key не хранится в settings.json
- API key не появляется в repr
- API key не появляется в ошибках
- API key не появляется в логах

## Изменённые файлы

| Файл | Изменение |
|------|-----------|
| `config/settings.json` | Добавлена секция `ai` |
| `src/ai/config.py` | Новый: AIConfig, load_config, get_ai_provider |
| `src/commands.py` | +import get_ai_provider, solve_flow() auto-detect |
| `tests/test_ai_config.py` | Новый: 22 теста |
| `src/ai/provider.py` | +2 метода (suggest_hypotheses, suggest_next_check) в AIProvider и NullProvider (v1.2.2) |
| `src/ai/context.py` | +2 builder'а (build_suggest_hypotheses_context, build_suggest_next_check_context), _compact_diagnostic_context (v1.2.2) |
| `src/ai/openai.py` | +2 метода OpenAIProvider, помощники _clean_suggestions/_parse_hypotheses_response/_parse_next_check_response (v1.2.2) |
| `src/ai/__init__.py` | экспорт новых builder'ов (v1.2.2) |
| `tests/fake_provider.py` | +2 метода (v1.2.2) |
| `tests/test_diagnostic_ai.py` | Новый: 62 теста (v1.2.2) |
| `src/diagnostic.py` | Новый: ядро диагностики (v1.2.1), не менялся в v1.2.2/v1.2.3 |
| `src/commands.py` | +цикл диагностики (v1.2.3): _show_diagnostic_state, _diagnostic_add_hypotheses, _diagnostic_add_check, _diagnostic_complete_step, _diagnostic_loop, _continue_with_conclusion; опция `d` в _investigate_problem; _do_solve(+cause_default) |
| `tests/test_diagnostic_cli.py` | Новый: 18 тестов (v1.2.3) |
| `src/solve.py` | +секция «Расследование» (v1.2.4): _build_knowledge_text(+diagnostic_context=None), новый _build_investigation_text; импорт MAX_SEARCH_RESULTS. Остальной solve.py/public API не менялись |
| `tests/test_diagnostic_ai_context.py` | Новый: 15 тестов (v1.2.4) |
| `src/commands.py` | +UX-полировка (v1.3.0): _confirm_cause (UX1), история в _show_diagnostic_state (UX2, _DIAG_HISTORY_LIMIT), _diagnostic_ai_hint + пункт меню 5 (UX3). Ядро/AI-слой не менялись |
| `tests/test_diagnostic_ux.py` | Новый: 20 тестов (v1.3.0) |

## Ограничения

- Нет UI настройки AI
- Нет streaming ответов
- Нет retry при 429
- Нет валидации model name
- Нет валидации timeout range

## Следующий этап

Кодовая база: v1.3 UX-полировка + v1.3.6 endpoint/base_url (545 тестов) реализованы. **Real AI smoke-test открыт**: прогон (v1.3.5) дал 403 `"Access denied by security policy."` со стороны OpenRouter (блок ключа/аккаунта, не код); скрипт `smoke_real_ai.py` готов к перепроверке (`OPENAI_API_KEY` + `OPENAI_BASE_URL`), когда аккаунт/ключ разрешит вызовы.

Следующий этап: **Ожидает решения пользователя**.

Не переходить дальше без явной команды и согласованного ТЗ.

### Инструкции следующей AI-модели

1. **Сначала прочитай `docs/AI_DESIGN.md` и `docs/DIAGNOSTIC_DESIGN.md`** — там вся архитектура
2. Прочитай `AI_HANDOFF.md`, `CHANGELOG.md`, `ROADMAP.md`
3. Используй Python 3.12 (`.venv` создан под него)
4. Запуск: `.\.venv\Scripts\python.exe launcher.py`
5. Тесты: `.\.venv\Scripts\python.exe -m pytest tests -v`
6. Все AI-вызовы опциональны — SOLVE работает без них
7. Не добавляй сторонние зависимости
8. Не меняй существующие тесты (итог на текущий момент — 521)
9. Малые изменения, тесты после каждого изменения
