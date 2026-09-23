# Дизайн QWEN_PATCH_SEAL

## Цель

`QWEN_PATCH_SEAL` отделяет способность Qwen создать ограниченный candidate diff
от ненадёжного завершения `yolo` через terminal structured output. Qwen остаётся
источником patch manifest, а Controller — единственной ролью, которая вправе
проверить или перенести candidate.

## Наблюдаемый failure

Smoke от 2026-09-19 показал, что `plan` возвращает schema-valid final
`structured_result`, тогда как `yolo` может внести однофайловую правку и пройти
targeted test, но исчерпывает 12 turns до вызова `structured_output`. Повтор
такого `yolo` packet запрещён действующим health gate. Увеличение его turn
budget расходовало бы дополнительный бюджет, не делая completion
детерминированным.

## Решение

Добавить одну необязательную terminal-стадию после unsealed `yolo` candidate:

```text
подтверждённый recon
  -> yolo candidate worktree
  -> отсутствует yolo manifest + observed bounded diff
  -> receipt Controller о scope и targeted test
  -> один read-only вызов QWEN_PATCH_SEAL в plan mode
  -> manifest Qwen, сопоставленный с observed receipt
  -> независимый review и возможный transfer
```

Seal не является retry `yolo` worker. Это отдельная однократная read-only
стадия completion со своей нормализованной root cause; она расходует один из
семи Qwen-вызовов ticket. Она доступна, только если Controller уже независимо
наблюдал все следующие факты:

- candidate worktree содержит uncommitted diff из одного или двух файлов и не
  более 200 изменённых строк;
- Git integration operation не происходила;
- ровно одна объявленная targeted command успешно завершилась в этой worktree;
- baseline candidate совпадает с baseline recon;
- исходный отказ `yolo` — отсутствие terminal structured output на turn limit;
  если host-side collector не смог спроецировать уже наблюдённый terminal
  envelope, допускается отдельная причина `COLLECTOR_PROJECTION_FAILED` при
  тех же независимых ограничениях diff и targeted test. Эта причина не
  утверждает terminal-причину Qwen.

## Контракт packet и результата

Controller формирует raw-free `PATCH_SEAL_RECEIPT` из наблюдаемых фактов:
baseline, имена изменённых файлов, число изменённых строк, targeted command и
её результат, а также terminal reason `yolo`. Он не формирует manifest.

Qwen получает этот receipt и read-only `plan` packet. Ей запрещены edit,
shell-команды, Git, network/MCP и subagents. Единственный полезный результат —
существующий manifest `qwen-assist-patch.schema.json`. Manifest принимается,
только если каждое заявленное имя файла, число изменённых строк, targeted test,
пустой `git_operations` и `full_suite: false` в точности совпадают с observed
receipt. Любое несовпадение, отсутствие terminal result или schema failure —
`QWEN_UNUSABLE` для `patch-seal`; fallback и transfer запрещены.

## Полномочия и безопасность

`QWEN_PATCH_SEAL` не делает unsealed candidate приемлемым. Controller всё ещё
проверяет фактический diff и test receipt, после чего запускает независимый
review до любого transfer. Qwen не получает полномочий на commit, merge,
cherry-pick, push, full suite или acceptance. Seal receipt не сохраняет token,
prompt, source text или raw terminal transcript в Git либо metrics.

## Границы реализации

- `scripts/qwen_assist.py`: validation observed receipt и сопоставление его с
  manifest, созданным Qwen.
- `scripts/invoke_qwen_assist.ps1` и capture wrapper: явный режим `seal`,
  который всегда использует `plan`, patch schema и read-only exclusions.
- tests: RED/GREEN coverage shape receipt, точного сопоставления, ограничений
  mode/tools и no-transfer failures.
- canonical lifecycle, reference `QWEN_ASSIST`, plugin skill, human lifecycle
  docs и `docs/decisions.md`: описание новой стадии и её stop gates.

## Критерии приёмки

1. Seal не может стартовать без bounded observed candidate receipt и
   специфичной причины отсутствующего yolo manifest: либо
   `STRUCTURED_OUTPUT_MISSING_AT_TURN_LIMIT`, либо
   `COLLECTOR_PROJECTION_FAILED` только для independently observed
   collector failure.
2. Seal mode не может выполнять write, shell/Git/network/MCP/subagent/full-suite
   actions; launcher передаёт пустой MCP-конфиг и read-only exclusions.
3. Только exact manifest, созданный Qwen, может перевести unsealed candidate в
   `SEALED_CANDIDATE`; Controller не может синтезировать его самостоятельно.
4. Несовпадение или отсутствующий output остаются terminal `QWEN_UNUSABLE` без
   automatic retry.
5. Новый isolated smoke демонстрирует полный путь `yolo` edit -> receipt
   Controller -> Qwen plan-seal manifest; это по-прежнему не acceptance
   evidence.
