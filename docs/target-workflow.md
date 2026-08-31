# Целевой workflow

```text
SPECIFICATION
    ↓
ACCEPTANCE CONTRACT
    ↓
PREFLIGHT: RISK + SCOPE + STOP CONDITIONS
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
    ├─ FAIL/NEW REQUIREMENT/DESIGN GAP
    │       ↓
    │   ADJUDICATION
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
- Full suite запускается после статического PASS, а не после каждого fix.
- Новое требование проходит adjudication и не становится автоматическим fix.
- Повтор одной корневой причины во втором раунде останавливает implementation-
  цикл.
- Раунды 3–5 требуют явного разрешения пользователя.
- До первого spawn определяются лимиты role-agent запусков, Sol-эскалаций,
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
- Sol `high` не является default для критичного ticket: его используют после
  измеримого недостатка Terra либо для design-adjudication.
- `DONE` требует независимого evidence по каждому acceptance criterion.
- После terminal status или `REJECTED` Controller показывает observed tokens
  Implementer и total ticket; неизвестные provider counters не оцениваются.
- После `REJECTED` Controller отделяет `PRIMARY_FAILURE` от подтверждённых
  `CASCADE_FAILURES` и назначает один focused next loop либо design stop.

## Следующий эксперимент

Установить plugin `agentic-development-workflow` и применить workflow версии
`1.8` к одному реальному ticket без workflow-файлов в проекте. До реализации
зафиксировать risk, ожидаемый file scope и stop conditions; после завершения
сравнить число запусков, тестов, исправлений и расхода контекста с ticket 353.
