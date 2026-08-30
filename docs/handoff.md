# Передача состояния разработки workflow

Дата: 2026-08-30

## Принятая модель

Implementer может вернуть `IMPLEMENTED`, `BLOCKED` или
`NEEDS_CLARIFICATION`, но только Controller после независимых `SPEC: PASS`,
`CODE_QUALITY: PASS` и `ACCEPTED` evidence присваивает `DONE`.

Повтор одной пары «тип finding + корневая причина» во втором fix даёт
`BLOCKED_FOR_DESIGN`; пять fix-раундов — абсолютный terminal limit. Design gap
не проектируется внутри repair-loop.

## Версия 1.3

Ticket 353 подтвердил, что независимая приёмка защитила корректность, но старый
Controller мог расходовать лимит через лишние role-agent запуски, compaction и
дорогую модель без заранее измеримого budget.

В `1.3` приняты следующие правила:

- перед первым spawn Controller объявляет budget: role-agent, Sol, full suite
  и compaction;
- ordinary ticket получает 3 role-agent запуска, critical — 4; превышение
  требует checkpoint и отдельного разрешения пользователя;
- Terra `high` — базовая критичная реализация; Sol `high` требует
  документированного недостатка Terra или design-adjudication;
- Verifier получает Luna `medium` для deterministic проверки либо Terra
  `medium` для интерпретации; Sol не назначается ему автоматически;
- full suite запускается не более одного раза и имеет воспроизводимую запись
  command, timestamps, exit code и counts;
- compaction перед дорогой ролью создаёт свежего Controller;
- Controller ждёт event-driven и делает не более одного follow-up к роли.

## Поставка

Исполняемый protocol находится в plugin:
`plugins/agentic-development-workflow/skills/finish-ticket/references/task-lifecycle.md`.

Проекты разработки не получают копии workflow-файлов. Для установки на любом
ПК используются clone репозитория и Codex plugin marketplace; порядок описан
в `docs/codex-task-lifecycle.md`.

## Состояние ticket 353

Исторический checkpoint 2026-08-28 остаётся evidence первоначального failure,
но не отражает текущий статус. Ticket 353 завершён локально и зафиксирован в
commit `1e7125569aa137951fcfb88dd36920934aeb7cef`; live проверка в установленном
OpenAI Desktop не выполнялась. Его raw trace — baseline расхода для проверки
версии 1.3, а не универсальная норма стоимости Sol.

## Следующий эксперимент

На следующем реальном ticket применить plugin `1.3` и сохранить: preflight
budget, фактические launches, модели/effort, compaction, full-suite evidence,
fix rounds, итоговый статус и причины превышения budget, если оно произойдёт.
Сравнение вести с `docs/experiments/ticket-353-cost-baseline-2026-08-29.md`.
