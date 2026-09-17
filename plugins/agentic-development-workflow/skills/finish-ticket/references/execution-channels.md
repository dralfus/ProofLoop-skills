# Execution channels

Execution channel — декларация наблюдаемого поведения одного evidence path, а не имя технологии или платформы. Receipt содержит `channel_id`, `side_effect_policy`, `timeout_seconds`, `identity_required` и `allowed_scope`.

## Закрытая классификация

- `isolated`: неинтерактивный путь без side effects;
- `side-effectful`: путь с контролируемым side effect;
- `interactive`: путь, требующий взаимодействия с пользователем или внешним UI.

Receipt обязан фиксировать фактические booleans `side_effectful` и `interactive`. Controller выводит channel только из них: interactive имеет приоритет над side-effectful. Несовпадение декларации и наблюдения — `CHANNEL_POLICY_VIOLATION`.

До запуска целевой команды environment failure возвращает `INFRASTRUCTURE_BLOCKER/PRE_COMMAND_ENVIRONMENT_FAILURE`, а не verdict о продукте. Для isolated suite каждая транзитивная invocation также должна быть isolated; иначе это `CHANNEL_POLICY_VIOLATION/TRANSITIVE_CHANNEL_MISMATCH`.

Политика валидирует receipt и не выполняет команду, не создаёт retries и не допускает автоматического перехода к acceptance.