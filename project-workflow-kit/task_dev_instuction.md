# Как выполнить одну задачу разработки

Версия workflow: `1.11`

## Один раз на каждом ПК

После clone workflow-репозитория выполните из его корня:

```powershell
codex plugin marketplace add .
codex plugin add agentic-development-workflow@personal
```

На домашнем ПК используйте тот же clone. После обновления plugin откройте новый
Codex task.

## Перед ticket

1. Убедитесь, что в проекте уже есть ticket и связанная спецификация.
2. Откройте корень проекта в Codex Desktop.
3. Создайте или продолжите Controller task.
4. Отправьте:

```text
Используй $finish-ticket для ticket <ID или путь>.
```

Больше ничего в проект копировать не нужно. Controller сам определит рабочую
папку, ветку, commit и fixed point, прочитает project-specific `AGENTS.md`,
ticket и спецификацию, а полный workflow загрузит из глобального skill.

## Контрольная точка перед разработкой

Controller сначала вернёт короткий `PREFLIGHT_REPORT`: ticket/spec, risk,
routing, budget, stop gates/design gaps и next action. Полные acceptance,
`SEAM_FEASIBILITY`, scope и commands остаются в handoff/evidence. Для critical,
resumed, design-gap и неизвестного scope разрешите первый spawn явно. Ordinary
ticket продолжает сам в своём budget.

Controller показывает этот отчёт одной компактной Markdown-таблицей. Если
есть stop gate, он добавляет одну blocking detail строку.

По умолчанию budget: ordinary — 3 role-agent запуска; critical — 4; full suite
— 1. standard `high` является базой критичной реализации. frontier `high`
Controller может выбрать лишь с записанной причиной; превышение budget создаёт checkpoint
и ждёт нового решения.

Implementer получает один компактный `IMPLEMENTATION_PACKET`, а не историю
Controller. Если criterion требует external state, но owner или injected seam
не доказаны, Controller возвращает `BLOCKED_FOR_DESIGN` до первого writer.
Если runtime не сообщает проверяемый inventory (model ID/tier/effort), dispatch,
tool policy или observed usage, Controller возвращает `BLOCKED_CAPABILITY`
до первого spawn и не использует model-name guessing или fallback. Для
совместимого inventory routing записывает requested/selected tier, degradation
flag и reason. Для Codex compatible inventory обязан иметь provenance
`provider: openai` и `source: codex-runtime`; Luna, Terra и Sol — только
примеры registry.

Для Qwen Code v0.22.2 Controller принимает только exact runtime declaration и
одну совпадающую configured/active model identity и lock этой identity для
всех ролей. До dispatch он требует
fresh named subagent, continuation Implementer, fresh read-only Reviewer без
fork/write и executable verification command. Любое отсутствие —
`BLOCKED_CAPABILITY`; observed usage возвращается как `AVAILABLE` либо
`NOT_AVAILABLE`. В `QWEN_CONVERGENT` нет numeric repair cap: local attempt
сохраняет текущий status, а repair candidate append-only фиксирует finding
fingerprint/root cause, RED/GREEN, hypothesis, scope и fresh Reviewer verdict.
Continuation возможна лишь после closure finding, static PASS, отсутствия
regression и unapproved scope. Повтор root cause без нового RED,
`NEW_REQUIREMENT`, `DESIGN_GAP` или scope expansion останавливают loop. Qwen
delivery extension не меняет common lifecycle gates или Codex numeric policy.
Boolean capability обязана быть literal `true`; verification command —
непустой string либо object `{"argv": ["<non-empty argument>", "..."]}`.
Truthy surrogate и пустой command блокируются.

Qwen пользователь устанавливает extension из корня workflow clone через
`qwen extensions install .`, проверяет `/skills` и `/agents manage`, затем
выполняет `/finish-ticket ticket <ID или путь>`. Extension публикует тот же
canonical skill/lifecycle и named `finish-ticket-controller`; не копируйте
lifecycle в проект ticket. Реальный pilot запускается только по процедуре из
`docs/experiments/qwen-code-v0222-pilot.md`; пока CLI отсутствует, evidence
должно оставаться `NOT_RUN`.

Controller сверяет model ID каждого historical `repair_candidate` с configured
Qwen identity; mismatch даёт `MODEL_IDENTITY_MISMATCH`. После valid baseline
любой policy `BLOCKED` оставляет append-only terminal event с непустой reason,
в том числе при insufficient repair evidence.

## После завершения

- `DONE`: сохранить evidence, архивировать role-agent tasks и перейти к
  следующему ticket.
- `BLOCKED_FOR_DESIGN`: не продолжать repair-loop; отдельно утвердить
  отсутствующее design-решение.
- `BLOCKED`: сохранить тип задачи, причину блокировки, тесты, findings,
  попытки и следующий диагностический шаг для общей статистики.

После `DONE`, `REJECTED`, `BLOCKED_FOR_DESIGN`, `BLOCKED` или `BUDGET_GATE`
Controller печатает `TOKEN_USAGE`: observed tokens Implementer/follow-ups и
total ticket. Если Codex не раскрыл счётчики, отчёт содержит `NOT_AVAILABLE`,
а не оценку.

## Разовый аудит test suite

Для ручного read-only аудита используйте отдельный prompt:

```text
Используй $audit-test-suite для измерительного аудита test suite этого проекта.
```

Этот skill не запускается автоматически и не удаляет/пропускает тесты: он
сначала строит карту `test -> risk -> seam` и выдаёт proposals с replacement proof.

## Возобновление

```text
Используй $finish-ticket, чтобы возобновить ticket <ID> по checkpoint
<путь>.
```

Новый Controller сначала проверит partial diff и stop gates. Он не продолжит
старый fix-раунд автоматически.

## Когда менять Controller

Используйте новый Controller, если контекст стал большим, смешаны разные
tickets, существенно обновилась версия workflow либо Controller сам изменял
production-код. Во всех остальных случаях один Controller можно сохранять.
