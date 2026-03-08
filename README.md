# Автономный агент разработки (vN pipeline)

Этот репозиторий содержит внешнего Python-агента, который запускается из директории версии проекта (`.../v1`, `.../v2`, ...) и полностью оркестрирует цикл «ТЗ → код → тесты → автоисправления → финализация».

> Важно: запускать агент нужно **из папки версии `vN`**. Сам репозиторий агента должен находиться отдельно от целевого проекта.

---

## Актуальная структура репозитория

```text
.
├── agent.py
├── README.md
├── ARCHITECTURE.md
├── src/
│   ├── __init__.py
│   ├── runner.py
│   ├── llm_client.py
│   ├── version_detector.py
│   ├── context_loader.py
│   ├── memory_manager.py
│   ├── requirements_extractor.py
│   ├── architect.py
│   ├── planner.py
│   ├── structure_planner.py
│   ├── executor.py
│   ├── source_validator.py
│   ├── api_extractor.py
│   ├── tester.py
│   ├── fixer.py
│   ├── project_state.py
│   └── sandbox_guard.py
└── test/
    ├── test_agent_pipeline.py
    └── test_validation_and_api.py
```

---

## Требования к окружению

- Python 3.10+
- `pytest` (для запуска проверок и для этапа валидации в агенте)
- Установленный и доступный в `PATH` `ollama`
- Локальная модель в Ollama: `qwen2.5-coder:14b`

Проверка модели:

```bash
ollama run qwen2.5-coder:14b
```

---

## Быстрый старт

### 1. Подготовьте директорию версии проекта

```bash
mkdir -p projects/my_project/v1/memory
$EDITOR projects/my_project/v1/memory/task.md
```

Минимум, что нужно для старта — файл `memory/task.md`.

### 2. Перейдите в директорию версии

```bash
cd projects/my_project/v1
```

### 3. Запустите агента

```bash
python /path/to/ai-agent/agent.py
```

или из корня этого репозитория:

```bash
python agent.py
```

(если текущая директория уже `.../vN`).

---

## Как работает pipeline

Оркестратор: `src/runner.py`.

1. Определяет версию `vN` и предыдущую `vN-1` (`src/version_detector.py`).
2. Загружает контекст из `memory/` текущей и (при наличии) предыдущей версии (`src/context_loader.py`).
3. Извлекает требования из `task.md` через LLM (`src/requirements_extractor.py`).
4. Генерирует архитектуру (`src/architect.py`).
5. Генерирует пошаговый план (`src/planner.py` → `memory/plan.json`).
6. Формирует структуру файлов (`src/structure_planner.py` → `memory/file_structure.json`).
7. Создает/обновляет `src/*.py` по архитектуре и контексту (`src/executor.py`).
8. Валидирует исходники до тестов (`src/source_validator.py` → `memory/source_validation_report.json`).
9. При ошибках исходников запускает pre-test исправления через LLM (до 4 попыток).
10. Извлекает реальный API из кода через AST (`src/api_extractor.py` → `memory/api_description.json`).
11. Генерирует тесты `tests/test_*.py` по извлеченному API (`src/executor.py`).
12. Запускает `pytest` (`src/tester.py`) и цикл исправлений (`src/fixer.py`) до 12 попыток.
13. Финализирует проект: обновляет `project_state.md`, `context.md`, `bugs.md`, очищает/создает `blocked.md`.

---

## Что пишет агент в `memory/`

Ожидаемые артефакты:

- `task.md` — входное ТЗ
- `requirements.md` — извлеченные требования
- `architecture.md` — архитектурное описание
- `plan.json` — пошаговый план
- `file_structure.json` — структура `src/` и `tests/`
- `source_validation_report.json` — отчет статической проверки исходников
- `api_description.json` — извлеченный API проекта
- `project_state.md` — текущие модули и тесты
- `devlog.md` — журнал этапов pipeline
- `context.md` — итоговый статус после успешного завершения
- `bugs.md` — список активных багов (или их отсутствие)
- `blocked.md` — причина блокировки при неуспешном завершении

Также агент пишет `tests/test_results.md` с выводом последней попытки запуска тестов.

---

## Ограничения и безопасность

- Все операции записи выполняются только внутри текущего `vN`.
- Это обеспечивается `SandboxGuard` (`src/sandbox_guard.py`), который запрещает выход за корень версии.
- `Fixer` применяет патчи только к существующим файлам в `src/` и `tests/`.

---

## Тесты самого агента

Локальный набор тестов находится в `test/`:

```bash
python -m pytest -q
```

Покрываются:

- end-to-end запуск pipeline на временном `vN`
- загрузка контекста предыдущей версии
- статическая валидация исходников
- извлечение API из AST
- классификация ошибок в `Fixer`

---

## Краткая карта модулей

- `agent.py` — точка входа CLI.
- `src/runner.py` — главный orchestration pipeline.
- `src/llm_client.py` — вызов Ollama (`ollama run qwen2.5-coder:14b`).
- `src/version_detector.py` — проверка и парсинг директории `vN`.
- `src/context_loader.py` — загрузка памяти текущей/предыдущей версии.
- `src/memory_manager.py` — запись markdown/json и devlog.
- `src/requirements_extractor.py` — извлечение требований.
- `src/architect.py` — построение архитектуры.
- `src/planner.py` — генерация плана реализации.
- `src/structure_planner.py` — генерация/нормализация структуры файлов.
- `src/executor.py` — генерация модулей, тестов, валидации зависимостей, API extraction.
- `src/source_validator.py` — синтаксис, локальные импорты, top-level `NameError`.
- `src/api_extractor.py` — AST-описание функций/классов/публичных методов.
- `src/tester.py` — запуск `pytest` по релевантным тестам.
- `src/fixer.py` — анализ фейлов и LLM-патчи.
- `src/project_state.py` — сводка по модулям и тестам.
- `src/sandbox_guard.py` — контроль безопасных путей.

