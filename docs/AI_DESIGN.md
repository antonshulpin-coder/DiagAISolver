# AI_DESIGN.md — Архитектура AI-слоя v1.0

## 1. Цель

AI-слой превращает Anton Harness из локального каталога в интеллектуального помощника. AI анализирует проблемы, помогает оценить найденный опыт, составляет планы решения и проверяет результаты.

AI — это советник. Harness — это хозяин данных.

---

## 2. Граница Core / AI

```
┌─────────────────────────────────────────────────────┐
│                   HARNESS CORE                      │
│                                                     │
│  Хранит: problems.json, notes.json                  │
│  Управляет: статусами, CRUD, поиском                │
│  Принимает решения: что сохранить, что показать     │
│  Работает без AI: полный локальный режим            │
│                                                     │
│  Модули: storage.py, problems.py, search.py,        │
│          solve.py, commands.py                      │
└──────────────────┬──────────────────────────────────┘
                   │
                   │  AI — советник
                   │  Возвращает структурированный результат
                   │  НЕ изменяет данные напрямую
                   │
┌──────────────────▼──────────────────────────────────┐
│                    AI LAYER                         │
│                                                     │
│  Анализирует: проблему, опыт, результат             │
│  Предлагает: вопросы, причины, план, оценку         │
│  НЕ хранит: ничего (stateless)                      │
│  НЕ знает: о JSON-файлах, статусах, CRUD            │
│                                                     │
│  Модули: src/ai/provider.py, types.py, context.py   │
└─────────────────────────────────────────────────────┘
```

### Правила границы

| Что делает Core | Что делает AI |
|-----------------|---------------|
| Создаёт/изменяет/удаляет записи | Анализирует данные и возвращает мнение |
| Управляет статусами | Предлагает возможные действия |
| Сохраняет в JSON | Не знает о JSON |
| Работает оффлайн | Недоступен → Core работает сам |
| Принимает финальное решение | Предлагает варианты |

### Критический принцип

```
AI возвращает dict:
{
    "success": True,
    "content": "Анализ...",
    "suggestions": ["...", "..."],
    "confidence": 0.8
}

Harness решает:
- показать ли suggestions пользователю
- применить ли какие-то из них
- сохранить ли content как knowledge record
```

AI НЕ должен напрямую:
- изменять problems.json или notes.json
- менять статусы проблем
- создавать записи без подтверждения
- удалять данные

---

## 3. Архитектура

```
src/
├── ai/
│   ├── __init__.py      # экспорт AIProvider, NullProvider
│   ├── provider.py      # AIProvider (base), NullProvider (заглушка)
│   ├── types.py         # AIResponse, AIRequest (dataclasses)
│   ├── context.py       # build_context() — сбор контекста для AI
│   └── openai.py        # OpenAIProvider (конкретный провайдер, опционально)
├── solve.py             # бизнес-логика (ОБНОВИТЬ: вызовы AI)
├── commands.py          # CLI (ОБНОВИТЬ: показ AI-результатов)
└── ...                  # без изменений
```

### Принцип построения модуля `ai/`

- `provider.py` — контракт + заглушка (стандартная библиотека)
- `types.py` — структуры данных (dataclasses из stdlib)
- `context.py` — сбор контекста из данных Core (стандартная библиотека)
- `openai.py` — конкретная реализация (только stdlib + `urllib.request`)

Каждый конкретный провайдер — отдельный файл. Если нужен SDK (например, `openai` pip package), он импортируется ТОЛЬКО в файле провайдера. Core никогда не зависит от SDK.

---

## 4. AIProvider — контракт

```python
# src/ai/provider.py

class AIProvider:
    """Базовый контракт AI-провайдера.

    Все методы возвращают AIResponse.
    Если AI недоступен — возвращают AIResponse(success=False).
    Никогда не бросают исключения наружу.
    """

    def analyze_problem(self, problem, search_results):
        """Анализ новой проблемы.

        Args:
            problem: dict — данные проблемы (title, description, context, error_message, tags)
            search_results: dict — {"knowledge": [...], "problems": [...]}
                            каждый элемент — (record, score)

        Returns:
            AIResponse с:
            - content: анализ проблемы (текст)
            - suggestions: уточняющие вопросы, предполагаемые причины, необходимые проверки
            - confidence: уверенность в анализе (0.0-1.0)
        """
        pass

    def analyze_experience(self, problem, search_results):
        """Анализ найденного опыта.

        Args:
            problem: dict — данные проблемы
            search_results: dict — {"knowledge": [...], "problems": [...]}

        Returns:
            AIResponse с:
            - content: анализ опыта
            - suggestions: наиболее релевантный опыт, возможные решения, предупреждения
            - confidence: уверенность
        """
        pass

    def create_plan(self, problem, cause, similar_solutions):
        """Составление плана решения.

        Args:
            problem: dict — данные проблемы
            cause: str — предполагаемая причина
            similar_solutions: list[str] — решения из похожих проблем

        Returns:
            AIResponse с:
            - content: план решения
            - suggestions: последовательность шагов с ожидаемыми результатами
            - confidence: уверенность
        """
        pass

    def analyze_result(self, problem, solution, helped):
        """Анализ результата решения.

        Args:
            problem: dict — данные проблемы
            solution: str — что было сделано
            helped: bool | None — помогло ли

        Returns:
            AIResponse с:
            - content: анализ результата
            - suggestions: возможная причина, следующий шаг, стоит ли попробовать ещё
            - confidence: уверенность
        """
        pass

    def format_knowledge(self, problem):
        """Помощь в формировании Knowledge Record.

        Args:
            problem: dict — данные проблемы (с cause, solution, helped)

        Returns:
            AIResponse с:
            - content: отформатированный текст для Knowledge Record
            - suggestions: рекомендации по тегам, улучшению описания
            - confidence: уверенность
        """
        pass
```

### NullProvider (заглушка по умолчанию)

```python
class NullProvider(AIProvider):
    """Заглушка — возвращает None для всех методов.

    Используется когда:
    - AI не настроен
    - API-ключ отсутствует
    - AI отключён в настройках
    """

    def analyze_problem(self, problem, search_results):
        return AIResponse(success=False, content="", suggestions=[], confidence=0.0)

    def analyze_experience(self, problem, search_results):
        return AIResponse(success=False, content="", suggestions=[], confidence=0.0)

    def create_plan(self, problem, cause, similar_solutions):
        return AIResponse(success=False, content="", suggestions=[], confidence=0.0)

    def analyze_result(self, problem, solution, helped):
        return AIResponse(success=False, content="", suggestions=[], confidence=0.0)

    def format_knowledge(self, problem):
        return AIResponse(success=False, content="", suggestions=[], confidence=0.0)
```

### Почему именно эти 5 методов

| # | Метод | Когда вызывается | Зачем |
|---|-------|-----------------|-------|
| 1 | `analyze_problem` | После ввода проблемы | Уточнить, найти причины, предложить проверки |
| 2 | `analyze_experience` | После поиска похожего | Оценить релевантность, предупредить о рисках |
| 3 | `create_plan` | Перед решением | Разбить на шаги, определить критерий успеха |
| 4 | `analyze_result` | После решения | Оценить, помогло ли, предложить следующий шаг |
| 5 | `format_knowledge` | При сохранении в базу | Помочь сформулировать итог |

### Почему НЕ fewer

- `analyze_problem` + `analyze_experience` — разные входные данные, разные вопросы
- `create_plan` — отдельный шаг перед решением (не часть анализа)
- `analyze_result` — замыкает цикл (отдельная операция)
- `format_knowledge` —的帮助 при сохранении (отдельная операция)

### Почему НЕ больше

- Нет `search` — поиск делает Core (search.py)
- Нет `store` / `update` — хранение делает Core
- Нет `confirm` — подтверждение делает CLI
- Нет `summarize_history` — статистика делает Core

---

## 5. Структуры данных

### AIResponse

```python
from dataclasses import dataclass, field

@dataclass
class AIResponse:
    """Стандартный ответ AI-провайдера."""
    success: bool                    # True если AI ответил, False если недоступен/ошибка
    content: str                     # Основной текст ответа (анализ, план, рекомендация)
    suggestions: list[str] = field(default_factory=list)  # Конкретные предложения/шаги
    confidence: float = 0.0          # Уверенность (0.0-1.0), 0.0 если AI недоступен
    error: str | None = None         # Описание ошибки (если success=False)
```

**Почему dict, а не Protocol/ABC:**
Малый проект. dataclass из stdlib, никаких зависимостей. Проще сериализовать, логировать, тестировать.

**Почему `suggestions` — список строк:**
Атомарные предложения проще показывать, выбирать, игнорировать. Никакой вложенной структуры.

**Почему `confidence`:**
Позволяет CLI решить, показать ли AI-результат как основной или как «возможное предположение». При низкой уверенности — молча логировать, не показывать.

### AIRequest (внутренний, для context builder)

```python
@dataclass
class AIRequest:
    """Подготовленный контекст для отправки AI."""
    operation: str               # "analyze_problem" / "analyze_experience" / ...
    problem: dict                # Данные проблемы
    search_results: dict | None  # Результаты поиска (если есть)
    extra: dict | None           # Дополнительные данные (cause, solution, helped)
```

---

## 6. Сбор контекста

### Проблема: сколько данных отправлять AI

Отправлять всю базу знаний нельзя:
- Токены стоят денег
- 1000 записей = context overflow
- Большинство записей не релевантны

### Решение: проблема + топ-N результатов

```python
# src/ai/context.py

MAX_SEARCH_RESULTS = 5  # Максимум записей из поиска

def build_analyze_problem_context(problem, knowledge_results, problem_results):
    """Собирает контекст для analyze_problem."""
    return {
        "problem": _compact_problem(problem),
        "similar_knowledge": [_compact_knowledge(r) for r, _ in knowledge_results[:MAX_SEARCH_RESULTS]],
        "similar_problems": [_compact_problem(r) for r, _ in problem_results[:MAX_SEARCH_RESULTS]],
    }

def build_analyze_experience_context(problem, knowledge_results, problem_results):
    """Собирает контекст для analyze_experience."""
    return {
        "problem": _compact_problem(problem),
        "knowledge_options": [_compact_knowledge(r) for r, _ in knowledge_results[:MAX_SEARCH_RESULTS]],
        "problem_options": [_compact_problem(r) for r, _ in problem_results[:MAX_SEARCH_RESULTS]],
    }

def build_create_plan_context(problem, cause, similar_solutions):
    """Собирает контекст для create_plan."""
    return {
        "problem": _compact_problem(problem),
        "cause": cause,
        "similar_solutions": similar_solutions[:3],
    }

def build_analyze_result_context(problem, solution, helped):
    """Собирает контекст для analyze_result."""
    return {
        "problem": _compact_problem(problem),
        "solution": solution,
        "helped": helped,
    }

def build_format_knowledge_context(problem):
    """Собирает контекст для format_knowledge."""
    return {
        "problem": _compact_problem(problem),
        "cause": problem.get("cause", ""),
        "solution": problem.get("solution", ""),
        "helped": problem.get("helped"),
    }


def _compact_problem(problem):
    """Сжимает проблему для передачи AI (без внутренних полей)."""
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

def _compact_knowledge(record):
    """Сжимает Knowledge Record для передачи AI."""
    return {
        "title": record.get("title", ""),
        "type": record.get("type", ""),
        "text": record.get("text", "")[:500],  # Обрезаем длинный текст
        "tags": record.get("tags", []),
    }
```

### Лимиты контекста

| Параметр | Значение | Почему |
|----------|----------|--------|
| MAX_SEARCH_RESULTS | 5 | Достаточно для выбора, не перегружает |
| compact text | 500 символов | AI не нужен полный текст, хватает превью |
| compact problem | все поля | Проблема маленькая, можно всю |

### Строка-системный промпт

AI получает системный промпт, определяющий роль:

```
Ты — AI-помощник для разработчика. Твоя задача — помогать анализировать
технические проблемы и предлагать решения.

Правила:
- Отвечай кратко и по существу
- Если не уверен — скажи об этом (confidence низкий)
- Не выдумывай факты
- Основывайся на переданных данных
- Язык ответа — русский (как у пользователя)
```

Системный промпт хранится в `src/ai/provider.py` как константа.

---

## 7. Fail-safe поведение

### Принцип

AI — это enhancement, не замена. SOLVE работает полностью без AI.

```
AI доступен?
    ├── Да → показать AI-анализ + локальный поиск
    └── Нет → показать локальный поиск (как раньше)
```

### Реализация

```python
# В solve.py / commands.py:

def investigate_problem_with_ai(problem, ai_provider):
    """Расследование проблемы с AI-поддержкой."""
    kr, pr = find_similar(problem)

    # AI-анализ (если доступен)
    ai_response = ai_provider.analyze_problem(problem, {"knowledge": kr, "problems": pr})

    if ai_response.success:
        _show_ai_analysis(ai_response)

    # Локальный поиск (всегда)
    _show_knowledge_results(kr)
    _show_problem_results(pr)

    # Выбор пользователя (как раньше)
    ...
```

### Сценарии отказа

| Сценарий | Поведение |
|----------|-----------|
| AI не настроен (нет ключа) | NullProvider → success=False → SOLVE работает без AI |
| API недоступен (сеть) | Исключение → перехват → success=False → логируем → SOLVE работает |
| API вернул ошибку | success=False, error="..." → показываем ошибку → SOLVE работает |
| API вернул мусор | success=False → логируем → SOLVE работает |
| API слишком медленный | Таймаут 30с → success=False → SOLVE работает |
| AI confidence < 0.3 | Показываем как «возможное предположение» с пометкой |

---

## 8. Конфигурация

### Где хранить настройки

```
config/
├── settings.json     # Путь к Академии + настройки AI
```

### Формат settings.json

```json
{
    "academy_root": "G:\\Academy\\Academy-Marketing",
    "ai": {
        "enabled": true,
        "provider": "openai",
        "model": "gpt-4o-mini",
        "max_completion_tokens": 1000,
        "timeout_seconds": 30
    }
}
```

### API ключ — ТОЛЬКО переменная окружения

```
ANTON_AI_API_KEY=sk-...
```

**Почему не в settings.json:**
settings.json может попасть в Git. API-ключ — секрет.

**Почему не в problems.json / notes.json:**
Данные пользователя отделены от конфигурации.

**Как читать:**

```python
import os

def get_api_key():
    return os.environ.get("ANTON_AI_API_KEY", "")
```

### Как отключить AI

1. `settings.json` → `"ai.enabled": false` — AI полностью отключён
2. Нет переменной `ANTON_AI_API_KEY` — автоматически NullProvider
3. `provider` неизвестен — NullProvider

### Как добавить нового провайдера

1. Создать `src/ai/my_provider.py`
2. Наследоваться от `AIProvider`
3. Реализовать 5 методов
4. Добавить `"my_provider"` в `settings.json` → `ai.provider`

---

## 9. Конкретный провайдер: OpenAI

### Реализация через stdlib

```python
# src/ai/openai.py

import json
import os
import urllib.request
import urllib.error

class OpenAIProvider(AIProvider):
    """Провайдер для OpenAI API через stdlib (без SDK)."""

    API_URL = "https://api.openai.com/v1/chat/completions"

    def __init__(self):
        self.api_key = os.environ.get("ANTON_AI_API_KEY", "")
        self.model = "gpt-4o-mini"
        self.max_completion_tokens = 1000
        self.timeout = 30

    def _call_api(self, messages):
        """Отправка запроса к OpenAI API."""
        if not self.api_key:
            return AIResponse(success=False, error="API key не задан")

        payload = json.dumps({
            "model": self.model,
            "messages": messages,
            "max_completion_tokens": self.max_completion_tokens,
        }).encode("utf-8")

        req = urllib.request.Request(
            self.API_URL,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                content = data["choices"][0]["message"]["content"]
                return AIResponse(success=True, content=content, confidence=0.7)
        except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as e:
            return AIResponse(success=False, error=str(e))

    def analyze_problem(self, problem, search_results):
        ctx = build_analyze_problem_context(problem, search_results.get("knowledge", []),
                                             search_results.get("problems", []))
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Проанализируй проблему:\n{json.dumps(ctx, ensure_ascii=False)}"},
        ]
        return self._call_api(messages)

    # ... остальные методы аналогично
```

### Почему `urllib.request`, а не `requests`

- `requests` — сторонняя зависимость
- `urllib.request` — stdlib, работает без установки
- Для v1.0 достаточно
- В будущем можно заменить на SDK конкретного провайдера

---

## 10. Интеграция с SOLVE

### Текущий поток (v0.9.4)

```
_create_new_problem()
    → input title/desc/context/error/tags
    → create_problem()
    → start_investigation()
    → find_similar()
    → показ результатов
    → выбор пользователя
    → _do_solve()
    → resolve_problem()
    → _ask_convert()
```

### Поток с AI (v1.0)

```
_create_new_problem()
    → input title/desc/context/error/tags
    → create_problem()
    → start_investigation()
    → find_similar()
    → [AI] analyze_problem()          ← НОВОЕ
    → показ AI-анализа + результатов  ← ОБНОВЛЕНО
    → выбор пользователя
    → [AI] analyze_experience()       ← НОВОЕ (опционально)
    → _do_solve()
    → [AI] create_plan()              ← НОВОЕ (опционально)
    → resolve_problem()
    → [AI] analyze_result()           ← НОВОЕ
    → [AI] format_knowledge()         ← НОВОЕ (опционально)
    → _ask_convert()
```

### Ключевые точки интеграции

| Точка | AI-метод | Обязательность | Что показываем |
|-------|----------|----------------|----------------|
| После поиска | `analyze_problem` | Если AI доступен | Анализ + вопросы |
| Выбор решения | `analyze_experience` | Если AI доступен | Оценка вариантов |
| Перед решением | `create_plan` | Если AI доступен + пользователь запросил | План шагов |
| После решения | `analyze_result` | Если AI доступен | Оценка + следующий шаг |
| При сохранении | `format_knowledge` | Если AI доступен + пользователь хочет | Отформатированный текст |

### Как AI-результаты попадают в CLI

```python
# В commands.py:

def _show_ai_analysis(response):
    """Показ AI-анализа в CLI."""
    if not response.success:
        return

    print("\n--- AI-анализ ---")
    print(response.content)

    if response.suggestions:
        print("\nПредложения:")
        for i, s in enumerate(response.suggestions, 1):
            print(f"  {i}. {s}")

    if response.confidence < 0.5:
        print("\n(низкая уверенность — проверьте самостоятельно)")
```

---

## 11. Безопасность

### API ключ

- Хранится ТОЛЬКО в переменной окружения
- Никогда не в JSON, Git, логах
- Читается через `os.environ.get("ANTON_AI_API_KEY", "")`
- Если пустой → NullProvider

### Отправка данных

- AI получает ТОЛЬКО то, что нужно для конкретной операции
- НЕ отправляется: ID проблемы, статус, related_record_id, helped
- НЕ отправляется: полный текст knowledge record (обрезается до 500 символов)
- НЕ отправляется: весь файл notes.json / problems.json

### Логи

- AI-запросы НЕ логируются (содержат данные пользователя)
- Только success/error логируются (без содержимого)

### Возможность отключения

- `"ai.enabled": false` в settings.json → AI полностью отключён
- Нет API-ключа → автоматически NullProvider
- Пользователь может игнорировать AI-предложения в CLI

---

## 12. Тестирование

### FakeProvider

```python
# tests/fake_provider.py

class FakeProvider(AIProvider):
    """Тестовый провайдер с предопределёнными ответами."""

    def __init__(self, responses=None):
        self.responses = responses or {}
        self.calls = []  # Лог вызовов для проверки

    def analyze_problem(self, problem, search_results):
        self.calls.append(("analyze_problem", problem, search_results))
        return self.responses.get("analyze_problem", AIResponse(
            success=True, content="Тестовый анализ", suggestions=["Проверь venv"], confidence=0.9
        ))

    def analyze_experience(self, problem, search_results):
        self.calls.append(("analyze_experience", problem, search_results))
        return self.responses.get("analyze_experience", AIResponse(
            success=True, content="Тестовый опыт", suggestions=["Попробуй pip install"], confidence=0.8
        ))

    def create_plan(self, problem, cause, similar_solutions):
        self.calls.append(("create_plan", problem, cause, similar_solutions))
        return self.responses.get("create_plan", AIResponse(
            success=True, content="Тестовый план", suggestions=["Шаг 1", "Шаг 2"], confidence=0.7
        ))

    def analyze_result(self, problem, solution, helped):
        self.calls.append(("analyze_result", problem, solution, helped))
        return self.responses.get("analyze_result", AIResponse(
            success=True, content="Тестовый результат", suggestions=["Работает"], confidence=0.85
        ))

    def format_knowledge(self, problem):
        self.calls.append(("format_knowledge", problem))
        return self.responses.get("format_knowledge", AIResponse(
            success=True, content="Текст записи", suggestions=["Добавь тег python"], confidence=0.75
        ))
```

### Тест-кейсы

| # | Сценарий | Что проверяем |
|---|----------|---------------|
| 1 | AI доступен, analyze_problem | Показывается анализ + suggestions |
| 2 | AI недоступен (NullProvider) | SOLVE работает без AI |
| 3 | API ошибка (сеть) | success=False → логируем → SOLVE работает |
| 4 | API вернул мусор | success=False → логируем → SOLVE работает |
| 5 | AI confidence низкий | Показываем пометку «возможное предположение» |
| 6 | AI НЕ изменяет данные | После AI-вызова problems.json не изменился |
| 7 | AI НЕ изменяет статусы | Статус проблемы не изменился после AI |
| 8 | Контекст ограничен | AI получает проблему + топ-5, не всю базу |
| 9 | API-ключ не в данных | Ключ не в problems.json / notes.json |
| 10 | FakeProvider вызван | calls логирует все вызовы |

---

## 13. План интеграции

### Этап 1: Ядро AI-слоя (без внешних зависимостей)

```
src/ai/__init__.py      — экспорт
src/ai/types.py         — AIResponse, AIRequest
src/ai/provider.py      — AIProvider, NullProvider, SYSTEM_PROMPT
src/ai/context.py       — build_*_context, _compact_problem, _compact_knowledge
tests/test_ai_types.py  — тесты структур
tests/test_ai_context.py — тесты сбора контекста
tests/test_ai_provider.py — тесты NullProvider + FakeProvider
```

### Этап 2: Интеграция с SOLVE

```
src/solve.py            — новые функции: investigate_with_ai, resolve_with_ai
src/commands.py         — обновление CLI: показ AI-анализа
tests/test_solve_ai.py  — тесты AI-интеграции с FakeProvider
tests/test_solve_cli_ai.py — CLI-тесты с FakeProvider
```

### Этап 3: Конкретный провайдер (опционально)

```
src/ai/openai.py        — OpenAIProvider (urllib.request)
tests/test_ai_openai.py — тесты с моком HTTP
```

### Этап 4: Конфигурация

```
config/settings.json    — секция ai
src/config.py           — загрузка настроек (если ещё нет)
```

---

## 14. План тестирования

### Каждый этап — тесты

| Этап | Тесты | Итого (примерно) |
|------|-------|-------------------|
| v0.9.4 (текущий) | 181 | 181 |
| Этап 1: Ядро AI | +8-12 | ~193 |
| Этап 2: Интеграция | +15-20 | ~210 |
| Этап 3: OpenAI | +5-8 | ~218 |
| Этап 4: Конфигурация | +3-5 | ~223 |

### Покрытие AI-слоя

- AIResponse: создание, значения по умолчанию, optional поля
- NullProvider: все методы возвращают success=False
- FakeProvider: все методы возвращают success=True, логируют вызовы
- context.py: build_*_context, лимиты, compact
- OpenAIProvider: мок HTTP, обработка ошибок, таймаут

### Интеграционные тесты SOLVE + AI

- Полный сценарий: create → investigate (AI) → solve (AI) → convert
- AI недоступен: тот же сценарий без AI
- AI ошибка в процессе: recover → продолжить без AI

---

## 15. Риски

### Риск: AI-dependent UX

**Проблема:** Если AI — основной способ взаимодействия, его отключение ломает UX.

**Решение:** AI — это дополнение, а не замена. Пользователь может полностью игнорировать AI-предложения. CLI работает и без AI.

### Риск: Токены стоят денег

**Проблема:** Каждый AI-вызов — это траты.

**Решение:** 
- Лимит контекста (5 записей, 500 символов)
- Опция отключения AI
- Пользователь выбирает, когда вызывать AI
- NullProvider по умолчанию

### Риск: Медленный API

**Проблема:** OpenAI может отвечать 5-30 секунд.

**Решение:**
- Таймаут 30 секунд
- AI-вызовы опциональны
- Не блокировать основной поток (показать «AI думает...»)
- В v1.0 — синхронно (async не нужен для CLI)

### Риск: Некорректный ответ AI

**Проблема:** AI может выдумать факты, предложить опасные действия.

**Решение:**
- AI-предложения показываются как «возможные варианты»
- Пользователь подтверждает каждое действие
- confidence < 0.5 → пометка «низкая уверенность»
- Harness НЕ применяет AI-предложения автоматически

### Риск: Зависимость от стороннего API

**Проблема:** OpenAI может изменить API, увеличить цены, заблокировать доступ.

**Решение:**
-抽象ный AIProvider — смена провайдера = новый файл
- NullProvider всегда доступен
- Core не зависит от AI

---

## 16. Что сознательно НЕ делаем в v1.0

| Не делаем | Почему |
|-----------|--------|
| Async/await | CLI — синхронный, async усложнит без benefit |
| Streaming ответов | Достаточно показать «AI думает...» и ждать |
| Кэширование AI-ответов | CLI используется редко, кэш не окупается |
| Vector embeddings | Local search уже работает, embeddings — premature |
| Fine-tuning | Нет данных для fine-tuning в v1.0 |
| Мультиязычность AI | Пользователь один, язык один |
| AI-модуль для обучения (LEARN) | Фокус на SOLVE, LEARN — позже |
| AI-модуль для проектов (BUILD) | Ещё не реализован |
| AI-чат / диалог | Одноразовые вызовы, не диалог |
| Промпт-инжиниринг | Минимальный системный промпт, итеративно улучшим |
|rate limiting | CLI для одного пользователя |
| Retry логика | Таймаут + один retry достаточны |

---

## 17. Итого

### Минимальная архитектура

```
src/ai/
├── __init__.py    # экспорт
├── types.py       # AIResponse (dataclass)
├── provider.py    # AIProvider (base), NullProvider
├── context.py     # build_*_context
└── openai.py      # OpenAIProvider (stdlib)
```

### Интеграция

- `solve.py` — 5 точек вызова AI (все опциональны)
- `commands.py` — показ AI-анализа
- `config/settings.json` — настройки AI

### Принципы

- Core владеет данными, AI советует
- AI всегда опционален (NullProvider)
- Без внешних зависимостей в Core
- Без API-ключей в данных
- Малый контекст (5 записей)
- 181+ тестов без регрессий
