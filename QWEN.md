# ProofLoop Skills для Qwen Code

Личный Qwen Skill `/finish-ticket` и Codex plugin используют общий lifecycle в
`plugins/agentic-development-workflow/skills/finish-ticket/references/task-lifecycle.md`.
Не создавать локальные копии lifecycle в проекте ticket.

Для установленного Qwen Code используйте короткий запуск:

```text
/finish-ticket ticket <ID или путь>
```

Это личный Skill из `~/.qwen/skills/finish-ticket/`. Extension skills вызываются
отдельно как `/<extension-name>:<skill-name>` и не являются его алиасом.
Launcher проверяет только личный `SKILL.md` и `name: finish-ticket` до protocol
dispatch; эта проверка не доказывает runtime-регистрацию Skill в CLI.

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
Версия Qwen записывается как наблюдаемое evidence, но не используется как
allow-list: допуск определяют фактические capabilities и проверки identity,
continuation, tool policy и verification.

## Controlled runtime modes

`recon` и `protocol` — отдельные launcher modes, а не новые lifecycle roles.
`recon` использует малый runtime budget и сохраняет thinking/reasoning,
настроенный оператором; launcher не требует переключателя `--no-thinking`.
`protocol` также использует настроенный reasoning и модельный output budget,
не задавая `QWEN_CODE_MAX_OUTPUT_TOKENS`. Launcher не меняет Qwen settings,
provider или sampling defaults.
В headless stream-json assistant `thinking` blocks допустимы как часть формата,
но их текст отбрасывается и не входит в raw-free evidence или loop fingerprints;
неизвестные/malformed blocks блокируются. Проверяется совместимость схемы, а не
конкретная версия CLI.
Raw-free `QWEN_TERMINAL_OUTCOME` v5 также фиксирует allowlisted CLI bridge stage
при pre-launch failure; exception details и секреты не сохраняются, автоматического
retry по этому evidence нет.
Protocol CLI consumer запускается отдельным PowerShell host; continuation packet
передаётся временным UTF-8 файлом и ограничен `14,000 bytes` для Windows argv.
Последний credential lookup failure локализован на несовпадении Windows identity
agent host и владельца credential; owner-context probe прошёл (D068).

Controller передаёт role packets на английском и требует ответы на русском.
Выбранная модель — операторская configuration, не version allow-list; active
server identity остаётся отдельным evidence limitation.
