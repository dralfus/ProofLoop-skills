# Qwen Code v0.24.4: terminal evidence in `--json-file`

Дата исследования: 2026-09-24. Источники ограничены официальными
документацией, release и исходным кодом Qwen Code. Проверен upstream tag
`v0.24.4`; установленный локально бинарный файл не запускался и его версию
этим исследованием не подтверждали.

## Вывод

Нет: JSONL sidecar `--json-file` в Qwen Code v0.24.4 сам по себе не даёт
надёжного машинно-читаемого доказательства точной причины остановки на
лимите ходов, лимите вызовов инструментов, лимите времени или loop detection.
Он полезен для transcript/counters и корреляции сессии, но `session_end` —
сигнал закрытия канала с `session_id`, не терминальный outcome. Нельзя
приравнивать его, завершившийся поток или достижение счётчиком порога к
`budget_stop=true` либо `loop_status=CLEAR`.

Официальный [описанный контракт dual output v0.24.4](https://github.com/QwenLM/qwen-code/blob/v0.24.4/docs/users/features/dual-output.md)
перечисляет lifecycle-события, сообщения, stream events и tool-permission
control plane. В исходнике [DualOutputBridge](https://github.com/QwenLM/qwen-code/blob/v0.24.4/packages/cli/src/dualOutput/DualOutputBridge.ts#L37-L56)
есть общий event kind `result`, но нет отдельных wire-событий для причины
budget stop или статуса loop. При shutdown bridge отправляет `session_end` с
`session_id` ([исходник](https://github.com/QwenLM/qwen-code/blob/v0.24.4/packages/cli/src/dualOutput/DualOutputBridge.ts#L374-L400)).

## Что показывают отдельные сигналы

| Причина | Что подтверждают официальные источники | Что это значит для sidecar |
|---|---|---|
| Лимит session turns | В core v0.24.4 появляется внутренний `MaxSessionTurns`; headless-документация указывает exit code `53` для этого лимита. | Это не отдельный `--json-file` terminal event. Внутреннее событие не входит в список sidecar `supported_events`, поэтому одних JSONL counters недостаточно. |
| Лимит tool calls | `model.maxToolCallsPerTurn` — per-turn cap. В core срабатывание представлено внутренним `LoopDetected` с типом, например `TURN_TOOL_CALL_CAP`. Отдельный `--max-tool-calls` в headless ограничивает cumulative top-level dispatches. | Не смешивать два разных лимита. Для interactive/TUI cap нет документированного sidecar поля `budget_reason` или `loop_status`; headless result — другой invocation contract. |
| Лимит wall time | `model.maxWallTimeSeconds` и `--max-wall-time` документированы для headless/unattended runs. В headless run-level budgets завершаются exit code `55`; тот же код указан и для `--max-tool-calls`. | Код `55` сам по себе не различает wall-time и tool-call budget. Headless terminal result несёт `is_error` и сообщение об ошибке, а не гарантированное enum-поле вида `budget_kind`; sidecar не обещает этот headless результат. |
| Loop detection | Core создаёт внутреннее `LoopDetected` с loop type. Настроенный `StopFailure` hook может получить `error=loop_detected` и optional `error_details`. | Hook — отдельный канал, не sidecar. Он fire-and-forget; отсутствие hook-события не доказывает `CLEAR`. В JSONL sidecar нет документированной гарантии явного `loop_detected`/`loop_clear`. |

Источники для таблицы: [headless output и budget semantics v0.24.4](https://github.com/QwenLM/qwen-code/blob/v0.24.4/docs/users/features/headless.md#L216-L324),
[settings v0.24.4](https://github.com/QwenLM/qwen-code/blob/v0.24.4/docs/users/configuration/settings.md#L188-L204),
[core turn-limit event](https://github.com/QwenLM/qwen-code/blob/v0.24.4/packages/core/src/core/client.ts#L3869-L3876),
[core loop-detection events](https://github.com/QwenLM/qwen-code/blob/v0.24.4/packages/core/src/core/client.ts#L4247-L4254)
и [always-on safeguards / `skipLoopDetection`](https://github.com/QwenLM/qwen-code/blob/v0.24.4/packages/core/src/core/client.ts#L4408-L4477),
[обработка событий общим JSON adapter](https://github.com/QwenLM/qwen-code/blob/v0.24.4/packages/cli/src/nonInteractive/io/BaseJsonOutputAdapter.ts#L670-L726),
[headless terminal result handling](https://github.com/QwenLM/qwen-code/blob/v0.24.4/packages/cli/src/nonInteractiveCli.ts#L1727-L1758)
и [run-budget error handling](https://github.com/QwenLM/qwen-code/blob/v0.24.4/packages/cli/src/nonInteractiveCli.ts#L3253-L3365),
[общая форма JSON result](https://github.com/QwenLM/qwen-code/blob/v0.24.4/packages/cli/src/nonInteractive/io/BaseJsonOutputAdapter.ts#L1260-L1332),
[StopFailure v0.24.4](https://github.com/QwenLM/qwen-code/blob/v0.24.4/docs/users/features/hooks.md#L959-L985).

### Важные различия лимитов

- `model.maxToolCallsPerTurn` — ограничение одного model turn. `--max-tool-calls`
  в headless — суммарный бюджет dispatches основного run loop. Это не взаимозаменяемые
  counters.
- Headless `--max-wall-time`/`--max-tool-calls` завершаются с кодом `55`, а
  `--max-session-turns` — с `53`. В первом случае код не идентифицирует, какой
  именно run-level budget сработал; нужны другие данные из headless outcome.
- В v0.24.4 `model.skipLoopDetection` по умолчанию `true`: streaming heuristic
  detection пропущен. `false` включает эти эвристики, но некоторые always-on
  safeguards (в частности per-turn tool cap) остаются активны независимо от
  этого флага. Проверка upstream defaults не подтверждает пользовательскую
  настройку.

## Следствие для ProofLoop

Для продолжения после checkpoint нужно считать sidecar достаточным для
контекста/метрик, но недостаточным для terminal gate. До получения отдельного
проверяемого host-side terminal receipt с причиной остановки и явным статусом
loop (либо источником, который гарантирует их полноту) безопасное решение —
fail closed: не разрешать continuation только по `session_end`, пороговым
counters или отсутствию сообщения об ошибке.

Headless `qwen -p --output-format stream-json` документирует terminal result и
различимые exit codes `53`/`55`, но это иной runtime path и он не доказывает
поведение native TUI sidecar. Возможность записать `loop_detected` через
заранее настроенный `StopFailure` hook также не доказывает отсутствие loop,
если hook event не поступил. Установка такого hook или изменение Qwen settings
в рамках этого исследования не выполнялись.

## Версионная оговорка

Выводы привязаны к официальному release tag [Qwen Code v0.24.4](https://github.com/QwenLM/qwen-code/releases/tag/v0.24.4)
и его документации/коду. Отдельная локальная capability-smoke проверка
2026-09-24 подтвердила `qwen.cmd --version` = `0.24.4` и наличие пяти
обязательных launcher markers; она не запускала модель. Raw-free receipt:
`.scratch/qwen-ticket24-capability-smoke-20260924.json`. Это подтверждает
локальную версию, но не меняет вывод о недостатке terminal facts в native
sidecar. Выводы не переносятся на более новые releases или `main`; при смене
версии нужно повторно проверить протокол sidecar, capabilities handshake и
поведение terminal outcomes.
