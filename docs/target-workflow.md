# Целевой workflow

```text
SPECIFICATION
    ↓
ACCEPTANCE CONTRACT
    ↓
PREFLIGHT: RISK + SCOPE + ACCEPTANCE LEDGER + STOP CONDITIONS
    ↓
SEAM FEASIBILITY: ENTRY POINT + TEST SEAM + RED COMMAND + OWNER
    ↓
CHANGED BOUNDARY: PRODUCTION CONSUMER + COMPATIBILITY COMMAND
    ↓
PRE-FLIGHT BUDGET + CONTEXT GATE
    ↓
IMPLEMENTER + TARGETED RED/GREEN
    ↓
IMPLEMENTED
    ↓
INDEPENDENT STATIC REVIEW
    ├─ FAIL/SCOPED_PASS/NEW REQUIREMENT/DESIGN GAP
    │       ↓
    │   ACCEPTANCE_INCOMPLETE / ADJUDICATION
    │       ├─ SCOPED FIX
    │       └─ BLOCKED_FOR_DESIGN
    ↓ PASS
INDEPENDENT VERIFIER
    ↓
TARGETED ACCEPTANCE + ONE FULL SUITE + LIVE EVIDENCE
    ↓
ACCEPTED / REJECTED
    ↓
TOKEN USAGE REPORT
    ↓
DONE / SCOPED FIX / BLOCKED
```

## Владение статусами

Implementer может сообщить:

- `IMPLEMENTED`;
- `BLOCKED`;
- `NEEDS_CLARIFICATION`.

Reviewer сообщает `SPEC` и `CODE_QUALITY`. Verifier сообщает исполняемый
вердикт. Только Controller присваивает:

- `DONE`;
- `BLOCKED_FOR_DESIGN`;
- `BLOCKED`.

## Инварианты

- Только Controller создаёт subagents.
- Role-agents не создают дочерних agents.
- Reviewer выполняется до Verifier.
- `SCOPED_PASS` подтверждает только scoped repair и не открывает Verifier.
- Verifier и full suite запускаются лишь когда каждый criterion acceptance
  ledger имеет implementation и independent review.
- Full suite запускается после статического PASS, а не после каждого fix.
- Новое требование проходит adjudication и не становится автоматическим fix.
- Повтор одной корневой причины во втором раунде останавливает implementation-
  цикл.
- Раунды 3–5 требуют явного разрешения пользователя.
- До первого spawn определяются лимиты role-agent запусков, frontier-эскалаций,
  full suite и context compaction.
- До Implementer каждый acceptance criterion имеет production entry point,
  test seam, red-capable command и owner; иначе ticket блокируется для design.
- Изменённая injectable boundary дополнительно имеет production-shaped consumer
  и compatibility command; fake seam сам по себе не является достаточным evidence.
- User-facing `PREFLIGHT_REPORT` содержит только decision receipt; полные
  feasibility details остаются в packet/evidence и выводятся лишь при stop gate.
- Role-agent получает один компактный `IMPLEMENTATION_PACKET`, а не историю
  Controller или полную спецификацию.
- Обычный ticket имеет бюджет трёх role-agent запусков; критичный — четырёх.
  Продолжение сверх него — новое явное решение пользователя и checkpoint.
- Frontier `high` не является default для критичного ticket: его используют
  после измеримого недостатка standard tier либо для design-adjudication.
- Только Controller создаёт schema-valid `TEST_PERMIT` для UI/Sandbox. Внешний
  runner без технического enforcement работает без доступа к этому каналу.
- `JOB_REJECTED` до запуска теста исправляется follow-up того же Verifier и не
  расходует новый role-agent slot.
- `DONE` требует независимого evidence по каждому acceptance criterion.
- После terminal status или `REJECTED` Controller показывает observed tokens
  Implementer и total ticket; неизвестные provider counters не оцениваются.
- После `REJECTED` Controller отделяет `PRIMARY_FAILURE` от подтверждённых
  `CASCADE_FAILURES` и назначает один focused next loop либо design stop.
- Qwen Code v0.22.2 допускается только после exact capability preflight:
  одна configured identity, fresh named roles, continuation Implementer,
  read-only Reviewer без fork/write и executable verification. `QWEN_CONVERGENT`
  заменяет numeric repair cap append-only ledger: baseline несёт fixed point и
  open findings; local attempt — finding, RED/hypothesis/GREEN; repair candidate
  — diff/scope, references attempts и runtime/model/usage trace; его normalized
  root cause точно совпадает с referenced attempts; review verdict
  — fresh read-only Reviewer, static verdicts, regression/scope flags и closures;
  terminal — reason. Вся history `CONTINUE` валидируется целиком;
  closures должны быть уникальным подмножеством current open findings и
  referenced attempts. Продолжение требует static PASS, отсутствия regression
  и unapproved scope; повтор нормализованной root cause без нового RED,
  `NEW_REQUIREMENT`, `DESIGN_GAP` или scope expansion останавливают loop.
  Qwen delivery extension публикует тот же canonical skill/lifecycle и named
  Controller agent; Codex numeric policy не меняется.

## Следующий эксперимент

Установить plugin `agentic-development-workflow` и применить workflow версии
`1.11` к одному реальному ticket без workflow-файлов в проекте. До реализации
зафиксировать runtime capability declaration, risk, ожидаемый file scope и
stop conditions; при отсутствующей capability подтвердить
`BLOCKED_CAPABILITY`. После завершения сравнить число запусков, тестов,
исправлений и расхода контекста в раннем критичном pilot.
