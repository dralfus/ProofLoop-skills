# Qwen Code v0.22.2 pilot

Статус: `NOT_RUN`.

Этот документ — воспроизводимая процедура реального pilot, а не
синтетическое live evidence. На машине, где подготовлен репозиторий, Qwen CLI
не найден: `QWEN_CLI=ABSENT`. Поэтому запуск ticket, model identity, role
traces, команды и observed usage не подменяются вымышленными значениями.

## Preconditions

1. Установить Qwen Code **ровно `0.22.2`** и подтвердить `qwen --version`.
2. Из корня этого репозитория установить extension: `qwen extensions install .`.
3. В Qwen открыть `/skills`, убедиться, что виден `finish-ticket`, и в
   `/agents manage` — `finish-ticket-controller`.
4. Выбрать один обычный ticket с воспроизводимым RED command и безопасным
   isolated worktree; не запускать live pilot до exact capability preflight.

## Procedure and required evidence

1. Выполнить `/finish-ticket ticket <ID или путь>` и сохранить exact runtime
   declaration: provider/product/version, configured/active model ID, identity
   lock, named role dispatch, continuation, Reviewer tool policy, verification
   command и observed usage availability.
2. Если declaration неполна, сохранить `BLOCKED_CAPABILITY` и завершить run;
   не продолжать self-review.
3. Для каждого repair candidate сохранить append-only ledger entries
   `local_attempt`, `repair_candidate`, `review_verdict`: fingerprint/root
   cause, RED/hypothesis/GREEN, diff/scope, runtime/model/usage, named
   read-only Reviewer и static verdict.
4. Сохранить один terminal verdict (`DONE`, `REJECTED`, `BLOCKED` или
   `BLOCKED_FOR_DESIGN`) вместе с acceptance/compatibility/full-suite/live
   commands and results. `NOT_AVAILABLE` допустим только для реально
   невыданного usage counter.

## Current evidence

| Field | Observed value |
| --- | --- |
| Qwen CLI discovery | `QWEN_CLI=ABSENT` |
| `qwen --version` | `NOT_RUN` |
| Extension installation | `NOT_RUN` |
| Capability preflight | `NOT_RUN` |
| Repair candidates | `NOT_RUN` |
| Terminal verdict | `NOT_RUN` |
| Runtime/model/role/command/usage trace | `NOT_RUN` |

The JSON fixtures under `tests/fixtures/end-to-end/` are policy evidence only;
they do not claim a live Qwen Code execution.
