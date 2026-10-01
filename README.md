# ProofLoop Skills

ProofLoop Skills определяет повторяемый workflow разработки программного
обеспечения с AI-агентами. Текущая версия протокола — `1.14`.

Для controlled delegation Qwen CLI из Codex используется отдельный
`QWEN_ASSIST`: он имеет только вспомогательную роль и не получает полномочий
на приёмку. Описание запуска находится в `docs/codex-task-lifecycle.md`.

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

## Qwen Code

Нативное Qwen extension из корня clone публикует named controller agent; для
этой отдельной capability его можно установить так:

```powershell
qwen extensions install .
```

Для protocol используйте личный Qwen Skill `/finish-ticket ticket <ID или путь>`
из `~/.qwen/skills/finish-ticket/`. Launcher только читает его `SKILL.md` и
проверяет `name: finish-ticket`; extension manifest для этого режима не нужен.
Extension skills используют отдельный namespaced route
`/<extension-name>:<skill-name>`, который не является алиасом личного Skill.
Preflight наличия файла не доказывает, что текущий CLI действительно загрузил
Skill. Перед role dispatch обязателен exact capability preflight;
неподтверждённая capability означает
`BLOCKED_CAPABILITY`. Процедура native `$finish-ticket` pilot находится в
`docs/experiments/qwen-code-v0222-pilot.md`; актуальный статус попыток — в
`docs/current-state.md`. Успешный полный role lifecycle пока не доказан.

Guarded launcher берёт API key из Windows Credential Manager только для
дочернего процесса Qwen и восстанавливает исходный environment сразу после
его возврата — до projection/других subprocess (с `finally` как защитой при
ошибке); ключ не записывается в settings или постоянные receipts.

Для отдельного bounded анализа launcher поддерживает explicit native `recon`
mode: clean fixed-point worktree, `qwen.cmd`, plan-mode tool exclusions,
structured JSON/schema и малый budget. Recon не запускает `/finish-ticket`,
role-agent или acceptance; existing `protocol` argv contract остаётся exact.

Несколько bounded live protocol attempts завершились без полного terminal/role
evidence; у последнего до D066 (`f923fa88f3c84434a8d517643467cf33`) был exit `1`,
но точная причина неизвестна. D050 исправляет raw-free сбор error-envelope
evidence: valid fail-closed projection adapter с exit code `3` больше не
теряется как общий unsupported. Синтетические тесты проверяют safe
classification/counters/exit codes и отсутствие raw message, но не превращают
live attempt в PASS.

Protocol checkpoint continuation использует host-owned terminal receipt:
supervisor владеет child process tree, читает полные JSONL events из stdout
`--output-format stream-json` и напрямую запускает только распознанный Node-shim
`qwen.cmd`. Protocol передаёт личный `/finish-ticket` через headless `--prompt`;
начальный system event принимается с subtype `init` или `session_start` при
валидном session id, а terminal event — валидный финальный `type=result` или
поддерживаемый `session_end`. Continuation требует `HOST_WALL_LIMIT` или
`HOST_TOOL_LIMIT`, полного `event_coverage=COMPLETE`, закрытого process tree,
post-stop terminal event, `HOST_CLEAR` от `exact_tool_interaction_cycle_v1` и
актуальных worktree/progress/test/review evidence. `NORMAL_EXIT`, `DETECTED`,
`UNKNOWN`, `INCOMPLETE` и неизвестный wrapper остаются fail-closed. Сырые
stream-json payloads удаляются после raw-free projection. Настройки Qwen,
provider/auth, sampling и reasoning не меняются. D059 заменяет прежний выбор
`--prompt-interactive` из D053; контракт не привязан к номеру версии CLI.
Protocol capability `--help` preflight использует тот же проверенный adapter;
неизвестный `.cmd` отклоняется до исполнения.
Для отдельно разрешённой bounded диагностики protocol launcher принимает
`-ShowOutput`; без флага Qwen child output остаётся подавленным. Raw-free
`QWEN_TERMINAL_OUTCOME` v5 хранит стадии запуска, состояние процесса/event file,
режим вывода, при partial JSONL failure — allowlisted counters по полным
валидным prefix records, а при `BLOCKED_CAPABILITY` — отдельный
allowlisted `runtime_projection_reason`. Сырые Qwen строки туда не попадают.
Обычный protocol budget — `20 turns / 20 tool calls / 30m / depth 1`; только отдельный
owner-authorized disposable Ticket 314 test-only pilot может использовать
scope-gated `pilot-expanded` на 40 tool calls. Это не меняет
`model.maxToolCallsPerTurn` или Qwen settings. Partial counters являются только
диагностикой, не terminal/role proof или разрешением на continuation.

Позднейший bounded pilot D068 также остановился на `CREDENTIAL_LOOKUP` до старта
Qwen child. Model-free диагностика установила несовпадение Windows identity
agent host и владельца credential; в PowerShell владельца target доступен.
Полный Qwen E2E не доказан. Следующие live attempts зависят от owner-controlled
host и отдельного решения по недоступному event evidence (D069).

Локальная host implementation проверена fake-process/evidence suite. Live
multi-repair continuation Ticket 24 и native event schema Ticket 25 остаются
`BLOCKED_EVIDENCE_SOURCE`; checkpoint Ticket 26 реализован только локально.
Локальные fixtures не являются live proof. Исследования native terminal output:
`docs/research/qwen-v0245-terminal-evidence-refresh-20260925.md` и
`docs/research/qwen-v0244-dual-output-terminal-evidence.md`.

## Лицензия

`Unlicense`: материалы можно использовать без ограничений; они поставляются
без гарантий. Полный текст — в `LICENSE`.
