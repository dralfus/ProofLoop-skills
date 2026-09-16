# Спецификация: сходимость `finish-ticket` по урокам Ticket 355

## Problem Statement

Сложный ticket с несколькими execution channels может формально следовать
части workflow, но всё равно расходовать непропорционально много контекста и
модельных запусков. Ticket 355 показал четыре таких разрыва: Controller
продолжал работу множеством follow-up ходов, parameterized tests давали
неоднозначные данные discovery и execution, успешная matrix не публиковала
машиночитаемое raw-free evidence, а production semantic delta был обнаружен
независимым review поздно.

Пользователь хочет универсальный workflow: он должен одинаково работать для
CLI, сервисов, UI, native-интеграций и иных окружений. Протокол не должен
содержать правила, привязанные к WinForms, UIA, Windows Sandbox или конкретному
test runner.

## Solution

Расширить `finish-ticket` универсальными receipts и health gates, которые
контролируют фактически сделанную работу, а не только число созданных агентов.
Controller до реализации подтверждает используемый протокол, маршрут
verification и бюджеты. Каждый новый repair обязан уменьшать пространство
гипотез. Discovery, фактическое выполнение тестов, semantic delta и успешное
acceptance evidence получают отдельные проверяемые записи.

## User Stories

1. Как владелец workflow, я хочу видеть подтверждённую версию протокола до
   первого role-agent, чтобы Controller не следовал устаревшей или неявной
   инструкции.
2. Как владелец ticket, я хочу, чтобы budget учитывал follow-up ходы и
   диагностические циклы, чтобы один долгоживущий Controller не обходил лимит
   на создание role-agents.
3. Как Controller, я хочу иметь журнал гипотез, чтобы следующий fix был
   разрешён только при новом наблюдаемом различии между причинами дефекта.
4. Как Implementer, я хочу получать один явный execution channel для каждого
   вида evidence, чтобы не смешивать быстрые локальные проверки с дорогой
   release-приёмкой.
5. Как Verifier, я хочу различать найденные test cases и фактически
   выполненные cases, чтобы особенности parameterization или адаптера не
   превращались в ложный preflight block или ложный GREEN.
6. Как независимый Reviewer, я хочу видеть semantic delta production-контракта
   до дорогой verification, чтобы production change не был ошибочно принят за
   test-only исправление.
7. Как владелец acceptance, я хочу получать raw-free projection и при PASS, и
   при REJECTED, чтобы успешный aggregate assertion был воспроизводимым
   evidence, а не требовал ручного чтения исходного кода.
8. Как разработчик любого типа приложения, я хочу классифицировать tests по
   execution characteristics, а не по имени технологии, чтобы изолированный
   suite не запускал скрытые interactive, network или privileged dependencies.
9. Как оператор, я хочу, чтобы environment failure был записан отдельно от
   product result, чтобы инфраструктурная проблема не создавала ложный repair
   loop.
10. Как пользователь дорогой frontier-модели, я хочу видеть причину каждой
    эскалации и фактический расход follow-up работы, чтобы выбирать сильную
    модель только там, где она даёт новое решение.
11. Как владелец workflow, я хочу иметь единый источник версии protocol во
    всех human docs, plugin и receipts, чтобы инструкции не расходились.
12. Как Controller следующего ticket, я хочу продолжать после checkpoint по
    компактному resume packet, содержащему budgets, evidence и hypothesis
    ledger, чтобы не перечитывать длинный transcript.

## Implementation Decisions

- До первого dispatch Controller создаёт `PROTOCOL_RECEIPT`: canonical version
  protocol, trusted runtime capability, выбранный execution channel, fixed
  point, budget и digest preflight record. Отсутствие receipt даёт
  `BLOCKED_CAPABILITY` или `PREFLIGHT_INCOMPLETE`, а не неявный fallback.
- Budget расширяется отдельными counters: `role_agent_launches`,
  `controller_decision_turns`, `implementer_followups`, `diagnostic_loops`,
  `full_suite_runs` и `interactive_release_runs`. Лимит follow-up не может
  обходиться переименованием роли или продолжением того же чата. Превышение
  требует `NEXT_CLOSURE` и явного решения пользователя.
- Для каждого открытого finding Controller ведёт append-only
  `HYPOTHESIS_LEDGER`: symptom, production boundary, hypothesis, различающее
  raw-free observation, команда, outcome и допустимый следующий шаг. Новый
  production fix допустим только после нового различающего observation либо
  одобренного design decision.
- `EXECUTION_CHANNEL_RECEIPT` объявляет ровно один маршрут каждого evidence:
  `noninteractive`, `interactive`, `isolated`, `privileged`, `external` либо
  project-defined value. Channel определяет side-effect policy, timeout,
  identity receipt и допустимый scope, но не содержит платформенных терминов.
- Test selection получает два независимых факта: `DISCOVERY_RECEIPT` с
  discovered cases и `EXECUTION_RECEIPT` с реально executed cases. Их
  расхождение является классифицированным runner limitation, а не основанием
  для выдуманного PASS/FAIL. Controller выбирает следующий evidence seam или
  блокирует ticket честным статусом.
- Перед full suite или release verification обязателен `SEMANTIC_DIFF_GATE`.
  Для каждого изменённого production contract фиксируются owner, входные и
  выходные состояния, разрешённые/запрещённые transitions, consumer evidence
  и regression. Test-only claim при production delta недопустим.
- Aggregate acceptance contract обязан публиковать raw-free
  `EVIDENCE_PROJECTION` на PASS и `FAILURE_PROJECTION` на REJECTED. PASS
  projection содержит criterion/scenario counts, required controls,
  cleanup/evidence status, identity и ссылку на artefact; он не содержит
  prompt, secrets, customer data, raw command output или exception text.
- Test classification строится по наблюдаемому execution behaviour. Static
  contract проверяет явные annotations и транзитивные вызовы channel-bound
  runner-ов; исключение не может быть broad name/FQN filter.
- Environment failure до целевой команды получает terminal category
  `INFRASTRUCTURE_BLOCKER`; он не расходует fix round и не разрешает retry без
  изменённого execution receipt.
- Canonical version извлекается из одного protocol source; human docs, skill
  manifest, reports и templates проверяются на совпадение статическим
  contract.

## Testing Decisions

Высокий seam — lifecycle decision boundary Controller: входом является
версионированный preflight/ledger/evidence record, выходом — разрешённое
следующее действие или честный terminal status. Тесты проверяют внешние
переходы и receipts, а не внутреннюю реализацию конкретного runner-а.

- Fixture без `PROTOCOL_RECEIPT` не допускает dispatch.
- Fixture с исчерпанным follow-up budget требует `NEXT_CLOSURE`; простое
  продолжение существующего role-agent не проходит gate.
- Fixture hypothesis ledger запрещает новый production fix без нового
  различающего observation.
- Fixture с parameterized discovery и меньшим execution count формирует
  `RUNNER_EVIDENCE_INCOMPLETE`, не подменяя его зелёным результатом.
- Fixture production semantic delta без owner/consumer/regression блокирует
  дорогую verification.
- PASS и REJECTED aggregate fixtures проверяют raw-free projection, identity
  и отсутствие чувствительных полей.
- Fixtures с разными channel characteristics проверяют, что скрытый
  interactive или privileged runner не попадает в noninteractive execution.
- Version fixture проверяет совпадение canonical protocol version во всех
  публикуемых точках.

## Out of Scope

- Платформенные правила для конкретных UI frameworks, browser automation,
  Windows Sandbox, UIA, COM, Docker, CI provider или test runner.
- Автоматическое исправление дефектов runner-а или инфраструктуры.
- Новая система задач, GitHub/GitLab issues, интеграции tracker-а и изменение
  сторонних skills в plugin cache.
- Переписывание существующих project specs и ticket history.
- Повышение acceptance authority внешнего worker-а или Qwen.

## Further Notes

Ticket 355 подтвердил ценность независимого review, разделения execution
channels и current-build identity receipt. Он также показал, что эти механизмы
нужно сделать обязательными и компактными: workflow должен сокращать число
решений, а не добавлять многостраничный control transcript.

До реализации необходимо проверить совместимость решений с текущими
append-only evidence, Qwen convergent repair policy и существующим
`BLOCKED_CAPABILITY` contract. Спецификация не создаёт GitHub issues и не
меняет текущий lifecycle сама по себе.

### Уточнения по автономному диагностическому циклу

Первая поставка вводит `DIAGNOSTIC_CYCLE_PERMIT`: исходный Implementer может
выполнить до трёх экспериментов в заранее утверждённых scope, execution channel
и budget. Permit фиксирует допустимые diagnostic/test changes, неизменяемые
guarantees и stop conditions. Новый permit обязателен только при изменении
security, ownership, side-effect semantics, channel или budget; resume после
сверки baseline сохраняет неиспользованный остаток.

Каждый результат классифицируется как `DIAGNOSTIC_PROGRESS`,
`REPAIR_FAILURE`, `NEXT_DEFECT` или `INFRASTRUCTURE_BLOCKER`. Сравниваются
первая подтверждённая отказавшая операция и её закрытый результат, а не один
верхний symptom. Две попытки без новой различающей информации требуют control
point. Новая локализация продолжает тот же permit; `DESIGN_GAP` означает только
отсутствующую либо противоречивую семантику.

До дорогой команды `SEAM_FEASIBILITY` обязана назвать минимальные raw-free
поля, которые различат текущие гипотезы. Aggregate checks публикуют
`EVIDENCE_PROJECTION` и при PASS, и при REJECTED. Evidence receipt применим
повторно лишь при неизменных значимых зависимостях: candidate, проверяющем
тесте, build/execution configuration и required environment.

Reviewer получает подготовленный candidate после диагностических RED/GREEN и
проверяет его delta и затронутые инварианты. Production semantic delta требует
явного owner, разрешённых/запрещённых transitions, consumer evidence и
regression до дорогой verification. Основной lifecycle остаётся компактным;
runtime profile, diagnostics и resume читаются только на соответствующей
ветви.

Поведенческие fixtures обязаны покрыть: переход к следующему defect после
