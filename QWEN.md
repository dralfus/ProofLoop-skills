# ProofLoop Skills для Qwen Code

Расширение публикует тот же skill `finish-ticket`, что и Codex plugin. Его
единственный канонический lifecycle находится в
`plugins/agentic-development-workflow/skills/finish-ticket/references/task-lifecycle.md`.
Не создавать локальные копии lifecycle в проекте ticket.

Для Qwen Code v0.22.2 используйте короткий запуск:

```text
/finish-ticket ticket <ID или путь>
```

Перед первым role dispatch Controller обязан выполнить Qwen capability
preflight. При любой недоказанной возможности результат —
`BLOCKED_CAPABILITY`, а не self-review или fallback. Для совместимого runtime
применяется `QWEN_CONVERGENT`; Codex сохраняет свою numeric budget policy.
