# QWEN_ASSIST: schema-smoke 2026-09-18

## Цель

Проверить current terminal structured-output contract Qwen Code до нового
read-only recon Ticket 314. Smoke не передавал ticket code и не был evidence
или acceptance Ticket 314.

## Условия

- Qwen Code: `0.24.0`;
- отдельная Qwen-managed worktree;
- `--bare`, `--approval-mode plan`, JSON schema из одного поля;
- 4 session turns, 2 минуты, 0 ordinary tool calls, depth 1;
- запрещены subagents, shell, MCP, extensions и чтение файлов.

## Результат

`INFRASTRUCTURE_BLOCKER`: оба запуска завершились с exit code `1` до первого
turn. `--bare` без auth type дал raw-free причину `No auth type is selected`.
Повтор с явным `--auth-type openai` дошёл до проверки OpenAI-compatible API key
и подтвердил, что ключ не доступен процессу. Ни terminal JSON shape, ни Ticket
314 recon live не запускались.

Каждый запуск создал отдельную Qwen-managed worktree и branch без изменений;
после проверки они были удалены. Основной workspace и Ticket 314 не получили
Qwen diff или test side effects.

## Следующий шаг

Создать Generic Credential текущего Windows-пользователя с target
`ProofLoop/Qwen/OpenAI`. Обёртка передаст secret процессу Qwen только на время
запуска и очистит process environment; после этого допустим один новый benign
schema-smoke. Ticket 314 recon по-прежнему зависит от schema-valid smoke.