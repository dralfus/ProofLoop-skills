# QWEN_ASSIST: внешний ограниченный worker

`QWEN_ASSIST` — дополнительный инструмент Controller, а не role-agent и не
вариант acceptance authority. Он не заменяет Codex adaptive profile и не
использует legacy-профиль `QWEN_CONVERGENT`.

Перед *каждым* вызовом Controller выполняет capability probe по фактическому
`qwen --help`. Версия CLI не является условием допуска. Обязательны
non-interactive prompt, JSON output и schema, isolated worktree, `plan` mode,
лимиты session turns/wall time/tool calls и исключение subagent tool. При
отсутствии любой возможности результат только `BLOCKED_CAPABILITY` для этого
вызова; fallback-модель и ослабление ограничений запрещены.

## QWEN_RECON

Первый режим — read-only анализ из чистой fixed-point worktree. В packet
запрещены записи, shell-команды, тесты, сеть/MCP и subagents. Qwen возвращает
`QWEN_RECON_REPORT`, соответствующий
`qwen-assist-recon.schema.json`. Полезный результат содержит не менее трёх
проверяемых фактов `file:line -> fact`, state owner, callback boundary и один
acceptance risk. Controller сам сверяет факты и отсутствие изменений; report
не является acceptance evidence ticket.

## Health gate

На один ticket суммарно разрешено не более семи Qwen-вызовов всех режимов.
Каждая повторная попытка должна изменить scope, criterion, RED-command либо
hypothesis и добавить новое evidence. Две непрогрессивные попытки подряд или
повтор нормализованной root cause завершают bridge как `QWEN_UNUSABLE` раньше
бюджета. После неудачи Controller уточняет packet, а не повторяет его вслепую.

## Patch candidate

Только после подтверждённого recon допускается candidate в отдельной worktree:
не более двух файлов, 200 изменённых строк и один targeted test. Qwen не делает
commit, merge, cherry-pick, push, full suite или acceptance. Controller
независимо проверяет diff и сам переносит только одобренное изменение.

Полный report остаётся в игнорируемом локальном каталоге проекта. В
`%LOCALAPPDATA%\ProofLoop Skills\qwen-metrics.jsonl` записываются только тип
задачи, outcome, attempts, duration, tool calls и stop reason.
