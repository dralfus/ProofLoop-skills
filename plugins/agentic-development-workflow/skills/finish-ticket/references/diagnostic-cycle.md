# Разрешённый диагностический цикл

Эта reference применяется только когда Controller получил `REJECTED`, но
`PRIMARY_FAILURE`, `CASCADE_FAILURES` или `IN_SCOPE` нельзя установить по
безопасному наблюдению. Она не заменяет repair-loop, review или независимую
приёмку.

## DIAGNOSTIC_CYCLE_PERMIT

Перед первым diagnostic experiment Controller записывает permit:

```json
{
  "baseline": "<commit или snapshot identity>",
  "scope": ["<разрешённые пути или criterion>"],
  "channel": "<один execution channel>",
  "max_experiments": 1,
  "issued_at": "<RFC 3339 timestamp>",
  "expires_at": "<RFC 3339 timestamp после issued_at>",
  "allowed_changes": ["test-only-diagnostic-patch"],
  "semantic_identity": {
    "security_boundary": "<неизменяемая граница>",
    "ownership": "<неизменяемый owner>",
    "side_effect_semantics": "<неизменяемая семантика>"
  },
  "immutable_guarantees": ["<например fail-closed>"],
  "stop_conditions": ["repeated-diagnostic-fingerprint"],
  "diagnostic_seam": {
    "criterion": "<acceptance criterion>",
    "competing_causes": ["<cause-a>", "<cause-b>"],
    "required_observations": [
      "first_failed_operation",
      "reason_code",
      "observed_result"
    ],
    "comparison_sides": []
  }
}
```

`max_experiments` — целое от 1 до 3. `issued_at` и `expires_at` должны быть
RFC 3339 с timezone; второе время позже первого. Изменение security boundary,
ownership, side-effect semantics, channel, budget, scope, allowed changes или
времени требует нового permit.

`diagnostic_seam` задаёт один criterion, минимум две конкурирующие причины и
минимальный набор raw-free observations. Обязательны
`first_failed_operation` и закрытый `reason_code`; `observed_result` добавляют,
когда без него причины ещё не различимы. Для сравнения `comparison_sides`
либо пуст, либо содержит ровно две уникальные стороны.

## HYPOTHESIS_LEDGER

`hypothesis_ledger` — единственная append-only запись experiment. Нумерация
начинается с 1 и не имеет пропусков. Каждая запись содержит:

- `classification`: `DIAGNOSTIC_PROGRESS`, `REPAIR_FAILURE`, `NEXT_DEFECT`
  или `INFRASTRUCTURE_BLOCKER`;
- `symptom`, `production_boundary`, `hypothesis`, `command`, `outcome` и
  `next_action`;
- для исполнившегося experiment — все `required_observations` seam;
- для seam со сравнением — `comparison` с обеими объявленными сторонами и тем
  же набором raw-free observations.

Запись с `INFRASTRUCTURE_BLOCKER` допустима только с
`target_command_started: false`; она возвращает
`PRE_COMMAND_INFRASTRUCTURE_FAILURE`, не тратит experiment budget и требует
восстановить канал до нового diagnostic experiment.

## Health gate

Fingerprint — упорядоченный набор observations, объявленный seam. Одинаковый
внешний symptom не является повтором, если fingerprint изменился. Два соседних
исполнившихся experiment с одинаковым fingerprint дают
`DIAGNOSTIC_CONTROL_POINT` с причиной
`REPEATED_DIAGNOSTIC_FINGERPRINT`. При исчерпании разрешённых experiment
Controller также возвращает control point и запрашивает design decision, новый
scope или явное разрешение; следующий patch по инерции не запускается.

После resume оставшийся budget сохраняется только при полном равенстве
`resume.permit_identity` и permit: baseline, scope, channel, budget, время,
допустимые изменения, immutable guarantees, stop conditions и semantic identity.
Несовпадение даёт `DIAGNOSTIC_CONTROL_POINT: PERMIT_IDENTITY_MISMATCH` до
запуска команд.

## Проверяемый policy seam

`scripts/validate_plugin.py --diagnostic-cycle <JSON>` — чистая локальная
policy-проверка schema, ledger, budget и health gate. Она не создаёт агентов,
не запускает команды и не интерпретирует model names. JSON fixtures лежат в
`tests/fixtures/diagnostic-cycle/`; они закрепляют новую локализацию при том же
symptom, повтор fingerprint, pre-command infrastructure failure, resume
identity mismatch, неполное сравнение и ошибочную sequence ledger.
