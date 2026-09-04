# Передача состояния разработки workflow

Дата: 2026-09-04

## Текущее состояние

Исполняемый protocol находится в
`plugins/agentic-development-workflow/skills/finish-ticket/references/task-lifecycle.md`.
Текущая версия protocol — `1.11`; plugin выпущен как `1.11.1`.

Только Controller присваивает `DONE` после независимых `SPEC: PASS`,
`CODE_QUALITY: PASS` и `ACCEPTED` evidence. Role-agents не создают других
agents и не обладают acceptance authority.

## Актуальные safeguards

- Capability preflight блокирует запуск при неподтверждённом runtime.
- `SEAM_FEASIBILITY` и production-consumer evidence проверяются до реализации.
- `SCOPED_PASS` не разрешает Verifier: acceptance ledger должен быть закрыт.
- `TEST_PERMIT` ограничивает submission проверок; `JOB_REJECTED` до запуска
  целевой команды не расходует новый role-agent slot.
- Внешний runner работает только в изолированной worktree и не получает доступ
  к контролируемой очереди.
- Numeric profile Codex ограничивает repair-loop; Qwen profile использует
  `QWEN_CONVERGENT` с append-only ledger и независимым review.

## Следующий эксперимент

Запустить plugin на новом проекте и сохранить только обезличенное evidence:
preflight routing/budget, фактические role-agent launches, модели/effort,
compaction, команды и exit codes, fix rounds, terminal status и причины
budget/design gates. Не добавлять в этот публичный repository внутренние пути,
названия проектов, ticket IDs, raw traces или customer data.
