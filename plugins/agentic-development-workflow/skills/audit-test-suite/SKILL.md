---
name: audit-test-suite
description: Использовать только по явному запросу пользователя для read-only измерительного аудита большого, медленного или нестабильного test suite перед объединением, переносом, quarantine или удалением тестов.
---

# Измерительный аудит test suite

Выполнять только по явному вызову `$audit-test-suite`. Не запускать
автоматически при реализации ticket, review или verification.

Цель — установить, какие тесты дают уникальное доказательство, а не уменьшить
их количество. Audit не изменяет тесты, production-код, CI configuration или
quarantine state и не создаёт subagents.

## Перед измерениями

1. Найти test runner, project instructions, существующие test-result artifacts
   и команду полного suite.
2. Зафиксировать baseline: commit/diff, число тестов, command, elapsed time и
   pass/fail/skipped counts. Не выводить предположения как измерения.
3. Объявить бюджет audit: по умолчанию один полный suite и не более трёх
   повторов одного targeted command. Больше — только после подтверждения
   пользователя.

## Карта доказательств

Для каждого кандидата или осмысленной группы тестов собрать таблицу:

| Test / group | Layer | Duration | Flake evidence | Risk / acceptance | Production seam | Unique evidence | Recommendation | Replacement proof |
|---|---|---:|---|---|---|---|---|---|
| `<name>` | `<unit|integration|acceptance>` | `<observed|unknown>` | `<observed runs|unknown>` | `<risk>` | `<entry/consumer>` | `<yes|no|unknown>` | `<keep|candidate>` | `<command or N/A>` |

`Flake evidence` — только наблюдаемые repeated runs, CI history или сохранённые
artifacts. Один failure не доказывает flake. `Unique evidence` становится `yes`
для security, fail-closed, production-consumer, release или live boundary, пока
другая команда не докажет эквивалентное evidence.

## Выводы

Допустимы только следующие рекомендации:

- `KEEP`: тест остаётся, потому что доказывает уникальный риск/seam.
- `CONSOLIDATE_CANDIDATE`: несколько тестов имеют один risk и seam; назвать
  сохраняемый тест и command, который доказывает замену.
- `TARGETED_LOOP`: выделить быстрый детерминированный command для разработки;
  acceptance evidence не удаляется.
- `QUARANTINE_PROPOSAL`: только для подтверждённо flaky теста, с видимой
  причиной, owner и отдельным решением пользователя.
- `GAP`: нет теста production consumer или нет карты evidence; сначала
  добавить доказательство, не уменьшать suite.

Не рекомендовать удаление, skip или перенос, когда `Unique evidence` равно
`yes` или `unknown`. Если candidate не имеет replacement proof, оставить его
`KEEP` и зафиксировать, каких измерений не хватает.

## Финальный отчёт

Вернуть `TEST_SUITE_AUDIT` с baseline, audit budget, evidence map, candidates,
неизвестными данными и одной из итоговых оценок:

- `NO_CHANGE_RECOMMENDED` — нет безопасно подтверждённой оптимизации;
- `OPTIMIZATION_PROPOSALS_READY` — есть кандидаты, но они ещё не изменены;
- `MEASUREMENT_INCOMPLETE` — не хватает duration, flake history или evidence map.

Любая реализация предложений выполняется отдельным ticket или явно одобренной
правкой с собственным RED/GREEN evidence.
