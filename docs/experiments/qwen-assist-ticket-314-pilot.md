# QWEN_ASSIST: read-only pilot ticket 314

Дата: 2026-09-08.

## Цель

Проверить техническую управляемость Qwen CLI как внешнего worker, а не
реализовать или принять ticket 314.

## Условия

- fixed point проекта: `6b79340202b331cfd69ffc8df687a47b6486f333`;
- отдельная Qwen worktree: `proofloop-ticket-314-recon`;
- режим: `plan`, JSON output и JSON schema;
- лимиты: 12 session turns, 10 минут, 20 tool calls, depth 1;
- prompt запрещал записи, shell, тесты, сеть/MCP, subagents, Git-операции и
  acceptance;
- default Qwen model, без model override и fallback.

## Результат

`QWEN_UNUSABLE`: CLI завершился с exit code `53` после лимита session turns,
не вызвав required structured output. Поэтому `QWEN_RECON_REPORT` отсутствует,
а факты, state owner, callback boundary и acceptance risk не были приняты.

Проверка после вызова показала: основной worktree ticket 355 не получил новых
изменений; в изолированной worktree был только служебный `.qwen-session`.
Ticket 314 не менялся, не запускал тесты и не получил acceptance status.

## Вывод

Не увеличивать лимит автоматически и не открывать patch candidate. Следующий
Qwen-вызов возможен только с уточнённым packet, который сократит область
анализа и приведёт модель к schema-valid terminal report; он всё ещё считается
в общих семи попытках ticket. Перед повтором worktree pilot должна быть
очищена или создана заново.
