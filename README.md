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

Из корня того же clone установите нативное Qwen extension:

```powershell
qwen extensions install .
```

Затем запустите `/finish-ticket ticket <ID или путь>`. Qwen extension публикует
тот же skill и единый canonical lifecycle, а не его копию. Перед role dispatch
обязателен exact capability preflight; неподтверждённая capability означает
`BLOCKED_CAPABILITY`. Процедура полного native `$finish-ticket` pilot находится
в `docs/experiments/qwen-code-v0222-pilot.md`. CLI доступен владельцу; полный
role-lifecycle pilot пока не выполнялся.

Guarded launcher берёт API key из Windows Credential Manager только для
дочернего процесса Qwen и восстанавливает исходный environment сразу после
его возврата — до projection/других subprocess (с `finally` как защитой при
ошибке); ключ не записывается в settings или постоянные receipts.

Для отдельного bounded анализа launcher поддерживает explicit native `recon`
mode: clean fixed-point worktree, `qwen.cmd`, plan-mode tool exclusions,
structured JSON/schema и малый budget. Recon не запускает `/finish-ticket`,
role-agent или acceptance; existing `protocol` argv contract остаётся exact.

Локальный bounded protocol attempt Ticket 18 завершился
`QWEN_COMMAND_FAILED`; исходная причина не установлена, повторного запуска не
было. D050 исправляет raw-free сбор error-envelope evidence: valid fail-closed
projection adapter с exit code `3` больше не теряется как общий unsupported.
Синтетический end-to-end тест проверяет safe classification/counters/exit
codes и отсутствие raw message, но не превращает live attempt в PASS.

Protocol checkpoint continuation использует host-owned terminal receipt:
supervisor владеет child process tree, читает только полные записи временного
`--json-file` sidecar и напрямую запускает только распознанный Node-shim
`qwen.cmd`. Continuation требует `HOST_WALL_LIMIT` или `HOST_TOOL_LIMIT`,
полного `event_coverage=COMPLETE`, закрытого process tree, post-stop
`session_end`, `HOST_CLEAR` от `exact_tool_interaction_cycle_v1` и актуальных
worktree/progress/test/review evidence. `NORMAL_EXIT`, `DETECTED`, `UNKNOWN`,
`INCOMPLETE` и неизвестный wrapper остаются fail-closed. Настройки Qwen и
protocol argv не меняются.
Protocol capability `--help` preflight использует тот же проверенный adapter;
неизвестный `.cmd` отклоняется до исполнения.

Локальная host implementation проверена fake-process/evidence suite; live
multi-repair continuation Ticket 24 остаётся `BLOCKED_EVIDENCE_SOURCE` и пока
`NOT_RUN`: отдельный disposable protocol launch 2026-09-25 завершился
`QWEN_COMMAND_FAILED` до eligible terminal evidence. Counters были unavailable,
`loop_status=UNOBSERVED`, `budget_stop=false`; причина отказа неизвестна.
Локальные fixtures не являются live proof. Исследования native terminal output:
`docs/research/qwen-v0245-terminal-evidence-refresh-20260925.md` и
`docs/research/qwen-v0244-dual-output-terminal-evidence.md`.

## Лицензия

`Unlicense`: материалы можно использовать без ограничений; они поставляются
без гарантий. Полный текст — в `LICENSE`.
