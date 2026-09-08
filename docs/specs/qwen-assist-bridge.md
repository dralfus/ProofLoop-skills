# Спецификация: QWEN_ASSIST — управляемый bridge Qwen CLI для Codex

Статус: готово к декомпозиции

## Постановка проблемы

Qwen Code предоставляет дешёвую вычислительную мощность, но не соблюдает
текстовые протоколы с достаточной надёжностью для самостоятельного Controller,
Implementer или acceptance authority. Она может повторять одинаковые попытки,
расширять scope, запускать лишние проверки и выдавать непроверенные заявления.
Полный Qwen lifecycle с независимой приёмкой остаётся непроверенным live-pilot.

Нужен способ передавать Qwen значительную, но ограниченную часть работы из
Codex Desktop: сначала разведку кода, затем малые patch-кандидаты. Codex должен
сохранять единоличную authority, технически ограничивать Qwen и получать
машиночитаемый результат, а не свободный transcript.

## Решение

Ввести отдельный профиль `QWEN_ASSIST`. Это не role-agent lifecycle и не
замена `finish-ticket`: Codex Controller запускает Qwen CLI как внешний,
синхронный worker, проверяет результат по JSON schema и сам решает, принять,
уточнить или отклонить candidate.

Bridge выполняет capability probe перед каждым запуском, а не привязывается к
номеру версии Qwen. Он требует non-interactive запуск, JSON schema/output,
изолированную worktree, лимиты turns/tool calls/wall-time и безопасный режим
read-only. Отсутствие любой обязательной возможности возвращает
`BLOCKED_CAPABILITY` только для данного запуска.

Первый режим — `QWEN_RECON`: Qwen читает codebase из clean fixed-point
worktree, не запускает shell-команды и не изменяет файлы. Она возвращает
`QWEN_RECON_REPORT` с проверяемыми фактами. После одного успешного report,
подтверждённого Codex, доступен `QWEN_PATCH_CANDIDATE`: до двух файлов, 200
изменённых строк и одного targeted test в отдельной worktree. Qwen никогда не
делает commit, merge, cherry-pick или acceptance.

На ticket действует общий budget не более семи вызовов Qwen. Каждый новый вызов
должен менять scope, criterion, RED-команду или hypothesis и добавлять новое
evidence. Две попытки без нового evidence или повтор нормализованной root
cause останавливают Qwen раньше лимита. После непригодного результата Codex
может один раз уточнить packet и продолжить только в пределах этих health gates.

## Пользовательские истории

1. Как владелец workflow, я хочу, чтобы Codex запускал Qwen CLI сам, чтобы
   передавать дешёвому worker ограниченную часть вычислений без ручного
   копирования prompt.
2. Как Controller, я хочу получать структурированный terminal JSON-результат,
   чтобы принимать решение по schema-valid evidence, а не по свободному тексту.
3. Как владелец workflow, я хочу принимать обновлённую Qwen без ручной правки
   version pin, если её необходимые capabilities по-прежнему доступны.
4. Как Controller, я хочу блокировать конкретный запуск при отсутствии нужной
   capability, чтобы обновление CLI не ослабило технические ограничения.
5. Как разработчик, я хочу поручить Qwen read-only карту codebase, чтобы
   быстрее найти entry point, state owner, callback boundary и существующие
   тестовые seams.
6. Как Controller, я хочу получать минимум три проверяемых факта
   `file:line -> fact`, чтобы отличать полезную разведку от правдоподобного
   пересказа.
7. Как владелец ticket, я хочу, чтобы Qwen работала из isolated fixed-point
   worktree, чтобы незакоммиченный diff другого ticket не загрязнял её вывод.
8. Как владелец workflow, я хочу, чтобы первый pilot не выполнял shell-команды,
   тесты или файловые изменения, чтобы сначала измерить управляемость bridge.
9. Как разработчик, я хочу разрешить Qwen небольшой patch-кандидат после
   подтверждённой разведки, чтобы переносить на неё механическую работу.
10. Как Controller, я хочу, чтобы Qwen не могла commit, merge, cherry-pick,
    запускать full suite или обладать acceptance authority, чтобы сохранить
    единственного writer и независимую приёмку.
11. Как владелец workflow, я хочу ограничить суммарное число Qwen-вызовов семью
    и останавливать повтор без progress evidence, чтобы бесплатный worker не
    создавал бесконечный loop.
12. Как Controller, я хочу уточнять packet после измеримой причины неудачи,
    чтобы Qwen получала новый шанс только на изменённой гипотезе.
13. Как Reviewer, я хочу, чтобы Codex independently проверял diff Qwen перед
    переносом, чтобы candidate не стал неявным принятием собственной работы.
14. Как владелец нескольких проектов, я хочу хранить полный Qwen report рядом
    с проектом вне Git, а обезличенные метрики — в локальном central store,
    чтобы сравнивать полезность Qwen без сбора кода и внутренних путей.
15. Как аналитик workflow, я хочу видеть тип задачи, outcome, число попыток,
    duration, tool calls и stop reason, чтобы измерять, где Qwen действительно
    разгружает Codex.
16. Как оператор, я хочу, чтобы default-модель Qwen выбиралась существующей
    администраторской конфигурацией без fallback, чтобы bridge не обходил
    локальную политику моделей.

## Решения по реализации

- `QWEN_ASSIST` является отдельным профилем внешнего worker, а не новым
  Implementer/Reviewer/Verifier и не изменяет acceptance authority `finish-ticket`.
- Controller запускает Qwen non-interactively, ждёт terminal result и валидирует
  его по versioned JSON schema. Потоковое управление, daemon и ACP не входят в
  первую версию.
- Capability probe выполняется на каждом запуске. Он проверяет доступность
  strict non-interactive input/output, JSON schema, worktree, limits turns,
  tool calls и wall-time, read-only approval mode, default model без fallback.
- Read-only packet содержит ticket, fixed point, разрешённый scope и ожидаемые
  поля отчёта. Он запрещает shell-команды, тесты, записи, subagents, network/MCP
  и любые действия вне локального codebase.
- `QWEN_RECON_REPORT` имеет terminal outcomes `EVIDENCE_FOUND`, `BLOCKED` и
  `QWEN_UNUSABLE`; включает baseline, минимум три locatable facts, state owner,
  callback boundary, один acceptance risk, evidence references и stop reason.
- Успешный recon требует schema-valid report, соблюдение limits, отсутствие
  изменений и подтверждение Codex всех требуемых фактов. Только после этого
  разрешается `QWEN_PATCH_CANDIDATE`.
- Patch-кандидат создаётся только в отдельной worktree и ограничен двумя
  файлами, 200 изменёнными строками и одним targeted test. Qwen не выполняет
  Git-операции интеграции; Codex выбирает, переносить ли independently
  проверенный diff в основную worktree.
- Общий ticket budget — семь Qwen-вызовов во всех режимах. Новая попытка требует
  нового evidence или изменённого scope, criterion, RED-command либо hypothesis.
  Две подряд попытки без progress либо повтор root cause возвращают terminal
  `QWEN_UNUSABLE` до лимита.
- Полный отчёт Qwen остаётся в игнорируемом локальном каталоге проекта. Central
  store расположен в `%LOCALAPPDATA%\ProofLoop Skills\qwen-metrics.jsonl` и
  содержит только обезличенные поля: task type, outcome, attempts, duration,
  tool calls и stop reason.
- Прямой Qwen full-ticket lifecycle и текущий `QWEN_CONVERGENT` не удаляются
  в этой версии, но не являются рекомендуемым способом запуска Qwen из Codex.

## Решения по тестированию

Высокий seam — bridge invocation boundary: он принимает packet и capability
declaration/CLI fixture, запускает либо имитирует внешний worker, затем выдаёт
validated structured outcome. Тесты проверяют внешний контракт и policy, а не
внутренние детали запуска процесса.

- Capability fixtures подтверждают принятие совместимого CLI независимо от его
  version string и `BLOCKED_CAPABILITY` при отсутствии каждой обязательной
  возможности.
- Read-only fixture подтверждает fixed-point isolation, запрет записи/команд и
  принятие report только с тремя locatable facts, state owner, callback boundary
  и acceptance risk.
- Negative fixtures покрывают invalid JSON, нарушение schema, отсутствие
  факта, неверный baseline, writes и исчерпание limits.
- Health-ledger fixtures покрывают максимум семь вызовов, допустимое уточнение
  packet, две попытки без progress и повтор root cause.
- Patch fixture подтверждает limits diff/test, отсутствие Git-интеграции со
  стороны Qwen и обязательную independent verification Codex перед переносом.
- Metrics fixture подтверждает, что full report не попадает в central store,
  а anonymized запись включает только утверждённые поля.
- Live-pilot на ticket 314 проверяет read-only mode отдельно от реализации
  ticket и не считается acceptance evidence самого ticket 314.

## Вне области действия

- Передача Qwen acceptance authority, статусов `DONE`/`ACCEPTED` или права
  создавать role-agents.
- Автоматический merge, commit, cherry-pick или push diff Qwen.
- Полный Qwen implementation lifecycle, streaming orchestration, daemon, ACP
  и параллельные Qwen workers.
- Запуск full suite, UI/Sandbox jobs, сетевых/MCP tools или shell-команд в
  первом read-only pilot.
- Сбор исходного кода, путей, raw findings, секретов или customer data в
  межпроектный metrics store.
- Изменение сторонних skills в plugin cache.

## Дополнительные сведения

Первый real pilot использует ticket 314 только как read-only предмет анализа и
только из clean fixed point, исключающего незакоммиченный diff ticket 355.
Успех pilot доказывает управляемость bridge, а не завершение или безопасность
ticket 314. Решение о расширении write-limits принимается только по
обезличенной статистике успешных patch-кандидатов.
