# Жизненный цикл задач Codex

Версия workflow: `1.14`

## Источник истины

Единственный исполняемый протокол находится в
`plugins/agentic-development-workflow/skills/finish-ticket/references/task-lifecycle.md`
и устанавливается вместе с plugin `agentic-development-workflow`.

Этот документ предназначен для человека: он объясняет установку, запуск и
обновление. Копировать его или другие workflow-файлы в проекты разработки не
нужно.

## Установка на текущем или домашнем ПК

После clone репозитория выполните из его корня:

```powershell
codex plugin marketplace add .
codex plugin add agentic-development-workflow@personal
```

На домашнем ПК достаточно clone того же GitHub-репозитория и этих двух команд.
Для обновления pull обновлённый commit и повторите `codex plugin add`; после
обновления откройте новый Codex task, чтобы он загрузил новую версию skill.

## Установка и запуск в Qwen Code v0.22.2

Из корня того же clone выполните:

```powershell
qwen extensions install .
```

Нативный manifest `qwen-extension.json` делает существующий `finish-ticket`
skill discoverable и добавляет named agent `finish-ticket-controller`; это не
вторая копия lifecycle. После установки проверьте `/skills` и `/agents manage`,
затем запустите:

```text
/finish-ticket ticket <ID или путь>
```

Обновление локально установленного extension требует `qwen extensions update
proofloop-skills`. Полная процедура первого real pilot и его текущий статус
`NOT_RUN` описаны в `experiments/qwen-code-v0222-pilot.md`.

## Запуск одного ticket

Открыть корень проекта в Codex и отправить:

```text
Используй $finish-ticket для ticket <ID или путь>.
```

Для paused/partial задачи:

```text
Используй $finish-ticket, чтобы возобновить ticket <ID> по checkpoint
<путь>.
```

Путь рабочей папки, ветку, commit и fixed point Controller определяет сам.
Спецификацию он берёт из ticket; если связь неоднозначна, запрашивает только
недостающий идентификатор.

## Откуда берутся инструкции

- Роли, модели, порядок review/verification, repair-loop и `DONE` — из
  установленного глобального skill.
- Архитектура, coding standards и команды — из существующих инструкций
  проекта.
- Acceptance criteria — из ticket и спецификации.
- Partial state — из checkpoint и текущего diff.

В проект не добавляются `context.md`, `task-lifecycle.md` или копии
`AGENTS.md` из workflow-репозитория.

## Совместимость runtime adapter

Перед preflight Controller запрашивает у runtime adapter обязательные
capabilities: проверяемый inventory model ID/tier/effort, dispatch/continuation
ролей, policy tools и observed usage. Если хотя бы одной нет, ticket получает
`BLOCKED_CAPABILITY` до spawn; Controller не подменяет её fallback или
самопроверкой. Codex принимает inventory только с provenance `provider: openai`
и `source: codex-runtime`, иначе также блокирует ticket. Затем выбирает tier `efficient`, `standard` или `frontier` по
протоколу, записывает requested/selected tier и degradation reason; Luna,
Terra и Sol — лишь примеры текущего registry, не правило маршрутизации.

Qwen Code v0.22.2 проходит отдельный fixture preflight только при exact
declaration `provider: qwen`, `product: qwen-code`, `version: 0.22.2`.
Configured и active model IDs должны совпадать и role model identity lock
должен применяться ко всем ролям; также обязательны fresh named subagent,
continuation исходного Implementer, fresh read-only Reviewer без
fork/write и executable verification command. Любое отсутствие даёт
`BLOCKED_CAPABILITY`. Успех фиксирует одну verified identity для всех ролей и
`usage: AVAILABLE|NOT_AVAILABLE`.

Qwen использует `QWEN_CONVERGENT`, а не числовой cap repair-раундов. Ledger
начинается с baseline/fixed point/open findings. Каждый `local_attempt` хранит
finding, RED, hypothesis и GREEN, не меняя ticket status; `repair_candidate`
содержит diff/scope, sequence references, normalized root cause и
runtime/model/usage trace; `review_verdict` содержит fresh read-only Reviewer,
static verdicts, regression/scope flags и closures; terminal event — причину.
Normalized root cause candidate точно совпадает с root cause referenced
attempts. Перед
продолжением Controller валидирует всю history `CONTINUE`: closures должны быть
уникальным подмножеством current open findings и referenced attempts, без
invented/repeated closure. `CONTINUE` требует `SPEC: PASS` и `CODE_QUALITY:
PASS`, без regression accepted criteria и unapproved scope.
Повтор root cause без нового reproducible RED даёт
`REPEATED_ROOT_CAUSE_WITHOUT_NEW_RED`; `NEW_REQUIREMENT`, `DESIGN_GAP` или
scope expansion дают stop gate. Qwen delivery extension не меняет эти common
gates, Codex profile или его numeric budget.

Перед продолжением Qwen Controller сверяет *все* historical candidate traces с
configured model identity; несовпадение даёт `MODEL_IDENTITY_MISMATCH`.
Любой policy `BLOCKED` после valid baseline оставляет append-only terminal event
с непустой причиной, включая `INSUFFICIENT_REPAIR_EVIDENCE`.

Boolean capability в Qwen declaration должна быть literal `true`; строковый
или иной truthy surrogate блокируется. Verification command — только
непустая строка либо object `{"argv": ["<non-empty argument>", "..."]}`;
пустой/неструктурный command также блокируется.

## QWEN_ASSIST из Codex Desktop

Это не запуск `finish-ticket` в Qwen и не дополнительный Implementer.
Controller Codex может вызвать Qwen CLI как внешний синхронный worker только
для bounded recon, а после успешной проверки — для малого patch candidate.
До каждого вызова он выполняет capability probe по `qwen --help`; номер версии
не используется как allow-list. Нужны `plan` mode, JSON output/schema,
worktree, limits turns/wall-time/tool-calls и исключение subagents. Если хотя
бы одной возможности нет, запуск завершается `BLOCKED_CAPABILITY` без fallback.


Перед первым recon конкретного ticket Controller выполняет benign schema-smoke
в clean worktree без ticket code. Он подтверждает only terminal
structured-output contract и не является evidence или acceptance ticket. Для
`--output-format json` bridge принимает single JSON object либо object из final
event `result.structured_result`; transcript и прочие JSON формы не принимаются.
Непройденный smoke останавливает pilot, а не увеличивает лимит или повторяет
recon.
Smoke и recon используют `--bare`, но не `--safe-mode`, чтобы не загружать
неявные workspace customizations. При `--auth-type openai` обёртка получает
Generic Credential текущего пользователя `ProofLoop/Qwen/OpenAI`, назначает его
только `OPENAI_API_KEY` дочернего процесса Qwen и в `finally` восстанавливает
или удаляет process variable. Отсутствующий credential —
`INFRASTRUCTURE_BLOCKER` до первого turn; token не входит в ticket packet,
report или metrics.
Первый Qwen-вызов читает код из clean fixed-point worktree и возвращает только
`QWEN_RECON_REPORT`: минимум три факта `file:line -> fact`, state owner,
callback boundary и acceptance risk. Он не пишет файлы и не запускает shell,
тесты, сеть/MCP или subagents. Controller самостоятельно проверяет report и
отсутствие diff; результат не является acceptance evidence ticket.

Суммарный budget — семь Qwen-вызовов на ticket. Повтор требует нового evidence
и изменённого scope, criterion, RED-command либо hypothesis. Повтор root cause
или две непрогрессивные попытки подряд дают `QWEN_UNUSABLE`. Patch candidate
разрешён только после подтверждённого recon и ограничен двумя файлами, 200
строками и одним targeted test. Qwen не делает Git-интеграцию, full suite или
acceptance; Codex independently проверяет candidate и сам переносит diff.

Исполняемые ограничения находятся в `scripts/qwen_assist.py` и
`scripts/invoke_qwen_assist.ps1`; полный report хранится локально вне Git,
а центральная JSONL-метрика — в `%LOCALAPPDATA%\ProofLoop Skills` без кода,
путей и raw findings.

## Контроль перед расходом лимита

До первого role-agent Controller обязан показать `PREFLIGHT_REPORT`: baseline,
acceptance evidence, `SEAM_FEASIBILITY` каждого критерия (production entry
point, test seam, RED command, owner), а для изменённой injectable boundary —
production-shaped consumer и compatibility command; риск, модели/effort, ожидаемый scope,
targeted feedback loop, stop gates, design gaps и budget/context counters. Для critical, resumed,
design-gap или неизвестного scope он ждёт подтверждения пользователя. Ordinary
ticket продолжает в опубликованном бюджете.

`PREFLIGHT_REPORT` выводится одной короткой Markdown-таблицей: ticket/spec,
risk, routing, budget, stop gates/design gaps и next action. Полные baseline,
acceptance, scope и feasibility данные остаются в `IMPLEMENTATION_PACKET` и
evidence; при stop gate показывается только блокирующий criterion. Evidence
только с fake seam не достаточно для изменённой boundary.

Обычный ticket имеет 3 role-agent запуска, critical — 4; максимум 1 full suite.
Для ordinary локальной реализации Controller начинает с verified
`efficient/high` (Luna-first, если registry относит выбранный model ID к этому
tier). После initial pass разрешён один scoped Luna repair; у механической
low-risk задачи — два, но только при новом RED/evidence. Переход на
`standard/high` требует записи `EFFICIENT_TIER_DEFICIENCY`: последний RED,
fingerprint, scope, конкретная причина и следующий red-capable loop. Review
остаётся independent `standard/medium`; critical/resumed/security/native/
concurrency ticket не получают дополнительный Luna repair.
После `Reviewer FAIL` Verifier ещё не запущен: один scoped fix использует
follow-up Implementer, scoped re-review и затем Verifier в тех же четырёх
critical launches. Role-agent получает только компактный implementation packet.
Frontier `high` допускается только по записанной причине. Превышение любого лимита
создаёт checkpoint и требует нового явного разрешения.
Расширение budget требует `NEXT_CLOSURE`: один criterion, его red-capable loop
и состояние остальных criteria; счётчики не сбрасываются.

До Verifier Controller сверяет acceptance ledger по всем criteria ticket.
`SCOPED_PASS` частичного repair не является `SPEC: PASS` ticket и не разрешает
Verifier или full suite. UI/Sandbox job создаёт только Controller после проверки
schema; rejected job до целевой команды исправляет follow-up того же Verifier,
не расходуя новый role-agent slot.

Внешняя модель или CLI без технического контроля side effects работает только в
изолированной worktree без Sandbox queue. Её код и сообщения — непроверенный
вход до повторной проверки Controller.

## Завершение и следующая задача

`DONE` допустим только после независимых `SPEC: PASS`, `CODE_QUALITY: PASS` и
`ACCEPTED`. Для следующего ticket можно оставить тот же Controller, пока его
контекст не смешивает состояния задач. Role-agent tasks после фиксации evidence
можно архивировать.

После `DONE`, `REJECTED`, `BLOCKED_FOR_DESIGN`, `BLOCKED` или `BUDGET_GATE`
Controller обязан показать `TOKEN_USAGE`: отдельно Implementer/follow-ups,
Controller/Reviewer/Verifier и total ticket. Используются только фактические
usage/trace counters; недоступные значения отмечаются `NOT_AVAILABLE`.
После `REJECTED` он также показывает `FAILURE_SUMMARY`: primary failure,
подтверждённые cascade failures, in-scope verdict и следующий focused loop.
Если aggregate acceptance-test вернул только общий boolean, Controller создаёт
ограниченный `DIAGNOSTIC_CYCLE_PERMIT`: от одного до трёх test-only experiment
с raw-free `FAILURE_PROJECTION`. До первого запуска он фиксирует
`diagnostic_seam`: criterion, конкурирующие причины, минимальные observations и
обе стороны требуемого сравнения. Единственный `HYPOTHESIS_LEDGER` хранит
непрерывную sequence, hypothesis и первую отказавшую операцию с reason code.
Новый role-agent, repair, Verifier и full suite до usable projection запрещены.
Повтор fingerprint два раза, исчерпание лимита или resume с иной identity дают
control point; pre-command infrastructure failure лимит не расходует. После локального GREEN Controller оформляет candidate с identity, scope, criteria, invariants и diagnostic RED/GREEN; receipt сравнивается только с тем же identity и evidence context, иначе `EVIDENCE_STALE`. Полная
схема — в канонической
[reference диагностического цикла](../plugins/agentic-development-workflow/skills/finish-ticket/references/diagnostic-cycle.md).

## Ручной аудит test suite

`$audit-test-suite` вызывается только явным пользовательским prompt и не
участвует в обычном lifecycle ticket. Он измеряет duration и flaky evidence,
строит карту `test -> risk -> seam` и готовит proposals с replacement proof.
Он не удаляет тесты, не меняет CI/quarantine и не создаёт agents.


## Execution channels

Каждый evidence path объявляет channel по наблюдаемому поведению: `isolated`, `side-effectful` или `interactive`. Изолированный suite не может транзитивно вызвать side-effectful или interactive path. Environment failure до команды — `INFRASTRUCTURE_BLOCKER`, а не verdict продукта. Полная схема — в [reference execution channels](../plugins/agentic-development-workflow/skills/finish-ticket/references/execution-channels.md).


## Receipts тестов

Controller хранит отдельно найденные и реально выполненные test cases. Их расхождение — `EVIDENCE_INCOMPLETE`, а не основание для retry по exit code. Схема: [reference test receipts](../plugins/agentic-development-workflow/skills/finish-ticket/references/test-receipts.md).


## Semantic diff gate

До дорогой verification каждый production semantic delta требует owner, transitions, consumer и regression evidence. Неполный contract блокирует verification. Схема: [semantic diff](../plugins/agentic-development-workflow/skills/finish-ticket/references/semantic-diff.md).

## Raw-free PASS projection

Verifier принимает итоговую PASS-приёмку только при raw-free projection с candidate identity, execution channel, artifact reference, criterion counts, required controls и evidence status. Projection не содержит prompt, secret, path, raw command output, exception text или customer data. Неполный либо небезопасный receipt означает `PASS_PROJECTION_BLOCKED`; полный — `PASS_PROJECTION_READY`. Схема: [reference PASS projection](../plugins/agentic-development-workflow/skills/finish-ticket/references/pass-projection.md).
## Scenario fixtures

Версия workflow `1.14`. Scenario fixtures подтверждают честные terminal states и не допускают ложный `DONE`.

### Qwen capture transport

If the host transport cannot retain terminal stdout, Controller launches the
bounded worker with `start_qwen_assist_capture.ps1` and polls it with
`get_qwen_assist_capture.ps1`. stdout/stderr remain under local app-data;
`RUNNING` and `COMPLETE_INVALID_OUTPUT` are not ticket evidence. Controller
parses a report only after `COMPLETE` and final schema validation.
