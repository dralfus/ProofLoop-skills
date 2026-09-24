# Native Qwen Code `$finish-ticket` pilot

Статус: `NOT_RUN` для полного native role-lifecycle pilot.

Этот документ — воспроизводимая процедура реального pilot, а не
синтетическое live evidence. Владелец подтвердил, что Qwen CLI установлен и
отвечает. Полный pilot с Implementer continuation, независимым Reviewer,
Verifier и terminal verdict ещё не выполнялся. Предыдущее наблюдение
`QWEN_CLI=ABSENT` относилось к более ранней проверке и не описывает текущую
доступность CLI.

## Preconditions

1. Зафиксировать доступные capabilities установленного CLI через ProofLoop
   capability preflight; версия сохраняется как evidence, но не служит
   allow-list.
2. Из корня этого репозитория установить или обновить extension:
   `qwen extensions install .`.
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
| Qwen CLI discovery | `AVAILABLE`; `qwen.cmd` resolved by the bounded capability smoke |
| `qwen --version` | `0.24.4`, exit 0 |
| Extension installation | Local `proofloop-skills` manifest present; native `/skills` and `/agents` discovery not independently verified in this run |
| Capability preflight | `PASS`: 11/11 required recon CLI markers, configured reasoning present, exit 0 |
| Recon pilot | `QWEN_RECON_READY`; launch `3bdb60eef61442fdba7f73467cbba746`, clean baseline `335ba1dc0364e7bb9ac0413925e1a1e8440cb760`, read-only and all dispatch/acceptance flags false |
| Repair candidates | `NOT_RUN` |
| Terminal verdict | `NOT_RUN` |
| Runtime/model/role/command/usage trace | Recon-only trace available; protocol role lifecycle, active server model attestation, and usage counters `NOT_RUN`/`NOT_AVAILABLE` |

The JSON fixtures under `tests/fixtures/end-to-end/` are policy evidence only;
they do not claim a live Qwen Code execution.
