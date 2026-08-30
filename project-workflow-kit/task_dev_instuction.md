# Как выполнить одну задачу разработки

Версия workflow: `1.3`

## Один раз на каждом ПК

После clone workflow-репозитория выполните из его корня:

```powershell
codex plugin marketplace add .
codex plugin add agentic-development-workflow@personal
```

На домашнем ПК используйте тот же clone. После обновления plugin откройте новый
Codex task.

## Перед ticket

1. Убедитесь, что в проекте уже есть ticket и связанная спецификация.
2. Откройте корень проекта в Codex Desktop.
3. Создайте или продолжите Controller task.
4. Отправьте:

```text
Используй $finish-ticket для ticket <ID или путь>.
```

Больше ничего в проект копировать не нужно. Controller сам определит рабочую
папку, ветку, commit и fixed point, прочитает project-specific `AGENTS.md`,
ticket и спецификацию, а полный workflow загрузит из глобального skill.

## Контрольная точка перед разработкой

Controller сначала вернёт `PREFLIGHT_REPORT` с acceptance evidence, риском,
scope, моделями/effort, budget/context counters и stop gates. Для critical,
resumed, design-gap и неизвестного scope разрешите первый spawn явно. Ordinary
ticket продолжает сам в своём budget.

По умолчанию budget: ordinary — 3 role-agent запуска; critical — 4; full suite
— 1. Terra `high` является базой критичной реализации. Sol `high` Controller
может выбрать лишь с записанной причиной; превышение budget создаёт checkpoint
и ждёт нового решения.

## После завершения

- `DONE`: сохранить evidence, архивировать role-agent tasks и перейти к
  следующему ticket.
- `BLOCKED_FOR_DESIGN`: не продолжать repair-loop; отдельно утвердить
  отсутствующее design-решение.
- `BLOCKED`: сохранить тип задачи, причину блокировки, тесты, findings,
  попытки и следующий диагностический шаг для общей статистики.

## Возобновление

```text
Используй $finish-ticket, чтобы возобновить ticket <ID> по checkpoint
<путь>.
```

Новый Controller сначала проверит partial diff и stop gates. Он не продолжит
старый fix-раунд автоматически.

## Когда менять Controller

Используйте новый Controller, если контекст стал большим, смешаны разные
tickets, существенно обновилась версия workflow либо Controller сам изменял
production-код. Во всех остальных случаях один Controller можно сохранять.
