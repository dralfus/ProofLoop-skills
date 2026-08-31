# Жизненный цикл задач Codex

Версия workflow: `1.7`

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
acceptance evidence, `SEAM_FEASIBILITY` каждого критерия (production entry
point, test seam, RED command, owner), а для изменённой injectable boundary —
production-shaped consumer и compatibility command; риск, модели/effort, ожидаемый scope,
targeted feedback loop, stop gates, design gaps и budget/context counters. Для critical, resumed,
design-gap или неизвестного scope он ждёт подтверждения пользователя. Ordinary
ticket продолжает в опубликованном бюджете.

`PREFLIGHT_REPORT` выводится двумя Markdown-таблицами: первая — ticket,
baseline, risk, scope, budget и next action; вторая — по одному row на
acceptance criterion с production seam, test/RED seam, production consumer/
compatibility command, owner и status. Evidence только с fake seam не достаточно
для изменённой boundary.

Обычный ticket имеет 3 role-agent запуска, critical — 4; максимум 1 full suite.
После `Reviewer FAIL` Verifier ещё не запущен: один scoped fix использует
follow-up Implementer, scoped re-review и затем Verifier в тех же четырёх
critical launches. Role-agent получает только компактный implementation packet.
Sol `high` допускается только по записанной причине. Превышение любого лимита
создаёт checkpoint и требует нового явного разрешения.

## Завершение и следующая задача

`DONE` допустим только после независимых `SPEC: PASS`, `CODE_QUALITY: PASS` и
`ACCEPTED`. Для следующего ticket можно оставить тот же Controller, пока его
контекст не смешивает состояния задач. Role-agent tasks после фиксации evidence
можно архивировать.

После `DONE`, `REJECTED`, `BLOCKED_FOR_DESIGN`, `BLOCKED` или `BUDGET_GATE`
Controller обязан показать `TOKEN_USAGE`: отдельно Implementer/follow-ups,
Controller/Reviewer/Verifier и total ticket. Используются только фактические
usage/trace counters; недоступные значения отмечаются `NOT_AVAILABLE`.
После `REJECTED` он также показывает `FAILURE_SUMMARY`: primary failure,
подтверждённые cascade failures, in-scope verdict и следующий focused loop.

## Ручной аудит test suite

`$audit-test-suite` вызывается только явным пользовательским prompt и не
участвует в обычном lifecycle ticket. Он измеряет duration и flaky evidence,
строит карту `test -> risk -> seam` и готовит proposals с replacement proof.
Он не удаляет тесты, не меняет CI/quarantine и не создаёт agents.
