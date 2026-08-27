# SOLVE_DESIGN.md — Архитектурный план v0.9

## 1. Цель

Режим SOLVE — главный рабочий механизм Anton Harness. Пользователь сталкивается с реальной проблемой, Harness помогает:

```
ПРОБЛЕМА → структурирование → уточнение → поиск похожего опыта → анализ → план → проверка → сохранение
```

SOLVE превращает каждый решённый случай в ценное знание для будущих проблем.

---

## 2. Пользовательский сценарий

```
=== РЕШЕНИЕ ПРОБЛЕМЫ ===

--- Шаг 1: Опишите проблему ---

Заголовок: Ошибка Python в vscode
Описание: При запуске кода возникает ModuleNotFoundError: No module named 'flask'
Контекст: Windows 11, Python 3.12, VSCode, venv
Текст ошибки: ModuleNotFoundError: No module named 'flask'
Теги: python, flask, vscode

--- Шаг 2: Поиск похожих ---

Найдено в базе знаний (2):
  1. [note] Bug in Flask — Server crashes on startup
  2. [note] Python guide — Learn Python

Найдено в базе проблем (1):
  1. [solved] Flask import error — Виртуальное окружение не активировано

--- Шаг 3: Действие ---

1. Использовать найденное решение
2. Продолжить — записать своё решение
3. Пропустить — сохранить как есть

Выберите: 2

--- Шаг 4: Решение ---

Причина: venv не был активирован в терминале VSCode
Решение: Активировал venv командой .\.venv\Scripts\activate
Помогло: да
Записать в базу знаний? (да/нет): да

--- Готово ---
Проблема решена и сохранена в базу знаний.
ID: abc123def456
```

---

## 3. Модель данных

### Problem

```python
{
    "id": "a1b2c3d4e5f6",          # uuid4 hex, 12 символов
    "created_at": "2026-08-27...",  # ISO 8601
    "title": "Ошибка Python",      # короткое описание
    "description": "При запуске...", # что произошло
    "context": "Windows 11...",     # среда, окружение
    "error_message": "Module...",   # текст ошибки (пусто если нет)
    "tags": ["python", "flask"],    # ключевые слова
    "status": "new",                # текущее состояние
    "solution": "",                 # что_FIXED (заполняется при решении)
    "cause": "",                    # причина (заполняется при решении)
    "helped": null,                 # помогло ли (bool/None)
    "related_record_id": null       # ID записи в базе знаний (если создана)
}
```

**Почему отдельные поля:**
- `title` — быстрый обзор (аналог title в knowledge records)
- `description` — подробное описание для поиска
- `context` — важен для повторения решения (среда, версии, ОС)
- `error_message` — точный текст ошибки для поиска
- `cause` — что оказалось корнем проблемы
- `solution` — что было сделано
- `helped` — факт успешности (для статистики и фильтрации)
- `related_record_id` — связь с knowledge record (если решение сохранено)

### Сравнение с Knowledge Record

| Поле | Knowledge Record | Problem |
|------|------------------|---------|
| id | + | + |
| created_at | + | + |
| title | + | + |
| text | + | description + solution |
| tags | + | + |
| type | note/bookmark/idea/problem | — (всегда problem) |
| context | — | + |
| error_message | — | + |
| status | — | + |
| solution | — | + |
| cause | — | + |
| helped | — | + |

---

## 4. Жизненный цикл

```
new → investigating → solving → solved / failed
                                        ↓
                                    archived
```

| Состояние | Описание | Переходы |
|-----------|----------|----------|
| `new` | Проблема только что описана | → investigating |
| `investigating` | Ищем причину, пробуем решения | → solving, → failed |
| `solving` | Знаем причину, применяем решение | → solved, → failed |
| `solved` | Проблема решена | → archived |
| `failed` | Не удалось решить | → archived |
| `archived` | Бывшая проблема, больше не актуальна | — |

**Почему не больше состояний:**
Малый проект. Пять состояний покрывают реальный flow. Добавление `waiting`, `blocked`, `reopened` premature для текущего масштаба.

---

## 5. Архитектура модулей

```
src/
├── main.py          # точка входа (без изменений)
├── menu.py          # главное меню (без изменений)
├── router.py        # маршрутизация (обновить: solve → solve_flow)
├── commands.py      # CLI команд (обновить: solve() → полный диалог)
├── storage.py       # CRUD knowledge records (без изменений)
├── search.py        # ранжирование (без изменений)
├── problems.py      # CRUD проблем (НОВЫЙ)
├── solve.py         # бизнес-логика SOLVE (НОВЫЙ)
└── ui.py            # заголовок (без изменений)
```

### Новые модули

#### `src/problems.py` — Хранение проблем

Аналог `storage.py`, но для `data/problems.json`.

Функции:
- `load_problems()` → list[dict]
- `save_problems(problems)`
- `create_problem(title, description, context, error_message, tags)` → dict
- `get_problem(problem_id)` → dict | None
- `get_all_problems()` → list[dict]
- `update_problem(problem_id, **fields)` → dict | None
- `delete_problem(problem_id)` → bool
- `search_problems(query)` → list[dict]

Использует ту же модель хранения (JSON), те же паттерны (tmp-файл, StorageError).

#### `src/solve.py` — Бизнес-логика SOLVE

Чистая логика без CLI. Оркестрирует workflow.

Функции:
- `build_search_query(problem)` → str — формирует поисковый запрос из полей проблемы
- `find_similar(problem, knowledge_records, problems)` → list[(record, score)] — ищет похожее
- `resolve_problem(problem_id, cause, solution, helped)` → dict — фиксирует решение
- `archive_problem(problem_id)` → dict — перемещает в archived
- `problem_to_knowledge_record(problem)` → dict — конвертирует решённую проблему в knowledge record
- `get_stats(problems)` → dict — статистика (сколько решено, сколько не решено)

---

## 6. Поток SOLVE

```
solve_flow() в commands.py
    │
    ├── Меню SOLVE
    │   ├── 1 → Новая проблема (_create_new_problem)
    │   ├── 2 → Продолжить существующую (_continue_existing_problem)
    │   └── 0 → Назад
    │
    ├── Новая проблема (_create_new_problem)
    │   ├── Шаг 1: Ввод проблемы (заголовок, описание, контекст, ошибка, теги)
    │   ├── Шаг 2: Автоматически new → investigating
    │   ├── Шаг 3: Поиск похожего (find_similar → knowledge + problems)
    │   ├── Шаг 4: Выбор
    │   │   ├── 1 → Использовать найденное решение
    │   │   ├── 2 → Продолжить самостоятельно
    │   │   └── 3 → Сохранить и выйти (оставить investigating)
    │   └── Шаг 5: Решение (причина, решение, помогло ли)
    │
    └── Продолжить существующую (_continue_existing_problem)
        ├── Показать активные проблемы (investigating/solving/failed)
        ├── Выбор проблемы
        └── Обработка по статусу:
            ├── investigating → _investigate_problem (поиск → выбор)
            ├── solving → quick resolve (отметка solved/failed)
            └── failed → повтор / архив / конвертация
```

---

## 7. Интеграция с поиском

### Формирование поискового запроса

```python
def build_search_query(problem):
    parts = []
    if problem["title"]:
        parts.append(problem["title"])
    if problem["error_message"]:
        parts.append(problem["error_message"])
    if problem["tags"]:
        parts.extend(problem["tags"])
    return " ".join(parts)
```

**Почему так:** Поиск в `search.py` работает по title, text, tags. Мы собираем ключевые слова из всех доступных полей проблемы. Description намеренно не включается — он слишком длинный и снизит точность поиска.

### Где искать

1. **База знаний** — `search_records_with_scores(query)` — ищет по title/text/tags
2. **База проблем** — `search_problems(query)` — ищет по title/description/error_message/tags

### Показ результатов

```
Найдено в базе знаний (2):
  1. [note] Bug in Flask (score: 12.4) — Server crashes on startup
  2. [solved] Flask error (score: 8.2) — Виртуальное окружение не активировано

Найдено в базе проблем (1):
  1. [solved] Flask import error — Виртуальное окружение не активировано
```

Score показывается только для отладки (архитектурно доступен, но не обязателен).

### Когда искать

- Сразу после ввода проблемы (шаг 2)
- Можно повторить поиск позже (через подменю)

---

## 8. Сохранение результата

### Фиксация решения

```python
def resolve_problem(problem_id, cause, solution, helped):
    problem = get_problem(problem_id)
    if not problem:
        return None
    
    fields = {"cause": cause, "solution": solution, "helped": helped}
    
    if helped is True:
        fields["status"] = "solved"
    elif helped is False:
        fields["status"] = "failed"
    # helped=None → статус не меняется
    
    return update_problem(problem_id, **fields)
```

### Конвертация Problem → Knowledge Record

```python
def problem_to_knowledge_record(problem):
    text_parts = []
    if problem["description"]:
        text_parts.append(problem["description"])
    if problem["context"]:
        text_parts.append(f"Контекст: {problem['context']}")
    if problem["cause"]:
        text_parts.append(f"Причина: {problem['cause']}")
    if problem["solution"]:
        text_parts.append(f"Решение: {problem['solution']}")
    if problem["error_message"]:
        text_parts.append(f"Ошибка: {problem['error_message']}")

    return create_record(
        title=f"[resolved] {problem['title']}",
        text="\n\n".join(text_parts),
        record_type="solution",
        tags=problem["tags"],
    )
```

**Почему `type="solution"`:** Отличает решённые проблемы от обычных записей. Позволяет фильтровать и искать именно решения.

---

## 9. Подготовка к AI

### Интерфейс (минимальный)

```python
# src/solve.py

class AIProvider:
    """Провайдер AI-анализа. По умолчанию — заглушка."""

    def analyze_problem(self, problem):
        """Анализ проблемы. Возвращает None (без AI)."""
        return None

    def suggest_solution(self, problem, similar_records):
        """Предложить решение. Возвращает None (без AI)."""
        return None
```

### Как будет использоваться

```python
def solve_flow():
    problem = collect_problem()
    similar = find_similar(problem, ...)

    # Шаг 3: AI может предложить решение
    ai_suggestion = ai_provider.suggest_solution(problem, similar)
    if ai_suggestion:
        print(f"AI предлагает: {ai_suggestion}")
```

### Почему не ABC/Protocol

Малый проект. Обычный класс с методами, возвращающими None. Когда AI будет подключён — наследуемся и переопределяем. Никаких абстракций, зависимостей, регистров.

---

## 10. План реализации

### Этап 1: Модель и хранение ✅ (v0.9.1)
- `src/problems.py` — CRUD для проблем
- `data/problems.json` — хранение
- 43 теста для problems.py

### Этап 2: Бизнес-логика ✅ (v0.9.2)
- `src/solve.py` — build_search_query, find_similar, resolve_problem, convert_to_knowledge
- 48 тестов для solve.py

### Этап 3: CLI ✅ (v0.9.3)
- `src/commands.py` — solve_flow с полным диалогом
- `src/router.py` — подключён solve_flow
- 10 CLI-тестов

### Этап 4: Интеграция и стабилизация ✅ (v0.9.4)
- Меню SOLVE: новая проблема / продолжить существующую
- Продолжение investigating/solving/failed
- Повтор попыток для failed
- helped=None с предложением повтора
- Улучшена конвертация (статус + результат в тексте)
- 21 CLI-тест (итого 181)

### Этап 5: Документация ✅
- AI_HANDOFF.md, CHANGELOG.md, ROADMAP.md, SOLVE_DESIGN.md

---

## 11. План тестирования

### tests/test_problems.py (43 теста)
- Создание проблемы (title, description, context, error_message, tags)
- Уникальность ID
- Даты (ISO, актуальность)
- Значения по умолчанию (status, solution, cause, helped, related_record_id)
- Получение (существующая, несуществующая)
- Обновление (все поля, включая helped: true/false/None)
- Удаление (существующая, несуществующая, только целевая)
- Поиск (по title, tags, error_message, пустой запрос, без совпадений, с оценками)
- Загрузка/сохранение (повреждённый JSON, отсутствующий файл, неправильный тип, атомарная запись)
- Все статусы acceptable

### tests/test_solve.py (48 тестов)
- build_search_query: пустая проблема,缺少 поля, только теги, title+error, title+error+tags, только title
- find_similar: пустой запрос, находит knowledge, находит problems, не находит, оценки в результатах
- start_investigation: new→investigating, investigating отклонён
- start_solving: investigating→solving, new отклонён
- resolve_problem: solving→solved/failed, helped=True/False/None, несуществующая, new отклонён
- Недопустимые переходы: archived без переходов, failed→solving разрешён, и др.
- archive_problem: solved→archived, failed→archived
- convert_to_knowledge: создаёт запись, дубликат запрещён, несуществующая, не resolved, связь, текст включает поля
- get_problem_summary: несуществующая, отражает статус, ожидаемые ключи
- Таблица переходов: все проверки

### tests/test_solve_cli.py (21 тест)
- Делегирование: solve() → solve_flow()
- Меню SOLVE: выход (0), неверный выбор
- Новая проблема: пустой заголовок, выход из investigation, happy path, helped=no, helped=None, helped=None с повтором, неверный выбор, KeyboardInterrupt, SolveError, использование найденного решения
- Продолжение: investigating, solving→solved, solving→failed, failed→повтор, failed→архив, failed→конвертация, нет активных, отмена

### tests/test_search.py (25 тестов)
- Normalize, tokenize, rank_records

### tests/test_storage.py (31 тест)
- Миграция, загрузка, сохранение, CRUD, поиск

### tests/test_router.py (7 тестов)
- Все варианты route()

---

## 12. Риски и спорные решения

### Риск: Два JSON-файла (notes.json + problems.json)
**Аргументы за:** Разные модели, разная жизнь цикла, проще управлять.
**Аргументы против:** Два файла — два хранилища, сложнее бэкап.
**Решение:** Два файла. Это малый проект, простота разделения важнее统一性.

### Риск: AIProvider как заглушка
**Аргументы за:** Минимальная абстракция, готовность к расширению.
**Аргументы против:** Мёртвый код.
**Решение:** Оставить. Класс из 6 строк не создаёт нагрузки.

### Риск: problem_to_knowledge_record может создать дубликат
**Аргументы за:** Решённая проблема = ценное знание.
**Аргументы против:** Может засорить базу знаний.
**Решение:** Пользователь подтверждает сохранение. Префикс `[resolved]` в заголовке.

### Спорное: description не включается в поисковый запрос
**Почему:** Длинный текст снижает точность поиска по подстроке. Лучше искать по title + error_message + tags.
**Альтернатива:** Включить первые N слов description. Пока не делаем — можно добавить позже.

### Спорное: Нет состояния "paused"
**Почему:** Проблему можно просто не закрывать. Статус `investigating` уже покрывает случай "я вернусь позже".
