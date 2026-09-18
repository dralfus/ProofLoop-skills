# QWEN_ASSIST: внешний ограниченный worker

`QWEN_ASSIST` — дополнительный инструмент Controller, а не role-agent и не
вариант acceptance authority. Он не заменяет Codex adaptive profile и не
использует legacy-профиль `QWEN_CONVERGENT`.

Перед *каждым* вызовом Controller выполняет capability probe по фактическому
`qwen --help`. Версия CLI не является условием допуска. Обязательны
non-interactive prompt, JSON output и schema, isolated worktree, `plan` mode,
лимиты session turns/wall time/tool calls, `--bare` и исключение subagent tool.
При отсутствии любой возможности результат только `BLOCKED_CAPABILITY` для
этого вызова; fallback-модель и ослабление ограничений запрещены.

До первого ticket recon Controller выполняет benign schema-smoke в clean
worktree без ticket code, shell, тестов, сети/MCP и subagents. Smoke проверяет
только terminal structured-output contract и не является ticket evidence или
acceptance. Для `--output-format json` bridge принимает legacy single JSON
object либо извлекает object из final event `{"type":"result",
"structured_result": {...}}`; transcript, пустой array, не-final result или
не-object result дают `QWEN_UNUSABLE`. Только schema-valid smoke разрешает
следующий уменьшенный recon packet. Непройденный smoke не получает retry по
инерции и останавливает ticket pilot.

Smoke и recon используют `--bare`, чтобы не загружать неявные workspace
customizations. `--safe-mode` запрещён. Для `--auth-type openai` обёртка
читает Generic Credential текущего пользователя с target
`ProofLoop/Qwen/OpenAI`, передаёт его только как `OPENAI_API_KEY` процессу Qwen
и в `finally` восстанавливает прежнее значение либо удаляет переменную. Имя
target допустимо передать параметром; credential, token и raw output не входят
в ticket packet, report или metrics.
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
