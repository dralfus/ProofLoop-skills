# QWEN_ASSIST и Ticket 314: факты, причина пилота и продолжение

Дата исследования: 2026-09-18. Область: контролируемый внешний вызов Qwen
из Codex (`QWEN_ASSIST`), а не самостоятельная приёмка ticket Qwen.

## Подтверждённое состояние

- Ticket 314 был выбран только для одного read-only bridge-pilot. Его целью
  было доказать управляемый `QWEN_RECON`, а не реализовать или принять сам
  ticket. Pilot имел fixed point `6b79340202b331cfd69ffc8df687a47b6486f333`,
  отдельную worktree, `plan`, JSON/schema и лимиты 12 turns, 10 минут,
  20 tool calls. См. [локальный pilot](../experiments/qwen-assist-ticket-314-pilot.md)
  и [ticket 4](../../tickets.md).
- CLI действительно был запущен: terminal result — exit code `53` после
  лимита turns. Не был вызван обязательный `structured_output`, поэтому
  schema-valid `QWEN_RECON_REPORT` не появился. Основной worktree не менялся;
  в isolated worktree остался только `.qwen-session`. Это означает не
  «неподключившийся Qwen», а неудачу terminal structured-output contract.
  Raw stdout/stderr того вызова не сохранены в Git, поэтому нельзя честно
  выбрать между тремя нижеследующими причинами.
- Официальная документация Qwen подтверждает семантику exit `53`: при
  `--json-schema` модель либо не вызвала `structured_output`, либо tool был
  запрещён permission rules, либо schema невыполнима. Каждый validation retry
  расходует отдельный turn, а terminal structured-output тоже учитывается
  turn budget. [Structured Output: retries and failures](https://github.com/QwenLM/qwen-code/blob/main/docs/users/features/structured-output.md).
- Qwen Code сейчас имеет release `v0.24.0` (16 сентября 2026), тогда как
  native extension в этом repository описывает `v0.22.2`. Значит, перед новым
  pilot нельзя переносить прежний CLI contract по версии: нужен фактический
  capability probe и отдельная compatibility fixture. [Официальные releases](https://github.com/QwenLM/qwen-code/releases).

## Требуемый минимальный CLI contract

`QWEN_ASSIST` должен использовать single-shot headless invocation `qwen -p`,
не ACP/daemon: именно в этом режиме документированы `--max-session-turns`,
`--max-wall-time` и `--max-tool-calls`. Для read-only recon нужны:

1. `--prompt` / `-p`, `--approval-mode plan`, `--worktree` и явное исключение
   subagent tool; плановый режим запрещает запись и shell. [Headless options](https://github.com/QwenLM/qwen-code-docs/blob/main/website/content/en/users/features/headless.md),
   [approval modes](https://github.com/QwenLM/qwen-code/blob/main/docs/users/configuration/settings.md).
2. `--json-schema` для terminal machine-readable result и schema, маленькая
   enough для первой валидной tool call; schema нельзя запускать внутри
   subagent. [Structured Output restrictions](https://github.com/QwenLM/qwen-code/blob/main/docs/users/features/structured-output.md).
3. `--worktree=<slug>` (form with `=` исключает неоднозначность positional
   prompt). Worktree переключает cwd до первого headless turn; ACP с ней
   несовместим. [Worktree documentation](https://github.com/QwenLM/qwen-code/blob/main/docs/users/features/worktree.md).
4. Наблюдение stdout по документированному формату. В current Qwen
   `--output-format json` — event array, а structured object находится в
   последнем result event как `structured_result`; `stream-json` — JSONL с
   terminal result event. [Headless output format](https://github.com/QwenLM/qwen-code-docs/blob/main/website/content/en/users/features/headless.md).

## Почему bridge пока не готов к повтору без исправления skill

Текущий `scripts/qwen_assist.py` требует в `parse_terminal_json()` единственный
JSON object, но command builder добавляет `--output-format json`.
Официальный current contract для этого mode — JSON array, а не object. Поэтому
даже успешный current structured run, вероятно, будет классифицирован bridge
как `INVALID_JSON_OUTPUT`, пока parser не извлечёт terminal
`structured_result`. Это **новое compatibility finding**, а не доказанная
причина pilot 8 сентября: pilot завершился раньше parser по exit `53`.

Существующий probe также проверяет лишь строки в `qwen --help`; он не
доказывает, что `structured_output` не отключён inherited
`permissions.deny`/`--exclude-tools`, хотя Qwen прямо указывает, что такая
политика скрывает tool и приводит к plain-text/turn-limit failure. См.
[официальное permission gating](https://github.com/QwenLM/qwen-code/blob/main/docs/users/features/structured-output.md).

## Рекомендованный следующий bounded task

Не возобновлять реализацию Ticket 314 и не повышать лимит прежнего запуска.
Следующий task skill должен быть compatibility/smoke pilot на чистой worktree:

1. Собрать и сохранить raw-free receipt: `qwen --version`, exact capability
   declaration, effective permission/tool policy, exit code, turn/tool/wall
   counters и parsed terminal event shape (без prompt/code/path).
2. Добавить fixture current `--output-format json` event array с final
   `structured_result`, затем исправить parser только под этот documented
   shape; existing object-only fixture сохранить как negative case.
3. Выполнить минимальный benign schema smoke (не repo recon): один required
   short field, `plan`, clean worktree, no extension/MCP/subagents, budget
   минимум `N+1` turns. Если он не вернул terminal object — зафиксировать
   конкретный official failure hint и остановиться.
4. Только после successful smoke сделать второй `QWEN_RECON` Ticket 314 с
   уменьшенным packet (три заранее выбранных files/criteria), fresh worktree и
   теми же no-write/no-shell gates. Это остаётся попыткой bridge и не является
   acceptance evidence Ticket 314.

Этот порядок использует Qwen максимально там, где её результат можно
технически ограничить и проверить, сохраняя acceptance authority у Codex. Он
согласуется с [bridge specification](../specs/qwen-assist-bridge.md),
[canonical QWEN_ASSIST reference](../../plugins/agentic-development-workflow/skills/finish-ticket/references/qwen-assist.md)
и текущей реализации [runner](../../scripts/qwen_assist.py).
