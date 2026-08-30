# Жизненный цикл задач Codex

Версия workflow: `1.3`

## Источник истины

Единственный исполняемый протокол находится в
`plugins/agentic-development-workflow/skills/finish-ticket/references/task-lifecycle.md`
и устанавливается вместе с plugin `agentic-development-workflow`.

Этот документ предназначен для человека: он объясняет установку, запуск и
обновление. Копировать его или другие workflow-файлы в проекты разработки не
нужно.

## Установка на текущем или домашнем ПК

После clone репозитория выполните из его корня:

```powershell
codex plugin marketplace add .
codex plugin add agentic-development-workflow@personal
```

На домашнем ПК достаточно clone того же GitHub-репозитория и этих двух команд.
Для обновления pull обновлённый commit и повторите `codex plugin add`; после
обновления откройте новый Codex task, чтобы он загрузил новую версию skill.

## Запуск одного ticket

Открыть корень проекта в Codex и отправить:

```text
Используй $finish-ticket для ticket <ID или путь>.
```

Для paused/partial задачи:

```text
Используй $finish-ticket, чтобы возобновить ticket <ID> по checkpoint
<путь>.
```

Путь рабочей папки, ветку, commit и fixed point Controller определяет сам.
Спецификацию он берёт из ticket; если связь неоднозначна, запрашивает только
недостающий идентификатор.

## Откуда берутся инструкции

- Роли, модели, порядок review/verification, repair-loop и `DONE` — из
  установленного глобального skill.
- Архитектура, coding standards и команды — из существующих инструкций
  проекта.
- Acceptance criteria — из ticket и спецификации.
- Partial state — из checkpoint и текущего diff.

В проект не добавляются `context.md`, `task-lifecycle.md` или копии
`AGENTS.md` из workflow-репозитория.

## Контроль перед расходом лимита

До первого role-agent Controller обязан показать `PREFLIGHT_REPORT`: baseline,
acceptance evidence, риск, модели/effort, ожидаемый scope, targeted feedback
loop, stop gates, design gaps и budget/context counters. Для critical, resumed,
design-gap или неизвестного scope он ждёт подтверждения пользователя. Ordinary
ticket продолжает в опубликованном бюджете.

Обычный ticket имеет 3 role-agent запуска, critical — 4; максимум 1 full suite.
Sol `high` допускается только по записанной причине. Превышение любого лимита
создаёт checkpoint и требует нового явного разрешения.

## Завершение и следующая задача

`DONE` допустим только после независимых `SPEC: PASS`, `CODE_QUALITY: PASS` и
`ACCEPTED`. Для следующего ticket можно оставить тот же Controller, пока его
контекст не смешивает состояния задач. Role-agent tasks после фиксации evidence
можно архивировать.
