# Qwen Code v0.24.5: повторная проверка terminal evidence

Дата: 2026-09-25. Проверены официальные release notes и документация Qwen Code.
Исследование read-only: Qwen CLI и модель не запускались; credentials и локальные
Qwen settings не читались и не менялись.

## Вывод для Ticket 24

Ticket 24 нельзя безопасно разблокировать на основании имеющихся штатных каналов.
Официальный контракт interactive TUI `--json-file` не гарантирует ни typed
per-session причину budget stop, ни явный `loop_status=CLEAR`. Более новый CLI
релиз v0.24.5 этого пробела не закрывает по опубликованному контракту.

Следовательно, разрешение на запуск само по себе не снимает evidence gate: ещё
один TUI pilot с тем же контрактом способен дать transcript/counters, но не
проверяемый terminal receipt, необходимый для безопасного continuation.

## Что установлено

| Канал | Официально подтверждённые данные | Ограничение для Ticket 24 |
|---|---|---|
| Interactive TUI `--json-file` / `--json-fd` | Dual Output зеркалирует structured JSONL в отдельный канал. Документированы `session_start`, stream events, завершённые user/assistant messages, control request/response и `session_end` при clean shutdown. | Документированный event schema не содержит обязательных полей `budget_stop_reason` и `loop_status`; `session_end` подтверждает закрытие сессии, а не причину остановки model turn. Отсутствие loop-события не доказывает `CLEAR`. |
| Headless `-p` / `--output-format stream-json` | Для headless run-level budgets документирован structured `FatalBudgetExceededError` с exit 55; session-turn cap имеет exit 53; SIGINT — 130. | Это другой execution mode, не доказательство native TUI поведения. Exit 55 объединяет run-level budget причины и сам по себе не является отдельным typed budget-kind полем. |
| `StopFailure` hook | При loop detection hook может получить `error=loop_detected` и optional `error_details`. | Hook настраивается отдельно, работает fire-and-forget; его output и exit code игнорируются. Он даёт возможный positive failure signal, но не явное подтверждение отсутствия loop и не budget-stop receipt. Использование потребовало бы hook configuration, которой сейчас нет в разрешённом settings-neutral scope. |

Первичный источник для Dual Output — [официальный контракт и схема событий](https://github.com/QwenLM/qwen-code/blob/main/docs/users/features/dual-output.md#output-event-schema), включая [описание `session_end`](https://github.com/QwenLM/qwen-code/blob/main/docs/users/features/dual-output.md#poc-6--session_end-as-a-clean-termination-signal). Headless budget semantics описаны отдельно в [официальной документации](https://github.com/QwenLM/qwen-code/blob/main/docs/users/features/headless.md#run-level-budgets). Ограничения hook описаны в [официальной документации StopFailure](https://github.com/QwenLM/qwen-code/blob/main/docs/users/features/hooks.md#stopfailure).

## Версия

Официальная страница [Qwen Code v0.24.5](https://github.com/QwenLM/qwen-code/releases/tag/v0.24.5)
указывает публикацию 2026-09-24; это более новый CLI release, чем
[v0.24.4 от 2026-09-22](https://github.com/QwenLM/qwen-code/releases/tag/v0.24.4),
который рассматривался в предыдущей заметке. В перечне изменений v0.24.5 нет
объявленного изменения Dual Output terminal contract, loop-clear event или
typed TUI budget receipt. Текущий опубликованный `main` contract для Dual Output,
headless budgets и `StopFailure` также не описывает такие поля. Это вывод о
документированных гарантиях, а не утверждение, что будущие/внутренние builds не
могут иметь дополнительных сигналов.

## Решение и условие разблокировки

Оставить Ticket 24 в fail-closed состоянии. Разблокировать continuation можно,
когда появится и будет локально подтверждён хотя бы один разрешённый источник,
который одновременно предоставляет:

1. terminal stop kind, связанный с конкретной сессией;
2. явный loop state, включая positive `CLEAR` при достаточном покрытии;
3. raw-free host receipt с counters/ledger, пригодный для независимой проверки.

Подходящие варианты — upstream native event с этими гарантиями либо отдельно
спроектированный и разрешённый host-side telemetry seam. Не следует выводить
`CLEAR` из отсутствия `StopFailure`, `session_end`, пороговых counters или
содержимого финального текста.
