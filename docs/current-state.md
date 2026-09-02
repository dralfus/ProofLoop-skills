# Текущее состояние

## Существующий workflow

1. Требования уточняются с mattpocock/skills.
2. Создаются спецификация и tickets.
3. Implementer реализует один ticket и пишет тесты.
4. Независимые роли проверяют спецификацию, код и исполняемое evidence.
5. Только Controller присваивает итоговый статус.

## Наблюдаемый failure mode 1: ложное завершение

Implementation-агенты сообщали о завершении при:

- пропущенных требованиях;
- преждевременно закрытых checkbox;
- placeholders и stubs;
- реализации только части поведения;
- зелёных тестах, не доказывающих полную спецификацию.

Разделение реализации и приёмки предотвращает такое `DONE`.

## Наблюдаемый failure mode 2: нездоровый repair-loop

Эксперимент с ticket 353 в проекте CodexRedactionGate показал другой отказ:

- сложная security/concurrency/OS задача была первоначально маршрутизирована на
  Terra, а Sol подключён только после нескольких исправлений;
- один production-seam finding повторялся в нескольких раундах;
- Reviewer создавал собственных review-subagents;
- полный test suite запускался до окончательного статического PASS;
- новые timeout/cancellation semantics формировались внутри implementation-
  цикла, хотя должны были быть отдельным design-решением;
- partial diff после usage limit требовал повторного чтения и анализа.

Независимая проверка сохранила безопасность и не допустила ложного `DONE`, но
процесс оказался неэффективным по токенам и времени.

## Уточнённая гипотеза

Надёжный workflow требует одновременно:

- независимой acceptance authority;
- единоличной spawn authority у Controller;
- risk-first выбора модели;
- статического review до Verifier/full suite;
- adjudication новых требований;
- ранней остановки повторяющейся корневой причины;
- отдельного статуса `BLOCKED_FOR_DESIGN`.

Ticket 353, завершённый локально после нескольких дорогих итераций, добавил
новый наблюдаемый failure: формально безопасные health gates не ограничивали
число role-agent запусков, повторное чтение контекста и эскалацию на Sol.
Значительная часть расхода пришлась на контекст Controller и повторные
проверки, поэтому дорогая модель сама по себе не является объяснением.

Пять fix-раундов остаются абсолютным пределом, но не являются штатной целью.

## Наблюдаемый failure mode 3: реализация до доказуемого seam

Предварительный разбор ticket 363 показал, что agent может начать critical
implementation, хотя acceptance criteria требуют external-state owner и
injected test seam, которых нет в исходном production path. Тогда работа
превращается в архитектурное исследование и дублирующее чтение кода уже после
дорогого запуска. Следующий протоколный gate должен останавливать такой ticket
до Implementer, а не добавлять ещё один review.

## Наблюдаемый failure mode 4: fake seam без production consumer evidence

Ticket 363 в CodexRedactionGate прошёл scoped matrix с deterministic clipboard
boundary, но full suite показал `capture_failed` в reference-composer, который
использует production clipboard boundary. Несколько reference и product-smoke
failures были каскадом одной причины, а не независимыми дефектами.

Следующий протокольный gate требует для изменённой injectable boundary один
production-shaped consumer и его compatibility command до Implementer;
Reviewer проверяет это evidence до Verifier. При `REJECTED` Controller
группирует только установленный primary failure и его cascade failures.

## Наблюдаемый failure mode 5: verbose preflight расходует контекст пользователя

Полный preflight нужен Controller для безопасного routing, но печать baseline,
scope, acceptance и feasibility каждого criterion в каждом чате делает первый
ответ длинным и отвлекает от решения пользователя: продолжать, подтвердить или
остановить ticket.

User-facing отчёт теперь оставляет только ticket/spec, risk, routing, budget,
stop gates/design gaps и next action. Детали сохраняются в packet/evidence и
показываются только как один blocking detail при реальном stop gate.

## Наблюдаемый failure mode 6: неподтверждённая переносимость Qwen runtime

Codex adaptive profile нельзя переносить в Qwen Code по имени модели или
неявным предположениям о subagent/tools. Без exact runtime version, одной
configured identity, fresh independent Reviewer и executable verification
workflow мог бы ошибочно выдать независимое evidence либо silently fallback к
self-review.

## Наблюдаемый failure mode 7: Qwen repair без доказуемой сходимости

У Qwen одна настроенная модель может делать много локальных исправлений, но
снятие числового cap без independent progress evidence превращает полезную
continuation в self-review loop. Статус local attempt и closure finding нельзя
смешивать: первый не меняет ticket, второй требует свежего Reviewer.

Политика `QWEN_CONVERGENT` заменяет только numeric cap append-only ledger и
остальными common lifecycle gates. Повтор type/root cause без нового
reproducible RED, regression accepted criteria, `NEW_REQUIREMENT`, `DESIGN_GAP`
или unapproved scope прекращают automatic continuation.

Для устранения failure mode 6 Qwen delivery теперь проверяется отдельным
native extension: он делает existing skill и named Controller discoverable, но
ссылается на единый canonical lifecycle. Реальный pilot остаётся честно
`NOT_RUN`, пока exact Qwen CLI/runtime не доступен.

## Текущая цель

Проверить глобальный plugin и протокол версии `1.11` на следующем реальном
ticket без копирования workflow-файлов в проект. До первого spawn подтвердить
runtime capability declaration и `BLOCKED_CAPABILITY` при её отсутствии, затем
измерить:

- число role-agent запусков;
- число fix-раундов;
- повторение корневых причин;
- рост diff относительно preflight;
- число full-suite запусков;
- фактическое число role-agent запусков против preflight-бюджета;
- модель/effort каждого запуска, compaction и повторное использование
  контекста;
- итоговый статус и качество evidence.

Версия `1.2` устранила failure mode: ручное распространение
нескольких файлов и большой стартовый prompt создают дублирование, drift и
лишний контекст. Исполняемый протокол теперь поставляется одним глобальным
skill.
