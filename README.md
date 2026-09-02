# ProofLoop Skills

ProofLoop Skills определяет повторяемый workflow разработки программного
обеспечения с AI-агентами.

## Цели

Workflow должен предотвращать два наблюдаемых failure modes:

1. ложное завершение — Implementer объявляет ticket готовым при пропущенных
   требованиях, заглушках или недостаточном evidence;
2. нездоровый repair-loop — независимая проверка порождает повторяющиеся
   исправления, архитектурное проектирование внутри implementation-цикла,
   вложенных subagents и чрезмерный расход контекста.

## Основной принцип

Агент, реализовавший ticket, не принимает собственную работу. Независимость
проверки сохраняется, но цикл останавливается раньше абсолютного лимита, если
повторяется одна корневая причина или обнаружен design gap.

## Текущий стек

- Codex;
- mattpocock/skills для требований, спецификации и декомпозиции;
- Superpowers для целевого TDD, диагностики и проверки;
- multi-agent orchestration под единоличным управлением Controller.

OpenSpec пока не входит в стандартный workflow.

## Основные документы

- `docs/current-state.md` — наблюдаемые проблемы и текущая гипотеза;
- `docs/target-workflow.md` — целевая последовательность;
- `docs/codex-task-lifecycle.md` — описание запуска и сопровождения протокола;
- `docs/decisions.md` — принятые архитектурные решения;
- `plugins/agentic-development-workflow/` — устанавливаемый Codex plugin с
  `finish-ticket` и manual-only `audit-test-suite` skills;
- `project-workflow-kit/task_dev_instuction.md` — инструкция человеку без
  копирования workflow-файлов в проекты.

## Быстрый запуск

Подключите marketplace из локального clone этого репозитория и установите
plugin:

```powershell
codex plugin marketplace add .
codex plugin add agentic-development-workflow@personal
```

Подробности, включая перенос репозитория на GitHub, — в
`docs/codex-task-lifecycle.md` и `docs/github-porting.md`. ZIP и PowerShell
installer больше не являются штатным способом установки.

Перезапустите Codex, откройте проект и отправьте:

```text
Используй $finish-ticket для ticket <ID или путь>.
```

Skill читает протокол из собственного глобального каталога. В проекте нужны
только его обычные инструкции, ticket, спецификация и код.

Для разового read-only аудита тестов, который не вызывается автоматически:

```text
Используй $audit-test-suite для измерительного аудита test suite этого проекта.
```

## Qwen Code v0.22.2

Из корня того же clone установите нативное Qwen extension:

```powershell
qwen extensions install .
```

Затем запустите `/finish-ticket ticket <ID или путь>`. Qwen extension публикует
тот же skill и единый canonical lifecycle, а не его копию. Перед role dispatch
обязателен exact capability preflight; неподтверждённая capability означает
`BLOCKED_CAPABILITY`. Процедура реального pilot и текущее честное состояние
`NOT_RUN` находятся в `docs/experiments/qwen-code-v0222-pilot.md`.

## Лицензия

`Unlicense`: материалы можно использовать без ограничений; они поставляются
без гарантий. Полный текст — в `LICENSE`.
