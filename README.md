# Автономный агент разработки

Этот репозиторий содержит отдельного внешнего агента, который запускается из директории версии проекта `vN` и автоматически создает или обновляет проектные артефакты по ТЗ.

Важно: агент не должен находиться внутри `projects/project_name/vN`.

---

## Файловая система агента

```text
.
├── agent.py
├── README.md
├── agent/
│   ├── __init__.py
│   ├── llm_client.py
│   ├── runner.py
│   ├── version_detector.py
│   ├── context_loader.py
│   ├── memory_manager.py
│   ├── requirements_extractor.py
│   ├── architect.py
│   ├── planner.py
│   ├── executor.py
│   ├── tester.py
│   ├── fixer.py
│   ├── project_state.py
│   └── sandbox_guard.py
└── tests/
    └── test_agent_pipeline.py
```

---

## LLM backend

Агент использует локальный Ollama backend.

Модель:

- `qwen2.5-coder:14b`

Команда вызова:

- `ollama run qwen2.5-coder:14b`

Модуль интеграции:

- `agent/llm_client.py`

LLM используется для:

1. извлечения требований,
2. генерации архитектуры,
3. генерации плана реализации,
4. генерации кода,
5. генерации тестов,
6. исправления ошибок.

Дополнительный артефакт памяти:

- `memory/project_state.md` — краткая сводка текущего состояния проекта (модули и тесты), которую агент добавляет в LLM-промпты.

---

## Как запускать

### 1) Подготовьте структуру проекта

```bash
mkdir -p projects/project_name/v1/memory
$EDITOR projects/project_name/v1/memory/task.md
```

### 2) Перейдите в директорию версии

```bash
cd projects/project_name/v1
```

### 3) Запустите агента

```bash
python /path/to/this/repo/agent.py
```

---

## Что делает агент

1. Определяет текущую версию (`v1`, `v2`, ...).
2. Загружает контекст:
   - `memory` текущей версии,
   - `memory` предыдущей версии (если `N > 1`),
   - входной `memory/task.md`.
3. Извлекает требования через LLM.
4. Генерирует архитектуру через LLM.
5. Создает `memory/plan.json` через LLM.
6. Генерирует и обновляет код в `src/` через LLM с полным контекстом (`task.md`, `requirements.md`, `architecture.md`, `project_state.md`).
7. Генерирует тесты в `tests/` через LLM и отбрасывает тривиальные placeholder-тесты.
8. Запускает тесты и пишет результаты в `tests/test_results.md`.
9. При ошибках запускает цикл автоисправлений через LLM (до 10 попыток).
10. Финализирует проект (`memory/context.md`, `memory/bugs.md`) или создает `memory/blocked.md`.

---

## Архитектура модулей

- `agent.py` — CLI-точка входа.
- `agent/runner.py` — оркестратор pipeline.
- `agent/llm_client.py` — клиент локальной модели Ollama.
- `agent/version_detector.py` — определение версии и предыдущей версии.
- `agent/context_loader.py` — загрузка памяти проекта.
- `agent/memory_manager.py` — запись артефактов memory.
- `agent/requirements_extractor.py` — LLM-извлечение требований.
- `agent/architect.py` — LLM-архитектура.
- `agent/planner.py` — LLM-планирование шагов.
- `agent/executor.py` — LLM-генерация/обновление кода и тестов с учетом полного memory-контекста и проверкой качества тестов.
- `agent/tester.py` — запуск `pytest`.
- `agent/fixer.py` — LLM-исправление ошибок тестов.
- `agent/project_state.py` — построение `memory/project_state.md` по актуальным `src/` и `tests/`.
- `agent/sandbox_guard.py` — ограничение записи внутри текущего `vN`.

---

## Структура целевого проекта после запуска

```text
vN/
  memory/
    task.md
    requirements.md
    architecture.md
    plan.json
    context.md
    devlog.md
    bugs.md
    blocked.md
    project_state.md
  src/
    ...
  tests/
    test_cases.md
    test_results.md
    ...
```

---

## Ограничения безопасности

- Агент пишет файлы только в текущую директорию версии (`vN`) через `SandboxGuard`.
- Изменения за пределами текущей версии запрещены.

---

## Критерий завершения

Разработка завершена, когда:

- шаги `memory/plan.json` выполнены,
- тесты пройдены,
- активных ошибок нет.

Если после 10 попыток исправлений тесты не проходят, создается `memory/blocked.md`.
