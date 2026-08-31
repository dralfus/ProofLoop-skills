# Устаревший переносимый файл

Workflow `1.4` не требует `docs/ai-workflow/context.md` в проектах.

Project-specific контекст Controller получает из существующего `AGENTS.md`,
ticket, спецификации и checkpoint. Общий протокол получает из plugin
`agentic-development-workflow` и skill `finish-ticket`.
