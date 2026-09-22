# Qwen Recon Lifecycle Replacement

## Статус

Accepted design for Ticket 21. Документ определяет replacement-модель для
recon lifecycle; реализация начинается только после отдельного review этого
design и implementation plan.

## Цель

Устранить неоднозначность между продолжением старого ledger и запуском новой
independent recon session. Новая модель должна сделать terminal ledger
необратимым, а новую session — неизбежно начинающейся с нового receipt и
пустого genesis ledger.

Protocol contract, Ticket 16 security gates и acceptance authority не меняются.

## Failure mode

Текущий recon policy seam смешивает `continuation` и fresh session:

- новый genesis ledger может пройти без доказанной fresh evidence;
- новый `launch_id` может присоединиться к active старому ledger;
- `continuation` стал частью recon contract;
- terminal и independent-session transitions недостаточно различены.

## Архитектура и seam

Глубокий pure module сохраняется на seam:

```text
qwen_recon_guard_decision(payload: object)
    -> raw-free decision + ledger projection
```

Его interface включает типы, identity binding, state transitions, rejection
reasons и append-only ledger rules. Он сам не запускает процессы и не имеет
acceptance authority.

PowerShell launcher является Adapter: он проверяет CLI/worktree/security gates,
создаёт receipt identities, вызывает Qwen CLI и передаёт structured evidence
в pure module.

## Identity contract

Каждая новая recon session создаёт все identity заново:

```text
receipt_type       = QWEN_RECON_GUARD
mode               = recon
launch_id          = new 32-char lowercase hex identity
session_id         = new 32-char lowercase hex identity
ledger_id          = new 32-char lowercase hex identity
fresh_evidence_id  = new 32-char lowercase hex identity
```

Receipt также сохраняет существующие raw-free fields: version, timestamp,
fixed point, limits, loop detection, extension availability, read-only,
role/subagent/acceptance false, structured output и clean worktree.

`fresh_evidence_id` генерирует launcher. Он не принимается из observation.
Launcher проверяет отсутствие token в локальном raw-free receipt registry;
collision regenerates before writing the receipt. Pure policy receives the
raw-free `used_fresh_evidence_ids` registry projection and fails closed when
the registry is missing or the token is already used for a new genesis ledger.

## Ledger state model

### Genesis

Новая session принимает только:

```json
{
  "ledger": [],
  "ledger_anchor": {
    "ledger_id": "<receipt.ledger_id>",
    "sequence": 0,
    "head_hash": "GENESIS"
  }
}
```

### Active session

Непустой ledger может быть принят только для той же session. Receipt identity
должна в точности совпадать с active ledger identity:

```text
launch_id + session_id + ledger_id + fresh_evidence_id
```

Это same-session append, не continuation operation. В recon interface нет поля
или semantics `continuation`.

### Terminal session

Ledger с terminal event закрыт навсегда. Любой input с таким ledger даёт
`BLOCKED_CAPABILITY / RECON_TERMINAL_LEDGER_CLOSED`, независимо от receipt
identity. Для новой session старый ledger не передаётся: создаются новый
receipt, новый ledger и новый genesis anchor.

Новый receipt с новым `launch_id` не может присоединиться даже к active
неterminal ledger; результат —
`BLOCKED_CAPABILITY / RECON_ACTIVE_LEDGER_LAUNCH_MISMATCH`.

## Recon observation contract

Observation содержит только raw-free runtime facts:

```text
session_id
turns
tool_calls
wall_time_seconds
loop_detected
tool_fingerprint
reproducible_evidence
structured_output_valid
writes
implementation
role_dispatch
subagent_dispatch
acceptance
```

В observation запрещены `continuation` и `fresh_evidence_id`. Policy binds
`session_id` к receipt, а `fresh_evidence_id` — к receipt/первому ledger event.

## Terminal outcomes

- `BLOCKED_CAPABILITY` — identity, anchor, state или security precondition не
  прошла; role dispatch не разрешается.
- `QWEN_RECON_READY` — schema-valid read-only report.
- `QWEN_RUNTIME_GUARD_STOP` — budget, loop или repeated fingerprint; создаётся
  append-only terminal event.
- `QWEN_UNUSABLE` — malformed или forbidden report; session закрывается с
  terminal reason.

Все recon outcomes явно возвращают:

```text
role_dispatch       = false
subagent_dispatch   = false
acceptance          = false
```

## Report schema

Canonical `QWEN_RECON_REPORT` требует поля:

```text
status, baseline, facts, state_owner, callback_boundary,
acceptance_risk, stop_reason, writes
```

`stop_reason` имеет тип `string|null`; `writes` — array of strings. Для
`EVIDENCE_FOUND` требуются `stop_reason=null` и `writes=[]`. Missing, null или
wrong type для `writes` блокируется до `QWEN_RECON_READY`.

## Precise acceptance invariants

1. Recon input с полем `continuation` блокируется; recon code/schema/tests не
   используют это поле.
2. Fresh session принимается только с пустым ledger, genesis anchor и
   `receipt.ledger_id == ledger_anchor.ledger_id`.
3. Fresh session требует новый `launch_id`, `session_id`, `ledger_id` и
   неповторяемый `fresh_evidence_id`.
4. Non-empty active ledger принимается только с тем же exact receipt identity;
   новый launch всегда блокируется.
5. Non-empty terminal ledger всегда блокируется и не может быть продолжен.
6. Hash chain и immutable anchor проверяются до append.
7. Missing/malformed `stop_reason` или `writes` не даёт `QWEN_RECON_READY`.
8. Protocol argv, protocol receipt, Ticket 16 gates и acceptance authority
   остаются неизменными.
9. Missing `used_fresh_evidence_ids` registry projection blocks a new genesis
   session; the current token may appear in that projection only for a same-
   receipt active-session append.

## Focused RED regression matrix

До реализации добавить и запустить следующие RED tests:

| Case | Expected result |
|---|---|
| Fresh receipt + empty genesis ledger + all new identities | `QWEN_RECON_READY` |
| Fresh receipt without `fresh_evidence_id` | `BLOCKED_CAPABILITY` |
| Recon payload containing `continuation` | malformed/forbidden block |
| Terminal ledger + same receipt | `RECON_TERMINAL_LEDGER_CLOSED` |
| Terminal ledger + new receipt | `RECON_TERMINAL_LEDGER_CLOSED` |
| Active ledger + new `launch_id` | `RECON_ACTIVE_LEDGER_LAUNCH_MISMATCH` |
| Active ledger + exact same receipt | same-session append only |
| Receipt/anchor ledger-id mismatch | `RECON_ANCHOR_MISMATCH` |
| Reused `fresh_evidence_id` in receipt registry | `RECON_FRESH_EVIDENCE_REUSED` |
| Report without `stop_reason` or `writes` | launcher `MALFORMED_REPORT` |
| `writes: null` or non-array | launcher `MALFORMED_REPORT` |
| Existing protocol canonical argv | unchanged passing test |

## Current Ticket 20 disposition

### Reuse

- protocol branch and CLI compatibility consumer;
- clean fixed-point worktree gate;
- CLI capability preflight and bounded read-only command flags;
- safe-mode, loop detection, extension, depth and raw-free receipt gates;
- generic hash/event helpers, only where they do not encode recon lifecycle;
- report baseline/facts validation and clean/dirty/capability fixtures;
- existing protocol exact-argv tests.

### Replace

- `_recon_receipt_reason`, `_recon_ledger_reason` and
  `qwen_recon_guard_decision` state transitions;
- recon receipt identity generation;
- recon observation validation/projection;
- lifecycle tests that model `continuation` or accept a new launch on an old
  active ledger;
- recon lifecycle prose in human docs and plugin lifecycle.

### Remove from recon only

- `continuation` field and all continuation branches;
- observation-level `fresh_evidence_id`;
- old reasons `FRESH_SESSION_EVIDENCE_REQUIRED` and
  `FRESH_SESSION_EVIDENCE_REUSED`;
- initial rule that equates `ledger_id` with `launch_id`.

Protocol-side `continuation` remains untouched.

## Measurable success criterion

The replacement is accepted only when:

- every negative matrix case returns non-`READY`;
- zero new launches are accepted with a non-empty old ledger;
- zero terminal ledgers are accepted as input;
- every fresh-session `READY` uses a new receipt and empty genesis ledger;
- no recon-specific implementation, schema or test contains a
  `continuation` field/branch;
- protocol exact-contract tests remain green.
