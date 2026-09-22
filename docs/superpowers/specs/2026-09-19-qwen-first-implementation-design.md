# Дизайн Qwen-first implementation lane

## Цель

Сделать Qwen основным исполнителем ограниченной реализации, оставив Controller
за более мощной моделью, а независимые validation и review — отдельными
ролями. Доказать полный путь на disposable test-only patch:

```text
Qwen recon -> Qwen implementation -> observed diff/test receipt
-> Qwen manifest-only -> SEALED_CANDIDATE -> independent review
```

Это не product acceptance и не даёт Qwen право на перенос, Git-интеграцию,
full suite или статус `DONE`.

## Наблюдаемый failure

19 сентября Qwen создала ограниченный yolo diff и прошла targeted test, но
исчерпала 12 turns до terminal structured output. Последующий seal в `plan`
также завершился `FatalTurnLimitedError` без manifest. Существующий seal
правильно не допускает transfer, но не доказывает завершение Qwen-first пути.

## Решение

Добавить отдельный `QWEN_MANIFEST_ONLY` lane. После Controller-наблюдаемого
receipt Qwen получает только raw-free receipt и точную инструкцию вернуть
существующий patch-schema JSON. Этот вызов не читает код и использует только
единственный structured-output tool: `plan`, `--bare`, `--max-tool-calls 1`,
structured-output вызова, exclusions для Agent/edit/shell,
network/MCP и subagents. Его короткий turn budget отдельный от write packet;
его величина определяется preflight fixture, а не расширением yolo budget.

Controller перед запуском проверяет receipt, резервирует единственный вызов
для ticket и передаёт receipt в prompt. Capture reader принимает только final
`result.structured_result`, сравнивает его с receipt и выдаёт
`SEALED_CANDIDATE` либо terminal `QWEN_UNUSABLE`. Нет fallback, retry или
transfer при отсутствии либо несовпадении manifest.

## Роли и границы

| Роль | Полномочия |
| --- | --- |
| Qwen | recon и ограниченный implementation candidate; один manifest-only ответ |
| Controller (сильная модель) | preflight, packet, independent diff/test observation, запуск и остановки |
| Validator | детерминированно проверяет schema, receipt и exact match |
| Reviewer (сильная модель) | независимый scope/spec review после `SEALED_CANDIDATE` |

Qwen — основной Implementer только внутри isolated candidate worktree. Сильная
модель не пишет вместо Qwen production/test patch и не синтезирует manifest.

## Доказательство

Disposable fixture меняет один test-only файл не более чем на 20 строк и имеет
одну targeted command. Успех требует одновременно:

1. Qwen выпускает diff в candidate worktree; Controller наблюдает допустимый
   scope и green targeted test.
2. Qwen manifest-only вызов завершается terminal patch-schema result без
   tool calls.
3. Exact validator возвращает `SEALED_CANDIDATE`.
4. Независимый Reviewer подтверждает, что fixture scope не вышел за пределы.
5. Raw-free experiment record содержит run identities, statuses и verdicts,
   но не token, prompt, source text или terminal transcript.

Любой иной исход — честный `QWEN_UNUSABLE`; одноразовый fixture не получает
автоматического повтора.

## Измеримый критерий улучшения

Один новый disposable pilot завершает весь путь выше с Qwen как автором diff и
manifest. Дополнительно tests доказывают, что manifest-only launch всегда
содержит `--max-tool-calls 1`, не получает write/network/subagent tools и не
может выдать `SEALED_CANDIDATE` без exact terminal result.

## Не входит в scope

- замена Controller, Validator или Reviewer Qwen;
- product-ticket implementation/acceptance;
- увеличение yolo turn budget или слепой retry;
- хранение токена, prompt либо transcript в Git.
