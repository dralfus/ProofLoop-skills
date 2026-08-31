---
name: finish-ticket
description: Использовать для реализации или возобновления одного ticket через Codex multi-agent orchestration, когда нужны независимая приёмка, ограниченный repair-loop, явный бюджет агентов/контекста, выбор моделей или защита от ложного DONE.
---

# Выполнение одного ticket

## Основной принцип

Выполнять один ticket через Controller. Он отделяет реализацию от независимой
приёмки, объявляет бюджет до первого дорогого запуска и останавливает
нездоровый repair-loop. Файлы workflow в проект не копировать.

## Запуск

1. Полностью прочитать `references/task-lifecycle.md`, разрешая путь
   относительно этого `SKILL.md`.
2. Найти корень открытого проекта и прочитать применимые проектные
   `AGENTS.md`/`agents.md`.
3. Прочитать указанный ticket, связанную спецификацию и checkpoint при
   возобновлении.
4. Если ticket не определён однозначно, вернуть `NEEDS_CLARIFICATION` и
   запросить только его путь или идентификатор.
5. Выполнить `PREFLIGHT_REPORT` и budget/context gate из протокола.
6. Для critical, resumed, design-gap или неопределённого scope остановиться до
   подтверждения пользователя; ordinary ticket продолжить в объявленном
   бюджете.
7. Передавать role-agent только `IMPLEMENTATION_PACKET` из протокола; до
   Implementer каждый acceptance criterion обязан иметь `SEAM_FEASIBILITY`.

Проектные инструкции определяют команды, архитектуру и coding standards.
Протокол skill определяет полномочия ролей, порядок приёмки, health gates и
условия `DONE`. При существенном противоречии остановиться с
`NEEDS_CLARIFICATION`.

## Короткий пользовательский prompt

```text
Используй $finish-ticket для ticket <ID или путь>.
```

Для возобновления:

```text
Используй $finish-ticket, чтобы возобновить ticket <ID> по checkpoint
<путь>.
```

## Обязательные ограничения

- Только Controller создаёт subagents.
- Один writer работает одновременно.
- Reviewer предшествует Verifier.
- `DONE` требует независимого исполняемого evidence.
- Повтор корневой причины, design gap, превышение scope, бюджета или контекста
  включает stop gate.
- После closure Controller публикует observed `TOKEN_USAGE`: отдельно
  Implementer/follow-ups и total ticket; недоступные provider counters помечает
  `NOT_AVAILABLE`.
- Один процессный skill на роль: Implementer использует TDD либо диагностику;
  Reviewer не оркестрирует; Verifier подтверждает evidence.

## Установка

Skill устанавливается вместе с plugin `agentic-development-workflow` через
Codex marketplace. Инструкции для человека находятся в репозитории plugin, а
не в проекте разработки.
