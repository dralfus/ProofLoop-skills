# Спецификация: Qwen Code профиль сходящегося repair-loop

Статус: реализовано; real pilot ожидает Qwen CLI

## Постановка проблемы

`finish-ticket` обеспечивает независимую приёмку и ограничивает нездоровый
repair-loop численным бюджетом role-agent запусков, model escalation и
fix-раундов. Эта политика обоснована стоимостью и иерархией разных моделей
Codex, но не соответствует Qwen Code, где одна модель может продолжать
исправление без заранее заданного лимита.

Простой перенос текущего лимита в Qwen Code остановит потенциально сходящуюся
работу преждевременно. Простое снятие лимита, напротив, разрешит бесконечный
self-repair без независимого доказательства улучшения, регрессии или
архитектурный поиск внутри implementation-loop.

## Решение

Расширить `finish-ticket` переносимым runtime/profile слоем. Controller
автоматически выбирает профиль по проверенным возможностям текущего runtime:
Codex использует существующую adaptive model policy, а Qwen Code использует
профиль одной настроенной Qwen-модели.

Qwen-профиль не имеет числового лимита repair-раундов. Вместо него он требует
монотонной сходимости, записанной в append-only журнале прогресса. Implementer
может выполнять неограниченное число локальных RED → fix → GREEN попыток для
одного finding. Каждая попытка заявить устранение внешнего finding создаёт
repair-кандидат и передаётся новому fresh Reviewer с отдельным контекстом.
Только Controller решает, что полученный verdict разрешает продолжение,
verification или stop gate.

Следующий repair-кандидат разрешён, только если independent Reviewer
подтвердил устранение как минимум одного открытого finding, отсутствие
регрессий ранее принятых criteria и отсутствие неутверждённого роста scope.
Новая гипотеза без нового наблюдаемого RED evidence не считается прогрессом.

## Пользовательские истории

1. Как пользователь Qwen Code, я хочу запускать `$finish-ticket` обычной
   короткой командой, чтобы runtime сам выбрал совместимую policy.
2. Как пользователь Codex, я хочу сохранить существующий adaptive routing,
   чтобы добавление Qwen не меняло установленную OpenAI policy.
3. Как владелец ticket, я хочу, чтобы Qwen Implementer мог продолжать локальные
   попытки, пока они воспроизводимы и сходятся, чтобы числовой лимит не
   обрывал полезную работу.
4. Как владелец ticket, я хочу свежий независимый review каждого
   repair-кандидата, чтобы одна и та же модель не принимала собственную работу.
5. Как Controller, я хочу различать локальную попытку и repair-кандидат,
   чтобы не запускать Reviewer на каждую промежуточную правку.
6. Как Reviewer, я хочу получить fixed-point diff, открытые findings и
   evidence журнала, чтобы подтвердить либо опровергнуть монотонный прогресс.
7. Как владелец workflow, я хочу остановить повторную root cause без нового
   RED evidence, чтобы unlimited policy не превратилась в зацикливание.
8. Как владелец workflow, я хочу блокировать design gap, новое требование и
   неутверждённый рост scope независимо от числа попыток, чтобы repair-loop не
   проектировал новую архитектуру.
9. Как пользователь, я хочу, чтобы отсутствие capability Qwen Code не вело к
   неявному fallback, чтобы workflow не заявлял независимую приёмку без неё.
10. Как аудитор, я хочу видеть model, runtime version, repair-кандидаты,
    verdicts и verification evidence, чтобы восстановить причину terminal
    статуса.
11. Как владелец ticket, я хочу продолжение без нового сообщения, пока
    сходимость подтверждена, чтобы ручное подтверждение требовалось только для
    изменения требований, дизайна или scope.
12. Как разработчик workflow, я хочу добавлять будущие LLM через adapter и
    profile, чтобы не копировать lifecycle и не создавать расходящиеся skills.

## Критерии приёмки

1. Один короткий запуск `$finish-ticket` определяет runtime по capability
   preflight, а не по имени модели или неявному текстовому предположению.
2. Codex и Qwen Code используют один канонический lifecycle, но разные
   model/repair policies через явные profiles.
3. Qwen-профиль до первого dispatch проверяет версию runtime, настроенную
   модель, запуск fresh named subagent, continuation Implementer, read-only
   policy Reviewer и возможность запуска verification command.
4. При отсутствии любой обязательной capability Controller возвращает
   `BLOCKED_CAPABILITY`; автоматического fallback к self-review нет.
5. Для Qwen каждый repair-кандидат имеет finding fingerprint, RED command и
   результат, гипотезу, diff/scope delta, GREEN commands и verdict свежего
   Reviewer.
6. Implementer может выполнять много локальных попыток, но не может объявить
   finding закрытым без independent review repair-кандидата.
7. Fresh Reviewer запускается отдельным named agent, не является fork
   Controller или Implementer, не изменяет файлы и имеет только read-only
   инструменты проверки.
8. Продолжение Qwen repair-loop допустимо только при подтверждённом закрытии
   открытого finding, отсутствии регрессии и отсутствии неутверждённого scope
   expansion.
9. Повтор finding type + normalized root cause без нового воспроизводимого RED
   evidence останавливает loop как `BLOCKED_FOR_DESIGN` либо `BLOCKED` согласно
   классификации причины.
10. `NEW_REQUIREMENT`, `DESIGN_GAP`, невозможность воспроизвести finding,
    регрессия принятого criterion и неутверждённый рост scope немедленно
    запрещают автоматическое продолжение.
11. После independent static PASS Verifier проверяет acceptance, compatibility
    evidence, допустимый full suite и live evidence по общему lifecycle.
12. `DONE` требует тех же независимых `SPEC: PASS`, `CODE_QUALITY: PASS` и
    `ACCEPTED` evidence, что и Codex-профиль.
13. Evidence включает наблюдаемый usage/runtime trace, если Qwen Code его
    предоставляет; иначе usage честно отмечен `NOT_AVAILABLE`.

## Решения по реализации

- Разделить канонический lifecycle и provider-specific policy. Общая часть
  хранит роли, acceptance authority, evidence, design gates, findings и
  terminal statuses; profiles определяют discovery, модели, dispatch и
  budget/repair policy.
- Ввести runtime adapter contract: capability preflight, model identity,
  создание fresh role, continuation существующего Implementer, ожидание
  результата, ограничения tools и извлечение observed usage.
- Ввести profile selection `auto`: она выбирает только adapter, чьи
  capabilities фактически подтверждены. Пользователь может явно запросить
  профиль; несовместимый запрос заканчивается `BLOCKED_CAPABILITY`.
- В Qwen Code использовать одну настроенную модель: Controller и role-agents
  наследуют текущую model identity. Preflight отклоняет запуск, если identity
  не совпадает с configured Qwen profile.
- Qwen Controller продолжает исходного Implementer только для scoped
  remediation. Independent Reviewer всегда новый named subagent с отдельным
  контекстом; fork запрещён для review, поскольку наследует контекст родителя.
- Qwen repair-loop разделяет local attempt и repair-candidate. Local attempt
  не меняет статус и не требует нового Reviewer; repair-candidate является
  checkpoint, на котором Controller фиксирует ledger и dispatches Reviewer.
- Progress ledger append-only и включает baseline/fixed point, открытые и
  закрытые findings, normalized root cause, RED/GREEN evidence, scope delta,
  reviewer verdict, verification verdict и terminal reason.
- Единственный заменяемый ограничитель в Qwen — числовой budget fix-раундов.
  Ограничения на независимую приёмку, запрет nested agents, design gate,
  production-consumer evidence и запрет regression сохраняются.
- Автономное продолжение разрешено только при validated progress. Новое
  требование, design decision, изменение scope или отсутствие evidence требуют
  stop status и решения пользователя.
- В Qwen runtime loop detection включается как дополнительная safety net, но
  не заменяет progress ledger и verdict Reviewer.
- Устанавливаемые оболочки могут различаться: Codex plugin остаётся способом
  доставки для Codex; Qwen Code получает совместимую skill/agent extension.
  Общий protocol не дублируется между ними.

## Решения по тестированию

Главный seam — runtime adapter contract: тесты подают декларацию capabilities
и последовательность role verdicts, а затем проверяют внешние lifecycle
переходы и сохранённый evidence. Тесты не должны зависеть от внутренних
вызовов конкретного CLI.

- Fixture Codex подтверждает выбор adaptive profile и сохранение текущих
  numeric budget gates.
- Fixture Qwen подтверждает выбор single-model profile, отсутствие numerical
  repair cap и требование configured model identity.
- Capability fixtures проверяют `BLOCKED_CAPABILITY` для отсутствующих fresh
  reviewer, continuation, read-only policy и executable verification.
- Convergence fixture содержит несколько local attempts, один подтверждённый
  repair-кандидат и независимый Reviewer PASS; Controller должен разрешить
  переход к следующему finding без ручного approval.
- Non-progress fixture повторяет нормализованную root cause без нового
  воспроизводимого RED evidence; Controller обязан остановить цикл.
- Regression fixture закрывает исходный finding, но делает ранее принятое
  criterion красным; Reviewer обязан вернуть FAIL, а Controller — запретить
  автоматическое продолжение.
- Scope и design fixtures проверяют немедленный stop для нового требования,
  design gap и неутверждённого scope expansion.
- Reviewer fixture проверяет, что fork или write-capable reviewer не может
  служить independent acceptance evidence.
- Evidence fixture проверяет append-only ledger и `NOT_AVAILABLE` для
  недоступного usage без подстановки оценочных токенов.

## Вне области действия

- Унификация API всех возможных LLM-провайдеров до появления второго
  поддерживаемого не-Codex runtime.
- Изменение задач, тестов или CI пользовательского проекта.
- Ослабление независимого Reviewer или Verifier ради скорости Qwen repair.
- Гарантия бесконечного исполнения при design gap, regression или отсутствии
  воспроизводимого evidence.
- Использование fork как независимого review.
- Неявная смена Qwen-модели, provider или permission policy в ходе ticket.

## Дополнительные сведения

Профиль проектируется по документированным возможностям Qwen Code v0.22.2:
skills, fresh named subagents, continuation, tool restrictions, hooks и
машиночитаемый event output. Capability preflight обязателен, поскольку версия
Qwen Code обновляется и эти возможности не должны считаться вечными.

Реализация обновляет канонический lifecycle, Codex plugin/skill, native Qwen
extension (`qwen-extension.json` + named Controller agent) и человеческие
инструкции. Extension ссылается на единый protocol и не содержит его копии.
Policy покрыта executable end-to-end fixtures; реальный ticket остаётся
следующим шагом только при наличии Qwen Code v0.22.2 и фиксируется в
`docs/experiments/qwen-code-v0222-pilot.md` без подстановки live evidence.
