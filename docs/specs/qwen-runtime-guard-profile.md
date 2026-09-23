# Спецификация: guarded runtime-профиль Qwen Code

Статус: принято; launcher реализован tickets 16, 19 и 20, lifecycle/modes
17--18 остаются отдельными.

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
- проверяет обязательные CLI capabilities и canonical argv compatibility;
  version string наблюдается для evidence, но не является allow-list;
- подтверждает доступность установленного ProofLoop Qwen extension;
- запускает fresh Qwen session с явными `max-session-turns`,
  `max-tool-calls`, `max-wall-time` и depth `1`;
- не использует `--safe-mode`, поскольку он отключает skills и extensions;
- создаёт raw-free `QWEN_SESSION_GUARD` receipt локально вне Git.

Новый launcher является дополнительным executable entry point; существующие
Qwen команды и настройки других программ не переписываются.

Общая pre-dispatch seam реализована pure-модулем
`scripts/qwen_guard_policy.py`. Adapter передаёт ему только projected
settings, capability markers, worktree facts и receipt facts через временный
JSON-файл. `QWEN_GUARD_READY` является единственным разрешением на child
dispatch; policy возвращает raw-free authority flags, проверяет freshness и
fixed point и не запускает процессы сама. Protocol сохраняет `20/20/30m` и
Controller authority, recon — `3/6/5m`, read-only и authority flags `false`.
Canonical argv, capability markers и exclusions для этих режимов находятся в
pure registry `scripts/qwen_invocation_contract.py`; отдельные `seal` и
`capability_smoke` entries не переиспользуют protocol/recon contract.

Ticket 19 уточняет только этот launcher capability path. Exact-version policy
для отдельного Qwen role-agent profile и acceptance lifecycle не изменяется
этим ticket.

### Ticket 20: native read-only recon

`recon` — отдельный explicit mode, а не альтернативный prompt для `protocol`.
Он запускает только `qwen.cmd` из clean fixed-point worktree с `--bare`,
`--approval-mode plan`, structured JSON/schema output и малым bounded budget:
3 turns, 6 tool calls, 5 минут и `max-subagent-depth 1` (CLI использует
1-based depth; запрет subagent обеспечивается `--exclude-tools Agent`). Capability preflight
обязан подтвердить все эти CLI controls; отсутствие доказуемого запрета
subagents даёт `BLOCKED_CAPABILITY`.

Recon command contract фиксирует `Agent,edit,notebook_edit,run_shell_command` в
`--exclude-tools`, отключает `review,loop` slash commands и использует bounded
prompt с одной read-only инспекцией и одним `structured_output`; parent
передаёт и повторно проверяет точный fixed-point baseline. Qwen не получает
write, implementation, Git, network/MCP,
review/yolo, role dispatch, subagent dispatch или acceptance authority.

Перед запуском guard проверяет clean worktree и сохраняет только raw-free
`QWEN_RECON_GUARD` receipt с fixed point, limits и control flags. Terminal JSON
повторно проверяется по `QWEN_RECON_REPORT` schema. Успех —
`QWEN_RECON_READY`; malformed output, policy violation или missing structured
result — `QWEN_UNUSABLE`; budget, loop и repeated fingerprint —
`QWEN_RUNTIME_GUARD_STOP`. Terminal recon ledger закрыт навсегда с
`RECON_TERMINAL_LEDGER_CLOSED`. Новая independent recon session принимает
только пустой ledger и genesis `ledger_anchor` с новыми `launch_id`,
`session_id`, `ledger_id` и registry-проверенным `fresh_evidence_id`.
Непустой active ledger допускает только exact same-receipt append; другой
launch получает `RECON_ACTIVE_LEDGER_LAUNCH_MISMATCH`. `role_dispatch`,
`subagent_dispatch` и acceptance всегда `false`.

Exact `protocol` argv contract и его `QWEN_SESSION_GUARD` receipt остаются
неизменными. Общие ledger/hash-chain и fail-closed security gates переиспользуются,
но recon evidence не является acceptance evidence и не запускает role-agent.

### Режимы session

`recon` предназначен для простого ограниченного анализа и использует малый
runtime budget без thinking. `protocol` предназначен для Controller,
skill-heavy анализа и repair: thinking включён, а output limit не меньше 8000.

Sampling (`temperature`, `top_p`, `top_k`, penalties) ProofLoop не задаёт:
серверные defaults являются источником истины. Packet передаётся на английском
языке с явным требованием ответить по-русски. Указанные модельные имена служат
операторскими примерами, а не version/model allow-list.

Для Ticket 18 controlled fixture declaration owner-authorized configured/active
identity — `qwen38-flash-next`, source `USER_AUTHORIZED_CONFIGURATION`. Это не
подменяет provider evidence: server-side active identity остаётся явно
неattested limitation пилота и не становится новым gate или version allow-list.

### Lifecycle gate

До первого role dispatch native Qwen Controller требует fresh
`QWEN_SESSION_GUARD` receipt с идентичностью запуска, режимом, limits, фактом
loop detection и extension availability. Отсутствующий, просроченный или
несовместимый receipt даёт `BLOCKED_CAPABILITY` до role launch.

Receipt использует raw-free schema с `receipt_version`, `issued_at_utc` и
bounded freshness window. Lifecycle gate принимает только `protocol` receipt
с теми же effective limits и control flags, которые выдал launcher. Отдельная
recon policy принимает только `QWEN_RECON_GUARD` с recon limits; terminal
ledger закрыт, а fresh independent session требует пустого genesis ledger,
новых receipt identities и raw-free registry evidence identity. Raw prompt,
secret, path и command output в evidence запрещены.

`QWEN_CONVERGENT` сохраняет прежнее правило: session budget не является
числовым cap repair-раундов. Но исчерпание session budget, streaming-loop
detection или повтор инструментального fingerprint даёт
`QWEN_RUNTIME_GUARD_STOP`. Продолжение возможно только fresh guarded session с
новым launch identity и reproducible evidence; инерционный resume запрещён.
Terminal event добавляется append-only. Gate сверяет immutable
`ledger_anchor` (`ledger_id`, `sequence`, `head_hash`) и hash chain
`prev_hash`/`event_hash`, поэтому удаление или замена prefix блокируется. Guard
decision сам не запускает Qwen, role-agent или acceptance.

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
5. Fresh protocol continuation требует новой evidence-причины и сохраняет
   append-only QWEN ledger; `DONE` по-прежнему требует независимых PASS и
   ACCEPTED. Recon использует отдельные fresh-ledger sessions.
6. `recon` и `protocol` имеют разные executable command/authority contracts:
   recon read-only и не dispatch'ит role, а protocol сохраняет Controller
   lifecycle. Ни один режим не меняет acceptance authority.
7. Pilot публикует только raw-free метрики: guard outcome, terminal reason,
   turns/tool calls при доступности, число repeated fingerprints, launch mode,
   duration и outcome.

## Проверка

- unit/fixture проверяет конфигурационные reject cases и receipt schema;
- integration test проверяет, что launcher передаёт лимиты, не передаёт secret
  и не использует `--safe-mode`;
- bounded smoke для установленного Qwen выполняет только `qwen --version` и
  `qwen --help`; он не dispatch'ит role и не является acceptance evidence;
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
