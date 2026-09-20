# Спецификация: guarded runtime-профиль Qwen Code

Статус: принято к реализации; tickets 16--18.

## Постановка проблемы

У native Qwen Code обнаружены два независимых failure mode:

1. модель может начать работу без фактического применения требуемого skill или
   заменить protocol собственной последовательностью действий;
2. модель может повторять одинаковые tool calls или гипотезы до срабатывания
   встроенного watchdog.

Настройки sampling, исправляющие смешение языков, не доказывают соблюдение
protocol и не заменяют внешний circuit breaker. Qwen бесплатна для владельца
workflow, но бесплодные циклы всё равно занимают время, tool budget, context и
искажают evidence.

## Цель

Native Qwen запуск `$finish-ticket` начинается только из ProofLoop-owned
guarded session с проверяемыми техническими ограничителями. Она сохраняет
единый canonical lifecycle, независимую приёмку и `QWEN_CONVERGENT`, но не
полагается на текстовое обещание модели остановиться.

## Границы

В области действия:

- native Qwen Code extension `finish-ticket`;
- отдельный ProofLoop-owned launcher и raw-free `QWEN_SESSION_GUARD` receipt;
- документация операторского профиля и bounded pilot.

Вне области действия:

- изменение `qwen.cmd`, пользовательской PowerShell-функции, чужих runners,
  endpoint, модели, API key или server-side defaults;
- автоматическая запись в `~/.qwen/settings.json`;
- изменение `QWEN_ASSIST`: это отдельный Codex-managed bridge с собственными
  limits и health ledger;
- обещание, что sampling или prompt сами по себе гарантируют послушание модели.

## Решение

### Guarded launcher

ProofLoop поставляет отдельный launcher, который до старта native Qwen:

- проверяет без вывода secrets, что effective local configuration включает
  `skipLoopDetection: false`, `maxToolCallsPerTurn <= 20` и
  `maxSubagentDepth: 1`;
- подтверждает доступность установленного ProofLoop Qwen extension;
- запускает fresh Qwen session с явными `max-session-turns`,
  `max-tool-calls`, `max-wall-time` и depth `1`;
- не использует `--safe-mode`, поскольку он отключает skills и extensions;
- создаёт raw-free `QWEN_SESSION_GUARD` receipt локально вне Git.

Новый launcher является дополнительным executable entry point; существующие
Qwen команды и настройки других программ не переписываются.

### Режимы session

`recon` предназначен для простого ограниченного анализа и использует малый
runtime budget без thinking. `protocol` предназначен для Controller,
skill-heavy анализа и repair: thinking включён, а output limit не меньше 8000.

Sampling (`temperature`, `top_p`, `top_k`, penalties) ProofLoop не задаёт:
серверные defaults являются источником истины. Packet передаётся на английском
языке с явным требованием ответить по-русски. Указанные модельные имена служат
операторскими примерами, а не version/model allow-list.

### Lifecycle gate

До первого role dispatch native Qwen Controller требует fresh
`QWEN_SESSION_GUARD` receipt с идентичностью запуска, режимом, limits, фактом
loop detection и extension availability. Отсутствующий, просроченный или
несовместимый receipt даёт `BLOCKED_CAPABILITY` до role launch.

`QWEN_CONVERGENT` сохраняет прежнее правило: session budget не является
числовым cap repair-раундов. Но исчерпание session budget, streaming-loop
detection или повтор инструментального fingerprint даёт
`QWEN_RUNTIME_GUARD_STOP`. Продолжение возможно только fresh guarded session с
новым reproducible evidence; инерционный resume запрещён.

Receipt доказывает параметры запуска, но не является свидетельством того, что
модель поняла или выполнила skill. Независимый Reviewer, ledger и common
acceptance gates остаются обязательными.

## Критерии приёмки

1. Launcher не изменяет пользовательский Qwen config, API key, сторонние
   runners или server-side model settings.
2. `--safe-mode`, отключённый loop detection, nesting глубже одного уровня и
   отсутствующий extension блокируют запуск до ticket work.
3. Каждая guarded session имеет raw-free receipt; native Qwen profile не
   dispatches role без валидного receipt.
4. Exhausted turn/tool/wall budget и loop detection заканчивают session
   воспроизводимым terminal reason без автоматического повторного запуска.
5. Fresh continuation требует новой evidence-причины и сохраняет append-only
   QWEN ledger; `DONE` по-прежнему требует независимых PASS и ACCEPTED.
6. `recon` и `protocol` различаются лишь runtime budget/thinking; они не
   меняют authority, acceptance criteria или доступную модели область работ.
7. Pilot публикует только raw-free метрики: guard outcome, terminal reason,
   turns/tool calls при доступности, число repeated fingerprints, launch mode,
   duration и outcome.

## Проверка

- unit/fixture проверяет конфигурационные reject cases и receipt schema;
- integration test проверяет, что launcher передаёт лимиты, не передаёт secret
  и не использует `--safe-mode`;
- lifecycle fixture проверяет `BLOCKED_CAPABILITY` без receipt и
  `QWEN_RUNTIME_GUARD_STOP` без нового role launch;
- один operator-run pilot сравнивает guard result и фактическую terminal
  причину. Он не является acceptance evidence пользовательского ticket.

## Измеримый критерий улучшения

На серии не менее трёх guarded native Qwen sessions нет запуска без receipt и
нет continuation после повторного fingerprint или исчерпания runtime budget.
Отдельно фиксируется, уменьшилось ли число повторных tool calls по сравнению с
предыдущими incidents. Отсутствие улучшения не оправдывает расширение prompt,
увеличение budgets или добавление новых role-agents.
