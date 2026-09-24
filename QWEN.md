# ProofLoop Skills для Qwen Code

Расширение публикует тот же skill `finish-ticket`, что и Codex plugin. Его
единственный канонический lifecycle находится в
`plugins/agentic-development-workflow/skills/finish-ticket/references/task-lifecycle.md`.
Не создавать локальные копии lifecycle в проекте ticket.

Для Qwen Code v0.22.2 используйте короткий запуск:

```text
/finish-ticket ticket <ID или путь>
```

Для каждого запроса на реализацию ticket сначала явно вызывайте установленный
`/finish-ticket` skill и следуйте его canonical lifecycle от начала до terminal
outcome. Не подменяйте lifecycle собственной последовательностью и не
переходите к правкам до предусмотренного skill этапа; если skill или его
обязательные инструкции недоступны, завершайте запуск как
`BLOCKED_CAPABILITY` с raw-free причиной.

Перед первым role dispatch Controller обязан выполнить Qwen capability
preflight. При любой недоказанной возможности результат —
`BLOCKED_CAPABILITY`, а не self-review или fallback. Для совместимого runtime
применяется `QWEN_CONVERGENT`; Codex сохраняет свою numeric budget policy.

## Controlled runtime modes

`recon` и `protocol` — отдельные launcher modes, а не новые lifecycle roles.
`recon` использует малый runtime budget и сохраняет thinking/reasoning,
настроенный оператором; launcher не требует переключателя `--no-thinking`.
`protocol` также использует настроенный reasoning и process-scoped output cap
не ниже 8000. Launcher не меняет Qwen settings, provider или sampling defaults.

Controller передаёт role packets на английском и требует ответы на русском.
Выбранная модель — операторская configuration, не version allow-list; active
server identity остаётся отдельным evidence limitation.
